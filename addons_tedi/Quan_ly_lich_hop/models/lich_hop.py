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
            # Nếu là Admin HOẶC Quản lý phòng họp -> Duyệt tất cả
            if is_admin or is_room_manager:
                can_meeting = True

            # Nếu không phải cấp cao, mới xét đến cấp Quản lý đơn vị (check cùng phòng ban)
            elif is_dept_manager:
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
            # Nếu chuyển từ draft sang pending (gửi duyệt)
            elif vals.get('state') == 'pending' and old_states.get(rec.id) == 'draft':
                rec._send_notification_to_dept_managers("pending_for_approval")

        return result

    def action_send_request(self):
        """Nhân viên gửi duyệt - Gửi thông báo đặc biệt cho trưởng đơn vị"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("Chỉ có thể gửi duyệt phiếu ở trạng thái Nháp.")

        # Gửi thông báo đặc biệt khi gửi duyệt
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        creator_name = self.create_uid.name if self.create_uid else "Người tạo"
        time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""

        # Lấy danh sách trưởng đơn vị
        manager_employees = self.env['hr.employee']
        for dept in self.don_vi:
            if dept.manager_id:
                manager_employees |= dept.manager_id

        for manager in manager_employees:
            if not manager.user_id:
                continue

            # Popup với action rõ ràng
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

            # Chatter trên lịch họp
            approval_message = f"⏳ Đã gửi yêu cầu phê duyệt tới trưởng đơn vị: {manager.name}"
            self.message_post(
                body=approval_message,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )

        self.write({'state': 'pending'})

        # Gửi email chi tiết
        for manager in manager_employees:
            if not manager.work_email:
                continue

            event_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"
            subject = f"[CẦN PHÊ DUYỆT] Lịch họp: {self.name}"
            body_html = f"""
                <div style="border-left:4px solid #f39c12;padding-left:15px;background:#fff8e1;">
                    <h3 style="color:#d35400;">⚠️ YÊU CẦU PHÊ DUYỆT LỊCH HỌP</h3>
                </div>
                <p>Kính gửi <b>{manager.name}</b>,</p>
                <p>Nhân viên <b>{creator_name}</b> vừa gửi yêu cầu phê duyệt lịch họp cho đơn vị của Quý Anh/Chị.</p>

                <p><b>Thông tin cuộc họp cần duyệt:</b></p>
                <table style="border-collapse:collapse;width:100%;">
                    <tr style="background:#f8f9fa;">
                        <td style="border:1px solid #ddd;padding:8px;"><b>Chủ đề</b></td>
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
                </table>

                <p style="margin-top:20px;">
                    <a href="{event_url}" 
                       style="background:#3498db;color:white;padding:10px 20px;border-radius:5px;text-decoration:none;font-weight:bold;display:inline-block;">
                        📋 Xem & Phê duyệt ngay
                    </a>
                </p>

                <p style="color:#7f8c8d;font-size:12px;margin-top:20px;">
                    <i>Vui lòng phê duyệt hoặc từ chối lịch họp này trong vòng 24 giờ.</i>
                </p>
            """

            try:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': manager.work_email,
                    'email_from': self.env.user.email or self.env.company.email,
                }).send()
            except Exception as e:
                _logger.error(f"Lỗi gửi email yêu cầu phê duyệt: {str(e)}")

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
        employee_ids = []

        if self.employee_ids:
            employee_ids.extend(self.employee_ids.ids)
        if self.lanh_dao:
            employee_ids.extend(self.lanh_dao.ids)
        employees = self.env['hr.employee'].browse(set(employee_ids))

        manager_employees = self.env['hr.employee']
        for dept in self.don_vi:
            if dept.manager_id:
                manager_employees |= dept.manager_id

        # ✅ THÊM: Người tạo phiếu (nếu có employee record)
        creator_employee = self.env['hr.employee'].search([('user_id', '=', self.create_uid.id)], limit=1)
        if creator_employee:
            employees |= creator_employee

        # Hàm helper tạo kênh chat
        def get_or_create_direct_chat(employee1, employee2):
            if not employee1.user_id or not employee2.user_id:
                return None
            partner1 = employee1.user_id.partner_id
            partner2 = employee2.user_id.partner_id
            domain = [
                ('channel_type', '=', 'chat'),
                ('channel_member_ids.partner_id', 'in', [partner1.id, partner2.id])
            ]
            channels = self.env['discuss.channel'].sudo().search(domain)
            for channel in channels:
                members = channel.channel_member_ids.mapped('partner_id')
                if len(members) == 2 and set(members.ids) == {partner1.id, partner2.id}:
                    return channel
            return self.env['discuss.channel'].sudo().create({
                'name': f"Lời mời họp: {employee2.name}",
                'channel_type': 'chat',
                'channel_member_ids': [
                    (0, 0, {'partner_id': partner1.id}),
                    (0, 0, {'partner_id': partner2.id}),
                ]
            })

        # Gửi notification
        all_notify_employees = employees | manager_employees
        for employee in all_notify_employees:
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

            # Chat
            time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""
            body_chat = f"""
                <p>📅 Cuộc họp: <b>{self.name}</b></p>
                <p>⏰ {time_str}</p>
                <p>🏢 Phòng: {self.room.name if self.room else 'Chưa đăng ký'}</p>
                <p><a href="{web_url}/web#id={self.id}&model=calendar.event&view_type=form" 
                      style="background:#28a745;color:white;padding:4px 8px;border-radius:4px;text-decoration:none;">📨 Xem chi tiết</a></p>
            """
            try:
                if odoobot_employee and odoobot_employee.user_id:
                    channel = get_or_create_direct_chat(odoobot_employee, employee)
                    if channel:
                        # Thêm thông điệp đặc biệt cho người tạo
                        if employee.id == creator_employee.id:
                            extra_msg = "<p style='color:#27ae60;font-weight:bold;'>✅ Lịch họp của bạn đã được phê duyệt thành công!</p>"
                            body_chat = extra_msg + body_chat

                        channel.sudo().message_post(
                            body=body_chat, message_type='comment', subtype_xmlid='mail.mt_comment',
                            author_id=odoobot_employee.user_id.partner_id.id, body_is_html=True
                        )
            except Exception as e:
                _logger.error(f"Lỗi gửi chat: {str(e)}")

        # ✅ THÊM: Gửi email cho người tạo
        if creator_employee and creator_employee.work_email:
            approver_name = self.env.user.name
            time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""
            event_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"
            subject = f"[ĐÃ DUYỆT] Lịch họp: {self.name}"
            body_html = f"""
                <div style="border-left:4px solid #27ae60;padding-left:15px;background:#e8f6ef;">
                    <h3 style="color:#27ae60;">✅ LỊCH HỌP ĐÃ ĐƯỢC DUYỆT</h3>
                </div>
                <p>Kính gửi <b>{creator_employee.name}</b>,</p>
                <p>Lịch họp của bạn đã được <b>{approver_name}</b> phê duyệt thành công.</p>

                <p><b>Thông tin cuộc họp đã duyệt:</b></p>
                <table style="border-collapse:collapse;width:100%;">
                    <tr style="background:#f8f9fa;">
                        <td style="border:1px solid #ddd;padding:8px;"><b>Chủ đề</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">{self.name}</td>
                    </tr>
                    <tr>
                        <td style="border:1px solid #ddd;padding:8px;"><b>Thời gian</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">{time_str}</td>
                    </tr>
                    <tr style="background:#f8f9fa;">
                        <td style="border:1px solid #ddd;padding:8px;"><b>Trạng thái</b></td>
                        <td style="border:1px solid #ddd;padding:8px;color:#27ae60;font-weight:bold;">✅ ĐÃ DUYỆT</td>
                    </tr>
                    <tr>
                        <td style="border:1px solid #ddd;padding:8px;"><b>Người duyệt</b></td>
                        <td style="border:1px solid #ddd;padding:8px;">{approver_name}</td>
                    </tr>
                </table>

                <p style="margin-top:20px;">
                    <b>Tiếp theo:</b> Bây giờ bạn có thể đăng ký phòng họp nếu cần.
                </p>

                <p style="margin-top:20px;">
                    <a href="{event_url}" 
                       style="background:#27ae60;color:white;padding:10px 20px;border-radius:5px;text-decoration:none;font-weight:bold;display:inline-block;">
                        📋 Xem chi tiết lịch họp
                    </a>
                </p>
            """
            try:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': creator_employee.work_email,
                    'email_from': self.env.user.email or self.env.company.email,
                }).send()
                _logger.info(f"Đã gửi email thông báo duyệt cho người tạo: {creator_employee.name}")
            except Exception as e:
                _logger.error(f"Lỗi gửi email cho người tạo: {str(e)}")

        # Gửi email manager
        for employee in manager_employees:
            if not employee.work_email:
                continue
            user_create = self.create_uid
            event_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"
            subject = f"Mời họp: {self.name}"
            body_html = f"""
                <p>Kính gửi {employee.name},</p>
                <p>Đơn vị được mời tham dự cuộc họp <b>{self.name}</b>.</p>
                <p>Thời gian: {time_str}</p>
                <p><a href="{event_url}">Xem chi tiết</a></p>
            """
            self.env['mail.mail'].sudo().create({
                'subject': subject, 'body_html': body_html, 'email_to': employee.work_email
            }).send()

        # ✅ THÊM: Chatter message thông báo đã duyệt
        approver = self.env.user.name
        self.message_post(
            body=f"✅ <b>Lịch họp đã được {approver} phê duyệt.</b><br/>"
                 f"Thời gian: {time_str}<br/>"
                 f"Trạng thái: Đã duyệt → Có thể đăng ký phòng họp.",
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            body_is_html=True
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
        Gửi thông báo duyệt/từ chối phòng cho người tạo

        :param approved: True nếu duyệt, False nếu từ chối
        """
        # Lấy thông tin người tạo
        creator_employee = self.env['hr.employee'].search([('user_id', '=', self.create_uid.id)], limit=1)
        if not creator_employee or not creator_employee.work_email:
            _logger.warning(f"Không tìm thấy email của người tạo lịch họp: {self.create_uid.name}")
            return

        # Lấy thông tin cần thiết
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        approver_name = self.env.user.name
        time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""

        # Chuẩn bị nội dung email
        if approved:
            subject = f"[ĐÃ DUYỆT PHÒNG] Lịch họp: {self.name}"
            status_text = "✅ ĐÃ DUYỆT"
            status_color = "#27ae60"
            border_color = "#27ae60"
            bg_color = "#e8f6ef"
            action_text = "được duyệt"
            button_text = "Xem chi tiết"
            next_steps = """
                <p><b>📋 Lịch họp của bạn đã sẵn sàng:</b></p>
                <ul>
                    <li>Phòng họp: <b>{}</b></li>
                    <li>Thời gian: <b>{}</b></li>
                    <li>Vui lòng có mặt đúng giờ tại phòng họp.</li>
                </ul>
            """.format(self.room.name if self.room else "", time_str)
        else:
            subject = f"[TỪ CHỐI PHÒNG] Lịch họp: {self.name}"
            status_text = "❌ BỊ TỪ CHỐI"
            status_color = "#e74c3c"
            border_color = "#e74c3c"
            bg_color = "#fdedec"
            action_text = "bị từ chối"
            button_text = "Đăng ký lại phòng"
            next_steps = """
                <p><b>🔄 Cần thực hiện:</b></p>
                <ul>
                    <li>Yêu cầu phòng họp của bạn đã bị từ chối.</li>
                    <li>Vui lòng chọn phòng khác hoặc điều chỉnh thời gian.</li>
                    <li>Nhấn nút "Đăng ký phòng họp" để chọn phòng khác.</li>
                </ul>
            """

        # Tạo nội dung email HTML
        event_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"
        body_html = f"""
            <div style="border-left:4px solid {border_color};padding-left:15px;background:{bg_color};">
                <h3 style="color:{status_color};">{status_text} - YÊU CẦU PHÒNG HỌP</h3>
            </div>

            <p>Kính gửi <b>{creator_employee.name}</b>,</p>

            <p>Yêu cầu phòng họp cho lịch họp của bạn đã <b>{action_text}</b> bởi <b>{approver_name}</b>.</p>

            <p><b>Thông tin cuộc họp:</b></p>
            <table style="border-collapse:collapse;width:100%;margin-bottom:20px;">
                <tr style="background:#f8f9fa;">
                    <td style="border:1px solid #ddd;padding:8px;"><b>Chủ đề</b></td>
                    <td style="border:1px solid #ddd;padding:8px;">{self.name}</td>
                </tr>
                <tr>
                    <td style="border:1px solid #ddd;padding:8px;"><b>Thời gian</b></td>
                    <td style="border:1px solid #ddd;padding:8px;">{time_str}</td>
                </tr>
                <tr style="background:#f8f9fa;">
                    <td style="border:1px solid #ddd;padding:8px;"><b>Phòng họp</b></td>
                    <td style="border:1px solid #ddd;padding:8px;">
                        {self.room.name if self.room and approved else '<span style="color:#e74c3c;">Không có phòng</span>'}
                    </td>
                </tr>
                <tr>
                    <td style="border:1px solid #ddd;padding:8px;"><b>Trạng thái phòng</b></td>
                    <td style="border:1px solid #ddd;padding:8px;color:{status_color};font-weight:bold;">
                        {status_text}
                    </td>
                </tr>
                <tr style="background:#f8f9fa;">
                    <td style="border:1px solid #ddd;padding:8px;"><b>Người xử lý</b></td>
                    <td style="border:1px solid #ddd;padding:8px;">{approver_name}</td>
                </tr>
            </table>

            {next_steps}

            <p style="margin-top:20px;">
                <a href="{event_url}" 
                   style="background:{status_color};color:white;padding:10px 20px;border-radius:5px;text-decoration:none;font-weight:bold;display:inline-block;">
                    📋 {button_text}
                </a>
            </p>

            <hr style="border:none;border-top:1px solid #eee;margin:20px 0;"/>

            <p style="color:#7f8c8d;font-size:12px;">
                <i>Đây là email tự động từ Hệ thống Quản lý Lịch họp.</i><br/>
                <i>Vui lòng không trả lời email này.</i>
            </p>
        """

        # Gửi email
        try:
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_html,
                'email_to': creator_employee.work_email,
                'email_from': self.env.user.email or self.env.company.email,
            }).send()
            _logger.info(f"Đã gửi email thông báo {action_text} phòng cho người tạo: {creator_employee.name}")
        except Exception as e:
            _logger.error(f"Lỗi gửi email thông báo phòng: {str(e)}")

        # ✅ THÊM: Gửi popup notification cho người tạo (nếu đang online)
        if creator_employee.user_id:
            if approved:
                self.env['bus.bus']._sendone(
                    creator_employee.user_id.partner_id,
                    'simple_notification',
                    {
                        'title': '✅ Phòng họp đã được duyệt',
                        'message': f"Phòng '{self.room.name if self.room else ''}' đã được duyệt cho cuộc họp '{self.name}'",
                        'sticky': True,
                        'type': 'success',
                    }
                )
            else:
                self.env['bus.bus']._sendone(
                    creator_employee.user_id.partner_id,
                    'simple_notification',
                    {
                        'title': '❌ Yêu cầu phòng bị từ chối',
                        'message': f"Yêu cầu phòng họp cho '{self.name}' đã bị từ chối",
                        'sticky': True,
                        'type': 'warning',
                    }
                )

    def open_room_booking_wizard(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError("Vui lòng đợi Lịch họp được duyệt trước khi đăng ký phòng!")
        if not self.start or not self.stop:
            raise UserError("Vui lòng nhập thời gian bắt đầu và kết thúc.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Đăng ký phòng họp',
            'res_model': 'room.booking.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_event_id': self.id},
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
        all_recipients = all_recipients.filtered(lambda emp: emp.user_id)

        if not all_recipients:
            _logger.warning(f"Không có người nhận thông báo cho cuộc họp {self.id}")
            return

        # --- NỘI DUNG THÔNG BÁO ---
        subject = f"⏰ NHẮC NHỞ: Cuộc họp {self.name} sắp bắt đầu"

        # HTML cho email
        body_html = f"""
        <div style="background-color:#e8f4fd; padding:20px; border-radius:10px; border-left:5px solid #2196F3;">
            <h2 style="color:#1565C0;">⏰ NHẮC NHỞ CUỘC HỌP</h2>
            <p>Cuộc họp sẽ bắt đầu sau <strong>{int(time_until_start)} phút</strong> nữa.</p>
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
                    <td style="padding:10px; border:1px solid #ddd;"><strong>Địa điểm</strong></td>
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
            <p><strong>📝 Lưu ý:</strong></p>
            <ul>
                <li>Vui lòng có mặt đúng giờ</li>
                <li>Chuẩn bị tài liệu cần thiết trước khi họp</li>
                <li>Kiểm tra thiết bị (nếu họp online)</li>
            </ul>
        </div>

        <div style="text-align:center; margin-top:30px;">
            <a href="{meeting_url}" 
               style="background-color:#2196F3; color:white; padding:12px 24px; 
                      text-decoration:none; border-radius:5px; font-weight:bold; 
                      display:inline-block;">
                📅 Xem chi tiết cuộc họp
            </a>
        </div>

        <hr style="margin:30px 0; border:none; border-top:1px solid #eee;">

        <p style="color:#666; font-size:12px;">
            Đây là thông báo tự động từ hệ thống Quản lý Lịch họp.<br>
            Vui lòng không trả lời email này.
        </p>
        """

        # --- GỬI THÔNG BÁO ---
        for employee in all_recipients:
            # 1. Gửi email
            if employee.work_email:
                try:
                    self.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'body_html': body_html,
                        'email_to': employee.work_email,
                        'email_from': self.env.user.email or self.env.company.email,
                    }).send()
                    _logger.info(f"Đã gửi email nhắc nhở cho {employee.name} ({employee.work_email})")
                except Exception as e:
                    _logger.error(f"Lỗi gửi email cho {employee.name}: {str(e)}")

            # 2. Gửi popup notification
            if employee.user_id:
                try:
                    self.env['bus.bus']._sendone(
                        employee.user_id.partner_id,
                        'simple_notification',
                        {
                            'title': '⏰ Nhắc nhở cuộc họp',
                            'message': f"Cuộc họp '{self.name}' sẽ bắt đầu sau {int(time_until_start)} phút",
                            'sticky': True,  # Hiển thị lâu hơn
                            'type': 'warning',
                        }
                    )
                except Exception as e:
                    _logger.error(f"Lỗi gửi popup cho {employee.name}: {str(e)}")

            # 3. Gửi chat message
            try:
                if employee.user_id:
                    odoobot = self.env.ref('base.user_root')
                    odoobot_employee = self.env['hr.employee'].search(
                        [('user_id', '=', odoobot.id)],
                        limit=1
                    )

                    if odoobot_employee and odoobot_employee.user_id:
                        # Tìm hoặc tạo kênh chat
                        partner1 = odoobot_employee.user_id.partner_id
                        partner2 = employee.user_id.partner_id

                        domain = [
                            ('channel_type', '=', 'chat'),
                            ('channel_member_ids.partner_id', 'in', [partner1.id, partner2.id])
                        ]

                        channels = self.env['discuss.channel'].sudo().search(domain)
                        channel = None

                        for ch in channels:
                            members = ch.channel_member_ids.mapped('partner_id')
                            if len(members) == 2 and set(members.ids) == {partner1.id, partner2.id}:
                                channel = ch
                                break

                        if not channel:
                            channel = self.env['discuss.channel'].sudo().create({
                                'name': f"⏰ Nhắc nhở họp: {employee.name}",
                                'channel_type': 'chat',
                                'channel_member_ids': [
                                    (0, 0, {'partner_id': partner1.id}),
                                    (0, 0, {'partner_id': partner2.id}),
                                ]
                            })

                        # Nội dung chat
                        chat_body = f"""
                        <div style="background:#fff3cd; padding:10px; border-radius:5px; border-left:4px solid #ffc107;">
                            <p><strong>⏰ NHẮC NHỞ CUỘC HỌP</strong></p>
                            <p>Cuộc họp <b>{self.name}</b> sẽ bắt đầu sau <b>{int(time_until_start)} phút</b>.</p>
                            <p><b>Thời gian:</b> {start_time_str}</p>
                            <p><b>Phòng:</b> {self.room.name if self.room else 'Chưa đăng ký'}</p>
                            <p>
                                <a href="{meeting_url}" style="background:#2196F3; color:white; padding:5px 10px; 
                                   text-decoration:none; border-radius:3px; font-size:12px;">
                                    Xem chi tiết
                                </a>
                            </p>
                        </div>
                        """

                        channel.sudo().message_post(
                            body=chat_body,
                            message_type='comment',
                            subtype_xmlid='mail.mt_comment',
                            author_id=partner1.id,
                            body_is_html=True
                        )

                        _logger.info(f"Đã gửi chat nhắc nhở cho {employee.name}")
            except Exception as e:
                _logger.error(f"Lỗi gửi chat cho {employee.name}: {str(e)}")

        # Đánh dấu đã gửi nhắc nhở
        self.reminder_sent = True

        # Ghi log vào chatter
        reminder_msg = f"""
        <div style="background:#e8f4fd; padding:10px; border-radius:5px; margin:10px 0;">
            <p><strong>⏰ ĐÃ GỬI NHẮC NHỞ 30 PHÚT TRƯỚC KHI HỌP</strong></p>
            <p>Thời gian: {now.strftime('%H:%M %d/%m/%Y')}</p>
            <p>Người nhận: {len(all_recipients)} người</p>
            <p>Thời gian còn lại: {int(time_until_start)} phút</p>
        </div>
        """

        self.message_post(
            body=reminder_msg,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            body_is_html=True
        )

        _logger.info(f"Đã gửi thông báo nhắc nhở 30 phút cho cuộc họp {self.id}: {self.name}")


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

        new_employees = self.employee_ids - self.event_id.employee_ids
        if not new_employees:
            return {'type': 'ir.actions.act_window_close'}

        # Thêm vào event
        for employee in new_employees:
            self.event_id.employee_ids = [(4, employee.id)]

        # Lấy thông tin cần thiết
        odoobot = self.env.ref('base.user_root')
        odoobot_employee = self.env['hr.employee'].search([('user_id', '=', odoobot.id)], limit=1)
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        time_str = f"{self.event_id.start.strftime('%H:%M %d/%m/%Y')} → {self.event_id.stop.strftime('%H:%M %d/%m/%Y')}" if self.event_id.start and self.event_id.stop else ""
        room_name = self.event_id.room.name if self.event_id.room else 'Chưa đăng ký'

        # 1. Gửi notification popup + chat
        for employee in new_employees:
            if not employee.user_id:
                continue

            # Popup notification
            self.env['bus.bus']._sendone(
                employee.user_id.partner_id,
                'simple_notification',
                {
                    'title': '📅 Lời mời họp mới',
                    'message': f"Bạn đã được thêm tham dự cuộc họp: {self.event_id.name}",
                    'sticky': False,
                    'type': 'info',
                }
            )

            # Chat HTML
            body_chat = f"""
                <p>📅 Bạn đã được thêm tham dự cuộc họp: <b>{self.event_id.name}</b></p>
                <p>⏰ {time_str}</p>
                <p>🏢 Phòng: {room_name}</p>
                <p>
                    <a href="{web_url}/web#id={self.event_id.id}&model=calendar.event&view_type=form"
                       style="background:#28a745;color:blue;padding:6px 12px;border-radius:4px;text-decoration:none;">📨 Xem cuộc họp</a>
                </p>
            """
            try:
                if odoobot_employee and odoobot_employee.user_id:
                    # Chat với OdooBot
                    channels = self.env['discuss.channel'].sudo().search([
                        ('channel_type', '=', 'chat'),
                        ('channel_member_ids.partner_id', 'in',
                         [odoobot_employee.user_id.partner_id.id, employee.user_id.partner_id.id])
                    ])
                    if channels:
                        channel = channels[0]
                    else:
                        channel = self.env['discuss.channel'].sudo().create({
                            'name': f"Lời mời họp: {employee.name}",
                            'channel_type': 'chat',
                            'channel_member_ids': [
                                (0, 0, {'partner_id': odoobot_employee.user_id.partner_id.id}),
                                (0, 0, {'partner_id': employee.user_id.partner_id.id}),
                            ]
                        })
                    channel.sudo().message_post(
                        body=body_chat,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=odoobot_employee.user_id.partner_id.id,
                        body_is_html=True,
                    )
            except Exception as e:
                _logger.error(f"Lỗi gửi chat cho {employee.name}: {str(e)}")

            # 2. Gửi email
            if employee.work_email:
                subject = f"Mời họp {self.event_id.name}"
                body_html = f"""
                    <p>Kính gửi {employee.name},</p>
                    <p>Bạn đã được thêm tham dự cuộc họp <b>{self.event_id.name}</b> với nội dung chi tiết:</p>
                    <p><b>Thời gian:</b> {time_str}</p>
                    <p><b>Phòng:</b> {room_name}</p>
                    <p>Anh/chị truy cập đường link dưới đây để xem chi tiết cuộc họp:</p>
                    <p><a href="{web_url}/web#id={self.event_id.id}&model=calendar.event&view_type=form">{web_url}/web#id={self.event_id.id}&model=calendar.event&view_type=form</a></p>
                    <p>Trân trọng,</p>
                    <p>{self.event_id.create_uid.name}</p>
                """
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': employee.work_email,
                }).send()

        return {'type': 'ir.actions.act_window_close'}
