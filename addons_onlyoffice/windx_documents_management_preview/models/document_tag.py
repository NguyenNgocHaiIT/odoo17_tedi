# -*- coding: utf-8 -*-
from odoo import models, fields
from random import randint

class DocumentTag(models.Model):
    _name = 'document.tag'
    _description = 'Document Tag'

    def _default_color(self):
        return randint(1, 20)

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer('Color', default=_default_color)

    _sql_constraints = [
        ('document_tag_name_uniq', 'unique(name)', "Document Tag name already exists!"),
    ]
