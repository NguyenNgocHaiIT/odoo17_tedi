# -*- coding: utf-8 -*-
from odoo import api, models, fields

class RoleOnlyOffice(models.Model):
    _name = 'role.onlyoffice'
    _rec_name="role_access"

    role_access = fields.Char('Role Access')
