# -*- coding: utf-8 -*-
from odoo import models, fields


class UserRolePermision(models.Model):
    _name = 'user.role.permision'
    _description = "User Role Permision"

    user_id = fields.Many2one('res.users', 'User')
    role_access_ids = fields.Many2many('role.onlyoffice', string='Role Access')
    document_share_id = fields.Many2one('document.share', string='Document share')
