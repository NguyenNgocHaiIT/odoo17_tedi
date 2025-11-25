from odoo import models, fields, api
from datetime import datetime


class TediAttendance(models.Model):
    _name = 'tedi.attendance'
    _description = 'Quản lý chấm công'
    _order = 'date desc, check_in desc'

    employee_id = fields.Many2one('hr.employee', string='Họ và tên', required=True)
    # Lấy mã nhân viên từ bảng Employee
    employee_code = fields.Char(related='employee_id.employee_code', string='Mã số NV', store=True)
    # Lấy phòng ban từ bảng Employee
    department_id = fields.Many2one(related='employee_id.department_id', string='Phòng ban/Vị trí', store=True)

    check_in = fields.Datetime(string='Checkin')
    check_out = fields.Datetime(string='Checkout')
    date = fields.Date(string='Ngày', default=fields.Date.context_today)
    job_code = fields.Char(string="HSCV")  # Hồ sơ công việc
    job_name = fields.Char(string="Công việc")  # Tên công việc
    description = fields.Text(string="Mô tả")  # Mô tả chi tiết
    duration = fields.Float(string="Giờ đã dùng")  # Giờ làm việc
    # Trạng thái với logic màu sắc
    status = fields.Selection([
        ('ontime', 'Đúng giờ'),
        ('late', 'Đi muộn'),
        ('early', 'Về sớm'),
        ('absent', 'Nghỉ làm')
    ], string='Trạng thái', default='ontime')
