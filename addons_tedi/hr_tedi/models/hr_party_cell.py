# -*- coding: utf-8 -*-
from odoo import models, fields

class HrPartyCell(models.Model):
    _name = "hr.party.cell"
    _description = "Chi bộ Đảng"
    _order = "name"

    name = fields.Char(string="Tên chi bộ", required=True)
    active = fields.Boolean(default=True, string="Hoạt động")

