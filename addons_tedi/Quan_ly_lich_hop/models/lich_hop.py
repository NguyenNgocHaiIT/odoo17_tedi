from email.policy import default

from odoo import api, models, fields
from odoo.exceptions import UserError
from datetime import timedelta

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

    @api.model
    def create(self, vals):
        record = super().create(vals)
        record.color = record.id % 12
        return record

    @api.depends('start', 'name')
    def _compute_calendar_label(self):
        for event in self:
            time_str = event.start.strftime("%H:%M") if event.start else ""
            event.calendar_label = f"{time_str} - {event.name or ''}"

    def approve(self):
        for event in self:
            # Ví dụ: đánh dấu trạng thái đã duyệt
            event.write({'state': 'approved'})
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
