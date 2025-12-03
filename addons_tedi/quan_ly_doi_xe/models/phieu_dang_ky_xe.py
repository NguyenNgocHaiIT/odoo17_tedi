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
    assigned_vehicle_id = fields.Many2one('fleet.vehicle', string="Phân công xe", tracking=True)

    # [NEW] Trường Tài xế - Tự động lấy từ xe nhưng cho phép sửa đổi nếu đổi tài
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
    # 2. LOGIC TỰ ĐỘNG (COMPUTE & DEFAULT & ONCHANGE)
    # ========================================================

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('hr_tedi.vehicle.registration') or 'New'
        return super(HrTediVehicleRegistration, self).create(vals)

    # [NEW] Logic: Khi chọn xe -> Tự điền tài xế
    @api.onchange('assigned_vehicle_id')
    def _onchange_assigned_vehicle_id(self):
        if self.assigned_vehicle_id and self.assigned_vehicle_id.driver_id:
            self.driver_id = self.assigned_vehicle_id.driver_id

    # ========================================================
    # 3. QUY TRÌNH XỬ LÝ (BUTTON ACTIONS)
    # ========================================================

    # ---------------------------------------------------------
    # BƯỚC 1: Gửi yêu cầu
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # BƯỚC 2: Lãnh đạo duyệt
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # BƯỚC 3: Văn phòng xếp xe
    # ---------------------------------------------------------
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

        # [Update] Nếu lúc bấm nút mà driver_id chưa có (do import hoặc code), fill luôn
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

    # ---------------------------------------------------------
    # BƯỚC 4: Hoàn thành chuyến đi
    # ---------------------------------------------------------
    def action_done(self):
        self.ensure_one()

        if self.distance_km <= 0:
            raise ValidationError("Vui lòng nhập số KM thực tế (phải lớn hơn 0).")
        if not self.assigned_vehicle_id:
            raise ValidationError("Chưa có xe được phân công.")

        self.state = 'done'

        # 2. Tạo bản ghi Odometer "Log"
        current_odometer = self.assigned_vehicle_id.odometer
        new_odometer_value = current_odometer + self.distance_km

        # [Update] Lấy tài xế từ phiếu đăng ký (self.driver_id)
        # Nếu phiếu ko có tài xế -> lấy tài xế của xe -> lấy người đề nghị
        driver_log = self.driver_id.id or self.assigned_vehicle_id.driver_id.id or self.requester_id.user_id.partner_id.id

        self.env['fleet.vehicle.odometer'].create({
            'vehicle_id': self.assigned_vehicle_id.id,
            'value': new_odometer_value,
            'date': self.end_date.date(),
            'driver_id': driver_log,
            'unit': 'kilometers',
            'report_type': 'log'
        })

        # 3. Cập nhật/Tạo Báo cáo tháng
        trip_month = self.end_date.month
        trip_year = self.end_date.year

        report = self.env['fleet.vehicle.odometer'].search([
            ('vehicle_id', '=', self.assigned_vehicle_id.id),
            ('month', '=', trip_month),
            ('year', '=', trip_year),
            ('report_type', '=', 'monthly')
        ], limit=1)

        if not report:
            report = self.env['fleet.vehicle.odometer'].create({
                'vehicle_id': self.assigned_vehicle_id.id,
                'month': trip_month,
                'year': trip_year,
                'report_type': 'monthly',
                'date': self.end_date.date(),
                'odometer_start': current_odometer
            })

        if hasattr(report, 'action_calculate_data'):
            report.action_calculate_data()

    def action_draft(self):
        self.state = 'draft'