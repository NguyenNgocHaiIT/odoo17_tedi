# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests
import json
import logging
import google.auth.transport.requests
from google.oauth2 import service_account
import base64

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    fcm_token = fields.Char(string="Firebase Token", readonly=False)

    @api.model
    def save_fcm_token(self, user_id, token):
        user = self.env['res.users'].sudo().browse(int(user_id))
        if user.exists():
            user.write({'fcm_token': token})
            _logger.info(f"Đã cập nhật Token mới cho {user.name}")
        return True

    def action_test_push(self):
        self.send_push_notification("Odoo V1", "Hệ thống Web Push V1 hoạt động tốt!")

    def _get_google_access_token(self):
        """Lấy Token từ file JSON lưu trong cấu hình database"""
        try:
            # Lấy cấu hình động
            config = self.env['web.push.config'].sudo().search([], limit=1, order='id desc')
            if not config or not config.fcm_json_file:
                _logger.error("Chưa upload file Firebase Key JSON!")
                return None

            json_data = json.loads(base64.b64decode(config.fcm_json_file))
            scopes = ['https://www.googleapis.com/auth/firebase.messaging']
            creds = service_account.Credentials.from_service_account_info(json_data, scopes=scopes)

            request = google.auth.transport.requests.Request()
            creds.refresh(request)
            return creds.token
        except Exception as e:
            _logger.error(f"Lỗi lấy Access Token: {str(e)}")
            return None

    def send_push_notification(self, title, body):
        config = self.env['web.push.config'].sudo().search([], limit=1, order='id desc')
        access_token = self._get_google_access_token()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        if not config or not access_token:
            return

        # Link icon động từ cấu hình
        icon_url = f"{base_url}/web/image/web.push.config/{config.id}/notification_icon" if config.notification_icon else f"{base_url}/web/static/img/favicon.ico"

        url = f"https://fcm.googleapis.com/v1/projects/{config.fcm_project_id}/messages:send"
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}

        for user in self:
            if not user.fcm_token: continue
            payload = {
                "message": {
                    "token": user.fcm_token,
                    "notification": {
                        "title": title,
                        "body": body,
                        "image": icon_url  # Hình ảnh lớn bên trong thông báo (nếu có)
                    },
                    "webpush": {
                        "notification": {
                            "icon": icon_url,  # Icon nhỏ bên cạnh tiêu đề
                            "badge": icon_url  # Icon trên thanh trạng thái
                        },
                        "fcm_options": {
                            "link": f"{base_url}/web"
                        }
                    }
                }
            }
            requests.post(url, headers=headers, data=json.dumps(payload))