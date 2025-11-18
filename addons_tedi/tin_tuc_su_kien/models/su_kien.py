from pygments.lexer import default

from odoo import api, models, fields

class EventEvent(models.Model):
    _inherit = 'event.event'

    link = fields.Char(string="Link chi tiết")

    state = fields.Selection([
        ('chua_dien_ra','Chưa diễn ra'),
        ('dang_dien_ra','Đang diễn ra'),
        ('da_ket_thuc','Đã kết thúc')
    ], string='Trạng thái', default='chua_dien_ra')