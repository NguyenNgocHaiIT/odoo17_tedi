from odoo import models, fields, api


class TediHolidayConfig(models.Model):
    _name = 'tedi.holiday.config'
    _description = 'Cấu hình ngày nghỉ'
    _order = 'date desc'

    name = fields.Char(string='Loại ngày nghỉ', required=True, help="Ví dụ: Nghỉ Quốc khánh, Tết Dương lịch...")
    date = fields.Date(string='Ngày', required=True)
    active = fields.Boolean(string='Hoạt động', default=True)
