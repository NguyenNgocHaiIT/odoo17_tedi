from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    ma_don_vi = fields.Char(
        string='Mã đơn vị',
        size=10,
        help='Mã viết tắt của đơn vị, dùng cho số văn bản'
    )