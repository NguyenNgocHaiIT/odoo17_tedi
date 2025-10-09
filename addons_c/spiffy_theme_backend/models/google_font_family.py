# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class GoogleFontlink(models.Model):
	_name = 'google.font.family'
	_description = "Google Font Link"

	name = fields.Char("Name")
	url = fields.Char("URL")
	config_id = fields.Many2one('backend.config', string="Backend Config")
	is_selected = fields.Boolean("Is Selected", default=False)