from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_email_otp_login = fields.Boolean(
        string="Bật xác thực 2 lớp (OTP qua Email)",
        config_parameter='om_email_otp.enable_email_otp_login',
        help="Bắt buộc tất cả người dùng xác thực bằng mã OTP gửi về Email khi đăng nhập."
    )