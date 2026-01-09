# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class FleetVehicleOdometer(models.Model):
    _inherit = 'fleet.vehicle.odometer'
    _order = 'date desc, value desc'

    # --- 1. PHÂN LOẠI RECORD ---
    report_type = fields.Selection([
        ('log', 'Khởi tạo'),
        ('monthly', 'Báo cáo theo Đăng ký')
    ], string='Loại bản ghi', default='log', required=True)

    # --- 2. CÁC TRƯỜNG CHO BÁO CÁO THÁNG ---
    month = fields.Integer(string="Tháng", group_operator=False)
    year = fields.Integer(string="Năm", group_operator=False)
    odometer_start = fields.Float(string="Số km đầu kỳ", digits=(12, 2))
    odometer_total = fields.Float(string="Tổng km hoạt động", digits=(12, 2), readonly=True)
    speedometer_total = fields.Float(string="Tổng km theo đồng hồ", digits=(12, 2), readonly=True)

    # Các trường mới cho báo cáo thanh toán
    km_noi_tinh = fields.Float(string="Số km nội tỉnh", digits=(12, 2), compute='_compute_km_by_type', store=False)
    km_ngoai_tinh = fields.Float(string="Số km ngoại tỉnh", digits=(12, 2), compute='_compute_km_by_type', store=False)

    xang_duoc_thanh_toan = fields.Float(string="Xăng được thanh toán (lít)", digits=(12, 2),
                                        compute='_compute_fuel_oil')
    dau_duoc_thanh_toan = fields.Float(string="Dầu được thanh toán (lít)", digits=(12, 2), compute='_compute_fuel_oil')

    def _compute_km_by_type(self):
        """Tính tổng km theo loại công tác (nội thành/ngoại thành)"""
        for record in self:
            if record.report_type != 'monthly':
                record.km_noi_tinh = 0
                record.km_ngoai_tinh = 0
                continue

            # Xác định thời gian đầu và cuối tháng
            start_date = date(record.year, record.month, 1)
            end_date = start_date + relativedelta(months=1)

            # Tìm các phiếu đăng ký trong tháng
            domain = [
                ('assigned_vehicle_id', '=', record.vehicle_id.id),
                ('state', '=', 'done'),
                ('end_date', '>=', datetime.combine(start_date, time.min)),
                ('end_date', '<', datetime.combine(end_date, time.min))
            ]

            trips = self.env['hr_tedi.vehicle.registration'].search(domain)

            # Tính tổng theo loại công tác
            noi_thanh_trips = trips.filtered(lambda t: t.trip_type == 'noi_thanh')
            ngoai_thanh_trips = trips.filtered(lambda t: t.trip_type == 'ngoai_thanh')

            record.km_noi_tinh = sum(noi_thanh_trips.mapped('distance_km'))
            record.km_ngoai_tinh = sum(ngoai_thanh_trips.mapped('distance_km'))

    def _compute_fuel_oil(self):
        """Tính nhiên liệu được thanh toán"""
        for record in self:
            if record.report_type != 'monthly':
                record.xang_duoc_thanh_toan = 0
                record.dau_duoc_thanh_toan = 0
                continue

            # Lấy định mức từ xe
            vehicle = record.vehicle_id

            # Xăng: định mức * (tổng km / 100)
            if vehicle.fuel_rate:
                try:
                    fuel_rate = float(vehicle.fuel_rate)
                    record.xang_duoc_thanh_toan = fuel_rate * (record.odometer_total / 100)
                except:
                    record.xang_duoc_thanh_toan = 0
            else:
                record.xang_duoc_thanh_toan = 0

            # Dầu: định mức * (tổng km / 3000)
            if vehicle.oil_change_rate:
                try:
                    oil_rate = float(vehicle.oil_change_rate)
                    record.dau_duoc_thanh_toan = oil_rate * (record.odometer_total / 3000)
                except:
                    record.dau_duoc_thanh_toan = 0
            else:
                record.dau_duoc_thanh_toan = 0

    # --- 3. HÀM TÍNH TOÁN (CORE LOGIC) ---
    def action_calculate_data(self):
        """
        Tính toán lại số liệu cho báo cáo tháng.
        """
        # Model phiếu đăng ký xe
        Registration = self.env['hr_tedi.vehicle.registration']

        for rec in self:
            # Chỉ chạy logic này cho loại báo cáo tháng
            if rec.report_type != 'monthly' or not rec.month or not rec.year:
                continue

            # 1. Xác định thời gian đầu tháng và cuối tháng hiện tại
            start_date = date(rec.year, rec.month, 1)
            end_date = start_date + relativedelta(months=1)

            # Chuyển sang datetime để so sánh giờ
            start_dt = datetime.combine(start_date, time.min)
            end_dt = datetime.combine(end_date, time.min)

            # --- XỬ LÝ SỐ KM ĐẦU KỲ ---
            # Tìm báo cáo của THÁNG TRƯỚC (Month - 1)
            prev_month_date = start_date - relativedelta(months=1)
            prev_report = self.search([
                ('vehicle_id', '=', rec.vehicle_id.id),
                ('month', '=', prev_month_date.month),
                ('year', '=', prev_month_date.year),
                ('report_type', '=', 'monthly')
            ], limit=1)

            if prev_report:
                # Có tháng trước -> Tự động lấy số cuối tháng trước
                rec.odometer_start = prev_report.value
            else:
                # Không có tháng trước -> Cố gắng lấy nhật ký Odometer gần nhất trước ngày mùng 1
                last_log = self.search([
                    ('vehicle_id', '=', rec.vehicle_id.id),
                    ('report_type', '=', 'log'),
                    ('date', '<', start_date)
                ], order='date desc, value desc', limit=1)

                if last_log:
                    rec.odometer_start = last_log.value
                elif rec.odometer_start == 0:
                    # Nếu vẫn = 0 và ko tìm thấy log cũ, có thể giữ nguyên hoặc set 0
                    pass

            # --- XỬ LÝ TỔNG KM HOẠT ĐỘNG TRONG THÁNG ---
            # Tìm các phiếu đăng ký xe hoàn thành trong tháng
            domain = [
                ('assigned_vehicle_id', '=', rec.vehicle_id.id),
                ('end_date', '>=', start_dt),
                ('end_date', '<', end_dt),
                ('state', '=', 'done')
            ]
            trips = Registration.search(domain)

            # Tính tổng quãng đường
            total_trip_km = sum(trips.mapped('distance_km'))
            rec.odometer_total = total_trip_km

            # Lấy km theo đồng hồ
            total_speedometer_km = sum(trips.mapped('speedometer_km'))
            rec.speedometer_total = total_speedometer_km

            # --- XỬ LÝ SỐ KM CUỐI KỲ ---
            # Công thức: Cuối = Đầu + Tổng chạy
            rec.value = rec.odometer_start + rec.odometer_total

            # Cập nhật ngày chốt sổ
            last_day_of_month = start_date + relativedelta(months=1, days=-1)
            rec.date = last_day_of_month

            # Tính lại các field phụ thuộc
            rec._compute_km_by_type()
            rec._compute_fuel_oil()

    @api.model
    def create(self, vals):
        if vals.get('report_type') == 'monthly' and vals.get('month') and vals.get('year'):
            # Tự động set ngày chốt là cuối tháng khi tạo báo cáo tháng
            last_day = date(vals['year'], vals['month'], 1) + relativedelta(months=1, days=-1)
            vals['date'] = last_day
        return super(FleetVehicleOdometer, self).create(vals)

    def action_open_vehicle_report(self):
        """Mở wizard xuất báo cáo từ odometer tree view"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Xuất báo cáo thanh toán',
            'res_model': 'thanh.toan.xe.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.vehicle_id.id,
                'default_month': self.month,
                'default_year': self.year,
            }
        }


class ThanhToanXeReportWizard(models.TransientModel):
    _name = 'thanh.toan.xe.report.wizard'
    _description = 'Wizard xuất báo cáo thanh toán xe'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Xe', required=True)
    month = fields.Integer(string='Tháng', required=True, default=lambda self: fields.Date.today().month)
    year = fields.Integer(string='Năm', required=True, default=lambda self: fields.Date.today().year)

    def action_export_excel(self):
        """Xuất Excel - đơn giản và hiệu quả"""
        self.ensure_one()

        # Chỉ trả về URL download
        # Odoo sẽ tự mở URL này khi popup đóng
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/binary/download_thanh_toan_report?vehicle_id={self.vehicle_id.id}&month={self.month}&year={self.year}',
            'target': 'download',  # hoặc 'current' cũng được
        }