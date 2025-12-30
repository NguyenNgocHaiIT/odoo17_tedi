from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
import pytz


class DashboardTV(http.Controller):

    @http.route('/dashboard/tv', type='http', auth="public", website=True, csrf=False)
    def tv_dashboard(self, **kw):
        """
        Hiển thị dashboard TV:
        - Lịch công tác: từ calendar.outside (sự kiện bên ngoài)
        - Lịch họp có phòng: từ calendar.event (có room)
        """
        # Xác định ngày hôm nay theo timezone người dùng
        tz = request.env.context.get('tz') or request.env.user.tz or 'UTC'
        today = datetime.now(pytz.timezone(tz)).date()

        # Domain chung: sự kiện hôm nay, không bị hủy
        base_domain = [
            ('start', '>=', datetime.combine(today, datetime.min.time())),
            ('start', '<', datetime.combine(today, datetime.max.time())),
            ('state', 'not in', ['canceled']),  # Loại bỏ đã hủy
        ]

        # 1. LỊCH CÔNG TÁC: từ calendar.outside (sự kiện bên ngoài)
        event_ids = request.env['calendar.outside'].sudo().search(
            base_domain,
            order='start'
        )

        # 2. LỊCH PHÒNG HỌP: từ calendar.event CÓ phòng (room != False)
        meeting_room_event_ids = request.env['calendar.event'].sudo().search(
            base_domain + [('room', '!=', False)],
            order='start'
        )

        return request.render('Quan_ly_lich_hop.calendar_dashboard_tv_template', {
            'date_today': today,
            'event_ids': event_ids,  # calendar.outside
            'meeting_room_event_ids': meeting_room_event_ids,  # calendar.event có phòng
        })