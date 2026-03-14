from odoo import models, fields, api
import random
from datetime import datetime, timedelta

class ResUsers(models.Model):
    _inherit = 'res.users'

    email_otp_code = fields.Char(string="OTP Code")
    email_otp_expiry = fields.Datetime(string="OTP Expiry")

    def generate_and_send_otp(self):
        self.ensure_one()
        otp = str(random.randint(100000, 999999))
        self.sudo().write({
            'email_otp_code': otp,
            'email_otp_expiry': datetime.now() + timedelta(minutes=5)
        })

        template = self.env.ref('om_email_otp.mail_template_email_otp', raise_if_not_found=False)
        if template:
            # Ép hệ thống dùng email này làm người gửi (thay vì phụ thuộc XML)
            template.sudo().send_mail(
                self.id,
                force_send=True,
                email_values={'email_from': 'emyeuaidayy@gmail.com'}  # Sửa lại thành Email tuỳ ý của bạn
            )

