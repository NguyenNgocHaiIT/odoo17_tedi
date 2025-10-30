# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HREmployeeTrip(models.Model):
    _name = "hr.employee.trip"
    _description = "Employee Overseas Trip"
    _order = "date_from desc, id asc"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    stt = fields.Integer(string="STT", compute="_compute_stt", store=False, readonly=True)
    date_from = fields.Date(string="Từ ngày", required=True)
    date_to = fields.Date(string="Đến ngày")
    purpose = fields.Char(string="Mục đích")
    country_id = fields.Many2one("res.country", string="Tên nước")
    cost = fields.Monetary(string="Kinh phí")
    currency_id = fields.Many2one(
        "res.currency", string="Tiền tệ",
        default=lambda self: self.env.company.currency_id.id
    )
    attachment_ids = fields.Many2many(
        "ir.attachment", string="Đính kèm",
        relation="trip_ir_attachments_rel", column1="trip_id", column2="att_id"
    )

    @api.depends('employee_id.trip_ids')
    def _compute_stt(self):
        """
        Tính toán lại STT cho các dòng dựa trên vị trí của chúng trong danh sách.
        """
        for employee in self.mapped('employee_id'):
            # Lấy danh sách các dòng one2many theo đúng thứ tự trên giao diện
            lines_in_order = employee.trip_ids
            for idx, line in enumerate(lines_in_order):
                # Gán trực tiếp STT
                line.stt = idx + 1

