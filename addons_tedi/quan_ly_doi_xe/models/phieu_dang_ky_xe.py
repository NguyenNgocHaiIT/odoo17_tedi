# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from datetime import datetime, date, time
from dateutil.relativedelta import relativedelta


class HrTediVehicleRegistration(models.Model):
    _name = "hr_tedi.vehicle.registration"
    _description = "Phiếu đăng ký xe"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "code"
    _order = "start_date desc"

    # ========================================================
    # 1. CÁC TRƯỜNG DỮ LIỆU (FIELDS)
    # ========================================================

    code = fields.Char(string="Mã phiếu", default="New", readonly=True)

    requester_id = fields.Many2one(
        'hr.employee', string="Người đề nghị",
        default=lambda self: self.env.user.employee_id, required=True, tracking=True)

    # --- Thông tin lịch trình ---
    start_date = fields.Datetime(string="Thời gian bắt đầu", required=True, tracking=True)
    end_date = fields.Datetime(string="Thời gian kết thúc", required=True, tracking=True)

    trip_type = fields.Selection([
        ('noi_thanh', 'Nội thành'),
        ('ngoai_thanh', 'Ngoại thành'),
    ], string="Loại công tác", required=True)

    destination = fields.Char(string="Địa điểm cụ thể", required=True, tracking=True)
    work_content = fields.Text(string="Nội dung công việc", required=True)
    num_passengers = fields.Integer(string="Số người đi kèm", default=1)
    attachment_ids = fields.Many2many('ir.attachment', string="Tệp đính kèm")

    # --- Thông tin xe (Chỉ hiện khi Văn phòng xếp xe) ---
    assigned_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string="Phân công xe",
        tracking=True,
        domain="[('state_id.name', '=', 'Đã đăng kiểm')]"
    )

    # Trường Tài xế - Tự động lấy từ xe nhưng cho phép sửa đổi
    driver_id = fields.Many2one('res.partner', string="Tài xế", tracking=True)

    # --- Kết quả thực tế (Nhập khi hoàn thành) ---
    distance_km = fields.Float(string="Số km thực tế đi được")

    # --- Trạng thái ---
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Chờ Lãnh đạo duyệt'),
        ('approved', 'Chờ Văn phòng xếp xe'),
        ('refused', 'Từ chối'),
        ('assigned', 'Đã phân xe'),
        ('no_car', 'Hết xe'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    # ========================================================
    # 2. LOGIC TỰ ĐỘNG
    # ========================================================

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('hr_tedi.vehicle.registration') or 'New'
        return super(HrTediVehicleRegistration, self).create(vals)

    @api.onchange('assigned_vehicle_id')
    def _onchange_assigned_vehicle_id(self):
        if self.assigned_vehicle_id and self.assigned_vehicle_id.driver_id:
            self.driver_id = self.assigned_vehicle_id.driver_id

    # ========================================================
    # 3. QUY TRÌNH XỬ LÝ (BUTTON ACTIONS)
    # ========================================================

    def action_submit(self):
        self.ensure_one()
        if not self.start_date or not self.end_date:
            raise ValidationError("Vui lòng nhập đầy đủ thời gian đi và về.")
        if self.start_date >= self.end_date:
            raise ValidationError("Thời gian kết thúc phải lớn hơn thời gian bắt đầu.")
        if not self.requester_id.parent_id:
            raise ValidationError(
                f"Nhân viên {self.requester_id.name} chưa được cấu hình 'Người quản lý' (Manager) trong hồ sơ nhân sự.")
        self.state = 'submitted'

    def action_manager_approve(self):
        self.ensure_one()
        current_user = self.env.user
        manager_user = self.requester_id.parent_id.user_id
        if current_user != manager_user and not current_user.has_group('base.group_system'):
            raise AccessError(
                f"Bạn không có quyền duyệt! Chỉ quản lý trực tiếp ({self.requester_id.parent_id.name}) mới được duyệt.")
        self.state = 'approved'
        self.message_post(body=f"Lãnh đạo ({current_user.name}) đã duyệt. Chuyển Văn phòng bố trí xe.")

    def action_manager_refuse(self):
        self.ensure_one()
        is_manager = self.env.user == self.requester_id.parent_id.user_id
        is_fleet_user = self.env.user.has_group('fleet.fleet_group_user')
        if not (is_manager or is_fleet_user or self.env.user.has_group('base.group_system')):
            raise AccessError("Bạn không có quyền từ chối phiếu này.")
        self.state = 'refused'
        self.message_post(body=f"Yêu cầu đã bị từ chối bởi {self.env.user.name}.")

    def action_office_assign(self):
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_manager') and not self.env.user.has_group(
                'base.group_system'):
            raise AccessError("Chỉ bộ phận Quản lý đội xe mới được thực hiện thao tác này.")
        if self.state != 'approved':
            raise ValidationError("Phiếu này chưa được Lãnh đạo đơn vị duyệt!")
        if not self.assigned_vehicle_id:
            raise ValidationError("Vui lòng chọn 'Xe phân công' trước khi xác nhận.")

        # Check trùng lịch xe
        domain = [
            ('id', '!=', self.id),
            ('assigned_vehicle_id', '=', self.assigned_vehicle_id.id),
            ('state', 'in', ['assigned', 'done']),
            ('start_date', '<', self.end_date),
            ('end_date', '>', self.start_date),
        ]
        duplicate = self.search(domain)
        if duplicate:
            raise ValidationError(
                f"Xe {self.assigned_vehicle_id.license_plate} bị trùng lịch với phiếu {duplicate[0].code} "
                f"({duplicate[0].start_date} - {duplicate[0].end_date})!"
            )

        if not self.driver_id and self.assigned_vehicle_id.driver_id:
            self.driver_id = self.assigned_vehicle_id.driver_id

        self.state = 'assigned'
        self.message_post(
            body=f"Văn phòng đã bố trí xe: {self.assigned_vehicle_id.license_plate}. Tài xế: {self.driver_id.name or 'Chưa rõ'}")

    def action_office_no_car(self):
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_manager') and not self.env.user.has_group(
                'base.group_system'):
            raise AccessError("Quyền hạn không hợp lệ.")
        self.state = 'no_car'
        self.message_post(body="Văn phòng phản hồi: Hiện tại không có xe sẵn sàng.")

    def action_done(self):
        """
        Xác nhận hoàn thành chuyến đi.
        Logic:
        1. Lấy số Odometer hiện tại của xe.
        2. Cộng thêm số km thực tế đi được (distance_km).
        3. Tạo bản ghi Log Odometer mới. Việc này sẽ TỰ ĐỘNG cập nhật lại số km tổng trên model fleet.vehicle.
        """
        self.ensure_one()

        if self.distance_km <= 0:
            raise ValidationError("Vui lòng nhập số KM thực tế (phải lớn hơn 0).")
        if not self.assigned_vehicle_id:
            raise ValidationError("Chưa có xe được phân công.")

        self.state = 'done'

        # --- 1. LẤY SỐ LIỆU & TÍNH TOÁN ---
        # Lấy số km hiện tại từ hồ sơ xe (đây là số km tích lũy)
        current_odometer = self.assigned_vehicle_id.odometer

        # Tính số km mới = Số cũ + Quãng đường vừa đi
        new_odometer_value = current_odometer + self.distance_km

        # Xác định tài xế cho log
        driver_log = self.driver_id.id or self.assigned_vehicle_id.driver_id.id or self.requester_id.user_id.partner_id.id

        # --- 2. CẬP NHẬT ODOMETER (Tạo Log) ---
        # Trong Odoo, khi tạo 1 bản ghi fleet.vehicle.odometer mới nhất,
        # trường 'odometer' trên fleet.vehicle sẽ tự động được cập nhật theo giá trị này.
        self.env['fleet.vehicle.odometer'].create({
            'vehicle_id': self.assigned_vehicle_id.id,
            'value': new_odometer_value,  # Đây là giá trị cộng dồn mới
            'date': self.end_date.date(),
            'driver_id': driver_log,
            'unit': 'kilometers',
            'report_type': 'log'  # Đánh dấu là nhật ký chạy xe
        })

        # --- 3. CẬP NHẬT/TẠO BÁO CÁO THÁNG (LOGIC CŨ) ---
        # Phần này giữ nguyên để phục vụ báo cáo tháng
        trip_month = self.end_date.month
        trip_year = self.end_date.year

        report = self.env['fleet.vehicle.odometer'].search([
            ('vehicle_id', '=', self.assigned_vehicle_id.id),
            ('month', '=', trip_month),
            ('year', '=', trip_year),
            ('report_type', '=', 'monthly')
        ], limit=1)

        # Nếu chưa có báo cáo tháng thì tạo mới (để tính toán sau)
        if not report:
            # Lấy số đầu kỳ (nếu có báo cáo tháng trước) hoặc lấy số km TRƯỚC khi cộng chuyến này
            report = self.env['fleet.vehicle.odometer'].create({
                'vehicle_id': self.assigned_vehicle_id.id,
                'month': trip_month,
                'year': trip_year,
                'report_type': 'monthly',
                'date': self.end_date.date(),
                'odometer_start': current_odometer  # Lưu tạm, hàm calculate sẽ tính lại chuẩn hơn
            })

        # Kích hoạt tính toán lại báo cáo tháng
        if hasattr(report, 'action_calculate_data'):
            report.action_calculate_data()

    def action_draft(self):
        self.state = 'draft'