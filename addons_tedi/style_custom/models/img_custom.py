# models/style_custom_image.py
from odoo import models, fields

class StyleCustomImage(models.Model):
    _name = 'style.custom.image'
    _description = 'Login Background Image'

    name = fields.Char(default="Login Background")
    image = fields.Binary(string="Ảnh nền", attachment=True)
    active = fields.Boolean(default=True)
