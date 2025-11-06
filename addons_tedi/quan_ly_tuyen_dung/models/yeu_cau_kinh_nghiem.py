from odoo import models, fields

class ExperienceRequest(models.Model):
    _name = 'experience.request'
    _description = 'Yêu cầu kinh nghiệm'

    name = fields.Char(string = "Tên")
    active = fields.Boolean(default=True , string = "Hoạt động" )