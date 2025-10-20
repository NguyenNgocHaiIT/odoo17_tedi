# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HREmployeeCertificate(models.Model):
    _name = "hr.employee.certificate"
    _description = "Employee Practice Certificate"
    _order = "id asc"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    stt = fields.Integer(string="STT", compute="_compute_stt", store=False, readonly=True)
    cert_type = fields.Char(string="Loại chứng chỉ", required=True)
    code = fields.Char(string="Mã chứng chỉ")
    issuer = fields.Char(string="Nơi cấp")
    practice_field = fields.Char(string="Lĩnh vực hành nghề")
    rank = fields.Char(string="Hạng")
    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")
    attachment_ids = fields.Many2many(
        "ir.attachment", string="Đính kèm",
        relation="cert_ir_attachments_rel", column1="cert_id", column2="att_id"
    )

    @api.depends('employee_id.certificate_ids')
    def _compute_stt(self):
        """
        Tính toán lại STT cho các dòng dựa trên vị trí của chúng trong danh sách.
        """
        for employee in self.mapped('employee_id'):
            # Lấy danh sách các dòng one2many theo đúng thứ tự trên giao diện
            lines_in_order = employee.certificate_ids
            for idx, line in enumerate(lines_in_order):
                # Gán trực tiếp STT
                line.stt = idx + 1

