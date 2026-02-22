# -*- coding: utf-8 -*-
{
    'name': "My Web Push Notification",
    'summary': "Gửi thông báo đẩy từ Odoo kể cả khi tắt Tab",
    'description': """
        Module tích hợp Firebase Cloud Messaging (FCM).
        Hỗ trợ Service Worker để nhận thông báo nền.
    """,
    'author': "Thưởng",
    'website': "http://www.thgdx.vn",
    'category': 'TEDI/Tools',
    'version': '1.0',
    'depends': ['base', 'web'],
    'data': [
        # 'views/assets.xml',
        "security/ir.model.access.csv",

        "wizard/send_push_wizard_view.xml",

        "data/web_push_data.xml",


        'views/res_users_view.xml',
        "views/web_push_template_view.xml",
        "views/res_config_settings_views.xml",


    ],
    'assets': {
    'web.assets_backend': [
        # Thư viện Google (Bắt buộc phải có trước)
        'https://www.gstatic.com/firebasejs/8.10.0/firebase-app.js',
        'https://www.gstatic.com/firebasejs/8.10.0/firebase-messaging.js',

        # File code của bạn
        'web_push_notification/static/src/js/firebase_client.js',


    ],
},
    'license': 'LGPL-3',
}