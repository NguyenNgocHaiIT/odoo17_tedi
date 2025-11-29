# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.exceptions import ValidationError
import logging
from datetime import datetime, time

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # --- CÁC TRƯỜNG CUSTOM ---
    employee_code = fields.Char(related='employee_id.employee_code', string='Mã số NV', store=True, readonly=True)

    department_id = fields.Many2one(
        related='employee_id.department_id',
        string="Phòng ban",
        store=True,
        readonly=True
    )

    job_id = fields.Many2one(
        related='employee_id.job_id',
        string="Chức vụ",
        store=True,
        readonly=True
    )

    attendance_date = fields.Date(string='Ngày', compute='_compute_attendance_date', store=True)

    # --- TRƯỜNG PHÂN LOẠI ---
    attendance_type = fields.Selection([
        ('attendance', 'Chấm công'),
        ('leave', 'Nghỉ phép')
    ], string='Loại dữ liệu', default='attendance', required=True)

    leave_id = fields.Many2one('hr.leave', string="Đơn nghỉ phép gốc", ondelete='cascade')

    status = fields.Selection([
        ('ontime', 'Đúng giờ'),
        ('late', 'Đi muộn'),
        ('early', 'Về sớm'),
        ('absent', 'Nghỉ làm'),
        ('leave', 'Đang nghỉ phép')
    ], string='Trạng thái', default='ontime')

    # --- LOGIC TÍNH TOÁN ---
    @api.depends('check_in')
    def _compute_attendance_date(self):
        for rec in self:
            rec.attendance_date = rec.check_in.date() if rec.check_in else False

    @api.depends('check_in', 'check_out', 'employee_id', 'attendance_type')
    def _compute_status(self):
        for rec in self:
            # 1. Nếu là nghỉ phép -> Status là leave
            if rec.attendance_type == 'leave':
                rec.status = 'leave'
                continue

            # 2. Logic Attendance Gốc
            if not rec.check_in and not rec.check_out:
                rec.status = 'absent'
                continue

            employee = rec.employee_id
            calendar = employee.resource_calendar_id
            if not calendar:
                rec.status = 'ontime'
                continue

            day = rec.check_in.weekday()
            attendances = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == day)

            if not attendances:
                rec.status = 'ontime'
                continue

            first_att = attendances.sorted(lambda a: a.hour_from)[0]
            last_att = attendances.sorted(lambda a: a.hour_to)[-1]

            start_time = time(int(first_att.hour_from), int((first_att.hour_from % 1) * 60))
            end_time = time(int(last_att.hour_to), int((last_att.hour_to % 1) * 60))

            check_in_time = rec.check_in.time() if rec.check_in else None
            check_out_time = rec.check_out.time() if rec.check_out else None

            late = check_in_time and check_in_time > start_time
            early = check_out_time and check_out_time < end_time

            if late:
                rec.status = 'late'
            elif early:
                rec.status = 'early'
            else:
                rec.status = 'ontime'

    # --- GHI ĐÈ CHECK TRÙNG LẶP ---
    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        """
        Override hoàn toàn logic kiểm tra của Odoo.
        """
        # 1. Bypass nếu có context đặc biệt (Quan trọng cho logic tự động tạo từ Leave)
        if self.env.context.get('bypass_attendance_validation'):
            return

        # 2. Lấy danh sách attendance THỰC TẾ (loại trừ các bản ghi ảo do Leave tạo ra)
        # Logic: Nếu bản ghi đang check là 'leave', ta bỏ qua luôn việc kiểm tra nó.
        real_checkING_attendances = self.filtered(lambda a: a.attendance_type != 'leave')

        if not real_checkING_attendances:
            return

        # 3. Logic check trùng lặp (Chỉ áp dụng cho attendance thật)
        for attendance in real_checkING_attendances:
            if not attendance.check_out:
                continue

            # Tìm xem có bản ghi nào trùng không
            # (Trừ chính nó và trừ các bản ghi loại 'leave' khác trong DB)
            domain = [
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<', attendance.check_out),
                ('check_out', '>', attendance.check_in),
                ('id', '!=', attendance.id),
                ('attendance_type', '!=', 'leave') # Không quan tâm trùng với đơn nghỉ phép
            ]

            if self.env['hr.attendance'].search_count(domain):
                raise ValidationError(
                    _("Nhân viên %s không thể check-in/check-out trong khoảng thời gian này vì đã có dữ liệu chấm công.")
                    % attendance.employee_id.name
                )