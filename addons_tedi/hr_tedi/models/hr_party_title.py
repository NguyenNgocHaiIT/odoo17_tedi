# -*- coding: utf-8 -*-
from odoo import models, fields

class HrPartyTitle(models.Model):
    _name = "hr.party.title"
    _description = "Chức danh Đảng"
    _order = "name"

    name = fields.Char(string="Tên chức danh", required=True)
    active = fields.Boolean(default=True, string="Hoạt động")


class HrMilitaryRank(models.Model):
    _name = 'hr.military.rank'
    _description = 'Cấp bậc/Chức danh Quân đội'
    _order = 'id'

    name = fields.Char(string="Tên cấp bậc", required=True)
    code = fields.Char(string="Mã", help="Ví dụ: THIEU_UY, TRUNG_UY...")
    description = fields.Text(string="Mô tả")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tên cấp bậc đã tồn tại!'),
        ('code_uniq', 'unique (code)', 'Mã cấp bậc phải là duy nhất!')
    ]
class HrUnionTitle(models.Model):
    _name = "hr.union.title"
    _description = "Chức danh Công đoàn"
    _order = "name"

    name = fields.Char(string="Tên chức danh", required=True)
    active = fields.Boolean(default=True, string="Hoạt động")

class HrYouthUnionTitle(models.Model):
    _name = "hr.youth.union.title"
    _description = "Chức danh Đoàn thanh niên"
    _order = "name"

    name = fields.Char(string="Tên chức danh", required=True)
    active = fields.Boolean(default=True, string="Hoạt động")

