# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.exceptions import ValidationError
import logging
from datetime import datetime, time
import pytz  # Cần import thư viện này để xử lý múi giờ

_logger = logging.getLogger(__name__)

class HolidaysType(models.Model):
    _inherit = "hr.leave.type"

    # Đây là checkbox riêng của bạn, không phụ thuộc Odoo
    auto_create_attendance = fields.Boolean(
        string='Tự động tạo chấm công',
        default=False,
        help="Nếu tích chọn, khi đơn nghỉ được duyệt, hệ thống sẽ tự tạo dữ liệu chấm công."
    )
    employee_id = fields.Many2one(
        'hr.employee',  # <--- Sửa thành hr.employee
        string='Người tạo',
        default=lambda self: self.env.user.employee_id,  # Lấy nhân viên gắn với user đang đăng nhập
    )


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # --- CÁC TRƯỜNG CUSTOM ---
    employee_code = fields.Char(related='employee_id.employee_code', string='Mã số NV', store=True, readonly=True)
    department_id = fields.Many2one(related='employee_id.department_id', string="Phòng ban", store=True, readonly=True)
    job_id = fields.Many2one(related='employee_id.job_id', string="Chức vụ", store=True, readonly=True)

    attendance_date = fields.Date(string='Ngày', compute='_compute_attendance_date', store=True)

    # --- TRƯỜNG PHÂN LOẠI ---
    attendance_type = fields.Selection([
        ('attendance', 'Chấm công'),
        ('leave', 'Nghỉ phép')
    ], string='Loại dữ liệu', default='attendance', required=True)

    leave_id = fields.Many2one('hr.leave', string="Đơn nghỉ phép gốc", ondelete='cascade')

    # Status: Thêm store=True để lưu cứng vào DB
    status = fields.Selection([
        ('ontime', 'Đúng giờ'),
        ('late', 'Đi muộn'),
        ('early', 'Về sớm'),
        ('late_early', 'Muộn & Về sớm'),
        ('leave', 'Đang nghỉ phép')
    ], string='Trạng thái', compute='_compute_status', store=True, default='ontime')

    # --- LOGIC TÍNH TOÁN ---
    @api.depends('check_in')
    def _compute_attendance_date(self):
        for rec in self:
            rec.attendance_date = rec.check_in.date() if rec.check_in else False

    # Thêm 'leave_id' vào depends để nếu gắn đơn nghỉ phép vào thì status tự cập nhật ngay
    @api.depends('check_in', 'check_out', 'employee_id', 'attendance_type', 'leave_id')
    def _compute_status(self):
        for rec in self:
            # === [0. LOGIC BẢO VỆ TRẠNG THÁI LEAVE] ===
            # Kiểm tra giá trị hiện tại trong Database.
            # Nếu bản ghi này ĐANG là 'leave' (dù do sửa tay hay do logic cũ),
            # thì ép buộc giữ nguyên là 'leave' và DỪNG (continue) ngay lập tức.
            if rec.status == 'leave':
                rec.status = 'leave'
                continue

            # === [LOGIC TÍNH TOÁN BÌNH THƯỜNG] ===

            # 1. Ưu tiên xử lý nếu bản chất nó là Nghỉ phép (theo phân loại hoặc có đơn đính kèm)
            if rec.attendance_type == 'leave' or rec.leave_id:
                rec.status = 'leave'
                continue

            # 2. Nếu chưa check-in
            if not rec.check_in:
                rec.status = 'ontime'
                continue

            # 3. Lấy thông tin Lịch & Timezone
            employee = rec.employee_id
            calendar = employee.resource_calendar_id
            if not calendar:
                rec.status = 'ontime'
                continue

            tz_name = employee.tz or 'UTC'
            user_tz = pytz.timezone(tz_name)

            # Chuyển đổi Check-in sang giờ Local
            check_in_local = pytz.utc.localize(rec.check_in).astimezone(user_tz)
            day_of_week = check_in_local.weekday()
            day_str = str(day_of_week)

            # Lấy các ca làm việc trong ngày (trừ giờ nghỉ trưa)
            work_hours = calendar.attendance_ids.filtered(lambda a: a.dayofweek == day_str and a.day_period != 'lunch')

            if not work_hours:
                rec.status = 'ontime'  # Ngày nghỉ
                continue

            # --- TÌM CA LÀM VIỆC PHÙ HỢP (Logic mới đã sửa ở câu trước) ---
            check_in_float = check_in_local.hour + check_in_local.minute / 60.0
            sorted_hours = work_hours.sorted(key=lambda r: r.hour_from)

            target_period = sorted_hours[-1]
            for period in sorted_hours:
                if check_in_float <= period.hour_to:
                    target_period = period
                    break

            start_hour_config = target_period.hour_from

            # --- TÍNH TOÁN ĐI MUỘN (LATE) ---
            limit_start_minutes = int(start_hour_config * 60)
            actual_in_minutes = check_in_local.hour * 60 + check_in_local.minute

            tolerance = 0
            is_late = actual_in_minutes > (limit_start_minutes + tolerance)

            # --- TÍNH TOÁN VỀ SỚM (EARLY) ---
            # Về sớm vẫn lấy mốc max(hour_to) tức là giờ về của ca cuối cùng
            end_hour_config = max(work_hours.mapped('hour_to'))

            is_early = False
            if rec.check_out:
                check_out_local = pytz.utc.localize(rec.check_out).astimezone(user_tz)
                limit_end_minutes = int(end_hour_config * 60)
                actual_out_minutes = check_out_local.hour * 60 + check_out_local.minute

                is_early = actual_out_minutes < limit_end_minutes

            # --- GÁN TRẠNG THÁI ---
            if is_late and is_early:
                rec.status = 'late_early'
            elif is_late:
                rec.status = 'late'
            elif is_early:
                rec.status = 'early'
            else:
                rec.status = 'ontime'

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        if self.env.context.get('bypass_attendance_validation'):
            return

        real_checkING_attendances = self.filtered(lambda a: a.attendance_type != 'leave')
        if not real_checkING_attendances:
            return

        for attendance in real_checkING_attendances:
            if not attendance.check_out:
                continue
            domain = [
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<', attendance.check_out),
                ('check_out', '>', attendance.check_in),
                ('id', '!=', attendance.id),
                ('attendance_type', '!=', 'leave')
            ]
            if self.env['hr.attendance'].search_count(domain):
                raise ValidationError(
                    _("Nhân viên %s không thể check-in/check-out trong khoảng thời gian này vì đã có dữ liệu chấm công.")
                    % attendance.employee_id.name
                )