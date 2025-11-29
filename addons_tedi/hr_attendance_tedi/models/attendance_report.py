# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
import pytz

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # --- CÁC TRƯỜNG CUSTOM ---
    request_date = fields.Date(string='Ngày đề nghị', default=fields.Date.context_today, readonly=True)
    report_title = fields.Char(string='Tiêu đề')
    employee_code = fields.Char(related='employee_id.employee_code', string='Mã NV', store=True)

    leaves_taken_count = fields.Float(string='Số ngày phép đã nghỉ', compute='_compute_leave_stats')
    remaining_leaves_count = fields.Float(string='Số ngày phép còn lại', compute='_compute_leave_stats')
    my_history_ids = fields.Many2many('hr.leave', string='Các đơn báo của tôi', compute='_compute_my_history')

    @api.depends('employee_id', 'holiday_status_id', 'date_from')
    def _compute_leave_stats(self):
        for rec in self:
            rec.leaves_taken_count = 0.0
            rec.remaining_leaves_count = 0.0
            if rec.employee_id and rec.holiday_status_id:
                leave_type = rec.holiday_status_id.with_context(
                    employee_id=rec.employee_id.id,
                    date=rec.date_from or fields.Date.today()
                )
                rec.remaining_leaves_count = leave_type.virtual_remaining_leaves
                rec.leaves_taken_count = leave_type.leaves_taken

    @api.depends('employee_id')
    def _compute_my_history(self):
        for rec in self:
            if rec.employee_id:
                domain = [
                    ('employee_id', '=', rec.employee_id.id),
                    ('id', '!=', rec.id if rec.id else False)
                ]
                rec.my_history_ids = self.env['hr.leave'].search(domain, order='create_date desc', limit=10)
            else:
                rec.my_history_ids = False

    # --- LOGIC TẠO ATTENDANCE ---

    def write(self, vals):
        res = super(HrLeave, self).write(vals)
        # Sử dụng sudo() để đảm bảo quyền truy cập khi trigger logic
        if 'state' in vals:
            for leave in self:
                if vals['state'] == 'validate':
                    leave.sudo()._create_attendance_from_leave()
                elif vals['state'] in ['refuse', 'draft', 'confirm']:
                    leave.sudo()._remove_attendance_from_leave()
        return res

    def _create_attendance_from_leave(self):
        """ Tạo các bản ghi Attendance chia theo ca làm việc """
        self.ensure_one()
        sudo_attendance = self.env['hr.attendance'].sudo()

        # 1. Kiểm tra đã tạo chưa
        if sudo_attendance.search_count([('leave_id', '=', self.id)]):
            return

        employee = self.employee_id
        calendar = employee.resource_calendar_id
        resource = employee.resource_id

        # 2. Xử lý Timezone: Chuyển Naive UTC (DB) -> Aware UTC
        start_dt = pytz.utc.localize(self.date_from)
        end_dt = pytz.utc.localize(self.date_to)

        # 3. Tính toán ca làm việc (Intervals)
        if not calendar or not resource:
            sudo_attendance.create({
                'employee_id': employee.id,
                'check_in': self.date_from, # Naive UTC
                'check_out': self.date_to, # Naive UTC
                'attendance_type': 'leave',
                'leave_id': self.id,
                'status': 'leave'
            })
            return

        # Lấy các khoảng thời gian làm việc trong khoảng nghỉ
        intervals = calendar._work_intervals_batch(start_dt, end_dt, resources=resource)
        my_intervals = intervals[resource.id]
        vals_list = []

        # 4. Duyệt qua từng ca và chuẩn bị dữ liệu
        for start, end, meta in my_intervals:
            # Bước 1: Convert về UTC Aware
            start_utc = start.astimezone(pytz.utc)
            end_utc = end.astimezone(pytz.utc)

            # Bước 2: Bỏ tzinfo để thành Naive UTC
            start_naive = start_utc.replace(tzinfo=None)
            end_naive = end_utc.replace(tzinfo=None)

            vals_list.append({
                'employee_id': employee.id,
                'check_in': start_naive,
                'check_out': end_naive,
                'attendance_type': 'leave',
                'leave_id': self.id,
                'status': 'leave'
            })

        # 5. Tạo dữ liệu hàng loạt
        if vals_list:
            _logger.info(f"TEDICT: Creating {len(vals_list)} leave-attendances for Leave ID {self.id}")
            # Truyền context bypass_attendance_validation
            sudo_attendance.with_context(bypass_attendance_validation=True).create(vals_list)

    def _remove_attendance_from_leave(self):
        """ Xóa attendance liên kết khi hủy/sửa đơn """
        self.ensure_one()
        sudo_attendance = self.env['hr.attendance'].sudo()
        attendances = sudo_attendance.search([('leave_id', '=', self.id)])
        if attendances:
            attendances.unlink()