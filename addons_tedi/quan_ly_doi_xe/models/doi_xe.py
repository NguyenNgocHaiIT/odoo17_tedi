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

    # --- LỊCH SỬ CÔNG TÁC ---
    trip_history_ids = fields.One2many(
        'hr_tedi.vehicle.registration',
        'assigned_vehicle_id',
        string="Lịch sử công tác"
    )

    @api.model
    def create(self, vals):
        """
        Khi tạo xe mới:
        1. Tạo xe.
        2. Tự động tạo bản ghi Odometer đầu tiên.
           - Nếu người dùng nhập 'odometer' thì dùng giá trị đó.
           - Nếu không nhập thì mặc định = 0.
        """
        # Nếu người dùng không nhập odometer, gán mặc định là 0 trong vals để Odoo xử lý
        initial_odometer = vals.get('odometer', 0.0)

        vehicle = super(FleetVehicle, self).create(vals)

        Odometer = self.env['fleet.vehicle.odometer']

        # [SỬA LỖI] Dùng search_count thay vì search(count=True)
        existing_log = Odometer.search_count([('vehicle_id', '=', vehicle.id)])

        if existing_log == 0:
            Odometer.create({
                'vehicle_id': vehicle.id,
                'value': initial_odometer,
                'date': fields.Date.today(),
                'report_type': 'log',  # Đánh dấu đây là nhật ký thường
                'driver_id': vehicle.driver_id.id or False,
                'unit': 'kilometers',  # Đơn vị mặc định
            })

        return vehicle