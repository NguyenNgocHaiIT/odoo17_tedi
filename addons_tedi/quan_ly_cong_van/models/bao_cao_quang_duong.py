# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrTediVehicleOdometerReport(models.Model):
    """
    Model để hiển thị báo cáo số km của từng xe theo tháng/năm.
    (Giả định dữ liệu được tính toán hoặc lấy từ các model khác)
    """
    _name = "hr_tedi.vehicle.odometer.report"
    _description = "Báo cáo số km từng xe"
    vehicle_id = fields.Many2one('hr_tedi.vehicle.record', string="Phân công xe")
    month = fields.Integer(string="Tháng")
    year = fields.Integer(string="Năm")
    odometer_total = fields.Float(string="Số Km")
    odometer_start = fields.Float(string="Số Km đầu")
    odometer_end = fields.Float(string="Số Km cuối")
