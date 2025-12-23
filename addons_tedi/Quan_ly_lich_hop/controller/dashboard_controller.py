from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
import pytz

class DashboardTV(http.Controller):

    @http.route('/dashboard/tv', type='http', auth="public", website=True, csrf=False)
    def tv_dashboard(self, **kw):
        # Xác định ngày hôm nay theo timezone người dùng
        tz = request.env.context.get('tz') or request.env.user.tz or 'UTC'
        today = datetime.now(pytz.timezone(tz)).date()

        # Tất cả sự kiện hôm nay (công tác + họp có/không phòng)
        base_domain = [
            ('start', '>=', datetime.combine(today, datetime.min.time())),
            ('start', '<', datetime.combine(today, datetime.max.time())),
            ('state', 'not in', ['canceled']),  # Loại bỏ đã hủy
        ]

        # Lịch công tác: không có phòng (hoặc room = False)
        event_ids = request.env['calendar.event'].sudo().search(
            base_domain + [('room', '=', False)],
            order='start'
        )

        # Lịch phòng họp: có đặt phòng
        meeting_room_event_ids = request.env['calendar.event'].sudo().search(
            base_domain + [('room', '!=', False)],
            order='start'
        )

        return request.render('Quan_ly_lich_hop.calendar_dashboard_tv_template', {
            'date_today': today,
            'event_ids': event_ids,
            'meeting_room_event_ids': meeting_room_event_ids,
        })