# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError


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
        'hr.employee',
        string="Người đề nghị",
        default=lambda self: self.env.user.employee_id,
        required=True,
        tracking=True,
        readonly=True  # <--- THÊM DÒNG NÀY: Khóa không cho sửa trên giao diện
    )

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

    # --- LOGIC TÀI XẾ MỚI (ĐỒNG BỘ VỚI FLEET) ---
    # 1. Field chọn trên giao diện (Nhân viên)
    tedi_driver_employee_id = fields.Many2one(
        'hr.employee',
        string="Tài xế (Nhân viên)",
        help="Chọn nhân viên lái xe.",
        tracking=True
    )

    # 2. Field kỹ thuật (Partner) - Bắt buộc để chạy logic Odoo gốc
    # Field này sẽ được tự động điền khi chọn Nhân viên ở trên
    driver_id = fields.Many2one(
        'res.partner',
        string="Tài xế (Partner)",
        tracking=True,
        help="Trường kỹ thuật lưu thông tin Partner của tài xế"
    )

    # --- Kết quả thực tế (Nhập khi hoàn thành) ---
    distance_km = fields.Float(string="Số km thực tế đi được")

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
    # 2. LOGIC TỰ ĐỘNG & HELPER
    # ========================================================

    def _get_partner_from_employee(self, employee):
        """Hàm lấy Partner từ Employee an toàn"""
        if not employee:
            return False
        # Ưu tiên 1: User
        if employee.user_id and employee.user_id.partner_id:
            return employee.user_id.partner_id
        # Ưu tiên 2: Work Contact (Odoo 17)
        if getattr(employee, 'work_contact_id', False):
            return employee.work_contact_id
        # Ưu tiên 3: Address Home (Dùng getattr để tránh lỗi)
        if getattr(employee, 'address_home_id', False):
            return employee.address_home_id
        return False

    @api.onchange('tedi_driver_employee_id')
    def _onchange_tedi_driver_employee_id(self):
        """Khi chọn Nhân viên -> Tự điền Partner"""
        self.driver_id = self._get_partner_from_employee(self.tedi_driver_employee_id)

    @api.onchange('assigned_vehicle_id')
    def _onchange_assigned_vehicle_id(self):
        """Khi chọn xe -> Lấy tài xế mặc định của xe đó (ưu tiên Nhân viên)"""
        if self.assigned_vehicle_id:
            # Nếu xe đã có cấu hình Nhân viên lái xe (field mới bên Fleet)
            if hasattr(self.assigned_vehicle_id,
                       'tedi_driver_employee_id') and self.assigned_vehicle_id.tedi_driver_employee_id:
                self.tedi_driver_employee_id = self.assigned_vehicle_id.tedi_driver_employee_id
                self._onchange_tedi_driver_employee_id()  # Trigger sync sang Partner

            # Fallback: Nếu xe chỉ có driver_id (Partner) cũ
            elif self.assigned_vehicle_id.driver_id:
                self.driver_id = self.assigned_vehicle_id.driver_id
                # Không điền ngược lại tedi_driver_employee_id vì 1 partner có thể ko có employee

    @api.model
    def create(self, vals):
        # --- LOGIC MỚI: BẮT BUỘC NGƯỜI YÊU CẦU LÀ NGƯỜI TẠO ---
        # Lấy hồ sơ nhân viên của user đang thao tác
        current_employee = self.env.user.employee_id

        if not current_employee:
            raise ValidationError("Tài khoản của bạn chưa được liên kết với hồ sơ Nhân viên nên không thể tạo phiếu.")

        # Gán đè requester_id bằng nhân viên hiện tại (bất chấp dữ liệu gửi lên là gì)
        vals['requester_id'] = current_employee.id
        # ------------------------------------------------------

        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('hr_tedi.vehicle.registration') or 'New'

        # Logic tự điền driver_id nếu người dùng tạo qua code/import
        if vals.get('tedi_driver_employee_id') and not vals.get('driver_id'):
            emp = self.env['hr.employee'].browse(vals['tedi_driver_employee_id'])
            partner = self._get_partner_from_employee(emp)
            if partner:
                vals['driver_id'] = partner.id

        return super(HrTediVehicleRegistration, self).create(vals)

    # ========================================================
    # 3. QUY TRÌNH XỬ LÝ (BUTTON ACTIONS)
    # ========================================================

    def action_submit(self):
        self.ensure_one()
        if not self.start_date or not self.end_date:
            raise ValidationError("Vui lòng nhập đầy đủ thời gian đi và về.")
        if self.start_date >= self.end_date:
            raise ValidationError("Thời gian kết thúc phải lớn hơn thời gian bắt đầu.")

        # --- LOGIC MỚI: XỬ LÝ NGƯỜI KHÔNG CÓ SẾP (PARENT_ID) ---

        # 1. Trường hợp chuẩn: Có người quản lý
        if self.requester_id.parent_id:
            self.state = 'submitted'

        # 2. Trường hợp đặc biệt: Không có người quản lý
        else:
            # Kiểm tra xem người dùng hiện tại có quyền Admin hoặc Quản lý đội xe không
            # (Dùng group 'base.group_system' cho Admin và 'fleet.fleet_group_manager' cho Quản lý xe)
            is_vip = self.env.user.has_group('base.group_system') or \
                     self.env.user.has_group('fleet.fleet_group_manager')

            if is_vip:
                # Nếu là Admin/Quản lý -> Tự động DUYỆT luôn (Bỏ qua bước chờ sếp)
                # Chuyển thẳng sang trạng thái chờ Văn phòng xếp xe
                self.state = 'approved'
                self.message_post(body="Hệ thống tự động duyệt (Người dùng là Admin/Quản lý hoặc không có cấp trên).")
            else:
                # Nếu là nhân viên thường mà quên cấu hình sếp -> Vẫn cho phép Submit (theo yêu cầu)
                # Trạng thái giữ là 'submitted' -> Admin/Quản lý xe sẽ phải vào duyệt thay
                self.state = 'submitted'
                self.message_post(body="Đã gửi yêu cầu (Lưu ý: Nhân viên này chưa được cấu hình Người quản lý).")

    def action_manager_approve(self):
        self.ensure_one()
        current_user = self.env.user
        manager_user = self.requester_id.parent_id.user_id
        if current_user != manager_user and not current_user.has_group('base.group_system'):
            raise AccessError(f"Chỉ quản lý trực tiếp ({self.requester_id.parent_id.name}) mới được duyệt.")
        self.state = 'approved'
        self.message_post(body=f"Lãnh đạo ({current_user.name}) đã duyệt.")

    def action_manager_refuse(self):
        self.ensure_one()
        # ... (Logic check quyền giữ nguyên)
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
            raise ValidationError("Phiếu chưa được duyệt!")
        if not self.assigned_vehicle_id:
            raise ValidationError("Vui lòng chọn 'Xe phân công'.")

        # 1. Check trùng lịch
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
                f"Xe {self.assigned_vehicle_id.license_plate} bị trùng lịch với phiếu {duplicate[0].code}!"
            )

        # 2. Xử lý logic điền tài xế nếu trống
        if not self.tedi_driver_employee_id and hasattr(self.assigned_vehicle_id,
                                                        'tedi_driver_employee_id') and self.assigned_vehicle_id.tedi_driver_employee_id:
            self.tedi_driver_employee_id = self.assigned_vehicle_id.tedi_driver_employee_id
            self._onchange_tedi_driver_employee_id()  # Sync Partner

        # Check kỹ thuật: Phải có driver_id (Partner)
        if not self.driver_id:
            raise ValidationError(
                "Không xác định được Tài xế (Partner). Vui lòng chọn Tài xế (Nhân viên) hoặc kiểm tra hồ sơ nhân viên.")

        # 3. CẬP NHẬT NGƯỢC LẠI XE (SYNC)
        # Cập nhật để xe biết ai đang giữ chìa khóa
        if self.assigned_vehicle_id:
            vals_update = {}
            # Cập nhật field Nhân viên bên xe (nếu field tồn tại)
            if hasattr(self.assigned_vehicle_id, 'tedi_driver_employee_id'):
                vals_update['tedi_driver_employee_id'] = self.tedi_driver_employee_id.id

            # Cập nhật field Partner bên xe
            vals_update['driver_id'] = self.driver_id.id

            if vals_update:
                self.assigned_vehicle_id.write(vals_update)

        self.state = 'assigned'
        driver_name = self.tedi_driver_employee_id.name or self.driver_id.name
        self.message_post(body=f"Đã bố trí xe: {self.assigned_vehicle_id.license_plate}. Tài xế: {driver_name}")

    def action_office_no_car(self):
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_manager') and not self.env.user.has_group(
                'base.group_system'):
            raise AccessError("Quyền hạn không hợp lệ.")
        self.state = 'no_car'
        self.message_post(body="Văn phòng báo hết xe.")

    def action_done(self):
        self.ensure_one()
        if self.distance_km <= 0:
            raise ValidationError("Vui lòng nhập số KM thực tế > 0.")

        self.state = 'done'

        # Tính toán
        current_odometer = self.assigned_vehicle_id.odometer
        new_odometer_value = current_odometer + self.distance_km

        # Log Odometer (Dùng driver_id là Partner)
        self.env['fleet.vehicle.odometer'].create({
            'vehicle_id': self.assigned_vehicle_id.id,
            'value': new_odometer_value,
            'date': self.end_date.date(),
            'driver_id': self.driver_id.id,  # Quan trọng: Phải là ID Partner
            'unit': 'kilometers',
            'report_type': 'log'
        })

        # Logic báo cáo tháng (Giữ nguyên logic cũ của bạn)
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