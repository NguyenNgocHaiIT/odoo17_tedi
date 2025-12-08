# -*- coding: utf-8 -*-

from odoo import api, models, fields


class Employee(models.Model):
    _inherit = 'hr.employee'

    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Attachments")
