# -*- coding: utf-8 -*-
from odoo import models, fields

class HrPartyTitle(models.Model):
    _name = "hr.party.title"
    _description = "Chức danh Đảng"
    _order = "name"

    name = fields.Char(string="Tên chức danh", required=True)
    active = fields.Boolean(default=True, string="Hoạt động")
