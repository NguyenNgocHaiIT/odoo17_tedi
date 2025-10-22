from odoo import models, fields

class DocumentCategory(models.Model):
    _name = 'office.document.category'
    _description = 'Phân loại văn bản'

    code = fields.Char('Mã phân loại', required=True)
    name = fields.Char('Tên phân loại', required=True)
