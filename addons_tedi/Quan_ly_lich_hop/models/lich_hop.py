from email.policy import default

from odoo import api, models, fields
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class Calendar(models.Model):
    _inherit = 'calendar.event'

    lanh_dao = fields.Many2one("res.users", string="Lãnh đạo")
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

    room = fields.Many2one('room.room', string='Phòng')

    calendar_label = fields.Char(string="Nhãn trên calendar", compute="_compute_calendar_label")

    color = fields.Integer(string='Màu', default=lambda self: 0)

    start_stop = fields.Char(string="Thời gian", compute="_compute_start_stop")

    date_only = fields.Date(string="Ngày", compute='_compute_date_only', store=True)

    @api.depends('start')
    def _compute_date_only(self):
        for rec in self:
            rec.date_only = rec.start.date() if rec.start else False

    @api.depends('start', 'stop')
    def _compute_start_stop(self):
        for rec in self:
            if rec.start and rec.stop:
                # chỉ lấy giờ:phút
                rec.start_stop = f"{rec.start.strftime('%H:%M')} → {rec.stop.strftime('%H:%M')}"
            else:
                rec.start_stop = ""

    def _get_default_partners(self, vals):
        """Lấy danh sách partner cần thêm vào sự kiện:
           - Lãnh đạo chủ trì
           - Manager của các đơn vị tham gia
        """
        partner_ids = set()

        # 1. Lãnh đạo chủ trì
        lanh_dao_id = vals.get("lanh_dao")
        if lanh_dao_id:
            user = self.env['res.users'].browse(lanh_dao_id)
            if user.partner_id:
                partner_ids.add(user.partner_id.id)

        return list(partner_ids)

    @api.model
    def create(self, vals):
        record = super().create(vals)

        # Lấy danh sách partner tự động
        auto_partner_ids = self._get_default_partners(vals)

        if auto_partner_ids:
            record.partner_ids = [(4, pid) for pid in auto_partner_ids]

        # Giữ logic cũ: tạo màu
        record.color = record.id % 12
        return record

    def write(self, vals):
        """Tự động cập nhật người tham dự khi thay đổi:
           - lãnh đạo
           - đơn vị tham gia
        """
        res = super().write(vals)

        auto_partner_ids = self._get_default_partners(vals)
        if auto_partner_ids:
            for rec in self:
                rec.partner_ids = [(4, pid) for pid in auto_partner_ids]

        return res

    @api.depends('start', 'name')
    def _compute_calendar_label(self):
        for event in self:
            time_str = event.start.strftime("%H:%M") if event.start else ""
            event.calendar_label = f"{time_str} - {event.name or ''}"

    def approve(self):
        """Duyệt cuộc họp, gửi notification chat + popup + email cho partner và manager các đơn vị tham gia"""
        self.ensure_one()
        odoobot = self.env.ref('base.user_root')
        odoobot_partner = odoobot.partner_id
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # 1. Đánh dấu đã duyệt
        self.write({'state': 'approved'})

        # 2. Lấy danh sách partner cần mời (người tham dự + lãnh đạo)
        partner_ids = self.partner_ids.ids
        if self.lanh_dao and self.lanh_dao.partner_id:
            partner_ids.append(self.lanh_dao.partner_id.id)
        partners = self.env['res.partner'].browse(set(partner_ids))

        # 3. Lấy các manager của các đơn vị tham gia
        manager_partners = self.env['res.partner']
        for dept in self.don_vi:
            if dept.manager_id and dept.manager_id.user_id and dept.manager_id.user_id.partner_id:
                manager_partners |= dept.manager_id.user_id.partner_id

        # 4. Hàm tạo kênh chat 1-1
        def get_or_create_direct_chat(partner1, partner2):
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
                'name': f"Lời mời họp: {partner2.name}",
                'channel_type': 'chat',
                'channel_member_ids': [
                    (0, 0, {'partner_id': partner1.id}),
                    (0, 0, {'partner_id': partner2.id}),
                ]
            })

        # 5. Gửi notification popup + chat cho tất cả partner + manager
        all_notify_partners = partners | manager_partners
        for partner in all_notify_partners:
            # Popup notification
            self.env['bus.bus']._sendone(
                partner,
                'simple_notification',
                {
                    'title': '📅 Lời mời họp mới',
                    'message': f"Bạn có lời mời tham dự cuộc họp: {self.name}" if partner in partners else
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
                <p>{'Bạn được mời tham dự.' if partner in partners else 'Đơn vị của bạn đã được mời tham dự.'}</p>
                <p><a href="{web_url}/web#id={self.id}&model=calendar.event&view_type=form"
                      style="background:#28a745;color:blue;padding:6px 12px;border-radius:4px;text-decoration:none;">📨 Xem cuộc họp</a></p>
            """
            try:
                channel = get_or_create_direct_chat(odoobot_partner, partner)
                channel.sudo().message_post(
                    body=body_chat,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot_partner.id,
                    body_is_html=True,
                )
            except Exception as e:
                _logger.error(f"Lỗi gửi chat cho {partner.name}: {str(e)}")

        # 6. Gửi email tới manager các đơn vị tham gia
        for partner in manager_partners:
            if not partner.email:
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
                <p>Kính gửi,</p>
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
                'email_to': partner.email,
            }).send()

        return True

    # Trong class Calendar(models.Model):
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
    partner_id = fields.Many2one('res.partner', string="Người tham dự", required=True)
    action_type = fields.Selection([
        ('accept', 'Đồng ý tham dự'),
        ('reject', 'Từ chối tham dự')
    ], string='Hành động', required=True)

    note = fields.Text(string='Ghi chú')

    def action_confirm(self):
        self.ensure_one()
        event = self.event_id
        partner = self.partner_id

        if self.action_type == 'accept':
            message = f"✅ {partner.name} đã <b>đồng ý tham dự</b> cuộc họp <b>{event.name}</b>."
            # Nếu partner chưa có trong danh sách, thêm vào
            if partner not in event.partner_ids:
                event.partner_ids = [(4, partner.id)]
        else:
            message = f"❌ {partner.name} đã <b>từ chối tham dự</b> cuộc họp <b>{event.name}</b>."
            # Nếu partner có trong danh sách, xóa khỏi cuộc họp
            if partner in event.partner_ids:
                event.partner_ids = [(3, partner.id)]

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
    partner_ids = fields.Many2many('res.partner', string="Người tham gia")

    def action_confirm(self):
        self.ensure_one()
        if not self.partner_ids:
            return {'type': 'ir.actions.act_window_close'}

        new_partners = self.partner_ids - self.event_id.partner_ids
        if not new_partners:
            return {'type': 'ir.actions.act_window_close'}

        # Thêm vào event
        for partner in new_partners:
            self.event_id.partner_ids = [(4, partner.id)]

        # Lấy thông tin cần thiết
        odoobot = self.env.ref('base.user_root')
        odoobot_partner = odoobot.partner_id
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        time_str = f"{self.event_id.start.strftime('%H:%M %d/%m/%Y')} → {self.event_id.stop.strftime('%H:%M %d/%m/%Y')}" if self.event_id.start and self.event_id.stop else ""
        room_name = self.event_id.room.name if self.event_id.room else 'Chưa đăng ký'

        # 1. Gửi notification popup + chat
        for partner in new_partners:
            # Popup notification
            self.env['bus.bus']._sendone(
                partner,
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
                # Chat với OdooBot
                channels = self.env['discuss.channel'].sudo().search([
                    ('channel_type', '=', 'chat'),
                    ('channel_member_ids.partner_id', 'in', [odoobot_partner.id, partner.id])
                ])
                if channels:
                    channel = channels[0]
                else:
                    channel = self.env['discuss.channel'].sudo().create({
                        'name': f"Lời mời họp: {partner.name}",
                        'channel_type': 'chat',
                        'channel_member_ids': [
                            (0, 0, {'partner_id': odoobot_partner.id}),
                            (0, 0, {'partner_id': partner.id}),
                        ]
                    })
                channel.sudo().message_post(
                    body=body_chat,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot_partner.id,
                    body_is_html=True,
                )
            except Exception as e:
                _logger.error(f"Lỗi gửi chat cho {partner.name}: {str(e)}")

            # 2. Gửi email
            if partner.email:
                subject = f"Mời họp {self.event_id.name}"
                body_html = f"""
                    <p>Kính gửi {partner.name},</p>
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
                    'email_to': partner.email,
                }).send()

        return {'type': 'ir.actions.act_window_close'}
