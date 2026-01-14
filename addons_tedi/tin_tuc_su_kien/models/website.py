from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class WebsitePost(models.Model):
    _name = 'website.post'

    name = fields.Char(string='Tiêu đề')
    post_type = fields.Many2one('post.type', string='Loại tin tức')
    create_user = fields.Many2one('res.users', string='Người tạo',  default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Ngày tạo')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('chua_duyet', 'chưa duyệt'),
        ('da_duyet', 'đã duyệt')
    ], string='Trạng thái', default='draft')
    confirm_user = fields.Many2one('res.users', string='Người duyệt')
    have_post = fields.Boolean(string='Đã đăng lên web')
    image = fields.Image(string='Hình ảnh đính kèm')
    content = fields.Text(string='Nội dung')

    def action_submit_leader(self):
        # logic trình lãnh đạo (ví dụ: chuyển trạng thái)
        self.write({'state': 'chua_duyet'})
        self._send_notification_to_van_thu()
        return True

    def action_cancel(self):
        self.write({'state': 'draft'})
        self._send_simple_reject_notification()
        return True

    def _send_simple_reject_notification(self):
        """Gửi bài đăng đơn giản cho người tạo khi bài đăng bị từ chối"""
        self.ensure_one()

        try:
            creator = self.create_user
            if not creator or not creator.partner_id:
                _logger.warning("Không tìm thấy thông tin người tạo")
                return

            # --- 1. GỬI bài đăng CHAT QUA ODOOBOT ---
            odoobot = self.env.ref('base.user_root')
            odoobot_partner = odoobot.partner_id

            # Hàm tạo kênh chat 1-1
            def get_or_create_direct_chat(partner1, partner2):
                try:
                    domain = [
                        ('channel_type', '=', 'chat'),
                        ('channel_member_ids.partner_id', 'in', [partner1.id, partner2.id])
                    ]
                    channels = self.env['discuss.channel'].sudo().search(domain)

                    for channel in channels:
                        member_partners = channel.channel_member_ids.mapped('partner_id')
                        if len(member_partners) == 2 and set(member_partners.ids) == {partner1.id, partner2.id}:
                            return channel

                    return self.env['discuss.channel'].sudo().with_context(
                        mail_create_nosubscribe=True,
                        odoobot_no_welcome_message=True
                    ).create({
                        'name': f"Chat với {partner2.name}",
                        'channel_type': 'chat',
                        'channel_member_ids': [
                            (0, 0, {'partner_id': partner1.id}),
                            (0, 0, {'partner_id': partner2.id})
                        ]
                    })
                except Exception as e:
                    _logger.error(f"Lỗi tạo kênh chat: {str(e)}")
                    return None

            # Nội dung chat đơn giản
            chat_body = f"""
            <div style="font-family: Arial, sans-serif;">
                <p><strong>bài đăng của bạn đã bị từ chối</strong></p>
                <p>bài đăng: <strong>{self.name}</strong></p>
                <p>Vui lòng kiểm tra và chỉnh sửa lại.</p>
            </div>
            """

            # Tạo kênh chat và gửi tin nhắn
            channel = get_or_create_direct_chat(odoobot_partner, creator.partner_id)
            if channel:
                channel.sudo().message_post(
                    body=chat_body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot_partner.id,
                    body_is_html=True,
                )
                _logger.info(f"Đã gửi bài đăng từ chối cho người tạo: {creator.name}")

            # --- 2. GỬI bài đăng POPUP (REAL-TIME) ---
            try:
                self.env['bus.bus']._sendone(
                    creator.partner_id,
                    'simple_notification',
                    {
                        'title': 'bài đăng bị từ chối',
                        'message': f'bài đăng "{self.name[:30]}..." đã bị từ chối',
                        'sticky': False,
                        'type': 'warning',
                    }
                )
            except Exception as e:
                _logger.error(f"Lỗi gửi popup notification: {str(e)}")


        except Exception as e:
            _logger.error(f"Lỗi khi gửi bài đăng từ chối: {str(e)}")

    def action_save_draft(self):
        # logic lưu nháp
        self.write({'state': 'draft'})
        return True

    def approve(self):
        self.write({'state': 'da_duyet'})
        return True

    def _send_notification_to_van_thu(self):
        """Gửi bài đăng đến văn thư khi có bài đăng mới được trình"""
        self.ensure_one()

        try:
            # Lấy nhóm lãnh đạo(cần tạo group với XML ID: tin_tuc_su_kien.group_quan_ly_tin_tuc)
            group_van_thu = self.env.ref('tin_tuc_su_kien.group_quan_ly_tin_tuc', raise_if_not_found=False)

            if not group_van_thu:
                _logger.warning("Không tìm thấy nhóm văn thư.")
                return

            # Lấy tất cả người dùng trong nhóm văn thư
            van_thu_users = group_van_thu.users

            # Lấy danh sách email của văn thư
            van_thu_emails = []
            for user in van_thu_users:
                if user.email:
                    van_thu_emails.append(user.email)

            if not van_thu_emails:
                _logger.warning("Không có email nào trong nhóm văn thư.")
                return

            # Chuẩn bị nội dung email
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model={self._name}&view_type=form"

            # Lấy thông tin người gửi
            current_user = self.env.user.name
            create_date = self.create_date or fields.Datetime.now()

            # Định dạng ngày tháng
            formatted_date = create_date.strftime('%d/%m/%Y %H:%M') if create_date else ''

            subject = f"[bài đăng mới trình duyệt] {self.name[:50]}..."
            body_html = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Kính gửi Anh/Chị Văn thư,</p>

                <p>bài đăng <b>"{self.name}"</b> đã được trình lên lãnh đạo để duyệt.</p>

                <div style="background:#f8f9fa; padding:15px; margin:15px 0; border-left:4px solid #3498db;">
                    <p><b>Thông tin chi tiết:</b></p>
                    <ul style="margin:0; padding-left:20px;">
                        <li><b>Người trình:</b> {current_user}</li>
                        <li><b>Thời gian trình:</b> {formatted_date}</li>
                        <li><b>Loại bài đăng:</b> {self.type.name or 'Không xác định'}</li>
                        <li><b>Trạng thái:</b> Chờ duyệt</li>
                    </ul>
                </div>
                <p style="margin:20px 0 10px 0;">
                    <a href="{detail_url}" 
                       style="background:#3498db;color:blue;padding:10px 20px;text-decoration:none;border-radius:4px;font-size:14px;font-weight:bold;">
                        📋 Xem chi tiết bài đăng
                    </a>
                </p>

                <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">

                <p style="color:#666;font-size:12px;">
                    Đây là bài đăng tự động từ hệ thống. Vui lòng không trả lời email này.
                </p>
            </div>
            """

            # Gửi email đến tất cả văn thư
            for email in van_thu_emails:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_to': email,
                    'email_from': self.env.user.email or self.env.company.email or 'no-reply@company.com',
                    'body_html': body_html,
                    'auto_delete': True,
                }).send()

            _logger.info(f"Đã gửi email bài đăng đến {len(van_thu_emails)} văn thư")

            # Gửi bài đăng chat qua OdooBot cho từng văn thư
            odoobot = self.env.ref('base.user_root')
            odoobot_partner = odoobot.partner_id

            def get_or_create_direct_chat(partner1, partner2):
                """Tạo kênh chat 1-1 giữa 2 partner"""
                try:
                    domain = [
                        ('channel_type', '=', 'chat'),
                        ('channel_member_ids.partner_id', 'in', [partner1.id, partner2.id])
                    ]
                    channels = self.env['discuss.channel'].sudo().search(domain)

                    for channel in channels:
                        member_partners = channel.channel_member_ids.mapped('partner_id')
                        if len(member_partners) == 2 and set(member_partners.ids) == {partner1.id, partner2.id}:
                            return channel

                    return self.env['discuss.channel'].sudo().with_context(
                        mail_create_nosubscribe=True,
                        odoobot_no_welcome_message=True
                    ).create({
                        'name': f"Chat với {partner2.name}",
                        'channel_type': 'chat',
                        'channel_member_ids': [
                            (0, 0, {'partner_id': partner1.id}),
                            (0, 0, {'partner_id': partner2.id})
                        ]
                    })
                except Exception as e:
                    _logger.error(f"Lỗi tạo kênh chat: {str(e)}")
                    return None

            # Gửi bài đăng chat cho từng văn thư
            chat_body = f"""
            <div style="font-family: Arial, sans-serif;">
                <p><strong>bài đăng mới cần xử lý</strong></p>
                <p><strong>Tiêu đề:</strong> {self.name}</p>
                <p><strong>Người trình:</strong> {current_user}</p>
                <p><strong>Thời gian:</strong> {formatted_date}</p>
                <p>
                    <a href="{detail_url}" style="color:#3498db;text-decoration:underline;">
                        Nhấn vào đây để xem chi tiết
                    </a>
                </p>
                <p style="color:#666;font-size:12px;margin-top:10px;">
                    <i>Vui lòng kiểm tra và xử lý bài đăng này.</i>
                </p>
            </div>
            """

            for user in van_thu_users:
                if user.partner_id and user != self.env.user:
                    try:
                        # Tạo hoặc lấy kênh chat với OdooBot
                        channel = get_or_create_direct_chat(odoobot_partner, user.partner_id)
                        if channel:
                            channel.sudo().message_post(
                                body=chat_body,
                                message_type='comment',
                                subtype_xmlid='mail.mt_comment',
                                author_id=odoobot_partner.id,
                                body_is_html=True,
                            )

                            # Gửi bài đăng popup (bus.bus)
                            self.env['bus.bus']._sendone(
                                user.partner_id,
                                'simple_notification',
                                {
                                    'title': 'bài đăng mới cần xử lý',
                                    'message': f"Có bài đăng mới: {self.name[:30]}...",
                                    'sticky': False,
                                    'type': 'info',
                                }
                            )
                            _logger.info(f"Đã gửi bài đăng chat cho văn thư: {user.name}")

                    except Exception as e:
                        _logger.error(f"Lỗi gửi bài đăng cho văn thư {user.name}: {str(e)}")

        except Exception as e:
            _logger.error(f"Lỗi khi gửi bài đăng cho văn thư: {str(e)}")

class PostType(models.Model):
    _name = 'post.type'

    name = fields.Char('Tên loại tin tức')