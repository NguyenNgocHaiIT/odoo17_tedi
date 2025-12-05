from email.policy import default

from odoo import api, models, fields
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class Calendar(models.Model):
    _inherit = 'calendar.event'

    lanh_dao = fields.Many2one("hr.employee", string="Lãnh đạo")
    don_vi = fields.Many2many(
        "hr.department",
        'calendar_don_vi_tham_gia_rel',
        'calendar_event_id', 'department_id',
        string='Đơn vị đồng xử lý'
    )
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('approved', 'Đã duyệt'),
        ('canceled', 'Đã hủy')
    ], string='Trạng thái', default='draft', tracking=True)

    room_sign = fields.Selection([
        ('no_sign', 'Chưa đăng ký'),
        ('have_sign', 'Đã đăng ký')
    ], string="Trạng thái đăng ký phòng", default='no_sign')

    room_materials = fields.Many2many(
        'room.materials',
        'calendar_room_materials_rel',
        'calendar_event_id', 'room_materials_id',
        string='Thông tin khác'
    )
    chu_tri = fields.Many2one("hr.employee", string="Người chủ trì", default=lambda self: self._get_default_chu_tri())

    room = fields.Many2one('room.room', string='Phòng')

    calendar_label = fields.Char(string="Nhãn trên calendar", compute="_compute_calendar_label")

    color = fields.Integer(string='Màu', default=lambda self: 0)

    start_stop = fields.Char(string="Thời gian", compute="_compute_start_stop")

    date_only = fields.Date(string="Ngày", compute='_compute_date_only', store=True)

    employee_ids = fields.Many2many(
        'hr.employee',
        'calendar_event_employee_rel',
        'event_id', 'employee_id',
        string='Người tham gia',
        default=lambda self: self._get_default_employees(),
    )

    def _get_default_chu_tri(self):
        """Lấy employee của user hiện tại làm chủ trì mặc định"""
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
        """Lấy danh sách người tham gia mặc định (bao gồm chủ trì)"""
        participant_ids = []

        # 1. Thêm chủ trì (employee của user hiện tại)
        if self.env.user.employee_ids:
            chu_tri_id = self.env.user.employee_ids[0].id
            participant_ids.append(chu_tri_id)

        return [(6, 0, participant_ids)]

    @api.model
    def create(self, vals):
        if not vals.get('chu_tri') and self.env.user.employee_ids:
            # Lấy employee từ user hiện tại
            current_employee = self.env.user.employee_ids[0]
            vals['chu_tri'] = current_employee.id

        record = super().create(vals)

        # Tạo màu
        record.color = record.id % 12
        return record

    def write(self, vals):
        """Tự động cập nhật người tham dự khi thay đổi:
           - lãnh đạo
           - đơn vị tham gia
        """
        res = super().write(vals)

        auto_employee_ids = self._get_default_employees(vals)
        if auto_employee_ids:
            for rec in self:
                rec.employee_ids = [(4, eid) for eid in auto_employee_ids]

        return res

    @api.depends('start', 'name')
    def _compute_calendar_label(self):
        for event in self:
            time_str = event.start.strftime("%H:%M") if event.start else ""
            event.calendar_label = f"{time_str} - {event.name or ''}"

    def approve(self):
        """Duyệt cuộc họp, gửi notification chat + popup + email cho employee và manager các đơn vị tham gia"""
        self.ensure_one()
        odoobot = self.env.ref('base.user_root')
        odoobot_employee = self.env['hr.employee'].search([('user_id', '=', odoobot.id)], limit=1)
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # 1. Đánh dấu đã duyệt
        self.write({'state': 'approved'})

        # 2. Lấy danh sách employee cần mời (người tham dự + lãnh đạo)
        employee_ids = self.employee_ids.ids
        if self.lanh_dao:
            employee_ids.append(self.lanh_dao.id)
        employees = self.env['hr.employee'].browse(set(employee_ids))

        # 3. Lấy các manager của các đơn vị tham gia
        manager_employees = self.env['hr.employee']
        for dept in self.don_vi:
            if dept.manager_id:
                manager_employees |= dept.manager_id

        # 4. Hàm tạo kênh chat 1-1 (dựa trên user của employee)
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

        # 5. Gửi notification popup + chat cho tất cả employees + managers
        all_notify_employees = employees | manager_employees
        for employee in all_notify_employees:
            if not employee.user_id:
                continue

            # Popup notification
            self.env['bus.bus']._sendone(
                employee.user_id.partner_id,
                'simple_notification',
                {
                    'title': '📅 Lời mời họp mới',
                    'message': f"Bạn có lời mời tham dự cuộc họp: {self.name}" if employee in employees else
                    f"Đơn vị của bạn đã được mời tham dự cuộc họp: {self.name}",
                    'sticky': False,
                    'type': 'info',
                }
            )

            # Chat HTML
            time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""
            body_chat = f"""
                <p>📅 Cuộc họp: <b>{self.name}</b></p>
                <p>⏰ {time_str}</p>
                <p>🏢 Phòng: {self.room.name if self.room else 'Chưa đăng ký'}</p>
                <p>{'Bạn được mời tham dự.' if employee in employees else 'Đơn vị của bạn đã được mời tham dự.'}</p>
                <p><a href="{web_url}/web#id={self.id}&model=calendar.event&view_type=form"
                      style="background:#28a745;color:blue;padding:6px 12px;border-radius:4px;text-decoration:none;">📨 Xem cuộc họp</a></p>
            """
            try:
                if odoobot_employee and odoobot_employee.user_id:
                    channel = get_or_create_direct_chat(odoobot_employee, employee)
                    if channel:
                        channel.sudo().message_post(
                            body=body_chat,
                            message_type='comment',
                            subtype_xmlid='mail.mt_comment',
                            author_id=odoobot_employee.user_id.partner_id.id,
                            body_is_html=True,
                        )
            except Exception as e:
                _logger.error(f"Lỗi gửi chat cho {employee.name}: {str(e)}")

        # 6. Gửi email tới manager các đơn vị tham gia
        for employee in manager_employees:
            if not employee.work_email:
                continue

            # Người tạo
            user_create = self.create_uid
            dept_create = user_create.employee_ids.department_id.name if user_create.employee_ids else ''
            contact_info = f"{user_create.email or ''} / {user_create.phone or ''}"

            # Thành phần tham dự
            don_vi_names = ", ".join(self.don_vi.mapped('name'))
            time_str = f"{self.start.strftime('%H:%M %d/%m/%Y')} → {self.stop.strftime('%H:%M %d/%m/%Y')}" if self.start and self.stop else ""

            # Link mở form cuộc họp
            event_url = f"{web_url}/web#id={self.id}&model=calendar.event&view_type=form"

            subject = f"Mời họp {self.name}"
            body_html = f"""
                <p>Kính gửi {employee.name},</p>
                <p>Phòng {dept_create} kính mời đơn vị tham dự cuộc họp <b>{self.name}</b> với nội dung chi tiết như sau:</p>
                <p><b>Thời gian:</b> {time_str}</p>
                <p><b>Thành phần tham dự:</b> {don_vi_names}</p>
                <p><b>Nội dung:</b> {self.name or 'Chưa có nội dung'}</p>
                <p>Anh/chị vui lòng thu xếp nhân sự, thời gian tham dự và chuẩn bị các nội dung liên quan (nếu có).</p>
                <p>Anh/chị truy cập vào đường link dưới đây để xem và cập nhật thành phần tham dự cuộc họp:</p>
                <p><a href="{event_url}">{event_url}</a></p>
                <p>Trân trọng,<br/>
                {user_create.name}<br/>
                {dept_create}<br/>
                {contact_info}</p>
            """
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_html,
                'email_to': employee.work_email,
            }).send()

        return True

    def open_room_booking_wizard(self):
        self.ensure_one()
        if not self.start or not self.stop:
            raise UserError("Vui lòng nhập thời gian bắt đầu và kết thúc trước khi đăng ký phòng.")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Đăng ký phòng họp',
            'res_model': 'room.booking.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_event_id': self.id,
            },
            'views': [(False, 'form')],
        }

    @api.model
    def on_TV(self, *args, **kwargs):
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
            'context': {
                'default_event_id': self.id,
            },
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
            'room_sign': 'have_sign',
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