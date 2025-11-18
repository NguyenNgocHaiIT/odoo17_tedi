from odoo import api, models, fields
from odoo.exceptions import UserError
from datetime import timedelta

class CalendarOutside(models.Model):
    _name = 'calendar.outside'

    name = fields.Char(string='Chủ đề cuộc họp')
    location = fields.Many2one('calendar.location', string='Địa điểm')
    start = fields.Datetime(string='Thời gian bắt đầu')
    stop = fields.Datetime(string='Thời gian kết thúc')
    user_id = fields.Many2one('res.users', string='Người chủ trì')
    partner_ids = fields.Many2many('res.users', string='Thành phần tham gia')
    lanh_dao = fields.Many2one('res.users', string='Lãnh đạo')
    color = fields.Integer(string='Màu', default=lambda self: 0)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('approved', 'Đã duyệt'),
        ('canceled', 'Đã hủy')
    ], string='Trạng thái', default='draft', tracking=True)

    def approve(self):
        for event in self:
            # Ví dụ: đánh dấu trạng thái đã duyệt
            event.write({'state': 'approved'})
        return True

    @api.model
    def create(self, vals):
        record = super().create(vals)
        record.color = record.id % 12
        return record


class CalendarLocation(models.Model):
    _name = 'calendar.location'

    name = fields.Char(string='Tên địa điểm')