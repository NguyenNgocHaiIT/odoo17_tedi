# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import  ValidationError




class HREmployeeWorkProcessOld(models.Model):
    _name = "hr.employee.work.process.old"
    _description = "Quá trình công tác tại đơn vị cũ"

    stt = fields.Integer(string="STT", compute="_compute_stt", store=False)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")

    company_name = fields.Char(string="Tên công ty")
    work_address = fields.Char(string="Địa chỉ làm việc")
    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")
    work_position = fields.Many2one(
        "hr.experience.position",
        string="Vị trí/Chức danh",
        required=True
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            # Kiểm tra: Nếu có cả 2 ngày và Ngày đến < Ngày từ
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError("Ngày kết thúc (Đến ngày) phải lớn hơn hoặc bằng Ngày bắt đầu (Từ ngày)!")

    @api.onchange('date_to', 'date_from')
    def _onchange_availability(self):
        if self.date_from and self.date_to:
            if self.date_to < self.date_from:

                # Cách fix ổn định: Gán luôn bằng ngày bắt đầu thay vì xóa trắng
                self.date_to = False
                # Cảnh báo nhẹ nhàng hơn
                return {
                    'warning': {
                        'title': "Điều chỉnh ngày",
                        'message': "Ngày kết thúc không được nhỏ hơn ngày bắt đầu. Hệ thống đã tự động điều chỉnh lại!"
                    }
                }

    @api.depends('employee_id.work_process_old_ids')
    def _compute_stt(self):
        """Tính toán lại STT cho các dòng."""
        for employee in self.mapped('employee_id'):
            for idx, line in enumerate(employee.work_process_old_ids):
                line.stt = idx + 1
