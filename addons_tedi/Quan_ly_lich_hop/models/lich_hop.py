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
        string='Đơn vị đồng xử lý'
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

    chu_tri = fields.Many2one("hr.employee", string="Người chủ trì", default=lambda self: self._get_default_chu_tri())
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
        if not vals.get('chu_tri') and self.env.user.employee_ids:
            vals['chu_tri'] = self.env.user.employee_ids[0].id
        record = super().create(vals)
        record.color = record.id % 12
        return record

    def write(self, vals):
        old_chu_tri_ids = {rec.id: rec.chu_tri.id for rec in self}
        res = super().write(vals)
        if 'chu_tri' in vals:
            for rec in self:
                old_chu_tri_id = old_chu_tri_ids.get(rec.id)
                new_chu_tri_id = rec.chu_tri.id
                current_ids = rec.employee_ids.ids
                new_employee_ids = current_ids.copy()
                if old_chu_tri_id and old_chu_tri_id in new_employee_ids:
                    new_employee_ids = [eid if eid != old_chu_tri_id else new_chu_tri_id for eid in new_employee_ids]
                elif new_chu_tri_id not in new_employee_ids:
                    new_employee_ids.append(new_chu_tri_id)
                rec.employee_ids = [(6, 0, list(set(new_employee_ids)))]
        return res

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

    def action_send_request(self):
        """Nhân viên gửi duyệt"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("Chỉ có thể gửi duyệt phiếu ở trạng thái Nháp.")
        self.write({'state': 'pending'})

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
        employee_ids = self.employee_ids.ids
        if self.lanh_dao:
            employee_ids.append(self.lanh_dao.id)
        employees = self.env['hr.employee'].browse(set(employee_ids))

        manager_employees = self.env['hr.employee']
        for dept in self.don_vi:
            if dept.manager_id:
                manager_employees |= dept.manager_id

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

            # Popup
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
                        channel.sudo().message_post(
                            body=body_chat, message_type='comment', subtype_xmlid='mail.mt_comment',
                            author_id=odoobot_employee.user_id.partner_id.id, body_is_html=True
                        )
            except Exception as e:
                _logger.error(f"Lỗi gửi chat: {str(e)}")

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

        return True

    def action_approve_room(self):
        self.ensure_one()
        if not self.can_approve_room:
            raise UserError("Bạn không có quyền duyệt phòng họp.")
        self.write({'room_sign': 'have_sign'})
        self.message_post(body="✅ Phòng họp đã được duyệt!", message_type='notification')

    def action_reject_room(self):
        self.ensure_one()
        if not self.can_approve_room:
            raise UserError("Bạn không có quyền từ chối phòng họp.")
        self.write({'room_sign': 'no_sign', 'room': False})
        self.message_post(body="❌ Yêu cầu phòng họp đã bị từ chối.", message_type='notification')

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

    @api.model
    def on_TV(self, *args, **kwargs):
        # Code dashboard TV của bạn
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dashboard hôm nay',
            'res_model': 'calendar.dashboard',
            'view_mode': 'form',
            'view_id': self.env.ref('Quan_ly_lich_hop.view_dashboard_today_form').id,
            'target': 'current',
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
            raise UserError(
                f"Phòng họp '{self.room_id.name}' đã được đăng ký trong khoảng:\n"
                f"{conflicting_event.start.strftime('%H:%M')} → {conflicting_event.stop.strftime('%H:%M')} "
                f"ngày {conflicting_event.start.strftime('%d/%m/%Y')}.\n"
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