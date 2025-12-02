# -*- coding: utf-8 -*-
from odoo import models, fields, api

class FleetVehicle(models.Model):
    """
    Kế thừa model fleet.vehicle chuẩn của Odoo.
    """
    _inherit = 'fleet.vehicle'

    country_of_manufacture = fields.Many2one('res.country', string="Nước sản xuất")
    engine_no = fields.Char(string="Số máy")
    year_manufacture = fields.Char(string="Năm sản xuất")
    year_in_use = fields.Char(string="Năm đưa vào sử dụng")

    color_select = fields.Selection([
        ('red', 'Đỏ'),
        ('black', 'Đen'),
        ('blue', 'Xanh'),
        ('white', 'Trắng'),
        ('silver', 'Bạc'),
    ], string="Màu sơn (Chọn)")

    cylinder_capacity = fields.Char(string="Dung tích xilanh")

    # --- THÔNG TIN TÀI CHÍNH / ĐỊNH MỨC ---
    original_cost = fields.Float(string="Nguyên giá TSCĐ")
    purchase_value = fields.Float(string="Giá trị mua")
    registration_fee = fields.Float(string="Lệ phí trước bạ")

    fuel_rate = fields.Char(string="Định mức nhiên liệu (L/100km)")
    oil_change_rate = fields.Char(string="Định mức thay dầu (km)")

    # --- LỊCH SỬ CÔNG TÁC (QUAN TRỌNG) ---
    # Sửa: Trỏ vào 'assigned_vehicle_id' vì đã bỏ 'vehicle_id'
    trip_history_ids = fields.One2many(
        'hr_tedi.vehicle.registration',
        'assigned_vehicle_id',
        string="Lịch sử công tác"
    )