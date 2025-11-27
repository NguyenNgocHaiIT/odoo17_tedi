# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HrTediVehicleRecord(models.Model):
    """
    Định nghĩa model cho Lý lịch xe (Thông tin xe)
    """
    _name = "hr_tedi.vehicle.record"
    _description = "Lý lịch xe"

    _rec_name = 'display_name'

    display_name = fields.Char(string="Tên", compute='_compute_display_name', store=True)

    driver_id = fields.Many2one('hr.employee', string="Lái xe")
    country_of_manufacture = fields.Many2one('res.country', string="Nước sản xuất")
    model_name = fields.Char(string="Model xe")
    license_plate = fields.Char(string="Biển kiểm soát", required=True)
    year_manufacture = fields.Char(string="Năm sản xuất")
    year_in_use = fields.Char(string="Năm đưa vào sử dụng")
    vin_sn = fields.Char(string="Số khung (VIN)")
    engine_no = fields.Char(string="Số máy")
    color = fields.Selection([
        ('red', 'Đỏ'),
        ('black', 'Đen'),
        ('blue', 'Xanh'),
        ('white', 'Trắng'),
    ], string="Màu sơn")

    cylinder_capacity = fields.Char(string="Dung tích xilanh")
    original_cost = fields.Float(string="Nguyên giá TSCĐ")
    purchase_value = fields.Float(string="Giá trị mua")
    registration_fee = fields.Float(string="Lệ phí trước bạ")
    fuel_rate = fields.Char(string="Định mức nhiên liệu")
    oil_change_rate = fields.Char(string="Định mức thay dầu")
    description = fields.Text(string="Mô tả")
    note = fields.Text(string="Ghi chú")

    # Tab Lịch sử công tác
    trip_history_ids = fields.One2many(
        'hr_tedi.vehicle.registration',
        'vehicle_id',
        string="Lịch sử công tác"
    )

    @api.depends('model_name', 'license_plate')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.license_plate or ''}] {rec.model_name or ''}"
