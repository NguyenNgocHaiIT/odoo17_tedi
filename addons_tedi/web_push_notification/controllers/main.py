# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class WebPushController(http.Controller):

    @http.route('/firebase-messaging-sw.js', type='http', auth='public')
    def service_worker(self):
        # Lấy cấu hình từ database
        config = request.env['web.push.config'].sudo().search([], limit=1, order='id desc')

        if not config:
            return request.not_found()

        # Tạo nội dung JS động
        js_content = f"""
importScripts('https://www.gstatic.com/firebasejs/8.10.0/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/8.10.0/firebase-messaging.js');

self.addEventListener('install', () => {{ self.skipWaiting(); }});
self.addEventListener('activate', (event) => {{ event.waitUntil(clients.claim()); }});

const firebaseConfig = {{
    apiKey: "{config.fcm_api_key or ''}",
    authDomain: "{config.fcm_auth_domain or ''}",
    projectId: "{config.fcm_project_id or ''}",
    storageBucket: "{config.fcm_project_id or ''}.firebasestorage.app",
    messagingSenderId: "{config.fcm_messaging_sender_id or ''}",
    appId: "{config.fcm_app_id or ''}"
}};

if (firebaseConfig.apiKey) {{
    firebase.initializeApp(firebaseConfig);
    const messaging = firebase.messaging();

    // XỬ LÝ CLICK: Mở trang Odoo khi bấm vào thông báo
    self.addEventListener('notificationclick', function(event) {{
        event.notification.close();
        event.waitUntil(
            clients.openWindow('/web')
        );
    }});

    // KHÔNG dùng showNotification ở đây nữa vì Backend đã gửi tag 'notification'
    // messaging.onBackgroundMessage(function(payload) {{ ... }});
}}
"""
        return request.make_response(js_content, [
            ('Content-Type', 'text/javascript'),
            ('Service-Worker-Allowed', '/'),
        ])