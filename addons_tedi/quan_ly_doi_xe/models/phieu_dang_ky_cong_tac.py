# -*- coding: utf-8 -*-
from dateutil.utils import today
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from datetime import date
_logger = logging.getLogger(__name__) # Khai báo logger

class HrTediVehicleRegistration(models.Model):
    _name = "business.trip.registration"
    _description = "Phiếu đăng ký công tác"
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
                                 required=True, default='ngoai_thanh')
    phuong_tien = fields.Selection([('oto', 'Ô tô'), ('may_bay', 'Máy bay'), ('phuongtienkhac', 'Phương tiện khác (tàu hỏa...)')], string="Phương tiện",
                                 required=True, default='oto')
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

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Chờ duyệt'),
        ('approved', 'đã duyệt'),
        ('refused', 'Từ chối'),
    ], string='Trạng thái', default='draft', tracking=True)

    calendar_title = fields.Char(
        string="Hiển thị trên lịch",
        compute='_compute_calendar_title'
    )

    @api.depends('state', 'code')
    def _compute_calendar_title(self):
        for rec in self:
            # =========================================================
            # NHÓM 1: ĐÃ CÓ XE (Assigned, Waiting Return, Done)
            # =========================================================
            if rec.state == 'no_car':
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



    @api.model
    def create(self, vals):
        # current_employee = self.env.user.employee_id
        # if not current_employee: raise ValidationError("Tài khoản chưa liên kết hồ sơ Nhân viên.")
        # vals['requester_id'] = current_employee.id
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('business.trip.registration') or 'New'
        if vals.get('tedi_driver_employee_id') and not vals.get('driver_id'):
            emp = self.env['hr.employee'].browse(vals['tedi_driver_employee_id'])
            partner = self._get_partner_from_employee(emp)
            if partner: vals['driver_id'] = partner.id
        record = super(HrTediVehicleRegistration, self).create(vals)
        if record.is_manager_department:
            record.state = 'approved'
            lichxe = record.create_lich_xe()
            if record.phuong_tien == 'oto':
             record._send_email_to_creator_by_manager('approve', lichxe)
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
            detail_url = f"{web_url}/web#id={self.id}&model=business.trip.registration"

            approver = self.env.user.name
            email_to = ', '.join(manager_emails)
            names_str = ', '.join(manager_names)

            if action_type == 'submit':
                subject = f'[Cần duyệt] Phiếu đăng ký công tác {self.code}'
                message = "Có phiếu đăng ký công tác mới cần duyệt"
                button_text = "Xem phiếu cần duyệt"
                status_color = "#007bff"
                status_title = "CẦN DUYỆT"
            else:  # feedback
                subject = f"[Xác nhận] Phiếu đăng ký công tác {self.code}"
                message = "Phiếu đăng ký công tác"
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


    def action_manager_approve(self):
        self.ensure_one()
        self.state = 'approved'
        lichxe = self.create_lich_xe()
        if self.phuong_tien == 'oto':
         self._send_email_to_creator_by_manager('approve', lichxe)


    def action_manager_refuse(self):
        self.ensure_one()
        self.state = 'refused'
        self._send_email_to_creator_by_manager('refuse')

    def _send_email_to_creator_by_manager(self, action_type,lichxe=False):
        """Gửi email cho người tạo phiếu khi duyệt/từ chối/phân xe"""
        self.ensure_one()

        try:
            id = 0
            if lichxe:
                id = lichxe.id

            # Lấy người tạo phiếu (create_uid)
            creator = self.create_uid
            if not creator or not creator.email:
                # Fallback: lấy từ requester_id nếu có
                creator_email = self.requester_id.work_email
                creator_name = self.requester_id.name
            else:
                creator_email = creator.email
                creator_name = creator.name

            if not creator_email:
                _logger.warning(f"Không có email cho người tạo phiếu: {self.code}")
                return
            group = self.env.ref('fleet.fleet_group_manager', raise_if_not_found=False)
            if not group or not group.users:
                return

            # Thu thập email của tất cả quản lý
            manager_emails = []
            manager_names = []
            manager_emails.append(creator_email)
            for user in group.users:
                if user.email:
                    manager_emails.append(user.email)
                    manager_names.append(user.name)

            if not manager_emails:
                _logger.warning("Không có email nào trong nhóm quản lý xe.")
                return

            email_to = ', '.join(manager_emails)

            # Chuẩn bị nội dung
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={id}&model=hr_tedi.vehicle.registration"

            approver = self.env.user.name
            time_str = self.start_date.strftime('%d/%m/%Y %H:%M') if self.start_date else ''

            if action_type == 'approve':
                subject = f"[ĐÃ DUYỆT] Phiếu đăng ký công tác {self.code}"
                status_text = "ĐÃ ĐƯỢC DUYỆT"
                status_color = "#28a745"
                message = "Yêu cầu của bạn đã được duyệt và đang chờ xếp xe."
                button_text = "Xem phiếu phiếu xe"

                body_html = f"""
                   <div style="font-family: Arial, sans-serif; padding: 20px;">
                       <p>Xin chào <b>{creator_name}</b>,</p>

                       <div style="background:{status_color}15; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0;">
                           <h3 style="color:{status_color}; margin-top:0;">Phiếu đăng ký công tác của bạn {status_text}</h3>
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
                           <b>Lãnh đạo đơn vị, quản lý đội xe</b>
                       </p>
                   </div>
                   """

            elif action_type == 'refuse':
                subject = f"[TỪ CHỐI] Phiếu đăng ký công tác {self.code}"
                status_text = "ĐÃ BỊ TỪ CHỐI"
                status_color = "#dc3545"
                message = "Yêu cầu của bạn không được chấp thuận lãnh đạo đơn vị."
                button_text = "Xem phiếu bị từ chối"

                body_html = f"""
                   <div style="font-family: Arial, sans-serif; padding: 20px;">
                       <p>Xin chào <b>{creator_name}</b>,</p>

                       <div style="background:{status_color}15; border-left: 4px solid {status_color}; padding: 15px; margin: 15px 0;">
                           <h3 style="color:{status_color}; margin-top:0;">Phiếu đăng ký công tác của bạn {status_text}</h3>
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
                'email_to': email_to,
                'email_from': self.env.user.email or 'no-reply@company.com',
                'body_html': body_html,
            }).send()

            _logger.info(f"Đã gửi email {action_type} cho người tạo và quản lý đội xe: {email_to}")

        except Exception as e:
            _logger.error(f"Lỗi gửi email cho người tạo: {str(e)}")

    def action_draft(self):
        self.state = 'draft'

    def create_lich_xe(self):
        self.ensure_one()

        code = self.env['ir.sequence'].next_by_code(
            'hr_tedi.vehicle.registration'
        ) or 'New'

        lichxe = self.env['hr_tedi.vehicle.registration'].create({
            'code': code,
            'state': 'approved',
            'start_date': self.start_date,
            'end_date': self.end_date,
            'trip_type': self.trip_type,
            'destination': self.destination,
            'work_content': self.work_content,
            'num_passengers': self.num_passengers,
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
            'requester_id': self.requester_id.id,
            'request_date': self.request_date,
        })

        return lichxe