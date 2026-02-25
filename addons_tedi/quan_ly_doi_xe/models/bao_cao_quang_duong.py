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
        ('monthly', 'Báo cáo theo Đăng ký'),
        ('period', 'Báo cáo theo Khoảng thời gian')  # Thêm loại báo cáo theo khoảng thời gian
    ], string='Loại bản ghi', default='log', required=True)

    # --- 2. CÁC TRƯỜNG CHO BÁO CÁO THÁNG ---
    month = fields.Integer(string="Tháng", group_operator=False)
    year = fields.Integer(string="Năm", group_operator=False)

    # --- THÊM TRƯỜNG CHO BÁO CÁO THEO KHOẢNG THỜI GIAN ---
    start_date_period = fields.Date(string="Ngày bắt đầu")
    end_date_period = fields.Date(string="Ngày kết thúc")

    odometer_start = fields.Float(string="Số km đầu kỳ", digits=(12, 2))
    odometer_total = fields.Float(string="Tổng km hoạt động", digits=(12, 2), readonly=True)
    speedometer_total = fields.Float(string="Tổng km theo đồng hồ", digits=(12, 2), readonly=True)

    # Các trường mới cho báo cáo thanh toán
    km_noi_tinh = fields.Float(string="Số km nội tỉnh", digits=(12, 2), compute='_compute_km_by_type', store=False)
    km_ngoai_tinh = fields.Float(string="Số km ngoại tỉnh", digits=(12, 2), compute='_compute_km_by_type', store=False)

    xang_duoc_thanh_toan = fields.Float(string="Xăng được thanh toán (lít)", digits=(12, 2),
                                        compute='_compute_fuel_oil')
    dau_duoc_thanh_toan = fields.Float(string="Dầu được thanh toán (lít)", digits=(12, 2), compute='_compute_fuel_oil')

    @api.depends('report_type', 'month', 'year', 'start_date_period', 'end_date_period')
    def _compute_km_by_type(self):
        """Tính tổng km theo loại công tác (nội thành/ngoại thành)"""
        for record in self:
            if record.report_type not in ['monthly', 'period']:
                record.km_noi_tinh = 0
                record.km_ngoai_tinh = 0
                continue

            # Xác định thời gian đầu và cuối dựa trên loại báo cáo
            if record.report_type == 'monthly':
                if not record.month or not record.year:
                    continue
                start_date = date(record.year, record.month, 1)
                end_date = start_date + relativedelta(months=1)
            else:  # report_type == 'period'
                if not record.start_date_period or not record.end_date_period:
                    continue
                start_date = record.start_date_period
                end_date = record.end_date_period + relativedelta(days=1)  # Thêm 1 ngày để bao gồm ngày cuối

            # Tìm các phiếu đăng ký trong khoảng thời gian
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
            if record.report_type not in ['monthly', 'period']:
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
        Tính toán lại số liệu cho báo cáo.
        """
        # Model phiếu đăng ký xe
        Registration = self.env['hr_tedi.vehicle.registration']

        for rec in self:
            # Chỉ chạy logic này cho loại báo cáo tháng hoặc khoảng thời gian
            if rec.report_type not in ['monthly', 'period']:
                continue

            # Xác định khoảng thời gian dựa trên loại báo cáo
            if rec.report_type == 'monthly':
                if not rec.month or not rec.year:
                    continue
                start_date = date(rec.year, rec.month, 1)
                end_date = start_date + relativedelta(months=1)
            else:  # report_type == 'period'
                if not rec.start_date_period or not rec.end_date_period:
                    continue
                start_date = rec.start_date_period
                end_date = rec.end_date_period + relativedelta(days=1)  # Thêm 1 ngày để bao gồm ngày cuối

            # Chuyển sang datetime để so sánh giờ
            start_dt = datetime.combine(start_date, time.min)
            end_dt = datetime.combine(end_date, time.min)

            # --- XỬ LÝ SỐ KM ĐẦU KỲ ---
            # Tìm báo cáo gần nhất trước ngày bắt đầu
            prev_reports = self.search([
                ('vehicle_id', '=', rec.vehicle_id.id),
                ('report_type', 'in', ['monthly', 'period']),
                ('date', '<', start_date)
            ], order='date desc', limit=1)

            if prev_reports:
                rec.odometer_start = prev_reports.value
            else:
                # Không có báo cáo trước -> Cố gắng lấy nhật ký Odometer gần nhất
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

            # --- XỬ LÝ TỔNG KM HOẠT ĐỘNG TRONG KHOẢNG THỜI GIAN ---
            # Tìm các phiếu đăng ký xe hoàn thành trong khoảng thời gian
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
            if rec.report_type == 'monthly':
                last_day_of_month = start_date + relativedelta(months=1, days=-1)
                rec.date = last_day_of_month
            else:
                rec.date = rec.end_date_period

            # Tính lại các field phụ thuộc
            rec._compute_km_by_type()
            rec._compute_fuel_oil()

    @api.model
    def create(self, vals):
        if vals.get('report_type') == 'monthly' and vals.get('month') and vals.get('year'):
            # Tự động set ngày chốt là cuối tháng khi tạo báo cáo tháng
            last_day = date(vals['year'], vals['month'], 1) + relativedelta(months=1, days=-1)
            vals['date'] = last_day
        elif vals.get('report_type') == 'period' and vals.get('end_date_period'):
            # Tự động set ngày chốt là ngày kết thúc khi tạo báo cáo theo khoảng thời gian
            vals['date'] = vals['end_date_period']
        return super(FleetVehicleOdometer, self).create(vals)

    # Thêm vào class FleetVehicleOdometer (sau hàm action_calculate_data)
    def action_open_vehicle_report(self):
        """Mở wizard xuất báo cáo thanh toán"""
        self.ensure_one()

        # Trả về action mở wizard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Xuất báo cáo thanh toán',
            'res_model': 'thanh.toan.xe.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.vehicle_id.id,
                'default_report_type': self.report_type,
                'default_month': self.month if self.report_type == 'monthly' else None,
                'default_year': self.year if self.report_type == 'monthly' else None,
                'default_start_date': self.start_date_period if self.report_type == 'period' else None,
                'default_end_date': self.end_date_period if self.report_type == 'period' else None,
            }
        }

class ThanhToanXeReportWizard(models.TransientModel):
    _name = 'thanh.toan.xe.report.wizard'
    _description = 'Wizard xuất báo cáo thanh toán xe'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Xe', required=True)
    report_type = fields.Selection([
        ('monthly', 'Báo cáo tháng'),
        ('period', 'Báo cáo khoảng thời gian')
    ], string='Loại báo cáo', default='monthly', required=True)

    month = fields.Integer(string='Tháng', default=lambda self: fields.Date.today().month)
    year = fields.Integer(string='Năm', default=lambda self: fields.Date.today().year)

    start_date = fields.Date(string='Ngày bắt đầu', default=lambda self: fields.Date.today())
    end_date = fields.Date(string='Ngày kết thúc', default=lambda self: fields.Date.today())

    @api.onchange('report_type')
    def _onchange_report_type(self):
        """Reset các trường khi thay đổi loại báo cáo"""
        if self.report_type == 'monthly':
            self.start_date = False
            self.end_date = False
        else:
            self.month = False
            self.year = False

    def action_export_excel(self):
        """Xuất Excel - đơn giản và hiệu quả"""
        self.ensure_one()

        # Xây dựng URL với các tham số
        url_params = f'?vehicle_id={self.vehicle_id.id}&report_type={self.report_type}'

        if self.report_type == 'monthly':
            url_params += f'&month={self.month}&year={self.year}'
        else:  # period
            url_params += f'&start_date={self.start_date}&end_date={self.end_date}'

        # Chỉ trả về URL download
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/binary/download_thanh_toan_report{url_params}',
            'target': 'download',
        }