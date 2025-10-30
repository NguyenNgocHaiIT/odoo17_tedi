# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HREmployeeWorkProcessTedi(models.Model):
    _name = "hr.employee.work.process.tedi"
    _description = "Quá trình công tác tại TEDI"
    _order = "decision_date desc, id desc"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")

    decision_no = fields.Char(string="Số quyết định")
    decision_date = fields.Date(string="Ngày quyết định")
    content = fields.Char(string="Nội dung")
    department_from_id = fields.Many2one('hr.department', string="Bộ phận đi")
    department_to_id = fields.Many2one('hr.department', string="Bộ phận đến")
    date_from = fields.Date(string="Ngày chuyển đi")
    date_to = fields.Date(string="Ngày chuyển đến")
