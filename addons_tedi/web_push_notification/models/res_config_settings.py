

# -*- coding: utf-8 -*-
from odoo import models, fields, api
import base64
import json
import logging

_logger = logging.getLogger(__name__)

class WebPushConfig(models.Model):
    _name = 'web.push.config'
    _description = 'Cấu hình Web Push'

    # Thông tin cho Frontend
    fcm_api_key = fields.Char(string="API Key")
    fcm_auth_domain = fields.Char(string="Auth Domain")
    fcm_project_id = fields.Char(string="Project ID")
    fcm_messaging_sender_id = fields.Char(string="Sender ID")
    fcm_app_id = fields.Char(string="App ID")
    fcm_vapid_key = fields.Char(string="VAPID Key (Public Key)") # Thêm trường này

    # Thêm trường Icon (Thường là hình vuông, hiện cạnh nội dung)
    notification_icon = fields.Binary(string="Notification Icon")
    # Thêm trường Badge (Icon nhỏ hiện trên thanh trạng thái Android)
    notification_badge = fields.Binary(string="Notification Badge")

    # Thông tin cho Backend
    fcm_json_file = fields.Binary(string="Firebase Key JSON")
    fcm_json_filename = fields.Char(string="Tên file JSON")

    @api.model
    def get_config(self):
        config = self.env['web.push.config'].sudo().search([], limit=1, order='id desc')
        if not config:
            return {}
        # Lấy base URL để tạo link ảnh tuyệt đối
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        res = {
            'apiKey': config.fcm_api_key or '',
            'authDomain': config.fcm_auth_domain or '',
            'projectId': config.fcm_project_id or '',
            'messagingSenderId': config.fcm_messaging_sender_id or '',
            'appId': config.fcm_app_id or '',
            'vapidKey': config.fcm_vapid_key or '',
            # Trả về link ảnh để Frontend hoặc Service Worker có thể dùng
            'icon': f"{base_url}/web/image/web.push.config/{config.id}/notification_icon" if config.notification_icon else f"{base_url}/web/static/img/favicon.ico",
        }
        return res

from odoo import models, fields, api

class WebPushTemplate(models.Model):
    _name = 'web.push.template'
    _description = 'Mẫu thông báo'

    name = fields.Char(string='Tên mẫu', required=True)
    title = fields.Char(string='Tiêu đề', required=True)
    body = fields.Text(string='Nội dung', required=True)

    def action_open_send_wizard(self):
        """Hàm này sẽ mở Wizard và truyền dữ liệu từ Template sang"""
        return {
            'name': 'Gửi thông báo Push',
            'type': 'ir.actions.act_window',
            'res_model': 'send.push.wizard', # Tên model của wizard bạn đã tạo
            'view_mode': 'form',
            'target': 'new', # Mở dưới dạng popup (cửa sổ mới)
            'context': {
                'default_template_id': self.id,
                'default_title': self.title,
                'default_body': self.body,
            }
        }