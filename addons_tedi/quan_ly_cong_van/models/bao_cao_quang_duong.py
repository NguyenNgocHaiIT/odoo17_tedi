# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class HrTediVehicleOdometerReport(models.Model):
    _name = "hr_tedi.vehicle.odometer.report"
    _description = "Báo cáo số km từng xe"
    _rec_name = "display_name"
    _order = "year desc, month desc"

    # Tham chiếu đến bản ghi xe (bảng lưu thông tin xe / phân công xe)
    vehicle_id = fields.Many2one('hr_tedi.vehicle.record', string="Phân công xe", required=True)
    # Tháng/năm của báo cáo (dùng để gom các phiếu đăng ký trong tháng đó)
    month = fields.Integer(string="Tháng", required=True)
    year = fields.Integer(string="Năm", required=True)

    # Số km đầu kỳ (có thể nhập tay). Lưu vào cơ sở dữ liệu (store=True)
    odometer_start = fields.Float(string="Số km đầu", digits=(12, 2), default=0.0, store=True)

    # Số km tổng trong tháng: tổng các distance_km của tất cả phiếu đăng ký xe trong tháng
    # Không store để luôn tính mới khi mở view / khi trường phụ thuộc thay đổi
    odometer_total = fields.Float(
        string="Số km",
        digits=(12, 2),
        compute='_compute_odometer_totals'
    )

    # Số km cuối kỳ = số km đầu + số km tổng
    odometer_end = fields.Float(
        string="Số km cuối",
        digits=(12, 2),
        compute='_compute_odometer_totals'
    )

    # Tên hiển thị: dùng để dễ đọc trong tree/form
    display_name = fields.Char(string="Tên", compute='_compute_display_name')

    @api.depends('vehicle_id', 'month', 'year')
    def _compute_display_name(self):
        """
        Tạo tên hiển thị theo dạng: <tên xe> / mm-yyyy
        Nếu không có vehicle_id thì chỉ hiển thị mm-yyyy
        """
        for rec in self:
            if rec.vehicle_id:
                rec.display_name = "%s / %02d-%04d" % (
                    rec.vehicle_id.name or rec.vehicle_id.id,
                    rec.month or 0,
                    rec.year or 0
                )
            else:
                rec.display_name = "%02d-%04d" % (rec.month or 0, rec.year or 0)

    # Tính phạm vi thời gian (bắt đầu, kết thúc) cho một tháng cụ thể
    def _month_date_range(self, year, month):
        start = date(year, month, 1)
        # end_date là ngày bắt đầu của tháng kế tiếp (để so sánh < end_date khi truy vấn)
        end_date = start + relativedelta(months=1)
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())
        return start_dt, end_dt

    # Tính: km tổng, km đầu, km cuối
    @api.depends('vehicle_id', 'month', 'year')
    def _compute_odometer_totals(self):
        Registration = self.env['hr_tedi.vehicle.registration']

        for rec in self:
            # Khởi tạo
            rec.odometer_total = 0.0

            # Nếu chưa có thông tin xe hoặc tháng/năm thì odometer_end bằng odometer_start (hoặc 0)
            if not rec.vehicle_id or not rec.month or not rec.year:
                rec.odometer_end = rec.odometer_start or 0.0
                continue

            # 1) Tính tổng km: lấy tất cả phiếu đăng ký trong khoảng thời gian của tháng
            start_dt, end_dt = self._month_date_range(rec.year, rec.month)

            registrations = Registration.search([
                ('assigned_vehicle_id', '=', rec.vehicle_id.id),
                ('start_date', '>=', start_dt),
                ('start_date', '<', end_dt),
            ])
            # Tổng số km của tất cả phiếu (nếu distance_km rỗng thì dùng 0.0)
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

        # Nếu chưa có báo cáo thì tạo mới (với odometer_start mặc định 0.0)
        if not rec:
            rec = self.create({
                'vehicle_id': vehicle_id,
                'year': year,
                'month': month,
            })

        # Gọi hàm tính toán để cập nhật các trường compute
        rec._compute_odometer_totals()
        return rec

    # Hàm tiện ích: tính tổng km của một xe trong tháng (trả về số km)
    def calculate_monthly_km(self, vehicle_id, year, month):
        """
        Tính tổng km cho vehicle_id trong tháng/year.
        Trả về tổng km (float).
        """
        # Xây dựng ngày bắt đầu tháng
        start_date = fields.Date.to_date(f"{year}-{month:02d}-01")
        # Ngày kết thúc là ngày cuối cùng của tháng (dùng relativedelta để cộng 1 tháng rồi trừ 1 ngày)
        end_date = start_date + relativedelta(months=1) - relativedelta(days=1)

        registrations = self.search([
            ('assigned_vehicle_id', '=', vehicle_id),
            ('start_date', '>=', start_date),
            ('start_date', '<=', end_date),
        ])

        total_km = sum(reg.distance_km for reg in registrations)
        return total_km
