# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AttendanceShiftConfig(models.Model):
    _name = 'attendance.shift.config'
    _description = 'Cấu hình Ca làm việc chuẩn'

    name = fields.Char(string='Tên ca', required=True, default='Ca Hành Chính')

    # Giờ chuẩn để chia ra số công (Ví dụ: 8 tiếng = 1 công)
    standard_hours_per_day = fields.Float(string='Giờ chuẩn/ngày', default=8.0, required=True)

    # Khung giờ Sáng
    morning_start = fields.Float(string='Sáng: Bắt đầu', default=8.5)  # 8h30
    morning_end = fields.Float(string='Sáng: Kết thúc', default=12.0)  # 12h00

    # Khung giờ Chiều
    afternoon_start = fields.Float(string='Chiều: Bắt đầu', default=13.0)  # 13h00
    afternoon_end = fields.Float(string='Chiều: Kết thúc', default=17.5)  # 17h30 (hoặc 18.0 tuỳ bạn)

    @api.constrains('morning_start', 'morning_end', 'afternoon_start', 'afternoon_end')
    def _check_times(self):
        for rec in self:
            if rec.morning_start >= rec.morning_end:
                raise ValidationError("Giờ bắt đầu sáng phải nhỏ hơn giờ kết thúc sáng!")
            if rec.morning_end > rec.afternoon_start:
                raise ValidationError("Giờ kết thúc sáng không được lấn sang giờ chiều!")
            if rec.afternoon_start >= rec.afternoon_end:
                raise ValidationError("Giờ bắt đầu chiều phải nhỏ hơn giờ kết thúc chiều!")