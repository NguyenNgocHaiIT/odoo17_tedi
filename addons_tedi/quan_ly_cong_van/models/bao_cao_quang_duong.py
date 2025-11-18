# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class HrTediVehicleOdometerReport(models.Model):
    _name = "hr_tedi.vehicle.odometer.report"
    _description = "Báo cáo số km từng xe"
    _rec_name = "display_name"
    _order = "year desc, month desc"

    vehicle_id = fields.Many2one('hr_tedi.vehicle.record', string="Phân công xe", required=True)
    month = fields.Integer(string="Tháng", required=True)
    year = fields.Integer(string="Năm", required=True)

    # Số km đầu → luôn lấy từ tháng trước
    odometer_start = fields.Float(string="Số km đầu", digits=(12, 2), default=0.0, store=True)

    # Không store → luôn tính khi mở view
    odometer_total = fields.Float(
        string="Số km",
        digits=(12, 2),
        compute='_compute_odometer_totals'
    )
    odometer_end = fields.Float(
        string="Số km cuối",
        digits=(12, 2),
        compute='_compute_odometer_totals'
    )

    display_name = fields.Char(string="Tên", compute='_compute_display_name')

    # Hiển thị: "Xe ABC / 01-2025"
    @api.depends('vehicle_id', 'month', 'year')
    def _compute_display_name(self):
        for rec in self:
            if rec.vehicle_id:
                rec.display_name = "%s / %02d-%04d" % (
                    rec.vehicle_id.name or rec.vehicle_id.id,
                    rec.month or 0,
                    rec.year or 0
                )
            else:
                rec.display_name = "%02d-%04d" % (rec.month or 0, rec.year or 0)

    # Tính phạm vi ngày của tháng
    def _month_date_range(self, year, month):
        start = date(year, month, 1)
        end_date = start + relativedelta(months=1)
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())
        return start_dt, end_dt

    # Tính: km tổng, km đầu, km cuối
    @api.depends('vehicle_id', 'month', 'year')
    def _compute_odometer_totals(self):
        Registration = self.env['hr_tedi.vehicle.registration']

        for rec in self:
            rec.odometer_total = 0.0

            if not rec.vehicle_id or not rec.month or not rec.year:
                rec.odometer_end = rec.odometer_start or 0.0
                continue

            # 1. Tính tổng km từ tất cả phiếu đăng ký xe trong tháng
            start_dt, end_dt = self._month_date_range(rec.year, rec.month)

            registrations = Registration.search([
                ('assigned_vehicle_id', '=', rec.vehicle_id.id),
                ('start_date', '>=', start_dt),
                ('start_date', '<', end_dt),
            ])
            rec.odometer_total = sum(reg.distance_km or 0.0 for reg in registrations)

            # 2. Tự động lấy số km cuối tháng trước làm số km đầu nếu chưa nhập tay
            if not rec.odometer_start:
                prev_month = rec.month - 1
                prev_year = rec.year
                if prev_month == 0:
                    prev_month = 12
                    prev_year -= 1

                prev_report = self.search([
                    ('vehicle_id', '=', rec.vehicle_id.id),
                    ('year', '=', prev_year),
                    ('month', '=', prev_month)
                ], limit=1)

                rec.odometer_start = prev_report.odometer_end if prev_report else 0.0

            # 3. Tính số km cuối = đầu + tổng
            rec.odometer_end = rec.odometer_start + rec.odometer_total

    # Dùng khi muốn force update từ registration
    def recompute_for_vehicle_month(self, vehicle_id, year, month):
        if not vehicle_id:
            return

        rec = self.search([
            ('vehicle_id', '=', vehicle_id),
            ('year', '=', year),
            ('month', '=', month)
        ], limit=1)

        # Nếu chưa có -> tạo
        if not rec:
            rec = self.create({
                'vehicle_id': vehicle_id,
                'year': year,
                'month': month,
            })

        rec._compute_odometer_totals()
        return rec

    # Added a method to calculate total kilometers for a vehicle in a given month and year.
    def calculate_monthly_km(self, vehicle_id, year, month):
        """
        Calculate the total kilometers for a specific vehicle in a given month and year.
        """
        start_date = fields.Date.to_date(f"{year}-{month:02d}-01")
        end_date = start_date + relativedelta(months=1) - relativedelta(days=1)

        registrations = self.search([
            ('assigned_vehicle_id', '=', vehicle_id),
            ('start_date', '>=', start_date),
            ('start_date', '<=', end_date),
        ])

        total_km = sum(reg.distance_km for reg in registrations)
        return total_km
