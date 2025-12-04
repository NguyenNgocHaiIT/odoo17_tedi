# -*- coding: utf-8 -*-
from odoo import models, fields
from random import randint

class DirectoryTag(models.Model):
    _name = 'directory.tag'
    _description = 'Directory Tag'

    def _default_color(self):
        return randint(1, 20)

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer('Color', default=_default_color)

    _sql_constraints = [
        ('directory_tag_name_uniq', 'unique(name)', "Directory Tag name already exists!"),
    ]
