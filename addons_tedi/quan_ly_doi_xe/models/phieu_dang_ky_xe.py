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
    # 1. CÁC TRƯỜNG DỮ LIỆU
    # ========================================================
    code = fields.Char(string="Mã phiếu", default="New", readonly=True)

    requester_id = fields.Many2one(
        'hr.employee',
        string="Người đề nghị",
        default=lambda self: self.env.user.employee_id,
        required=True, tracking=True, readonly=True
    )

    start_date = fields.Datetime(string="Thời gian bắt đầu", required=True, tracking=True)
    end_date = fields.Datetime(string="Thời gian kết thúc", required=True, tracking=True)
    trip_type = fields.Selection([('noi_thanh', 'Nội thành'), ('ngoai_thanh', 'Ngoại thành')], string="Loại công tác",
                                 required=True)
    destination = fields.Char(string="Địa điểm cụ thể", required=True, tracking=True)
    work_content = fields.Text(string="Nội dung công việc", required=True)
    num_passengers = fields.Integer(string="Số người đi kèm", default=1)
    attachment_ids = fields.Many2many('ir.attachment', string="Tệp đính kèm")

    assigned_vehicle_id = fields.Many2one(
        'fleet.vehicle', string="Phân công xe", tracking=True,
        domain="[('state_id.name', '=', 'Đã đăng kiểm')]"
    )
    tedi_driver_employee_id = fields.Many2one('hr.employee', string="Tài xế (Nhân viên)", tracking=True)
    driver_id = fields.Many2one('res.partner', string="Tài xế (Partner)", tracking=True)

    distance_km = fields.Float(string="Số km thực tế đi được", tracking=True)

    rating = fields.Selection([
        ('0', 'Chưa đánh giá'),
        ('1', 'Rất tệ'), ('2', 'Tệ'), ('3', 'Bình thường'), ('4', 'Tốt'), ('5', 'Tuyệt vời')
    ], string='Đánh giá sao', default='0', tracking=True)
    feedback_comment = fields.Text(string="Ý kiến đóng góp", tracking=True)

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Chờ duyệt'),
        ('approved', 'Chờ xếp xe'),
        ('refused', 'Từ chối'),
        ('assigned', 'Đã phân xe'),
        ('waiting_return', 'Chờ trả xe'),
        ('no_car', 'Hết xe'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    # ========================================================
    # 2. LOGIC TỰ ĐỘNG
    # ========================================================
    def _get_partner_from_employee(self, employee):
        if not employee: return False
        if employee.user_id and employee.user_id.partner_id: return employee.user_id.partner_id
        if getattr(employee, 'work_contact_id', False): return employee.work_contact_id
        if getattr(employee, 'address_home_id', False): return employee.address_home_id
        return False

    @api.onchange('tedi_driver_employee_id')
    def _onchange_tedi_driver_employee_id(self):
        self.driver_id = self._get_partner_from_employee(self.tedi_driver_employee_id)

    @api.onchange('assigned_vehicle_id')
    def _onchange_assigned_vehicle_id(self):
        if self.assigned_vehicle_id:
            if hasattr(self.assigned_vehicle_id,
                       'tedi_driver_employee_id') and self.assigned_vehicle_id.tedi_driver_employee_id:
                self.tedi_driver_employee_id = self.assigned_vehicle_id.tedi_driver_employee_id
                self._onchange_tedi_driver_employee_id()
            elif self.assigned_vehicle_id.driver_id:
                self.driver_id = self.assigned_vehicle_id.driver_id

    @api.model
    def create(self, vals):
        current_employee = self.env.user.employee_id
        if not current_employee: raise ValidationError("Tài khoản chưa liên kết hồ sơ Nhân viên.")
        vals['requester_id'] = current_employee.id
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('hr_tedi.vehicle.registration') or 'New'
        if vals.get('tedi_driver_employee_id') and not vals.get('driver_id'):
            emp = self.env['hr.employee'].browse(vals['tedi_driver_employee_id'])
            partner = self._get_partner_from_employee(emp)
            if partner: vals['driver_id'] = partner.id
        return super(HrTediVehicleRegistration, self).create(vals)

    # ========================================================
    # 3. ACTIONS
    # ========================================================

    def action_submit(self):
        self.ensure_one()
        if not self.start_date or not self.end_date: raise ValidationError("Nhập đủ thời gian.")
        if self.start_date >= self.end_date: raise ValidationError("Thời gian kết thúc phải lớn hơn bắt đầu.")
        self.state = 'submitted'
        self.message_post(body="Đã gửi yêu cầu.")

    def action_fleet_approve(self):
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_user') and not self.env.user.has_group('base.group_system'):
            raise AccessError("Quyền hạn không hợp lệ.")
        self.state = 'approved'
        self.message_post(body=f"Đã tiếp nhận bởi {self.env.user.name}.")

    def action_fleet_refuse(self):
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_user') and not self.env.user.has_group('base.group_system'):
            raise AccessError("Quyền hạn không hợp lệ.")
        self.state = 'refused'
        self.message_post(body=f"Từ chối bởi {self.env.user.name}.")

    def action_office_assign(self):
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_user') and not self.env.user.has_group(
                'base.group_system'):
            raise AccessError("Quyền hạn không hợp lệ.")
        if self.state != 'approved': raise ValidationError("Phiếu chưa được duyệt.")
        if not self.assigned_vehicle_id: raise ValidationError("Chưa chọn xe.")

        domain = [('id', '!=', self.id), ('assigned_vehicle_id', '=', self.assigned_vehicle_id.id),
                  ('state', 'in', ['assigned', 'waiting_return', 'done']),
                  ('start_date', '<', self.end_date), ('end_date', '>', self.start_date)]
        if self.search(domain):
            raise ValidationError(f"Xe {self.assigned_vehicle_id.license_plate} bị trùng lịch!")

        if not self.tedi_driver_employee_id and hasattr(self.assigned_vehicle_id,
                                                        'tedi_driver_employee_id') and self.assigned_vehicle_id.tedi_driver_employee_id:
            self.tedi_driver_employee_id = self.assigned_vehicle_id.tedi_driver_employee_id
            self._onchange_tedi_driver_employee_id()
        if not self.driver_id: raise ValidationError("Chưa có thông tin tài xế.")

        if self.assigned_vehicle_id:
            vals_update = {'driver_id': self.driver_id.id}
            if hasattr(self.assigned_vehicle_id, 'tedi_driver_employee_id'):
                vals_update['tedi_driver_employee_id'] = self.tedi_driver_employee_id.id
            self.assigned_vehicle_id.write(vals_update)

        self.state = 'assigned'
        self.message_post(body=f"Đã phân xe: {self.assigned_vehicle_id.license_plate}.")

    def action_send_feedback(self):
        """Bước 1: Người dùng đánh giá xong -> Chuyển sang chờ trả xe"""
        self.ensure_one()
        if self.rating == '0':
            raise ValidationError("Vui lòng chọn số sao để đánh giá chuyến đi.")

        self.state = 'waiting_return'
        rating_label = dict(self._fields['rating'].selection).get(self.rating)
        self.message_post(body=f"Người dùng đã đánh giá: {rating_label}. Đang chờ Văn phòng xác nhận xe về.")

    def action_confirm_return(self):
        """Bước 2: Admin xác nhận xe về -> Ghi nhận log & báo cáo -> Hoàn tất"""
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_user') and not self.env.user.has_group('base.group_system'):
            raise AccessError("Chỉ bộ phận Quản lý đội xe mới được xác nhận hoàn thành.")

        if self.distance_km <= 0:
            raise ValidationError("Vui lòng nhập 'Số km thực tế đi được' trước khi xác nhận.")

        # 1. Ghi Odometer Log
        current_odometer = self.assigned_vehicle_id.odometer
        new_odometer_value = current_odometer + self.distance_km

        self.env['fleet.vehicle.odometer'].create({
            'vehicle_id': self.assigned_vehicle_id.id,
            'value': new_odometer_value,
            'date': self.end_date.date(),
            'driver_id': self.driver_id.id,
            'unit': 'kilometers',
            'report_type': 'log'
        })

        # 2. LOGIC BÁO CÁO THÁNG (ĐÃ BỔ SUNG LẠI)
        trip_month = self.end_date.month
        trip_year = self.end_date.year
        # Tìm báo cáo tháng tồn tại
        report = self.env['fleet.vehicle.odometer'].search([
            ('vehicle_id', '=', self.assigned_vehicle_id.id),
            ('month', '=', trip_month),
            ('year', '=', trip_year),
            ('report_type', '=', 'monthly')
        ], limit=1)

        # Nếu chưa có thì tạo mới
        if not report:
            report = self.env['fleet.vehicle.odometer'].create({
                'vehicle_id': self.assigned_vehicle_id.id,
                'month': trip_month,
                'year': trip_year,
                'report_type': 'monthly',
                'date': self.end_date.date(),
                'odometer_start': current_odometer
            })

        # Gọi hàm tính toán lại dữ liệu (nếu module custom của bạn có hàm này)
        if hasattr(report, 'action_calculate_data'):
            report.action_calculate_data()

        # 3. Hoàn tất
        self.state = 'done'
        self.message_post(body=f"Xe đã về kho. KM thực tế: {self.distance_km}. Phiếu hoàn tất.")

    def action_office_no_car(self):
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_user'): raise AccessError("Quyền hạn không hợp lệ.")
        self.state = 'no_car'
        self.message_post(body="Văn phòng báo hết xe.")

    def action_draft(self):
        self.state = 'draft'