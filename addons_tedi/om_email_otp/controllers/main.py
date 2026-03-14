from odoo import http, fields
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.exceptions import AccessDenied
from odoo.service import security


class EmailOTPHome(Home):

    @http.route('/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        request.params['login_success'] = False

        # 1. Lấy trạng thái Bật/Tắt từ Cấu hình hệ thống (mặc định là False nếu chưa lưu)
        otp_enabled = request.env['ir.config_parameter'].sudo().get_param('om_email_otp.enable_email_otp_login',
                                                                          'False')

        # 2. CHỈ chạy luồng OTP nếu nút này được BẬT (bằng 'True')
        if otp_enabled == 'True' and request.httprequest.method == 'POST' and request.params.get(
                'login') and request.params.get('password'):
            db = request.session.db or request.params.get('db')
            login = request.params['login']
            password = request.params['password']

            try:
                uid = request.env['res.users'].sudo().authenticate(db, login, password, {})
                if uid:
                    user = request.env['res.users'].sudo().browse(uid)
                    user.generate_and_send_otp()

                    request.session.logout(keep_db=True)

                    request.session['pending_uid'] = uid
                    request.session['pending_login'] = login

                    return request.redirect('/web/login/otp')
            except AccessDenied:
                pass

                # 3. Luồng mặc định: Dùng khi tính năng OTP tắt, HOẶC người dùng nhập sai mật khẩu
        return super(EmailOTPHome, self).web_login(redirect, **kw)

    # TUYẾN ĐƯỜNG MỚI: Dành riêng để hiển thị Form OTP
    @http.route('/web/login/otp', type='http', auth="public", website=True)
    def web_login_otp(self, **kw):
        # Nếu truy cập thẳng mà không có session chờ, đẩy về trang login
        if not request.session.get('pending_uid'):
            return request.redirect('/web/login')

        error_msg = 'Mã OTP không hợp lệ hoặc đã hết hạn!' if kw.get('error') else None

        return request.render('om_email_otp.otp_verify_form', {
            'login': request.session.get('pending_login'),
            'error': error_msg
        })

    @http.route('/web/otp/verify', type='http', auth="public", methods=['POST'], csrf=False)
    def verify_otp(self, **kw):
        otp_code = kw.get('otp_code')
        uid = request.session.get('pending_uid')

        if not uid or not otp_code:
            return request.redirect('/web/login')

        user = request.env['res.users'].sudo().browse(uid)

        if user.email_otp_code == otp_code and user.email_otp_expiry and user.email_otp_expiry > fields.Datetime.now():
            user.sudo().write({'email_otp_code': False, 'email_otp_expiry': False})

            request.session.uid = uid
            request.session.login = request.session.get('pending_login')
            request.session.session_token = security.compute_session_token(request.session, request.env)
            request.session.rotate = True

            request.session.pop('pending_uid', None)
            request.session.pop('pending_login', None)

            return request.redirect('/web')
        else:
            # Nếu sai mã, chuyển hướng lại trang OTP kèm cờ báo lỗi
            return request.redirect('/web/login/otp?error=1')