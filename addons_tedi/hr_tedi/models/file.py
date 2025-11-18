# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HRDecision(models.Model):
    _name = "hr.decision"
    _description = "Quản lý Quyết định (Khen thưởng/Kỷ luật)"
    _order = "decision_date desc, id desc"
    _rec_name = 'display_name'

    decision_no = fields.Char(string="Số quyết định", required=True)
    decision_date = fields.Date(string="Ngày quyết định", required=True)
    decision_level = fields.Char(string="Cấp quyết định")
    content = fields.Text(string="Nội dung/Trích yếu")
    display_name = fields.Char(string="Tên hiển thị", compute='_compute_display_name', store=True)

    @api.depends('decision_no', 'content')
    def _compute_display_name(self):
        for rec in self:
            name = rec.decision_no or 'Chưa có số QĐ'
            if rec.content:
                name = f"[{name}] {rec.content[:50]}..."
            rec.display_name = name
