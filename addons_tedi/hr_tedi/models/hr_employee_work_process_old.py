# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HREmployeeWorkProcessOld(models.Model):
    _name = "hr.employee.work.process.old"
    _description = "Quá trình công tác tại đơn vị cũ"

    stt = fields.Integer(string="STT", compute="_compute_stt", store=False)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")

    company_name = fields.Char(string="Tên công ty")
    work_address = fields.Char(string="Địa chỉ làm việc")
    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")
    position = fields.Char(string="Vị trí")

    @api.depends('employee_id.work_process_old_ids')
    def _compute_stt(self):
        """Tính toán lại STT cho các dòng."""
        for employee in self.mapped('employee_id'):
            for idx, line in enumerate(employee.work_process_old_ids):
                line.stt = idx + 1
