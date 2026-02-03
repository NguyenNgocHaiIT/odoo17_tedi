from email.policy import default

from odoo import api, models, fields
from odoo.exceptions import UserError
from datetime import timedelta
import logging



# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class Calendar(models.Model):
    _inherit = 'calendar.event'

    # --- 1. CÁC TRƯỜNG DỮ LIỆU ---
    lanh_dao = fields.Many2many(
        "hr.employee",
        'calendar_lanh_dao_rel',
        'calendar_event_id','employee_id',
        string="Lãnh đạo"
    )
    don_vi = fields.Many2many(
        "hr.department",
        'calendar_don_vi_tham_gia_rel',
        'calendar_event_id', 'department_id',
        string='Đơn vị tham gia'
    )

    # State mới có thêm 'pending'
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã duyệt lịch'),
        ('completed', 'Đã hoàn thành'),
        ('canceled', 'Đã hủy')
    ], string='Trạng thái', default='draft', tracking=True)

    room_sign = fields.Selection([
        ('no_sign', 'Chưa đăng ký'),
        ('pending', 'Chờ duyệt phòng'),
        ('have_sign', 'Đã duyệt phòng')
    ], string="Trạng thái phòng", default='no_sign', tracking=True)

    room_materials = fields.Many2many(
        'room.materials',
        'calendar_room_materials_rel',
        'calendar_event_id', 'room_materials_id',
        string='Thông tin khác'
    )

    chu_tri = fields.Many2one("hr.employee", string="Người chủ trì")
    room = fields.Many2one('room.room', string='Phòng')
    calendar_label = fields.Char(string="Nhãn trên calendar", compute="_compute_calendar_label")
    color = fields.Integer(string='Màu', default=0)
    start_stop = fields.Char(string="Thời gian", compute="_compute_start_stop")
    date_only = fields.Date(string="Ngày", compute='_compute_date_only', store=True)

    employee_ids = fields.Many2many(
        'hr.employee',
        'calendar_event_employee_rel',
        'event_id', 'employee_id',
        string='Người tham gia',
        # default=lambda self: self._get_default_employees(),
    )

    # --- Fields phân quyền ---
    can_approve_meeting = fields.Boolean(compute="_compute_permissions")
    can_approve_room = fields.Boolean(compute="_compute_permissions")

    is_current_user_creator = fields.Boolean(
        compute='_compute_is_current_user_creator',
        string='Is Current User Creator',
        default=True,
        store=False
    )
    loai_cuoc_hop = fields.Selection([
        ('online', 'Họp online'),
        ('offline', 'Họp offline'),
    ], string='Loại cuộc họp', default='offline')

    link_cuoc_hop = fields.Char(string="link cuộc họp")
    so_nguoi_tham_gia = fields.Integer(string="Số người tham gia")

    # Thêm field này
    reminder_sent = fields.Boolean(
        string='Đã gửi nhắc nhở',
        default=False,
        help='Đánh dấu đã gửi thông báo nhắc nhở trước 30 phút'
    )

    can_complete_meeting = fields.Boolean(
        string="Có thể hoàn thành",
        compute="_compute_can_complete_meeting",
        store=False
    )

    @api.depends_context('uid')
    @api.depends('create_uid', 'state')
    def _compute_can_complete_meeting(self):
        """Tính toán xem user hiện tại có thể hoàn thành cuộc họp không"""
        current_user = self.env.user
        is_room_manager = current_user.has_group('Quan_ly_lich_hop.group_meeting_room_manager')

        for rec in self:
            # Người tạo HOẶC quản lý phòng
            rec.can_complete_meeting = rec.state == 'approved' and (
                    is_room_manager or rec.is_current_user_creator
            )

    @api.depends_context('uid')
    def _compute_is_current_user_creator(self):
        current_user = self.env.user
        for rec in self:
            # Xử lý trường hợp đang tạo mới (chưa có ID)
            if not rec.id:
                # Khi đang tạo mới, mặc định cho phép chỉnh sửa
                rec.is_current_user_creator = True
            elif rec.create_uid:
                rec.is_current_user_creator = rec.create_uid.id == current_user.id
            else:
                rec.is_current_user_creator = False

    # --- 2. LOGIC PHÂN QUYỀN (ĐÃ SỬA) ---
    @api.depends_context('uid')
    @api.depends('create_uid', 'room_sign', 'state')
    def _compute_permissions(self):
        current_user = self.env.user

        # ID của Group
        group_dept_manager = 'Quan_ly_lich_hop.group_calendar_department_manager'
        group_room_manager = 'Quan_ly_lich_hop.group_meeting_room_manager'

        is_admin = current_user.has_group('base.group_system')
        is_dept_manager = current_user.has_group(group_dept_manager)
        is_room_manager = current_user.has_group(group_room_manager)

        # Lấy phòng ban hiện tại của user đang login
        current_employee = self.env['hr.employee'].search([('user_id', '=', current_user.id)], limit=1)
        current_dept = current_employee.department_id if current_employee else False

        for rec in self:
            # --- A. DUYỆT LỊCH HỌP ---
            can_meeting = False

            # Tìm phòng ban người tạo phiếu
            creator_employee = self.env['hr.employee'].search([('user_id', '=', rec.create_uid.id)], limit=1)
            creator_dept = creator_employee.department_id if creator_employee else False

            # SỬA: Thêm "or is_room_manager" vào điều kiện cao nhất
            # xét đến cấp Quản lý đơn vị (check cùng phòng ban)
            if is_dept_manager:
                if current_dept and creator_dept and current_dept.id == creator_dept.id:
                    can_meeting = True

            rec.can_approve_meeting = can_meeting

            # --- B. DUYỆT PHÒNG (Giữ nguyên) ---
            can_room = False
            if (is_admin or is_room_manager) and rec.room_sign == 'pending':
                can_room = True
            rec.can_approve_room = can_room

    # --- 3. CÁC HÀM COMPUTE & DEFAULT KHÁC ---
    def _get_default_chu_tri(self):
        if self.env.user.employee_ids:
            return self.env.user.employee_ids[0].id
        return False

    @api.depends('start')
    def _compute_date_only(self):
        for rec in self:
            rec.date_only = rec.start.date() if rec.start else False

    @api.depends('start', 'stop')
    def _compute_start_stop(self):
        for rec in self:
            if rec.start and rec.stop:
                rec.start_stop = f"{rec.start.strftime('%H:%M')} → {rec.stop.strftime('%H:%M')}"
            else:
                rec.start_stop = ""

    def _get_default_employees(self):
        participant_ids = []
        if self.env.user.employee_ids:
            participant_ids.append(self.env.user.employee_ids[0].id)
        return participant_ids

    @api.depends('start', 'name')
    def _compute_calendar_label(self):
        for event in self:
            time_str = event.start.strftime("%H:%M") if event.start else ""
            event.calendar_label = f"{time_str} - {event.name or ''}"

    # --- 4. CRUD OVERRIDES ---
    @api.model
    def create(self, vals):

        self._check_room_conflict(vals)

        record = super().create(vals)
        record.color = record.id % 12
        return record

    def _send_notification_to_dept_managers(self, action_type="created"):
        """
        Gửi thông báo cho trưởng các đơn vị tham gia cuộc họp

        :param action_type: "created" (tạo mới) hoặc "updated" (cập nhật)
        """
        # Lấy danh sách các trưởng đơn vị tham gia
        manager_employees = self.env['hr.employee']
        for dept in self.don_vi:
            if dept.manager_id:
                manager_employees |= dept.manager_id

        if not manager_employees:
            return

        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        creator_name = self.create_uid.name if self.create_uid else "Người tạo"

        # Tạo nội dung thông báo
        action_text = "được tạo mới" if action_type == "created" else "được cập nhật"
        time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""

        for manager in manager_employees:
            if not manager.user_id:
                continue

            # 1. Popup notification
            self.env['bus.bus']._sendone(
                manager.user_id.partner_id,
                'simple_notification',
                {
                    'title': f"📅 Lịch họp {action_text}",
                    'message': f"Đơn vị của bạn có lịch họp mới: {self.name}",
                    'sticky': True,  # Hiển thị lâu hơn
                    'type': 'info',
                }
            )

            # 2. Chatter notification trên chính lịch họp
            manager_message = f"📋 Đã thông báo cho trưởng đơn vị: {manager.name}"
            self.message_post(
                body=manager_message,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )

            # 3. Gửi email (tùy chọn)
            if manager.work_email:
                subject = f"Thông báo lịch họp {action_text}: {self.name}"
                event_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"
                body_html = f"""
                    <p>Kính gửi <b>{manager.name}</b>,</p>
                    <p>Đơn vị <b>{manager.department_id.name if manager.department_id else ''}</b> của Quý Anh/Chị có lịch họp {action_text}.</p>
                    <p><b>Thông tin cuộc họp:</b></p>
                    <ul>
                        <li><b>Chủ đề:</b> {self.name}</li>
                        <li><b>Thời gian:</b> {time_str}</li>
                        <li><b>Người tạo:</b> {creator_name}</li>
                        <li><b>Trạng thái:</b> {dict(self._fields['state'].selection).get(self.state)}</li>
                    </ul>
                    <p><a href="{event_url}" style="background:#28a745;color:white;padding:8px 16px;border-radius:4px;text-decoration:none;font-weight:bold;">
                        📋 Xem chi tiết lịch họp
                    </a></p>
                    <p>Trân trọng,<br/>Hệ thống Quản lý Lịch họp</p>
                """

                try:
                    self.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'body_html': body_html,
                        'email_to': manager.work_email,
                        'email_from': self.env.user.email or self.env.company.email,
                    }).send()
                    _logger.info(f"Đã gửi email thông báo tới trưởng đơn vị: {manager.name} ({manager.work_email})")
                except Exception as e:
                    _logger.error(f"Lỗi gửi email cho trưởng đơn vị {manager.name}: {str(e)}")


    def write(self, vals):
        old_states = {rec.id: rec.state for rec in self}

        for rec in self:
            check_vals = {
                'room': vals.get('room', rec.room.id),
                'start': vals.get('start', rec.start),
                'stop': vals.get('stop', rec.stop),
            }

            self._check_room_conflict(
                check_vals,
                exclude_ids=[rec.id]
            )

        result = super().write(vals)

        # Gửi thông báo khi có thay đổi quan trọng
        for rec in self:
            # Nếu thay đổi thời gian hoặc đơn vị tham gia
            if any(field in vals for field in ['start', 'stop', 'don_vi']):
                rec._send_notification_to_dept_managers("updated")

        return result

    def action_request_room_approval(self):
        """Gửi yêu cầu duyệt phòng đến quản lý phòng"""
        self.ensure_one()

        # Kiểm tra điều kiện
        if not self.room:
            raise UserError("Vui lòng chọn phòng họp trước khi gửi duyệt.")

        if self.room_sign == 'pending':
            raise UserError("Yêu cầu duyệt phòng đã được gửi trước đó.")

        # Cập nhật trạng thái
        self.write({'room_sign': 'pending'})

        # Gửi thông báo đến quản lý phòng
        self._send_room_approval_request()

        # Ghi log
        self.message_post(body=f"📤 Đã gửi yêu cầu duyệt phòng '{self.room.name}' đến Quản lý phòng.")

        return True

    def _send_room_approval_request(self):
        """Gửi email yêu cầu duyệt phòng đến quản lý phòng"""
        try:
            # Lấy nhóm quản lý phòng
            group = self.env.ref('Quan_ly_lich_hop.group_meeting_room_manager', raise_if_not_found=False)

            if not group or not group.users:
                _logger.warning("Không tìm thấy nhóm Quản lý phòng họp")
                return

            # Thu thập email của tất cả quản lý phòng
            manager_emails = []
            manager_names = []

            for user in group.users:
                if user.email:
                    manager_emails.append(user.email)
                    manager_names.append(user.name)

            if not manager_emails:
                _logger.warning("Không có email nào trong nhóm quản lý phòng")
                return

            # Chuẩn bị nội dung email
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"

            creator_name = self.create_uid.name if self.create_uid else "Người tạo"
            time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""

            # Tạo danh sách người nhận
            email_to = ', '.join(manager_emails)
            names_str = ', '.join(manager_names)

            subject = f"[CẦN DUYỆT PHÒNG] Lịch họp: {self.name}"

            body_html = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="border-left:4px solid #f39c12;padding-left:15px;background:#fff8e1; margin-bottom: 20px;">
                    <h3 style="color:#d35400; margin-top:0;">⚠️ YÊU CẦU DUYỆT PHÒNG HỌP</h3>
                </div>

                <p>Kính gửi: {names_str},</p>
                <p>Nhân viên <b>{creator_name}</b> vừa gửi yêu cầu duyệt phòng họp.</p>

                <p><b>Thông tin yêu cầu cần duyệt:</b></p>
                <table style="border-collapse:collapse;width:100%; margin-bottom: 20px;">
                    <tr style="background:#f8f9fa;">
                        <td style="border:1px solid #ddd;padding:8px; width:30%;"><b>Chủ đề họp</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">{self.name}</td>
                    </tr>
                    <tr>
                        <td style="border:1px solid #ddd;padding:8px;"><b>Thời gian</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">{time_str}</td>
                    </tr>
                    <tr style="background:#f8f9fa;">
                        <td style="border:1px solid #ddd;padding:8px;"><b>Phòng yêu cầu</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">
                            <strong style="color:#2980b9;">{self.room.name if self.room else ''}</strong>
                        </td>
                    </tr>
                    <tr>
                        <td style="border:1px solid #ddd;padding:8px;"><b>Người tạo</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">{creator_name}</td>
                    </tr>
                    <tr style="background:#f8f9fa;">
                        <td style="border:1px solid #ddd;padding:8px;"><b>Đơn vị tham gia</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">
                            {', '.join(dept.name for dept in self.don_vi) if self.don_vi else 'Không có'}
                        </td>
                    </tr>
                    <tr>
                        <td style="border:1px solid #ddd;padding:8px;"><b>Số người tham gia</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">{self.so_nguoi_tham_gia or '0'}</td>
                    </tr>
                    <tr style="background:#f8f9fa;">
                        <td style="border:1px solid #ddd;padding:8px;"><b>Loại cuộc họp</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">
                            {'Họp online' if self.loai_cuoc_hop == 'online' else 'Họp offline'}
                        </td>
                    </tr>
                </table>

                <div style="background:#e8f4fd; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <p><b>📋 Hướng dẫn xử lý:</b></p>
                    <ul>
                        <li>Kiểm tra phòng họp có sẵn sàng không</li>
                        <li>Kiểm tra thiết bị trong phòng (nếu có yêu cầu)</li>
                        <li>Duyệt hoặc từ chối yêu cầu này</li>
                        <li>Thời gian xử lý đề xuất: Trong vòng 2 giờ</li>
                    </ul>
                </div>

                <p style="text-align: center; margin: 20px 0;">
                    <a href="{detail_url}" 
                       style="background:#3498db;color:white;padding:10px 20px;border-radius:5px;
                              text-decoration:none;font-weight:bold;display:inline-block;">
                        Xem & Duyệt phòng ngay
                    </a>
                </p>

                <p style="color:#7f8c8d;font-size:12px;margin-top:20px;">
                    <i>Vui lòng duyệt hoặc từ chối yêu cầu này trong vòng 2 giờ làm việc.</i>
                </p>
            </div>
            """

            # Gửi 1 email cho tất cả quản lý phòng
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': email_to,
                'email_from': self.env.user.email or self.env.company.email,
                'body_html': body_html,
            }).send()

            _logger.info(f"Đã gửi email yêu cầu duyệt phòng đến {len(manager_emails)} quản lý phòng")

            # Gửi popup notification cho từng quản lý
            for user in group.users:
                if user.partner_id:
                    self.env['bus.bus']._sendone(
                        user.partner_id,
                        'simple_notification',
                        {
                            'title': '⚠️ Yêu cầu duyệt phòng họp',
                            'message': f"Có yêu cầu duyệt phòng: {self.room.name if self.room else ''}",
                            'sticky': True,
                            'type': 'warning',
                        }
                    )

        except Exception as e:
            _logger.error(f"Lỗi gửi email yêu cầu duyệt phòng: {str(e)}")
            raise UserError(f"Có lỗi khi gửi yêu cầu: {str(e)}")

    def action_send_request(self):
        """Nhân viên gửi duyệt - Gửi thông báo đặc biệt cho trưởng đơn vị"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("Chỉ có thể gửi duyệt phiếu ở trạng thái Nháp.")

        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        creator_name = self.create_uid.name if self.create_uid else "Người tạo"
        time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/Y')}" if self.start and self.stop else ""

        # Lấy danh sách trưởng đơn vị
        current_user = self.env.user
        user_employee = self.env['hr.employee'].search([('user_id', '=', current_user.id)], limit=1)
        manager_employees = self.env['hr.employee']

        if user_employee and user_employee.department_id and user_employee.department_id.manager_id:
            manager_employees |= user_employee.department_id.manager_id

        # GỬI EMAIL NHÓM CHO TẤT CẢ TRƯỞNG ĐƠN VỊ
        if manager_employees:
            try:
                # Thu thập email
                email_list = []
                name_list = []

                for manager in manager_employees:
                    if manager.work_email:
                        email_list.append(manager.work_email)
                        name_list.append(manager.name)

                if email_list:
                    # Tạo danh sách người nhận
                    email_to = ', '.join(email_list)
                    names_str = ', '.join(name_list)

                    subject = f"[CẦN PHÊ DUYỆT] Lịch họp: {self.name}"
                    event_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"

                    body_html = f"""
                    <div style="font-family: Arial, sans-serif; padding: 20px;">
                        <div style="border-left:4px solid #f39c12;padding-left:15px;background:#fff8e1; margin-bottom: 20px;">
                            <h3 style="color:#d35400; margin-top:0;">⚠️ YÊU CẦU PHÊ DUYỆT LỊCH HỌP</h3>
                        </div>

                        <p>Kính gửi: {names_str},</p>
                        <p>Nhân viên <b>{creator_name}</b> vừa gửi yêu cầu phê duyệt lịch họp cho đơn vị của Quý Anh/Chị.</p>

                        <p><b>Thông tin cuộc họp cần duyệt:</b></p>
                        <table style="border-collapse:collapse;width:100%; margin-bottom: 20px;">
                            <tr style="background:#f8f9fa;">
                                <td style="border:1px solid #ddd;padding:8px; width:30%;"><b>Chủ đề</b></td>
                                <td style="border:1px solid #ddd;padding:8px;">{self.name}</td>
                            </tr>
                            <tr>
                                <td style="border:1px solid #ddd;padding:8px;"><b>Thời gian</b></td>
                                <td style="border:1px solid #ddd;padding:8px;">{time_str}</td>
                            </tr>
                            <tr style="background:#f8f9fa;">
                                <td style="border:1px solid #ddd;padding:8px;"><b>Người chủ trì</b></td>
                                <td style="border:1px solid #ddd;padding:8px;">{self.chu_tri.name if self.chu_tri else ''}</td>
                            </tr>
                            <tr>
                                <td style="border:1px solid #ddd;padding:8px;"><b>Đơn vị tham gia</b></td>
                                <td style="border:1px solid #ddd;padding:8px;">
                                    {', '.join(dept.name for dept in self.don_vi) if self.don_vi else ''}
                                </td>
                            </tr>
                            <tr style="background:#f8f9fa;">
                                <td style="border:1px solid #ddd;padding:8px;"><b>Người tạo</b></td>
                                <td style="border:1px solid #ddd;padding:8px;">{creator_name}</td>
                            </tr>
                        </table>

                        <div style="background:#e8f4fd; padding: 15px; border-radius: 5px; margin: 15px 0;">
                            <p><b>📋 Hướng dẫn:</b></p>
                            <ul>
                                <li>Vui lòng xem xét và phê duyệt lịch họp này</li>
                                <li>Có thể từ chối nếu lịch họp không phù hợp</li>
                                <li>Thời gian xử lý đề xuất: Trong vòng 24 giờ</li>
                            </ul>
                        </div>

                        <p style="text-align: center; margin: 20px 0;">
                            <a href="{event_url}" 
                               style="background:#3498db;color:white;padding:10px 20px;border-radius:5px;
                                      text-decoration:none;font-weight:bold;display:inline-block;">
                                Xem & Phê duyệt ngay
                            </a>
                        </p>

                        <p style="color:#7f8c8d;font-size:12px;margin-top:20px;">
                            <i>Vui lòng phê duyệt hoặc từ chối lịch họp này trong vòng 24 giờ.</i>
                        </p>
                    </div>
                    """

                    # Gửi 1 email cho tất cả trưởng đơn vị
                    self.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'email_to': email_to,
                        'email_from': self.env.user.email or self.env.company.email,
                        'body_html': body_html,
                    }).send()

                    _logger.info(f"Đã gửi email yêu cầu phê duyệt đến {len(email_list)} trưởng đơn vị")

            except Exception as e:
                _logger.error(f"Lỗi gửi email yêu cầu phê duyệt: {str(e)}")

        # Gửi popup cho từng trưởng đơn vị (giữ nguyên)
        for manager in manager_employees:
            if not manager.user_id:
                continue

            self.env['bus.bus']._sendone(
                manager.user_id.partner_id,
                'simple_notification',
                {
                    'title': '⚠️ Lịch họp cần phê duyệt',
                    'message': f"Có lịch họp chờ phê duyệt: {self.name}",
                    'sticky': True,
                    'type': 'warning',
                }
            )

        self.write({'state': 'pending'})

    # --- 5. BUTTON ACTIONS ---
    def action_complete(self):
        """
        Chuyển trạng thái sang Hoàn thành.
        - Cho phép: Quản lý phòng họp HOẶC Người tạo phiếu (create_uid).
        - Nếu kết thúc sớm: Cập nhật lại thời gian kết thúc thực tế để giải phóng phòng (tùy chọn).
        """
        self.ensure_one()

        # 1. Check quyền: Là quản lý HOẶC là người tạo ra phiếu này
        is_manager = self.env.user.has_group('Quan_ly_lich_hop.group_meeting_room_manager')


        if not (is_manager):
            raise UserError("Bạn không có quyền xác nhận hoàn thành (Chỉ Người đăng ký hoặc Quản lý).")

        # 2. Xử lý logic
        vals = {'state': 'completed'}

        if self.reminder_sent:
            vals['reminder_sent'] = False

        # (Tùy chọn) Nếu muốn giải phóng phòng ngay lập tức trên Calendar khi kết thúc sớm:
        # Nếu thời gian hiện tại < thời gian kết thúc dự kiến -> cập nhật stop = hiện tại
        if fields.Datetime.now() < self.stop:
            vals['stop'] = fields.Datetime.now()

        self.write(vals)

    @api.model
    def _cron_auto_complete_meetings(self):
        """
        Hàm được gọi bởi Cron job.
        Tìm các cuộc họp đang 'approved' mà thời gian kết thúc < hiện tại -> chuyển 'completed'.
        """
        now = fields.Datetime.now()
        # Tìm các bản ghi: Trạng thái Approved VÀ Thời gian kết thúc đã qua
        expired_meetings = self.search([
            ('state', '=', 'approved'),
            ('stop', '<', now)
        ])

        if expired_meetings:
            _logger.info(f"Cron Job: Auto completing {len(expired_meetings)} meetings.")
            expired_meetings.write({'state': 'completed'})

    def action_cancel(self):
        """Hủy phiếu"""
        self.write({'state': 'canceled'})

    def approve(self):
        """Quản lý duyệt: Gửi thông báo và đổi trạng thái"""
        self.ensure_one()
        if not self.can_approve_meeting:
            raise UserError("Bạn không có quyền duyệt nội dung lịch họp này (Khác phòng ban hoặc thiếu quyền).")

        odoobot = self.env.ref('base.user_root')
        odoobot_employee = self.env['hr.employee'].search([('user_id', '=', odoobot.id)], limit=1)
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # 1. Đánh dấu đã duyệt
        self.write({'state': 'approved'})

        # 2. Lấy danh sách cần thông báo
        all_recipients = self.env['hr.employee']  # ✅ TẠO DANH SÁCH TẤT CẢ NGƯỜI NHẬN

        # Thêm tất cả người tham gia vào danh sách
        if self.employee_ids:
            all_recipients |= self.employee_ids
        if self.lanh_dao:
            all_recipients |= self.lanh_dao

        # ✅ THÊM: Người tạo phiếu (nếu có employee record)
        creator_employee = self.env['hr.employee'].search([('user_id', '=', self.create_uid.id)], limit=1)
        if creator_employee:
            all_recipients |= creator_employee

        # ✅ THÊM: Trưởng đơn vị tham gia
        for dept in self.don_vi:
            if dept.manager_id:
                all_recipients |= dept.manager_id

        # Loại bỏ trùng lặp và chỉ lấy những người có email
        all_recipients = all_recipients.filtered(lambda emp: emp.work_email)

        # --- GỬI EMAIL NHÓM CHO TẤT CẢ NGƯỜI LIÊN QUAN ---
        if all_recipients:
            try:
                # Thu thập thông tin người nhận
                email_list = []
                name_list = []

                for employee in all_recipients:
                    email = employee.work_email
                    if email and email not in email_list:
                        email_list.append(email)
                        name_list.append(employee.name)

                if email_list:
                    # Tạo danh sách người nhận (tất cả trong 1 email)
                    email_to = ', '.join(email_list)
                    names_str = ', '.join(name_list)

                    # Thông tin cuộc họp
                    time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""
                    event_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"
                    approver_name = self.env.user.name

                    subject = f"[THÔNG BÁO MỜI HỌP] {self.name}"

                    # Tạo HTML email chuyên nghiệp
                    body_html = f"""
                    <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto;">
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; color: white; text-align: center;">
                            <h1 style="margin: 0; font-size: 28px;">📅 LỊCH HỌP MỚI</h1>
                            <p style="font-size: 18px; margin-top: 10px;">{self.name}</p>
                        </div>

                        <div style="padding: 30px; border: 1px solid #e0e0e0; border-radius: 0 0 10px 10px; background: white;">
                            <p>Kính gửi: <b>{names_str}</b>,</p>
                            <p>Bạn/Đơn vị của bạn được mời tham dự cuộc họp quan trọng sau:</p>

                            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                                <h3 style="color: #2c3e50; margin-top: 0;">📋 THÔNG TIN CUỘC HỌP</h3>
                                <table style="width: 100%; border-collapse: collapse;">
                                    <tr>
                                        <td style="padding: 10px; width: 30%; font-weight: bold;">Chủ đề:</td>
                                        <td style="padding: 10px;">{self.name}</td>
                                    </tr>
                                    <tr style="background: #f0f0f0;">
                                        <td style="padding: 10px; font-weight: bold;">Thời gian:</td>
                                        <td style="padding: 10px;">{time_str}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px; font-weight: bold;">Người chủ trì:</td>
                                        <td style="padding: 10px;">{self.chu_tri.name if self.chu_tri else 'Chưa xác định'}</td>
                                    </tr>
                                    <tr style="background: #f0f0f0;">
                                        <td style="padding: 10px; font-weight: bold;">Đơn vị tham gia:</td>
                                        <td style="padding: 10px;">
                                            {', '.join(dept.name for dept in self.don_vi) if self.don_vi else 'Chưa xác định'}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px; font-weight: bold;">Người tạo:</td>
                                        <td style="padding: 10px;">{creator_employee.name if creator_employee else self.create_uid.name}</td>
                                    </tr>
                                    <tr style="background: #f0f0f0;">
                                        <td style="padding: 10px; font-weight: bold;">Người duyệt:</td>
                                        <td style="padding: 10px; color: #27ae60;">{approver_name}</td>
                                    </tr>
                                </table>
                            </div>

                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{event_url}" 
                                   style="background: #3498db; color: white; padding: 15px 30px; 
                                          text-decoration: none; border-radius: 5px; font-weight: bold; 
                                          font-size: 16px; display: inline-block;">
                                    📅 XEM CHI TIẾT & XÁC NHẬN THAM DỰ
                                </a>
                            </div>

                            <div style="background: #e8f6ef; padding: 15px; border-radius: 5px; border-left: 4px solid #27ae60;">
                                <p style="margin: 0; color: #27ae60; font-weight: bold;">
                                    ✅ Lịch họp đã được phê duyệt và sẵn sàng
                                </p>
                            </div>

                            <hr style="border: none; border-top: 2px solid #eee; margin: 30px 0;">

                            <p style="color: #7f8c8d; font-size: 12px; text-align: center;">
                                Đây là email tự động từ Hệ thống Quản lý Lịch họp.<br>
                                Vui lòng không trả lời email này.
                            </p>
                        </div>
                    </div>
                    """

                    # Gửi 1 email cho tất cả người liên quan
                    self.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'body_html': body_html,
                        'email_to': email_to,
                        'email_from': self.env.user.email or self.env.company.email,
                    }).send()

                    _logger.info(f"✅ Đã gửi email thông báo mời họp đến {len(email_list)} người liên quan")

            except Exception as e:
                _logger.error(f"Lỗi gửi email mời họp nhóm: {str(e)}")

        # Gửi popup notification (giữ nguyên)
        for employee in all_recipients:
            if not employee.user_id:
                continue

            # Popup với nội dung khác nhau
            if employee.id == creator_employee.id:
                # Thông báo đặc biệt cho người tạo
                self.env['bus.bus']._sendone(
                    employee.user_id.partner_id,
                    'simple_notification',
                    {
                        'title': '✅ Lịch họp đã được duyệt',
                        'message': f"Lịch họp '{self.name}' của bạn đã được phê duyệt",
                        'sticky': True,
                        'type': 'success',
                    }
                )
            else:
                # Thông báo thông thường cho người khác
                self.env['bus.bus']._sendone(
                    employee.user_id.partner_id,
                    'simple_notification',
                    {
                        'title': '📅 Lời mời họp mới',
                        'message': f"Bạn/Đơn vị được mời tham dự: {self.name}",
                        'sticky': False,
                        'type': 'info',
                    }
                )

        return True

    def action_approve_room(self):
        """Duyệt phòng họp và gửi thông báo cho người tạo"""
        self.ensure_one()
        if not self.can_approve_room:
            raise UserError("Bạn không có quyền duyệt phòng họp.")

        # Duyệt phòng
        self.write({'room_sign': 'have_sign'})

        # ✅ THÊM: Gửi thông báo cho người tạo
        self._send_room_approval_notification(approved=True)

        # Chatter message
        self.message_post(body="✅ Phòng họp đã được duyệt!", message_type='notification')

    def action_reject_room(self):
        """Từ chối phòng họp và gửi thông báo cho người tạo"""
        self.ensure_one()
        if not self.can_approve_room:
            raise UserError("Bạn không có quyền từ chối phòng họp.")

        # Từ chối phòng
        self.write({'room_sign': 'no_sign', 'room': False})

        # ✅ THÊM: Gửi thông báo cho người tạo
        self._send_room_approval_notification(approved=False)

        # Chatter message
        self.message_post(body="❌ Yêu cầu phòng họp đã bị từ chối.", message_type='notification')

    def _send_room_approval_notification(self, approved=True):
        """
        Gửi thông báo duyệt/từ chối phòng cho người tạo VÀ tất cả người liên quan

        :param approved: True nếu duyệt, False nếu từ chối
        """
        # 1. LẤY DANH SÁCH TẤT CẢ NGƯỜI NHẬN THÔNG BÁO
        all_recipients = self.env['hr.employee']

        # a) Người tạo phiếu
        creator_employee = self.env['hr.employee'].search([('user_id', '=', self.create_uid.id)], limit=1)
        if creator_employee:
            all_recipients |= creator_employee

        # b) Người chủ trì
        if self.chu_tri:
            all_recipients |= self.chu_tri

        # c) Lãnh đạo
        if self.lanh_dao:
            all_recipients |= self.lanh_dao

        # d) Người tham gia
        if self.employee_ids:
            all_recipients |= self.employee_ids

        # e) TRƯỞNG ĐƠN VỊ CỦA CÁC ĐƠN VỊ THAM GIA (QUAN TRỌNG!)
        for dept in self.don_vi:
            if dept.manager_id:
                # Kiểm tra trưởng đơn vị đã có trong danh sách chưa
                if dept.manager_id not in all_recipients:
                    all_recipients |= dept.manager_id

        # Loại bỏ trùng lặp và chỉ lấy những người có email
        all_recipients = all_recipients.filtered(lambda emp: emp.work_email)

        if not all_recipients:
            _logger.warning(f"Không có email của người nhận thông báo cho cuộc họp {self.id}")
            return

        # 2. CHUẨN BỊ THÔNG TIN CHUNG
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        approver_name = self.env.user.name
        time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""
        event_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"

        # 3. CHUẨN BỊ NỘI DUNG EMAIL THEO TRẠNG THÁI
        if approved:
            subject = f"[ĐÃ DUYỆT PHÒNG] Lịch họp: {self.name}"
            status_text = "✅ ĐÃ DUYỆT"
            status_color = "#27ae60"
            border_color = "#27ae60"
            bg_color = "#e8f6ef"
            action_text = "được duyệt"
            button_text = "Xem chi tiết"

            next_steps = f"""
                <div style="background:#e8f6ef; padding:15px; border-radius:5px; border-left:4px solid #27ae60; margin:20px 0;">
                    <p style="font-weight:bold; color:#27ae60; margin-top:0;">📋 THÔNG BÁO QUAN TRỌNG:</p>
                    <p>Lịch họp đã được sắp xếp phòng và sẵn sàng tổ chức.</p>
                    <ul style="margin-bottom:0;">
                        <li><b>Phòng họp:</b> {self.room.name if self.room else "Chưa có"}</li>
                        <li><b>Thời gian:</b> {time_str}</li>
                        <li><b>Loại họp:</b> {"Họp online" if self.loai_cuoc_hop == 'online' else "Họp offline"}</li>
                        {"<li><b>Link họp:</b> " + self.link_cuoc_hop + "</li>" if self.loai_cuoc_hop == 'online' and self.link_cuoc_hop else ""}
                    </ul>
                </div>
            """
        else:
            subject = f"[TỪ CHỐI PHÒNG] Lịch họp: {self.name}"
            status_text = "❌ BỊ TỪ CHỐI"
            status_color = "#e74c3c"
            border_color = "#e74c3c"
            bg_color = "#fdedec"
            action_text = "bị từ chối"
            button_text = "Xem chi tiết"

            next_steps = f"""
                <div style="background:#fdedec; padding:15px; border-radius:5px; border-left:4px solid #e74c3c; margin:20px 0;">
                    <p style="font-weight:bold; color:#e74c3c; margin-top:0;">⚠️ LƯU Ý QUAN TRỌNG:</p>
                    <p>Yêu cầu phòng họp đã bị từ chối. Người tạo lịch họp cần đăng ký phòng khác.</p>
                    <ul style="margin-bottom:0;">
                        <li>Lịch họp này chưa có phòng họp</li>
                        <li>Người tạo lịch họp sẽ đăng ký phòng khác</li>
                        <li>Bạn sẽ nhận được thông báo mới khi có phòng họp</li>
                    </ul>
                </div>
            """

        # 4. TẠO DANH SÁCH EMAIL NGƯỜI NHẬN (NHÓM)
        email_list = []
        name_list = []
        for employee in all_recipients:
            email = employee.work_email
            if email and email not in email_list:
                email_list.append(email)
                name_list.append(employee.name)

        # 5. TẠO NỘI DUNG EMAIL HTML
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; color: white; text-align: center; }}
                .content {{ padding: 30px; border: 1px solid #e0e0e0; border-radius: 0 0 10px 10px; background: white; }}
                .info-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .info-table td {{ padding: 12px; border: 1px solid #e0e0e0; }}
                .info-table tr:nth-child(even) {{ background: #f9f9f9; }}
                .info-table tr:hover {{ background: #f5f5f5; }}
                .button {{ background: {status_color}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; }}
                .status-badge {{ background: {bg_color}; border-left: 4px solid {border_color}; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ color: #7f8c8d; font-size: 12px; text-align: center; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0; font-size: 28px;">{status_text} - PHÒNG HỌP</h1>
                    <p style="font-size: 18px; margin-top: 10px;">{self.name}</p>
                </div>

                <div class="content">
                    <p>Kính gửi: <b>{', '.join(name_list)}</b>,</p>

                    <div class="status-badge">
                        <h3 style="margin-top: 0; color: {status_color};">
                            Yêu cầu phòng họp cho lịch họp này đã <b>{action_text}</b> bởi <b>{approver_name}</b>
                        </h3>
                    </div>

                    <h3>📋 THÔNG TIN CUỘC HỌP</h3>
                    <table class="info-table">
                        <tr>
                            <td style="width: 30%; font-weight: bold;">Chủ đề cuộc họp:</td>
                            <td>{self.name}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: bold;">Thời gian:</td>
                            <td>{time_str}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: bold;">Phòng họp:</td>
                            <td>
                                <span style="color: {status_color}; font-weight: bold;">
                                    {self.room.name if self.room and approved else 'CHƯA CÓ PHÒNG'}
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <td style="font-weight: bold;">Trạng thái phòng:</td>
                            <td style="color: {status_color}; font-weight: bold;">{status_text}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: bold;">Người chủ trì:</td>
                            <td>{self.chu_tri.name if self.chu_tri else 'Chưa xác định'}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: bold;">Đơn vị tham gia:</td>
                            <td>{', '.join(dept.name for dept in self.don_vi) if self.don_vi else 'Không có'}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: bold;">Số người tham gia:</td>
                            <td>{self.so_nguoi_tham_gia or '0'}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: bold;">Loại cuộc họp:</td>
                            <td>{'Họp online' if self.loai_cuoc_hop == 'online' else 'Họp offline'}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: bold;">Người xử lý:</td>
                            <td>{approver_name}</td>
                        </tr>
                    </table>

                    {next_steps}

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{event_url}" class="button">
                            📋 {button_text}
                        </a>
                    </div>

                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

                    <div class="footer">
                        <p>Đây là email tự động từ Hệ thống Quản lý Lịch họp.</p>
                        <p>Vui lòng không trả lời email này.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        # 6. GỬI EMAIL CHO TẤT CẢ NGƯỜI LIÊN QUAN
        try:
            # Gửi 1 email cho tất cả người nhận
            email_to = ', '.join(email_list)

            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_html,
                'email_to': email_to,
                'email_from': self.env.user.email or self.env.company.email,
            }).send()

            _logger.info(f"✅ Đã gửi email thông báo {action_text} phòng đến {len(email_list)} người liên quan")

        except Exception as e:
            _logger.error(f"Lỗi gửi email thông báo phòng: {str(e)}")

        # 7. GỬI POPUP NOTIFICATION CHO TỪNG NGƯỜI (NẾU ĐANG ONLINE)
        for employee in all_recipients:
            if not employee.user_id:
                continue

            # Tùy chỉnh thông báo popup theo vai trò
            if employee.id == creator_employee.id:
                # Thông báo đặc biệt cho người tạo
                if approved:
                    self.env['bus.bus']._sendone(
                        employee.user_id.partner_id,
                        'simple_notification',
                        {
                            'title': '✅ Phòng họp đã được duyệt',
                            'message': f"Phòng '{self.room.name if self.room else ''}' đã được duyệt cho '{self.name}'",
                            'sticky': True,
                            'type': 'success',
                        }
                    )
                else:
                    self.env['bus.bus']._sendone(
                        employee.user_id.partner_id,
                        'simple_notification',
                        {
                            'title': '❌ Yêu cầu phòng bị từ chối',
                            'message': f"Yêu cầu phòng họp cho '{self.name}' đã bị từ chối",
                            'sticky': True,
                            'type': 'warning',
                        }
                    )
            else:
                # Thông báo thông thường cho người tham gia
                if approved:
                    self.env['bus.bus']._sendone(
                        employee.user_id.partner_id,
                        'simple_notification',
                        {
                            'title': '📅 Cập nhật phòng họp',
                            'message': f"Phòng họp cho '{self.name}' đã được xác nhận: {self.room.name if self.room else ''}",
                            'sticky': False,
                            'type': 'info',
                        }
                    )
                else:
                    self.env['bus.bus']._sendone(
                        employee.user_id.partner_id,
                        'simple_notification',
                        {
                            'title': '⚠️ Cập nhật phòng họp',
                            'message': f"Phòng họp cho '{self.name}' đã bị từ chối",
                            'sticky': False,
                            'type': 'warning',
                        }
                    )

    def open_room_booking_wizard(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError("Vui lòng đợi Lịch họp được duyệt trước khi đăng ký phòng!")
        if not self.start or not self.stop:
            raise UserError("Vui lòng nhập thời gian bắt đầu và kết thúc.")

        # Mở form lịch họp với view đặc biệt cho đăng ký phòng
        return {
            'type': 'ir.actions.act_window',
            'name': f'Đăng ký phòng họp - {self.name}',
            'res_model': 'calendar.event',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',  # Mở trong tab hiện tại
            'view_id': self.env.ref('Quan_ly_lich_hop.view_calendar_event_room_form').id,  # Sử dụng form đặc biệt
            'views': [(self.env.ref('Quan_ly_lich_hop.view_calendar_event_room_form').id, 'form')],
            'context': {
                'default_event_id': self.id,
                'form_view_ref': 'Quan_ly_lich_hop.view_calendar_event_room_form',  # Đảm bảo mở đúng form
                'default_room': self.room.id if self.room else False,
                'search_default_state': 'approved',  # Chỉ hiển thị lịch đã duyệt
                'hide_create_button': True,  # Ẩn nút tạo mới
                'hide_edit_button': not self.is_current_user_creator,  # Ẩn nút chỉnh sửa nếu không phải người tạo
            },
            'flags': {
                'mode': 'readonly' if not self.is_current_user_creator else 'edit',
                'form_view_ref': 'Quan_ly_lich_hop.view_calendar_event_room_form',
            }
        }

    def on_TV(self): # Mở dashboard TV
        return {
            'type': 'ir.actions.act_url',
            'url': '/dashboard/tv',
            'target': 'new', # hoặc 'self' nếu muốn thay tab hiện tại
        }

    def action_add_participants(self):
        self.ensure_one()
        return {
            'name': 'Thêm người tham gia',
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.add.participants.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_event_id': self.id},
        }

    def _check_room_conflict(self, vals, exclude_ids=None):
        """
        Check trùng phòng họp theo thời gian
        """
        room_id = vals.get('room')
        start = vals.get('start')
        stop = vals.get('stop')

        if not room_id or not start or not stop:
            return

        domain = [
            ('room', '=', room_id),
            ('start', '<', stop),
            ('stop', '>', start),
            ('state', '!=', 'canceled'),
        ]

        if exclude_ids:
            domain.append(('id', 'not in', exclude_ids))

        conflict = self.search(domain, limit=1)
        if conflict:
            user_tz_start = fields.Datetime.context_timestamp(self, conflict.start)
            user_tz_stop = fields.Datetime.context_timestamp(self, conflict.stop)
            raise UserError(
                f"❌ Phòng họp '{conflict.room.name}' đã được đăng ký "
                f"từ {user_tz_start.strftime('%H:%M %d/%m/%Y')} "
                f"đến {user_tz_stop.strftime('%H:%M %d/%m/%Y')}."
            )

    can_add_participants = fields.Boolean(
        compute='_compute_can_add_participants',
        string='Có thể thêm người tham gia',
        store=False
    )

    @api.depends_context('uid')
    @api.depends('create_uid', 'don_vi')
    def _compute_can_add_participants(self):
        current_user = self.env.user
        for rec in self:
            can_add = False

            # 1. Người tạo phiếu
            if rec.is_current_user_creator:
                can_add = True
            else:
                # 2. Quản lý của các đơn vị tham gia
                current_employee = self.env['hr.employee'].search(
                    [('user_id', '=', current_user.id)], limit=1
                )
                if current_employee:
                    # Kiểm tra nếu người dùng hiện tại là manager của bất kỳ đơn vị nào tham gia cuộc họp
                    for dept in rec.don_vi:
                        if dept.manager_id and dept.manager_id.id == current_employee.id:
                            can_add = True
                            break

            rec.can_add_participants = can_add

    @api.model
    def _cron_send_meeting_reminder(self):
        """
        Cron job chạy mỗi 5 phút để kiểm tra và gửi thông báo
        khi còn 30 phút nữa đến giờ họp
        """
        now = fields.Datetime.now()

        # Tính thời điểm 30 phút sau
        reminder_time = now + timedelta(minutes=30)

        # Tìm các cuộc họp có thời gian bắt đầu trong khoảng 30 phút tới
        upcoming_meetings = self.search([
            ('state', '=', 'approved'),  # Chỉ gửi cho cuộc họp đã duyệt
            ('room_sign', '=', 'have_sign'),  # Đã có phòng
            ('start', '>', now),  # Chưa bắt đầu
            ('start', '<=', reminder_time),  # Sẽ bắt đầu trong 30 phút tới
            ('reminder_sent', '=', False),  # Chưa gửi nhắc nhở
        ])

        _logger.info(f"Cron: Tìm thấy {len(upcoming_meetings)} cuộc họp sắp diễn ra trong 30 phút tới")

        for meeting in upcoming_meetings:
            try:
                meeting._send_30_minutes_reminder()
            except Exception as e:
                _logger.error(f"Lỗi gửi thông báo nhắc nhở cho cuộc họp {meeting.id}: {str(e)}")

    def _send_30_minutes_reminder(self):
        """
        Gửi thông báo cho tất cả người tham gia 30 phút trước khi cuộc họp bắt đầu
        """
        self.ensure_one()

        if self.reminder_sent:
            return

        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        meeting_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"

        # Tính thời gian còn lại
        now = fields.Datetime.now()
        time_until_start = (self.start - now).total_seconds() / 60  # Số phút

        # Định dạng thời gian
        start_time_str = self.start.strftime('%H:%M %d/%m/%Y') if self.start else "Chưa xác định"
        room_info = f"Phòng: {self.room.name}" if self.room else "Phòng: Chưa đăng ký"

        if self.loai_cuoc_hop == 'online':
            room_info = f"Link họp: {self.link_cuoc_hop}" if self.link_cuoc_hop else "Link họp: Sẽ cập nhật"

        # --- TẬP HỢP DANH SÁCH NGƯỜI NHẬN THÔNG BÁO ---
        all_recipients = self.env['hr.employee']

        # 1. Người tạo phiếu
        creator_employee = self.env['hr.employee'].search(
            [('user_id', '=', self.create_uid.id)],
            limit=1
        )
        if creator_employee:
            all_recipients |= creator_employee

        # 2. Người chủ trì
        if self.chu_tri:
            all_recipients |= self.chu_tri

        # 3. Lãnh đạo
        if self.lanh_dao:
            all_recipients |= self.lanh_dao

        # 4. Người tham gia
        if self.employee_ids:
            all_recipients |= self.employee_ids

        # 5. Trưởng đơn vị tham gia
        for dept in self.don_vi:
            if dept.manager_id:
                all_recipients |= dept.manager_id

        # Loại bỏ trùng lặp
        all_recipients = all_recipients.filtered(lambda emp: emp.work_email)

        if not all_recipients:
            _logger.warning(f"Không có email của người nhận thông báo cho cuộc họp {self.id}")
            return

        # --- GỬI EMAIL NHÓM CHO TẤT CẢ NGƯỜI THAM GIA ---
        try:
            # Thu thập email
            email_list = []
            name_list = []

            for employee in all_recipients:
                email = employee.work_email
                if email and email not in email_list:
                    email_list.append(email)
                    name_list.append(employee.name)

            if email_list:
                # Tạo danh sách người nhận
                email_to = ', '.join(email_list)
                names_str = ', '.join(name_list)

                subject = f"⏰ NHẮC NHỞ: Cuộc họp {self.name} sắp bắt đầu"

                # HTML cho email
                body_html = f"""
                <div style="font-family: Arial, sans-serif; padding: 20px;">
                    <div style="background-color:#e8f4fd; padding:20px; border-radius:10px; border-left:5px solid #2196F3; margin-bottom: 20px;">
                        <h2 style="color:#1565C0; margin-top:0;">⏰ NHẮC NHỞ CUỘC HỌP</h2>
                        <p>Kính gửi: {names_str},</p>
                        <p>Cuộc họp sẽ bắt đầu sau <strong style="color:#e74c3c; font-size: 18px;">{int(time_until_start)} phút</strong> nữa.</p>
                    </div>

                    <div style="margin:20px 0;">
                        <h3 style="color:#333;">📋 Thông tin cuộc họp</h3>
                        <table style="width:100%; border-collapse:collapse; margin-top:10px;">
                            <tr style="background-color:#f5f5f5;">
                                <td style="padding:10px; border:1px solid #ddd; width:30%;"><strong>Chủ đề</strong></td>
                                <td style="padding:10px; border:1px solid #ddd;">{self.name}</td>
                            </tr>
                            <tr>
                                <td style="padding:10px; border:1px solid #ddd;"><strong>Thời gian</strong></td>
                                <td style="padding:10px; border:1px solid #ddd;">{start_time_str}</td>
                            </tr>
                            <tr style="background-color:#f5f5f5;">
                                <td style="padding:10px; border:1px solid #ddd;"><strong>Người chủ trì</strong></td>
                                <td style="padding:10px; border:1px solid #ddd;">{self.chu_tri.name if self.chu_tri else 'Chưa xác định'}</td>
                            </tr>
                            <tr>
                                <td style="padding:10px; border:1px solid #ddd;"><strong>Địa điểm/Link</strong></td>
                                <td style="padding:10px; border:1px solid #ddd;">{room_info}</td>
                            </tr>
                            <tr style="background-color:#f5f5f5;">
                                <td style="padding:10px; border:1px solid #ddd;"><strong>Loại họp</strong></td>
                                <td style="padding:10px; border:1px solid #ddd;">
                                    {'Họp online' if self.loai_cuoc_hop == 'online' else 'Họp offline'}
                                </td>
                            </tr>
                        </table>
                    </div>

                    <div style="margin:20px 0; padding:15px; background-color:#fff8e1; border-radius:5px;">
                        <p><strong>📝 Lưu ý quan trọng:</strong></p>
                        <ul style="margin-top: 5px;">
                            <li>Vui lòng có mặt đúng giờ tại cuộc họp</li>
                            <li>Chuẩn bị tài liệu cần thiết trước khi họp</li>
                            <li>Kiểm tra thiết bị và đường truyền internet (nếu họp online)</li>
                            <li>Đối với họp online, vui lòng truy cập đường link trước 5 phút</li>
                        </ul>
                    </div>

                    <div style="text-align:center; margin-top:30px;">
                        <a href="{meeting_url}" 
                           style="background-color:#2196F3; color:white; padding:12px 24px; 
                                  text-decoration:none; border-radius:5px; font-weight:bold; 
                                  display:inline-block; font-size: 16px;">
                            📅 Xem chi tiết cuộc họp
                        </a>
                    </div>

                    <hr style="margin:30px 0; border:none; border-top:1px solid #eee;">

                    <p style="color:#666; font-size:12px;">
                        Đây là thông báo tự động từ hệ thống Quản lý Lịch họp.<br>
                        Vui lòng không trả lời email này.
                    </p>
                </div>
                """

                # Gửi 1 email cho tất cả người tham gia
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': email_to,
                    'email_from': self.env.user.email or self.env.company.email,
                }).send()

                _logger.info(f"Đã gửi email nhắc nhở đến {len(email_list)} người tham gia cuộc họp")

        except Exception as e:
            _logger.error(f"Lỗi gửi email nhắc nhở: {str(e)}")

        # Đánh dấu đã gửi nhắc nhở
        self.reminder_sent = True

    total_participants = fields.Integer(
        string="Tổng số người tham gia",
    )

    @api.depends('employee_ids', 'lanh_dao', 'chu_tri', 'don_vi')
    def _compute_total_participants(self):
        for rec in self:
            total = 0

            # Đếm người tham gia từ employee_ids
            total += len(rec.employee_ids)

            # Đếm lãnh đạo (loại trùng với employee_ids)
            for leader in rec.lanh_dao:
                if leader not in rec.employee_ids:
                    total += 1

            # Đếm người chủ trì (loại trùng)
            if rec.chu_tri and rec.chu_tri not in rec.employee_ids and rec.chu_tri not in rec.lanh_dao:
                total += 1

            # Đếm trưởng đơn vị tham gia (loại trùng)
            for dept in rec.don_vi:
                if dept.manager_id and \
                        dept.manager_id not in rec.employee_ids and \
                        dept.manager_id not in rec.lanh_dao and \
                        dept.manager_id != rec.chu_tri:
                    total += 1

            rec.total_participants = total

            # Cập nhật luôn vào trường so_nguoi_tham_gia nếu muốn
            rec.so_nguoi_tham_gia = total

class RoomMaterials(models.Model):
    _name = 'room.materials'
    _description = 'Thông tin vật dụng phòng họp'

    name = fields.Char(string='Tên đồ vật')


class RoomRoom(models.Model):
    _name = 'room.room'
    _description = 'Phòng họp'

    name = fields.Char(string='Tên phòng')


class CalendarEventDashboard(models.Model):
    _name = 'calendar.dashboard'
    _description = 'Dashboard hôm nay'

    date_today = fields.Date(default=fields.Date.context_today)

    # Lấy lịch công tác: sự kiện không gắn phòng
    event_ids = fields.One2many(
        'calendar.event', compute='_compute_event_ids', string='Lịch công tác'
    )
    # Lấy lịch phòng họp: sự kiện có gắn phòng
    meeting_room_event_ids = fields.One2many(
        'calendar.event', compute='_compute_meeting_room_event_ids', string='Lịch phòng họp'
    )

    @api.depends('date_today')
    def _compute_event_ids(self):
        today = self.date_today
        for rec in self:
            rec.event_ids = self.env['calendar.event'].search([
                ('start', '>=', today),
                ('start', '<', today + timedelta(days=1)),
                ('room', '=', False),
            ])

    @api.depends('date_today')
    def _compute_meeting_room_event_ids(self):
        today = self.date_today
        for rec in self:
            rec.meeting_room_event_ids = self.env['calendar.event'].search([
                ('start', '>=', today),
                ('start', '<', today + timedelta(days=1)),
                ('room', '!=', False),
            ])



class RoomBookingWizard(models.TransientModel):
    _name = 'room.booking.wizard'
    _description = 'Đăng ký phòng họp'

    event_id = fields.Many2one('calendar.event', string="Sự kiện", required=True, ondelete='cascade')
    room_id = fields.Many2one('room.room', string='Phòng họp', required=True)
    start = fields.Datetime(string="Bắt đầu", related='event_id.start', readonly=True)
    stop = fields.Datetime(string="Kết thúc", related='event_id.stop', readonly=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.room_id:
            raise UserError("Vui lòng chọn phòng họp!")

        # Kiểm tra trùng phòng trong khoảng thời gian
        conflicting_event = self.env['calendar.event'].search([
            ('room', '=', self.room_id.id),
            ('id', '!=', self.event_id.id),
            ('start', '<', self.stop),
            ('stop', '>', self.start),
            ('state', '!=', 'canceled')
        ], limit=1)

        if conflicting_event:
            start_local = fields.Datetime.context_timestamp(self, conflicting_event.start)
            stop_local = fields.Datetime.context_timestamp(self, conflicting_event.stop)

            raise UserError(
                f"Phòng họp '{self.room_id.name}' đã được đăng ký trong khoảng thời gian:\n"
                f"{start_local.strftime('%H:%M %d/%m/%Y')} "
                f"→ {stop_local.strftime('%H:%M %d/%m/%Y')}\n\n"
                "Vui lòng chọn phòng khác hoặc điều chỉnh thời gian."
            )

        # Đăng ký thành công
        self.event_id.write({
            'room_sign': 'pending',  # <--- Chờ duyệt
            'room': self.room_id.id,
        })

        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}


class MeetingInvitationWizard(models.TransientModel):
    _name = 'meeting.invitation.wizard'
    _description = 'Xử lý lời mời họp'

    event_id = fields.Many2one('calendar.event', string="Cuộc họp", required=True)
    employee_id = fields.Many2one('hr.employee', string="Người tham dự", required=True)
    action_type = fields.Selection([
        ('accept', 'Đồng ý tham dự'),
        ('reject', 'Từ chối tham dự')
    ], string='Hành động', required=True)

    note = fields.Text(string='Ghi chú')

    def action_confirm(self):
        self.ensure_one()
        event = self.event_id
        employee = self.employee_id

        if self.action_type == 'accept':
            message = f"✅ {employee.name} đã <b>đồng ý tham dự</b> cuộc họp <b>{event.name}</b>."
            # Nếu employee chưa có trong danh sách, thêm vào
            if employee not in event.employee_ids:
                event.employee_ids = [(4, employee.id)]
        else:
            message = f"❌ {employee.name} đã <b>từ chối tham dự</b> cuộc họp <b>{event.name}</b>."
            # Nếu employee có trong danh sách, xóa khỏi cuộc họp
            if employee in event.employee_ids:
                event.employee_ids = [(3, employee.id)]

        # Gửi notification vào chatter
        event.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )

        return {'type': 'ir.actions.act_window_close'}


class CalendarAddParticipantsWizard(models.TransientModel):
    _name = 'calendar.add.participants.wizard'
    _description = 'Thêm người tham gia cuộc họp'

    event_id = fields.Many2one('calendar.event', string="Cuộc họp", required=True)
    employee_ids = fields.Many2many('hr.employee', string="Người tham gia")

    def action_confirm(self):
        self.ensure_one()
        if not self.employee_ids:
            return {'type': 'ir.actions.act_window_close'}

        # Lấy những người **thực sự mới** được thêm vào
        current_participants = self.event_id.employee_ids
        new_employees = self.employee_ids - current_participants

        if not new_employees:
            return {'type': 'ir.actions.act_window_close'}

        # Thực hiện thêm người mới
        for employee in new_employees:
            self.event_id.employee_ids = [(4, employee.id)]

        # Chỉ gửi email cho **người mới** + người tạo (nếu muốn)
        self._send_email_to_new_participants(new_employees)

        return {'type': 'ir.actions.act_window_close'}

    def _send_email_to_new_participants(self, new_employees):
        """Chỉ gửi email thông báo cho những người vừa được mời"""
        if not new_employees:
            return

        event = self.event_id
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        time_str = f"{event.start.strftime('%H:%M %d/%m/%Y')} → {event.stop.strftime('%H:%M %d/%m/%Y')}" if event.start and event.stop else ""
        room_name = event.room.name if event.room else 'Chưa đăng ký'
        meeting_url = f"{web_url}/web#id={event.id}&model=calendar.event&view_type=form"

        email_list = []
        name_list = []

        for emp in new_employees:
            if emp.work_email and emp.work_email.strip():
                email_list.append(emp.work_email.strip())
                name_list.append(emp.name)

        if not email_list:
            return

        # Có thể thêm email người tạo để họ biết có người mới tham gia
        if event.create_uid and event.create_uid.email:
            creator_email = event.create_uid.email.strip()
            if creator_email not in email_list:
                email_list.append(creator_email)
                name_list.append(event.create_uid.name)

        email_to = ', '.join(email_list)

        body_html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #2c3e50;">📩 Lời mời tham gia cuộc họp</h2>
            <p>Kính gửi <strong>{', '.join(name_list)}</strong>,</p>
            <p>Bạn vừa được mời tham dự cuộc họp:</p>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Chủ đề:</strong> {event.name}</p>
                <p><strong>Thời gian:</strong> {time_str}</p>
                <p><strong>Phòng / Link:</strong> {room_name}</p>
                <p><strong>Người chủ trì:</strong> {event.chu_tri.name if event.chu_tri else 'Chưa xác định'}</p>
            </div>

            <p style="text-align:center; margin: 30px 0;">
                <a href="{meeting_url}" style="background:#3498db; color:white; padding:12px 24px; border-radius:5px; text-decoration:none; font-weight:bold;">
                    📅 Xem chi tiết & Xác nhận tham dự
                </a>
            </p>

            <p>Trân trọng,<br>Hệ thống Quản lý Lịch họp</p>
        </div>
        """

        try:
            self.env['mail.mail'].sudo().create({
                'subject': f'[Mời họp] {event.name}',
                'body_html': body_html,
                'email_to': email_to,
                'email_from': self.env.user.email or self.env.company.email,
            }).send()
            _logger.info(f"Đã gửi lời mời cho {len(email_list)} người mới: {email_to}")
        except Exception as e:
            _logger.error(f"Lỗi gửi email mời người mới: {str(e)}")
