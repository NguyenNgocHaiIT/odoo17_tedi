# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HREmployeeRewardDiscipline(models.Model):
    _name = "hr.employee.reward.discipline"
    _description = "Khen thưởng - Kỷ luật của nhân viên"
    _order = "decision_date desc, id desc"

    employee_id = fields.Many2one(
        "hr.employee", string="Nhân viên", required=True, ondelete="cascade")

    decision_no = fields.Char(string="Số quyết định")
    decision_date = fields.Date(string="Ngày quyết định")
    decision_level = fields.Char(string="Cấp quyết định")
    content = fields.Text(string="Nội dung")
