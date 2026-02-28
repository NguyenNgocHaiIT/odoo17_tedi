# -*- coding: utf-8 -*-
from dateutil.utils import today
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from datetime import date
_logger = logging.getLogger(__name__) # Khai báo logger

class VehicleNoCarWizard(models.TransientModel):
    _name = 'vehicle.no.car.wizard'
    _description = 'Wizard báo hết xe'
    booking_option = fields.Selection([
        ('manager', 'Quản lý đặt xe bên ngoài'),
        ('unit', 'Đơn vị tự đặt xe bên ngoài')
    ], string="Phương án xử lý", required=True, default='manager')
    note = fields.Text(string="Ghi chú thêm")

    def action_confirm(self):
        self.ensure_one()
        active_id = self.env.context.get('active_id')
        if active_id:
            record = self.env['hr_tedi.vehicle.registration'].browse(active_id)

            # 1. Cập nhật thông tin
            record.write({
                'state': 'no_car',
                'external_booking_type': self.booking_option,
                'no_car_note': self.note
            })

            # 2. Ghi log chatter
            option_label = dict(self._fields['booking_option'].selection).get(self.booking_option)
            record.message_post(body=f"Báo hết xe. Phương án: {option_label}. Ghi chú: {self.note or 'Không'}")

            # 3. GỬI EMAIL CHO NGƯỜI TẠO PHIẾU (người đề nghị)
            try:
                # Lấy thông tin người đề nghị (người tạo phiếu)
                requester = record.requester_id
                if requester and (requester.work_email or requester.user_id.email or record.create_uid.email):
                    # Lấy email người nhận
                    email_to = requester.work_email or requester.user_id.email or record.create_uid.email
                    requester_name = requester.name or "Người đề nghị"

                    web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    detail_url = f"{web_url}/web#id={record.id}&model=hr_tedi.vehicle.registration"

                    option_label = dict(record._fields['external_booking_type'].selection).get(
                        record.external_booking_type)

                    subject = f"[BÁO HẾT XE] Phiếu xe {record.code}"

                    body_html = f"""
                    <div style="font-family: Arial, sans-serif; padding: 20px;">
                        <p>Xin chào <b>{requester_name}</b>,</p>

                        <div style="background:#ff980015; border-left: 4px solid #ff9800; padding: 15px; margin: 15px 0;">
                            <h3 style="color:#ff9800; margin-top:0;">THÔNG BÁO: HẾT XE</h3>
                            <p><b>Mã phiếu:</b> {record.code}</p>
                            <p><b>Phương án xử lý:</b> {option_label}</p>
                            <p><b>Ghi chú:</b> {record.no_car_note or 'Không có'}</p>
                            <p><b>Thời gian yêu cầu:</b> {record.start_date.strftime('%d/%m/%Y %H:%M') if record.start_date else ''}</p>
                            <p><b>Địa điểm:</b> {record.destination or 'Không có'}</p>
                            <p><b>Thời gian thông báo:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        </div>

                        <div style="background:#f8f9fa; padding: 15px; margin: 15px 0; border-radius: 5px;">
                            <h4 style="margin-top:0;">📋 Hướng dẫn xử lý:</h4>
                            <ul>
                                <li><b>Trường hợp Quản lý đặt xe:</b> Văn phòng/đội xe sẽ hỗ trợ đặt xe ngoài và thông báo lại</li>
                                <li><b>Trường hợp Đơn vị tự đặt:</b> Vui lòng tự liên hệ đặt xe ngoài theo quy định</li>
                                <li>Nếu có thắc mắc, vui lòng liên hệ bộ phận quản lý xe</li>
                            </ul>
                        </div>

                        <p style="text-align: center; margin: 20px 0;">
                            <a href="{detail_url}" style="background:#ff9800; color:white; padding: 10px 20px; text-decoration:none; border-radius:5px;">
                                Xem chi tiết phiếu
                            </a>
                        </p>

                        <p style="color:#666; font-size:14px;">
                            Trân trọng,<br>
                            <b>Đội ngũ quản lý xe</b>
                        </p>
                    </div>
                    """

                    # Gửi email trực tiếp
                    self.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'email_to': email_to,
                        'email_from': self.env.user.email or 'no-reply@company.com',
                        'body_html': body_html,
                    }).send()

                    _logger.info(f"Đã gửi email báo hết xe đến người tạo phiếu: {email_to}")

            except Exception as e:
                _logger.error(f"Lỗi gửi email báo hết xe: {str(e)}")

        return {'type': 'ir.actions.act_window_close'}


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

    request_date = fields.Date(string="Ngày tạo", default=fields.Date.context_today)

    requester_id = fields.Many2one(
        'hr.employee',
        string="Người đề nghị",
        default=lambda self: self.env.user.employee_id,
        required=True,
        tracking=True
        # Đã xóa readonly=True để có thể xử lý điều kiện bên XML
    )


    def _default_can_edit_requester(self):
        return self.env.user.has_group('fleet.fleet_group_manager')

    # 2. Thêm default vào field boolean
    can_edit_requester = fields.Boolean(
        compute='_compute_can_edit_requester',
        default=_default_can_edit_requester, # <--- QUAN TRỌNG: Thêm dòng này
        store=False
    )

    @api.depends_context('uid')
    def _compute_can_edit_requester(self):
        is_manager = self.env.user.has_group('fleet.fleet_group_manager')
        for rec in self:
            rec.can_edit_requester = is_manager

    is_manager_department = fields.Boolean(
        string="Is Manager Department",
        compute="_compute_is_manager_department",
        store=False
    )

    @api.depends('requester_id')
    def _compute_is_manager_department(self):
        for rec in self:
            rec.is_manager_department = False

            employee = rec.requester_id
            current_employee = self.env.user.employee_id
            if not current_employee:
                continue

            if not employee or not employee.department_id:
                continue

            # Leo lên phòng ban gốc (root department)
            dept = employee.department_id
            while dept.parent_id:
                dept = dept.parent_id

            # Lấy danh sách manager
            managers = dept.manager_ids if hasattr(dept, 'manager_ids') else self.env['hr.employee']

            if current_employee in managers:
                rec.is_manager_department = True



    start_date = fields.Datetime(string="Thời gian bắt đầu", required=True, tracking=True)
    end_date = fields.Datetime(string="Thời gian kết thúc", required=True, tracking=True)
    trip_type = fields.Selection([('noi_thanh', 'Nội thành'), ('ngoai_thanh', 'Ngoại thành')], string="Loại công tác",
                                 required=True, default='noi_thanh')
    destination = fields.Char(string="Địa điểm cụ thể", required=True, tracking=True)
    work_content = fields.Text(string="Nội dung công việc", required=True)
    num_passengers = fields.Integer(string="Số người đi kèm", default=1)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'vehicle_reg_attachment_rel',  # Tên relation
        'registration_id',
        'attachment_id',
        compute='_compute_attachment_ids',
        inverse='_inverse_attachment_ids',
        string='Tệp đính kèm'
    )

    def _compute_attachment_ids(self):
        """Luôn lấy attachments có res_model và res_id đúng"""
        for record in self:
            attachments = self.env['ir.attachment'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id),
            ])
            record.attachment_ids = attachments

    def _inverse_attachment_ids(self):
        """Khi thay đổi attachments, đảm bảo res_id đúng"""
        Attachment = self.env['ir.attachment'].sudo()

        for record in self:
            # Lấy tất cả attachment hiện tại của vehicle registration
            current_attachments = Attachment.search([
                ('res_model', '=', record._name),
                ('res_id', '=', record.id),
            ])

            # Attachment mới được thêm
            new_attachments = record.attachment_ids - current_attachments
            # Attachment bị xóa khỏi record này
            removed_attachments = current_attachments - record.attachment_ids

            # Gắn attachment mới
            if new_attachments:
                new_attachments.write({
                    'res_model': record._name,
                    'res_id': record.id,
                    'public': True,  # Thêm public=True để đảm bảo quyền
                })

            # Xử lý attachment bị xóa
            if removed_attachments:
                for att in removed_attachments:
                    # Kiểm tra xem attachment có còn được reference bởi record nào khác không
                    other_refs = Attachment.search_count([
                        ('id', '=', att.id),
                        ('res_model', '!=', False),
                        ('res_id', '!=', False),
                    ])

                    # Nếu không còn record nào reference, xóa attachment
                    if other_refs == 0:
                        att.write({
                            'res_model': False,
                            'res_id': False,
                        })

    assigned_vehicle_id = fields.Many2one(
        'fleet.vehicle', string="Phân công xe", tracking=True,
        domain="[('id', 'in', available_vehicle_ids)]"
    )
    available_vehicle_ids = fields.Many2many(
        'fleet.vehicle',
        compute='_compute_available_vehicles',
        store=False
    )

    tedi_driver_employee_id = fields.Many2one('hr.employee', string="Tài xế (Nhân viên)", tracking=True)
    driver_id = fields.Many2one('res.partner', string="Tài xế (Partner)", tracking=True)

    distance_km = fields.Float(string="Số km thực tế đi được", tracking=True)
    speedometer_km = fields.Float(string="Số km theo đồng hồ", tracking=True)

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

    external_booking_type = fields.Selection([
        ('manager', 'Quản lý đặt xe bên ngoài'),
        ('unit', 'Đơn vị tự đặt xe bên ngoài')
    ], string="Phương án khi hết xe", readonly=True)

    no_car_note = fields.Text(string="Ghi chú báo hết xe", readonly=True)

    calendar_title = fields.Char(
        string="Hiển thị trên lịch",
        compute='_compute_calendar_title'
    )

    @api.depends('state', 'code', 'assigned_vehicle_id', 'tedi_driver_employee_id', 'driver_id',
                 'external_booking_type')
    def _compute_calendar_title(self):
        for rec in self:
            # =========================================================
            # NHÓM 1: ĐÃ CÓ XE (Assigned, Waiting Return, Done)
            # =========================================================
            if rec.assigned_vehicle_id:
                # 1. Biển số (Ưu tiên số 1)
                plate = rec.assigned_vehicle_id.license_plate or 'Đang cập nhật'

                # 2. Hãng xe
                brand = rec.assigned_vehicle_id.model_id.brand_id.name or ''

                # 3. Tên lái xe (Lấy tên tắt cho ngắn gọn)
                # Ví dụ: "Nguyễn Văn A" -> hiển thị "A" hoặc giữ nguyên tùy ý
                driver_full_name = rec.tedi_driver_employee_id.name or rec.driver_id.name or 'Chưa có TX'

                # Tạo chuỗi: "30A-123.45 (Toyota - Tài xế A)"
                # Tôi đưa Biển số lên đầu vì trên Lịch nó quan trọng nhất để phân biệt
                detail_parts = [brand, driver_full_name]
                detail_str = " - ".join(filter(None, detail_parts))

                rec.calendar_title = f"{plate} ({detail_str})"

            # =========================================================
            # NHÓM 2: CÁC TRẠNG THÁI KHÁC (Chưa có xe / Hủy / ...)
            # =========================================================
            elif rec.state == 'no_car':
                # Hết xe: Hiển thị phương án xử lý (Tự đặt / VP đặt)
                # Lấy nhãn hiển thị của selection field thay vì key 'manager/unit'
                booking_label = dict(rec._fields['external_booking_type'].selection).get(
                    rec.external_booking_type) or 'Ngoài'
                rec.calendar_title = f"HẾT XE: {booking_label}"

            elif rec.state == 'approved':
                rec.calendar_title = "CHỜ XẾP XE"  # Đã duyệt, đang đợi văn phòng gán xe

            elif rec.state == 'submitted':
                rec.calendar_title = "CHỜ DUYỆT"  # Lãnh đạo chưa duyệt

            elif rec.state == 'draft':
                rec.calendar_title = "NHÁP"

            elif rec.state == 'refused':
                rec.calendar_title = "ĐÃ TỪ CHỐI"

            elif rec.state == 'cancel':
                rec.calendar_title = "ĐÃ HỦY"

            else:
                # Fallback cho các trường hợp lạ
                rec.calendar_title = "ĐANG XỬ LÝ"

    @api.depends('code', 'calendar_title')
    def _compute_display_name(self):
        for rec in self:
            # Format: [Mã phiếu] Thông tin xe
            # Ví dụ: [DX/2025/001] Toyota - 30A.12345 - Nguyễn Văn A
            if rec.calendar_title:
                rec.display_name = f" {rec.calendar_title} [{rec.code}]"
            else:
                rec.display_name = rec.code or "New"
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
        # current_employee = self.env.user.employee_id
        # if not current_employee: raise ValidationError("Tài khoản chưa liên kết hồ sơ Nhân viên.")
        # vals['requester_id'] = current_employee.id
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('hr_tedi.vehicle.registration') or 'New'
        if vals.get('tedi_driver_employee_id') and not vals.get('driver_id'):
            emp = self.env['hr.employee'].browse(vals['tedi_driver_employee_id'])
            partner = self._get_partner_from_employee(emp)
            if partner: vals['driver_id'] = partner.id
        record = super(HrTediVehicleRegistration, self).create(vals)
        if record.is_manager_department:
            record.state = 'approved'
        return record



    # ========================================================
    # 3. ACTIONS
    # ========================================================

    def action_submit(self):
        self.ensure_one()

        if self.start_date >= self.end_date:
            raise ValidationError("Thời gian kết thúc phải lớn hơn bắt đầu.")

        self.state = 'submitted'

        truong_phong = False
        pho_phongs = self.env['hr.employee']  # empty recordset

        # Lấy user tạo phiếu
        user_create = self.create_uid or self.env.user
        employee = self.env['hr.employee'].search(
            [('user_id', '=', user_create.id)],
            limit=1
        )

        if not employee or not employee.department_id:
            return

        # Leo lên phòng ban root
        dept = employee.department_id
        while dept.parent_id:
            dept = dept.parent_id

        # Lấy trưởng phòng
        if dept.manager_id:
            truong_phong = dept.manager_id

        # Nếu có field manager_ids (phó phòng - custom)
        if hasattr(dept, 'manager_ids'):
            pho_phongs = dept.manager_ids

        # =============================
        # Kiểm tra nếu người submit là lãnh đạo
        # =============================

        is_truong_phong = truong_phong and employee.id == truong_phong.id
        is_pho_phong = employee in pho_phongs

        if is_truong_phong or is_pho_phong:
           return

        else:
            self._send_notification_to_vehicle_managers_department(
                'submit',
                truong_phong,
                pho_phongs
            )

    def _send_notification_to_vehicle_managers_department(self, action_type,truong_phong,pho_phongs):
        """Gửi thông báo ngắn cho lãnh đạo đơn vị - 1 EMAIL NHIỀU NGƯỜI"""
        self.ensure_one()

        try:
            # Lấy lãnh đạo đơn vị
            if not truong_phong and not pho_phongs:
                return

            # Thu thập email của tất cả quản lý
            manager_emails = []
            manager_names = []
            # if truong_phong:
            #     manager_emails.append(truong_phong.email)
            #     manager_names.append(truong_phong.name)
            for user in pho_phongs:
                if user.work_email:
                    manager_emails.append(user.work_email )
                    manager_names.append(user.name)

            if not manager_emails:
                _logger.warning("Không có email nào trong lãnh đạo đơn vị.")
                return

            # Chuẩn bị nội dung email
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model=hr_tedi.vehicle.registration"

            approver = self.env.user.name
            email_to = ', '.join(manager_emails)
            names_str = ', '.join(manager_names)

            if action_type == 'submit':
                subject = f'[Cần duyệt] Phiếu xe {self.code}'
                message = "Có phiếu đăng ký xe mới cần duyệt"
                button_text = "Xem phiếu cần duyệt"
                status_color = "#007bff"
                status_title = "CẦN DUYỆT"
            else:  # feedback
                subject = f"[Xác nhận] Phiếu xe {self.code}"
                message = "Có lịch xe đã hoàn thành và đang chờ xác nhận."
                button_text = "Xem phiếu cần xác nhận"
                status_color = "#28a745"
                status_title = "CHỜ XÁC NHẬN"

            body_html = f"""
                   <div style="font-family: Arial, sans-serif; padding: 20px;">
                       <p>Kính gửi: {names_str},</p>
    
                       <div style="background:{status_color}15; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0;">
                           <h3 style="color:{status_color}; margin-top:0;">THÔNG BÁO: {status_title}</h3>
                           <p><b>Mã phiếu:</b> {self.code}</p>
                           <p><b>Người đề nghị:</b> {self.requester_id.name if self.requester_id else 'Không có'}</p>
                           <p><b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                           <p><b>Nội dung:</b> {message}</p>
                           <p><b>Địa điểm:</b> {self.destination or 'Không có'}</p>
                           <p><b>Nội dung công việc:</b> {self.work_content[:100]}...</p>
                       </div>
    
                       <p style="text-align: center; margin: 20px 0;">
                           <a href="{detail_url}" style="background:{status_color}; color:white; padding: 10px 20px; text-decoration:none; border-radius:5px;">
                               {button_text}
                           </a>
                       </p>
    
                       <p style="color:#666; font-size:14px;">
                           Trân trọng,<br>
                           <b>Lãnh đạo đơn vị</b>
                       </p>
                   </div>
                   """

            # Gửi 1 email cho tất cả quản lý
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': email_to,
                'email_from': self.env.user.email or 'no-reply@company.com',
                'body_html': body_html,
            }).send()

        except Exception as e:
                _logger.error(f"Lỗi gửi thông báo: {str(e)}")
    def _send_notification_to_vehicle_managers(self, action_type):
        """Gửi thông báo ngắn cho quản lý xe - 1 EMAIL NHIỀU NGƯỜI"""
        self.ensure_one()

        try:
            # Lấy nhóm quản lý xe
            group = self.env.ref('fleet.fleet_group_manager', raise_if_not_found=False)
            if not group or not group.users:
                return

            # Thu thập email của tất cả quản lý
            manager_emails = []
            manager_names = []
            for user in group.users:
                if user.email:
                    manager_emails.append(user.email)
                    manager_names.append(user.name)

            if not manager_emails:
                _logger.warning("Không có email nào trong nhóm quản lý xe.")
                return

            # Chuẩn bị nội dung email
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model=hr_tedi.vehicle.registration"

            approver = self.env.user.name
            email_to = ', '.join(manager_emails)
            names_str = ', '.join(manager_names)

            if action_type == 'submit':
                subject = f'[Cần duyệt] Phiếu xe {self.code}'
                message = "Có phiếu đăng ký xe mới cần duyệt"
                button_text = "Xem phiếu cần duyệt"
                status_color = "#007bff"
                status_title = "CẦN DUYỆT"
            else:  # feedback
                subject = f"[Xác nhận] Phiếu xe {self.code}"
                message = "Có lịch xe đã hoàn thành và đang chờ xác nhận."
                button_text = "Xem phiếu cần xác nhận"
                status_color = "#28a745"
                status_title = "CHỜ XÁC NHẬN"

            body_html = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <p>Kính gửi: {names_str},</p>

                <div style="background:{status_color}15; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0;">
                    <h3 style="color:{status_color}; margin-top:0;">THÔNG BÁO: {status_title}</h3>
                    <p><b>Mã phiếu:</b> {self.code}</p>
                    <p><b>Người đề nghị:</b> {self.requester_id.name if self.requester_id else 'Không có'}</p>
                    <p><b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                    <p><b>Nội dung:</b> {message}</p>
                    <p><b>Địa điểm:</b> {self.destination or 'Không có'}</p>
                    <p><b>Nội dung công việc:</b> {self.work_content[:100]}...</p>
                </div>

                <p style="text-align: center; margin: 20px 0;">
                    <a href="{detail_url}" style="background:{status_color}; color:white; padding: 10px 20px; text-decoration:none; border-radius:5px;">
                        {button_text}
                    </a>
                </p>

                <p style="color:#666; font-size:14px;">
                    Trân trọng,<br>
                    <b>Đội ngũ quản lý xe</b>
                </p>
            </div>
            """

            # Gửi 1 email cho tất cả quản lý
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': email_to,
                'email_from': self.env.user.email or 'no-reply@company.com',
                'body_html': body_html,
            }).send()

        except Exception as e:
            _logger.error(f"Lỗi gửi thông báo: {str(e)}")

    def action_fleet_approve(self):
        self.ensure_one()
        self.state = 'approved'
        self._send_email_to_creator('approve')

    def action_fleet_refuse(self):
        self.ensure_one()
        self.state = 'refused'
        self._send_email_to_creator('refuse')

    def action_manager_approve(self):
        self.ensure_one()
        self.state = 'approved'
        self._send_email_to_creator_by_manager('approve')

    def action_manager_refuse(self):
        self.ensure_one()
        self.state = 'refused'
        self._send_email_to_creator_by_manager('refuse')

    def _send_email_to_creator(self, action_type):
        """Gửi email cho người tạo phiếu khi duyệt/từ chối/phân xe"""
        self.ensure_one()

        try:
            # Lấy người tạo phiếu (create_uid)
            creator = self.create_uid
            if not creator or not creator.email:
                # Fallback: lấy từ requester_id nếu có
                creator_email = self.requester_id.work_email or self.requester_id.user_id.email
                creator_name = self.requester_id.name
            else:
                creator_email = creator.email
                creator_name = creator.name

            if not creator_email:
                _logger.warning(f"Không có email cho người tạo phiếu: {self.code}")
                return

            # Chuẩn bị nội dung
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model=hr_tedi.vehicle.registration"

            approver = self.env.user.name
            time_str = self.start_date.strftime('%d/%m/%Y %H:%M') if self.start_date else ''

            if action_type == 'approve':
                subject = f"[ĐÃ DUYỆT] Phiếu xe {self.code}"
                status_text = "ĐÃ ĐƯỢC DUYỆT"
                status_color = "#28a745"
                message = "Yêu cầu của bạn đã được duyệt và đang chờ xếp xe."
                button_text = "Xem phiếu đã duyệt"

                body_html = f"""
                <div style="font-family: Arial, sans-serif; padding: 20px;">
                    <p>Xin chào <b>{creator_name}</b>,</p>

                    <div style="background:{status_color}15; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0;">
                        <h3 style="color:{status_color}; margin-top:0;">Phiếu đăng ký xe của bạn {status_text}</h3>
                        <p><b>Mã phiếu:</b> {self.code}</p>
                        <p><b>Người xử lý:</b> {approver}</p>
                        <p><b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        <p><b>Nội dung:</b> {message}</p>
                    </div>

                    <p style="text-align: center; margin: 20px 0;">
                        <a href="{detail_url}" style="background:{status_color}; color:white; padding: 10px 20px; text-decoration:none; border-radius:5px;">
                            {button_text}
                        </a>
                    </p>

                    <p style="color:#666; font-size:14px;">
                        Trân trọng,<br>
                        <b>Đội ngũ quản lý xe</b>
                    </p>
                </div>
                """

            elif action_type == 'refuse':
                subject = f"[TỪ CHỐI] Phiếu xe {self.code}"
                status_text = "ĐÃ BỊ TỪ CHỐI"
                status_color = "#dc3545"
                message = "Yêu cầu của bạn không được chấp thuận."
                button_text = "Xem phiếu bị từ chối"

                body_html = f"""
                <div style="font-family: Arial, sans-serif; padding: 20px;">
                    <p>Xin chào <b>{creator_name}</b>,</p>

                    <div style="background:{status_color}15; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0;">
                        <h3 style="color:{status_color}; margin-top:0;">Phiếu đăng ký xe của bạn {status_text}</h3>
                        <p><b>Mã phiếu:</b> {self.code}</p>
                        <p><b>Người xử lý:</b> {approver}</p>
                        <p><b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        <p><b>Nội dung:</b> {message}</p>
                    </div>

                    <p style="text-align: center; margin: 20px 0;">
                        <a href="{detail_url}" style="background:{status_color}; color:white; padding: 10px 20px; text-decoration:none; border-radius:5px;">
                            {button_text}
                        </a>
                    </p>

                    <p style="color:#666; font-size:14px;">
                        Trân trọng,<br>
                        <b>Đội ngũ quản lý xe</b>
                    </p>
                </div>
                """

            elif action_type == 'assigned':
                subject = f"[ĐÃ PHÂN XE] Phiếu xe {self.code}"
                status_text = "ĐÃ ĐƯỢC PHÂN XE"
                status_color = "#007bff"
                vehicle_info = f"{self.assigned_vehicle_id.license_plate} - {self.assigned_vehicle_id.model_id.name if self.assigned_vehicle_id.model_id else ''}"
                driver_info = f"{self.tedi_driver_employee_id.name if self.tedi_driver_employee_id else self.driver_id.name or 'Đang cập nhật'}"
                button_text = "Xem thông tin chi tiết"

                body_html = f"""
                <div style="font-family: Arial, sans-serif; padding: 20px;">
                    <p>Xin chào <b>{creator_name}</b>,</p>

                    <div style="background:{status_color}15; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0;">
                        <h3 style="color:{status_color}; margin-top:0;">Phiếu đăng ký xe của bạn {status_text}</h3>
                        <p><b>Mã phiếu:</b> {self.code}</p>
                        <p><b>Thời gian sử dụng:</b> {time_str}</p>
                        <p><b>Thông tin xe:</b> {vehicle_info}</p>
                        <p><b>Tài xế:</b> {driver_info}</p>
                        <p><b>Liên hệ tài xế:</b> {self.driver_id.phone or self.tedi_driver_employee_id.work_phone or 'Đang cập nhật'}</p>
                        <p><b>Địa điểm:</b> {self.destination}</p>
                    </div>

                    <div style="background:#f8f9fa; padding: 15px; margin: 15px 0; border-radius: 5px;">
                        <h4 style="margin-top:0;">📋 Hướng dẫn sử dụng:</h4>
                        <ul>
                            <li>Vui lòng có mặt đúng giờ tại địa điểm đón xe</li>
                            <li>Giữ liên lạc với tài xế để phối hợp lịch trình</li>
                            <li>Sau khi hoàn thành chuyến đi, vui lòng đánh giá chất lượng dịch vụ</li>
                        </ul>
                    </div>

                    <p style="text-align: center; margin: 20px 0;">
                        <a href="{detail_url}" style="background:{status_color}; color:white; padding: 10px 20px; text-decoration:none; border-radius:5px;">
                            {button_text}
                        </a>
                    </p>

                    <p style="color:#666; font-size:14px;">
                        Trân trọng,<br>
                        <b>Đội ngũ quản lý xe</b>
                    </p>
                </div>
                """
            else:
                return

            # Gửi email
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': creator_email,
                'email_from': self.env.user.email or 'no-reply@company.com',
                'body_html': body_html,
            }).send()

            _logger.info(f"Đã gửi email {action_type} cho người tạo: {creator_email}")

        except Exception as e:
            _logger.error(f"Lỗi gửi email cho người tạo: {str(e)}")

    def _send_email_to_creator_by_manager(self, action_type):
        """Gửi email cho người tạo phiếu khi duyệt/từ chối/phân xe"""
        self.ensure_one()

        try:
            # Lấy người tạo phiếu (create_uid)
            creator = self.create_uid
            if not creator or not creator.email:
                # Fallback: lấy từ requester_id nếu có
                creator_email = self.requester_id.work_email or self.requester_id.user_id.email
                creator_name = self.requester_id.name
            else:
                creator_email = creator.email
                creator_name = creator.name

            if not creator_email:
                _logger.warning(f"Không có email cho người tạo phiếu: {self.code}")
                return

            # Chuẩn bị nội dung
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model=hr_tedi.vehicle.registration"

            approver = self.env.user.name
            time_str = self.start_date.strftime('%d/%m/%Y %H:%M') if self.start_date else ''

            if action_type == 'approve':
                subject = f"[ĐÃ DUYỆT] Phiếu xe {self.code}"
                status_text = "ĐÃ ĐƯỢC DUYỆT"
                status_color = "#28a745"
                message = "Yêu cầu của bạn đã được duyệt và đang chờ xếp xe."
                button_text = "Xem phiếu đã duyệt"

                body_html = f"""
                   <div style="font-family: Arial, sans-serif; padding: 20px;">
                       <p>Xin chào <b>{creator_name}</b>,</p>

                       <div style="background:{status_color}15; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0;">
                           <h3 style="color:{status_color}; margin-top:0;">Phiếu đăng ký xe của bạn {status_text}</h3>
                           <p><b>Mã phiếu:</b> {self.code}</p>
                           <p><b>Người xử lý:</b> {approver}</p>
                           <p><b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                           <p><b>Nội dung:</b> {message}</p>
                       </div>

                       <p style="text-align: center; margin: 20px 0;">
                           <a href="{detail_url}" style="background:{status_color}; color:white; padding: 10px 20px; text-decoration:none; border-radius:5px;">
                               {button_text}
                           </a>
                       </p>

                       <p style="color:#666; font-size:14px;">
                           Trân trọng,<br>
                           <b>Lãnh đạo đơn vị</b>
                       </p>
                   </div>
                   """

            elif action_type == 'refuse':
                subject = f"[TỪ CHỐI] Phiếu xe {self.code}"
                status_text = "ĐÃ BỊ TỪ CHỐI"
                status_color = "#dc3545"
                message = "Yêu cầu của bạn không được chấp thuận lãnh đạo đơn vị."
                button_text = "Xem phiếu bị từ chối"

                body_html = f"""
                   <div style="font-family: Arial, sans-serif; padding: 20px;">
                       <p>Xin chào <b>{creator_name}</b>,</p>

                       <div style="background:{status_color}15; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0;">
                           <h3 style="color:{status_color}; margin-top:0;">Phiếu đăng ký xe của bạn {status_text}</h3>
                           <p><b>Mã phiếu:</b> {self.code}</p>
                           <p><b>Người xử lý:</b> {approver}</p>
                           <p><b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                           <p><b>Nội dung:</b> {message}</p>
                       </div>

                       <p style="text-align: center; margin: 20px 0;">
                           <a href="{detail_url}" style="background:{status_color}; color:white; padding: 10px 20px; text-decoration:none; border-radius:5px;">
                               {button_text}
                           </a>
                       </p>

                       <p style="color:#666; font-size:14px;">
                           Trân trọng,<br>
                           <b>Lãnh đạo đơn vị</b>
                       </p>
                   </div>
                   """
            else:
                return

            # Gửi email
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': creator_email,
                'email_from': self.env.user.email or 'no-reply@company.com',
                'body_html': body_html,
            }).send()

            _logger.info(f"Đã gửi email {action_type} cho người tạo: {creator_email}")

        except Exception as e:
            _logger.error(f"Lỗi gửi email cho người tạo: {str(e)}")

    def action_office_assign(self):
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError("Phiếu chưa được duyệt.")
        if not self.assigned_vehicle_id:
            raise ValidationError("Chưa chọn xe.")

        # Kiểm tra trùng lịch
        domain = [
            ('id', '!=', self.id),
            ('assigned_vehicle_id', '=', self.assigned_vehicle_id.id),
            ('state', 'in', ['assigned', 'waiting_return']),
            ('start_date', '<', self.end_date),
            ('end_date', '>', self.start_date)
        ]
        if self.search(domain):
            raise ValidationError(f"Xe {self.assigned_vehicle_id.license_plate} bị trùng lịch!")

        # THÊM/ĐIỀU CHỈNH: Đồng bộ tài xế từ phiếu lên xe TRƯỚC khi gửi email
        # ----------------------------------------------------------------
        if self.tedi_driver_employee_id:
            # Cập nhật cả TEDI driver và partner driver lên xe
            driver_vals = {
                'tedi_driver_employee_id': self.tedi_driver_employee_id.id,
                'driver_id': self.driver_id.id if self.driver_id else False
            }
            self.assigned_vehicle_id.write(driver_vals)
        # ----------------------------------------------------------------

        # Gán tài xế từ xe nếu chưa có (fallback logic)
        if not self.tedi_driver_employee_id and hasattr(self.assigned_vehicle_id,
                                                        'tedi_driver_employee_id') and self.assigned_vehicle_id.tedi_driver_employee_id:
            self.tedi_driver_employee_id = self.assigned_vehicle_id.tedi_driver_employee_id
            self._onchange_tedi_driver_employee_id()

        # Cập nhật thông tin tài xế trên xe (đảm bảo lại)
        if self.assigned_vehicle_id:
            vals_update = {'driver_id': self.driver_id.id}
            if hasattr(self.assigned_vehicle_id, 'tedi_driver_employee_id'):
                vals_update['tedi_driver_employee_id'] = self.tedi_driver_employee_id.id
            self.assigned_vehicle_id.write(vals_update)

        # Cập nhật trạng thái
        self.state = 'assigned'

        # Gửi email cho người tạo phiếu
        # Gửi email cho tài xế
        self._send_email_to_driver_and_creator()

    def _send_email_to_driver_and_creator(self):
        """Gửi email cho cả tài xế VÀ người tạo phiếu khi phân công lái xe"""
        self.ensure_one()

        try:
            # KIỂM TRA XE ĐƯỢC PHÂN CÔNG
            if not self.assigned_vehicle_id:
                _logger.warning(f"Phiếu {self.code}: Không có xe được phân công, không gửi email")
                return

            # DANH SÁCH EMAIL SẼ GỬI
            emails_to_send = []  # (email, name, role)

            # 1. LẤY EMAIL TÀI XẾ (giữ nguyên logic cũ)
            driver_email = None
            driver_name = None

            if self.tedi_driver_employee_id and self.tedi_driver_employee_id.work_email:
                driver_email = self.tedi_driver_employee_id.work_email.strip()
                driver_name = self.tedi_driver_employee_id.name
            elif self.driver_id and self.driver_id.email:
                driver_email = self.driver_id.email.strip()
                driver_name = self.driver_id.name
            elif self.assigned_vehicle_id.tedi_driver_employee_id and self.assigned_vehicle_id.tedi_driver_employee_id.work_email:
                driver_email = self.assigned_vehicle_id.tedi_driver_employee_id.work_email.strip()
                driver_name = self.assigned_vehicle_id.tedi_driver_employee_id.name
            elif self.assigned_vehicle_id.driver_id and self.assigned_vehicle_id.driver_id.email:
                driver_email = self.assigned_vehicle_id.driver_id.email.strip()
                driver_name = self.assigned_vehicle_id.driver_id.name

            if driver_email:
                emails_to_send.append((driver_email, driver_name or 'Tài xế', 'Tài xế'))

            # 2. LẤY EMAIL NGƯỜI TẠO PHIẾU (người đề nghị)
            # Logic 1: Lấy từ create_uid (người bấm tạo phiếu)
            creator_email = None
            creator_name = None
            creator_role = "Người đề nghị"

            if self.create_uid and self.create_uid.email:
                creator_email = self.create_uid.email.strip()
                creator_name = self.create_uid.name

            # Logic 2: Fallback - lấy từ requester_id (nhân viên đề nghị)
            if not creator_email and self.requester_id:
                # Thử lấy work_email từ employee
                if hasattr(self.requester_id, 'work_email') and self.requester_id.work_email:
                    creator_email = self.requester_id.work_email.strip()
                    creator_name = self.requester_id.name

                # Thử lấy từ user của employee
                elif self.requester_id.user_id and self.requester_id.user_id.email:
                    creator_email = self.requester_id.user_id.email.strip()
                    creator_name = self.requester_id.name

            # Logic 3: Lấy email từ partner nếu có
            if not creator_email and self.requester_id and hasattr(self.requester_id, 'email'):
                creator_email = self.requester_id.email.strip()
                creator_name = self.requester_id.name

            # Thêm người tạo vào danh sách nếu có email và không trùng với tài xế
            if creator_email:
                # Kiểm tra không trùng với tài xế
                if not any(email == creator_email for email, _, _ in emails_to_send):
                    emails_to_send.append((creator_email, creator_name or 'Người đề nghị', creator_role))
                else:
                    _logger.info(f"Người tạo phiếu trùng với tài xế, không thêm trùng")

            # 3. KIỂM TRA CÓ NGƯỜI NHẬN
            if not emails_to_send:
                _logger.warning(f"Không có người nhận email nào cho phiếu {self.code}")
                return

            # 4. CHUẨN BỊ THÔNG TIN CHO EMAIL
            # Lấy số điện thoại người đề nghị
            requester_phone = None
            if self.requester_id:
                phone_fields = ['work_phone', 'mobile_phone', 'personal_mobile', 'phone', 'mobile']
                for field in phone_fields:
                    if hasattr(self.requester_id, field) and getattr(self.requester_id, field):
                        requester_phone = getattr(self.requester_id, field)
                        break

            phone_display = requester_phone or 'Đang cập nhật'

            # Thông tin web
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model=hr_tedi.vehicle.registration"

            # Thông tin xe và thời gian
            vehicle_info = f"{self.assigned_vehicle_id.license_plate} - {self.assigned_vehicle_id.model_id.name if self.assigned_vehicle_id.model_id else ''}"
            start_time = self.start_date.strftime('%d/%m/%Y %H:%M') if self.start_date else ''
            end_time = self.end_date.strftime('%d/%m/%Y %H:%M') if self.end_date else ''

            # Tên người đề nghị để hiển thị
            requester_display_name = creator_name or self.requester_id.name if self.requester_id else 'Người đề nghị'

            # 5. TẠO NỘI DUNG EMAIL
            subject = f"[PHÂN CÔNG LÁI XE] Phiếu xe {self.code}"

            # Tạo danh sách người nhận cho phần chào hỏi
            recipient_list = []
            for _, name, role in emails_to_send:
                if role == 'Tài xế':
                    recipient_list.append(f"{name} (tài xế)")
                else:
                    recipient_list.append(f"{name} (người đề nghị)")

            greeting_names = ", ".join(recipient_list)

            body_html = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                    THÔNG BÁO PHÂN CÔNG LÁI XE
                </h2>

                <p>Kính gửi: <b>{greeting_names}</b>,</p>

                <div style="background-color: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; margin: 20px 0;">
                    <h3 style="color: #2c3e50; margin-top: 0;">📋 Thông tin chi tiết</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; width: 40%;"><b>Mã phiếu:</b></td>
                            <td style="padding: 8px;"><span style="background: #e3f2fd; padding: 2px 8px; border-radius: 4px;">{self.code}</span></td>
                        </tr>
                        <tr>
                            <td style="padding: 8px;"><b>Người đề nghị:</b></td>
                            <td style="padding: 8px;">{requester_display_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px;"><b>Tài xế:</b></td>
                            <td style="padding: 8px;">{driver_name or 'Chưa xác định'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px;"><b>Xe được phân:</b></td>
                            <td style="padding: 8px;">{vehicle_info}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px;"><b>Thời gian:</b></td>
                            <td style="padding: 8px;">{start_time} → {end_time}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px;"><b>Địa điểm:</b></td>
                            <td style="padding: 8px;">{self.destination or 'Không có'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px;"><b>Số người:</b></td>
                            <td style="padding: 8px;">{self.num_passengers}</td>
                        </tr>
                    </table>
                </div>

                <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                    <h4 style="color: #856404; margin-top: 0;">⚠️ Lưu ý quan trọng</h4>
                    <ul style="color: #856404;">
                        <li>Tài xế vui lòng có mặt đúng giờ tại điểm đón</li>
                        <li>Kiểm tra xe trước khi xuất phát</li>
                        <li>Liên hệ người đề nghị: <b>{phone_display}</b></li>
                        <li>Tuân thủ quy định an toàn giao thông</li>
                        <li>Người đề nghị chuẩn bị đầy đủ giấy tờ cần thiết</li>
                    </ul>
                </div>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{detail_url}" 
                       style="background: linear-gradient(to right, #3498db, #2c3e50); 
                              color: white; 
                              padding: 12px 30px; 
                              text-decoration: none; 
                              border-radius: 5px; 
                              font-weight: bold;
                              display: inline-block;">
                        🔗 Xem chi tiết phiếu
                    </a>
                </div>

                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #7f8c8d; font-size: 12px;">
                    <p>
                        <i>Đây là email tự động từ hệ thống quản lý xe.<br>
                        Vui lòng không trả lời email này.</i>
                    </p>
                    <p>
                        📅 Ngày gửi: {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}
                    </p>
                </div>
            </div>
            """

            # 6. GỬI EMAIL - 1 EMAIL CHO TẤT CẢ NGƯỜI NHẬN
            # Tạo danh sách email_to cách nhau bằng dấu phẩy
            email_to_list = [email for email, _, _ in emails_to_send]
            email_to = ", ".join(email_to_list)

            mail = self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': email_to,
                'email_from': self.env.user.email or self.env.company.email or 'no-reply@company.com',
                'body_html': body_html,
                'reply_to': self.env.user.email or self.env.company.email or 'no-reply@company.com',
            })

            mail.send()

            _logger.info(f"Đã tạo và gửi email phân công lái xe đến tài xế: {driver_name} ({driver_email})")
            _logger.info(f"Mail ID: {mail.id}, State: {mail.state}")

            # Thêm thông báo vào chatter
            self.message_post(
                body=f"Đã gửi email thông báo phân công lái xe đến tài xế: {driver_name} ({driver_email})",
                subject="Thông báo cho tài xế"
            )

        except Exception as e:
            _logger.error(f"Lỗi gửi email cho tài xế: {str(e)}", exc_info=True)

    def action_send_feedback(self):
        """Bước 1: Người dùng đánh giá xong -> Chuyển sang chờ trả xe"""
        self.ensure_one()
        if self.rating == '0':
            raise ValidationError("Vui lòng chọn số sao để đánh giá chuyến đi.")

        self.state = 'waiting_return'
        rating_label = dict(self._fields['rating'].selection).get(self.rating)
        self._send_notification_to_vehicle_managers('feedback')

    def action_confirm_return(self):
        self.ensure_one()
        # 1. Check quyền
        if not self.env.user.has_group('fleet.fleet_group_user') and not self.env.user.has_group('base.group_system'):
            raise AccessError("Chỉ bộ phận Quản lý đội xe mới được xác nhận hoàn thành.")

        if self.distance_km <= 0:
            raise ValidationError("Vui lòng nhập 'Số km thực tế đi được' trước khi xác nhận.")

        # ==========================================================================
        # 2. TÍNH TOÁN SỐ LIỆU
        # ==========================================================================
        # Lấy số Odometer hiện tại trên hệ thống (coi như là số đầu của chuyến này)
        current_odometer = self.assigned_vehicle_id.odometer

        # Số Odometer mới (Sau khi cộng chuyến này)
        new_odometer_value = current_odometer + self.distance_km

        trip_month = self.end_date.month
        trip_year = self.end_date.year

        # ==========================================================================
        # 3. CẬP NHẬT BÁO CÁO THÁNG
        # ==========================================================================
        # Tìm báo cáo tháng hiện tại
        report = self.env['fleet.vehicle.odometer'].search([
            ('vehicle_id', '=', self.assigned_vehicle_id.id),
            ('month', '=', trip_month),
            ('year', '=', trip_year),
            ('report_type', '=', 'monthly')
        ], limit=1)

        if not report:
            # === TRƯỜNG HỢP 1: TẠO MỚI (Chưa có báo cáo tháng này) ===
            # Km chạy trong tháng = Chính là km của chuyến này
            km_total_month = self.distance_km

            # Số đầu kỳ của báo cáo = Số hiện tại (trước khi cộng chuyến này)
            # Lưu ý: Logic này đúng nếu đây là chuyến đầu tiên trong tháng được ghi nhận
            start_val = current_odometer

            report = self.env['fleet.vehicle.odometer'].create({
                'vehicle_id': self.assigned_vehicle_id.id,
                'month': trip_month,
                'year': trip_year,
                'report_type': 'monthly',
                'date': self.end_date.date(),
                'driver_id': self.driver_id.id,

                'odometer_start': start_val,  # Số đầu kỳ
                'value': new_odometer_value,  # Số cuối kỳ

                # --- SỬA TÊN TRƯỜNG KHỚP VỚI CODE BẠN GỬI ---
                'odometer_total': km_total_month,  # Tổng km hoạt động
            })
        else:
            # === TRƯỜNG HỢP 2: CẬP NHẬT (Đã có báo cáo) ===
            # Logic: Tổng km tháng = (Số cuối mới) - (Số đầu kỳ đã lưu)
            # Ta không cộng dồn thủ công mà lấy (Cuối - Đầu) cho chính xác tuyệt đối
            km_total_month = new_odometer_value - report.odometer_start

            report.write({
                'value': new_odometer_value,  # Cập nhật số cuối
                'odometer_total': km_total_month,  # Cập nhật tổng chạy
                'date': self.end_date.date(),  # Cập nhật ngày mới nhất
                'driver_id': self.driver_id.id
            })

        # Bước 4: Chuyển trạng thái phiếu về Done
        self.state = 'done'

        # Bước 5 (Tùy chọn): Gọi hàm tính toán lại của Odoo để đồng bộ hóa nếu cần
        # Hàm này trong model fleet.vehicle.odometer sẽ quét lại toàn bộ các phiếu 'done' để tính tổng
        # Việc gọi lại ở đây giúp đảm bảo số liệu chắc chắn khớp với danh sách phiếu
        if hasattr(report, 'action_calculate_data'):
            report.action_calculate_data()

        self.message_post(body=f"Xe về kho. Odoo mới: {new_odometer_value}. Tổng tháng: {km_total_month}.")

    def action_office_no_car(self):
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_user'):
            raise AccessError("Quyền hạn không hợp lệ.")

        # Mở Wizard thay vì đổi state ngay lập tức
        return {
            'name': 'Xác nhận báo hết xe',
            'type': 'ir.actions.act_window',
            'res_model': 'vehicle.no.car.wizard',
            'view_mode': 'form',
            'target': 'new',  # Quan trọng: Mở dạng Popup
            'context': {'active_id': self.id}  # Truyền ID phiếu sang Wizard
        }

    def action_draft(self):
        self.state = 'draft'

    @api.depends('start_date', 'end_date')
    def _compute_available_vehicles(self):
        for rec in self:
            if not rec.start_date or not rec.end_date:
                rec.available_vehicle_ids = self.env['fleet.vehicle']
                continue

            # 👉 ID thật (chỉ có khi record đã save)
            real_id = rec._origin.id

            domain = [
                ('assigned_vehicle_id', '!=', False),
                ('state', 'in', ['assigned', 'waiting_return']),
                ('start_date', '<', rec.end_date),
                ('end_date', '>', rec.start_date),
            ]

            # CHỈ thêm điều kiện loại trừ khi đã có id thật
            if real_id:
                domain.append(('id', '!=', real_id))

            conflict_regs = self.env['hr_tedi.vehicle.registration'].search(domain)

            conflict_vehicle_ids = conflict_regs.mapped('assigned_vehicle_id').ids

            vehicles = self.env['fleet.vehicle'].search([
                ('state_id.name', '=', 'Đã đăng kiểm'),
                ('id', 'not in', conflict_vehicle_ids)
            ])

            rec.available_vehicle_ids = vehicles

    def action_open_airline_expenses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Chi phí vé máy bay',
            'res_model': 'hr.expense',
            'view_mode': 'form',
            'views': [
                (self.env.ref('quan_ly_doi_xe.view_hr_expense_airlines_form').id, 'form')
            ],
            'target': 'current',
        }