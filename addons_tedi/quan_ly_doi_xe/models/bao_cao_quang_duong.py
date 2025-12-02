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
        ('log', 'Nhật ký thường'),
        ('monthly', 'Báo cáo tháng')
    ], string='Loại bản ghi', default='log', required=True)

    # --- 2. CÁC TRƯỜNG CHO BÁO CÁO THÁNG ---
    month = fields.Integer(string="Tháng", group_operator=False)
    year = fields.Integer(string="Năm", group_operator=False)
    odometer_start = fields.Float(string="Số km đầu kỳ", digits=(12, 2))

    # Trường hiển thị tổng km chạy trong tháng
    odometer_total = fields.Float(
        string="Tổng km hoạt động",
        digits=(12, 2),
        readonly=True
    )

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

            # Chuyển sang datetime để so sánh giờ (nếu cần chính xác từng phút)
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
                # TRƯỜNG HỢP 1: Có tháng trước -> Tự động lấy số cuối tháng trước làm đầu kỳ này
                rec.odometer_start = prev_report.value
            else:
                # TRƯỜNG HỢP 2: Không có tháng trước (Tháng đầu tiên nhập liệu)
                # -> Giữ nguyên giá trị người dùng nhập tay, không làm gì cả.
                # Nếu người dùng chưa nhập gì thì mặc định là 0.
                pass

                # --- XỬ LÝ TỔNG KM HOẠT ĐỘNG TRONG THÁNG ---
            # Tìm các phiếu đăng ký xe có trạng thái 'done' và ngày về nằm trong tháng này
            domain = [
                ('assigned_vehicle_id', '=', rec.vehicle_id.id),
                ('end_date', '>=', start_dt),
                ('end_date', '<', end_dt),
                ('state', '=', 'done')
            ]
            trips = Registration.search(domain)

            # Tính tổng quãng đường (giả sử field lưu km trong phiếu là distance_km)
            total_trip_km = sum(trips.mapped('distance_km'))
            rec.odometer_total = total_trip_km

            # --- XỬ LÝ SỐ KM CUỐI KỲ ---
            # Công thức: Cuối = Đầu + Tổng chạy
            rec.value = rec.odometer_start + rec.odometer_total

            # Cập nhật ngày chốt sổ (để hiển thị đúng ngày cuối tháng)
            last_day_of_month = start_date + relativedelta(months=1, days=-1)
            rec.date = last_day_of_month

    @api.model
    def create(self, vals):
        if vals.get('report_type') == 'monthly' and vals.get('month') and vals.get('year'):
            # Tự động set ngày chốt là cuối tháng khi tạo mới
            last_day = date(vals['year'], vals['month'], 1) + relativedelta(months=1, days=-1)
            vals['date'] = last_day
        return super(FleetVehicleOdometer, self).create(vals)