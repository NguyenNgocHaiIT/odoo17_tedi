from odoo import api, models, fields
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class NotifyEvent(models.Model):
    _name = 'notify.event'

    name = fields.Char(string='Tiêu đề')
    type = fields.Many2one('notify.type', string='Loại thông báo')
    create_user = fields.Many2one('res.users', string='Người tạo', default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Ngày tạo')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('chua_duyet', 'Chưa duyệt'),
        ('da_duyet', 'Đã duyệt'),
        ('da_thong_bao', 'Đã thông báo')
    ], string='Trạng thái', default='draft')
    confirm_user = fields.Many2one('res.users', string='Người duyệt')
    sent = fields.Boolean(string='Đã gửi thông báo')
    content = fields.Text(string='Nội dung')
    send_all = fields.Boolean(string='Gửi toàn bộ nhân viên')
    send_individual = fields.Many2many(
        'res.users',
        'notify_event_users_rel',  # tên bảng trung gian
        'notify_id',  # khóa ngoại trỏ tới notify.event
        'user_id',  # khóa ngoại trỏ tới res.users
        string='Gửi cho cá nhân'
    )

    send_department = fields.Many2many(
        'hr.department',
        'notify_event_department_rel',
        'notify_id',
        'department_id',
        string='Gửi cho phòng ban'
    )

    def action_submit_leader(self):
        # logic trình lãnh đạo (ví dụ: chuyển trạng thái)
        self.write({'state': 'chua_duyet'})
        self._send_notification_to_van_thu()
        return True

    def _send_notification_to_van_thu(self):
        """Gửi thông báo đến văn thư khi có thông báo mới được trình"""
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

            subject = f"[Thông báo mới trình duyệt] {self.name[:50]}..."
            body_html = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Kính gửi Anh/Chị Văn thư,</p>

                <p>Thông báo <b>"{self.name}"</b> đã được trình lên lãnh đạo để duyệt.</p>

                <div style="background:#f8f9fa; padding:15px; margin:15px 0; border-left:4px solid #3498db;">
                    <p><b>Thông tin chi tiết:</b></p>
                    <ul style="margin:0; padding-left:20px;">
                        <li><b>Người trình:</b> {current_user}</li>
                        <li><b>Thời gian trình:</b> {formatted_date}</li>
                        <li><b>Loại thông báo:</b> {self.type.name or 'Không xác định'}</li>
                        <li><b>Trạng thái:</b> Chờ duyệt</li>
                    </ul>
                </div>
                <p style="margin:20px 0 10px 0;">
                    <a href="{detail_url}" 
                       style="background:#3498db;color:blue;padding:10px 20px;text-decoration:none;border-radius:4px;font-size:14px;font-weight:bold;">
                        📋 Xem chi tiết thông báo
                    </a>
                </p>

                <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">

                <p style="color:#666;font-size:12px;">
                    Đây là thông báo tự động từ hệ thống. Vui lòng không trả lời email này.
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

            _logger.info(f"Đã gửi email thông báo đến {len(van_thu_emails)} văn thư")

            # Gửi thông báo chat qua OdooBot cho từng văn thư
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

            # Gửi thông báo chat cho từng văn thư
            chat_body = f"""
            <div style="font-family: Arial, sans-serif;">
                <p><strong>Thông báo mới cần xử lý</strong></p>
                <p><strong>Tiêu đề:</strong> {self.name}</p>
                <p><strong>Người trình:</strong> {current_user}</p>
                <p><strong>Thời gian:</strong> {formatted_date}</p>
                <p>
                    <a href="{detail_url}" style="color:#3498db;text-decoration:underline;">
                        Nhấn vào đây để xem chi tiết
                    </a>
                </p>
                <p style="color:#666;font-size:12px;margin-top:10px;">
                    <i>Vui lòng kiểm tra và xử lý thông báo này.</i>
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

                            # Gửi thông báo popup (bus.bus)
                            self.env['bus.bus']._sendone(
                                user.partner_id,
                                'simple_notification',
                                {
                                    'title': 'Thông báo mới cần xử lý',
                                    'message': f"Có thông báo mới: {self.name[:30]}...",
                                    'sticky': False,
                                    'type': 'info',
                                }
                            )
                            _logger.info(f"Đã gửi thông báo chat cho văn thư: {user.name}")

                    except Exception as e:
                        _logger.error(f"Lỗi gửi thông báo cho văn thư {user.name}: {str(e)}")

        except Exception as e:
            _logger.error(f"Lỗi khi gửi thông báo cho văn thư: {str(e)}")

    def action_save_draft(self):
        # logic lưu nháp
        self.write({'state': 'draft'})
        return True

    def action_cancel(self):
        self.write({'state': 'draft'})
        self._send_simple_reject_notification()
        return True

    def _send_simple_reject_notification(self):
        """Gửi thông báo đơn giản cho người tạo khi thông báo bị từ chối"""
        self.ensure_one()

        try:
            creator = self.create_user
            if not creator or not creator.partner_id:
                _logger.warning("Không tìm thấy thông tin người tạo")
                return


            # --- 1. GỬI THÔNG BÁO CHAT QUA ODOOBOT ---
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
                <p><strong>Thông báo của bạn đã bị từ chối</strong></p>
                <p>Thông báo: <strong>{self.name}</strong></p>
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
                _logger.info(f"Đã gửi thông báo từ chối cho người tạo: {creator.name}")

            # --- 2. GỬI THÔNG BÁO POPUP (REAL-TIME) ---
            try:
                self.env['bus.bus']._sendone(
                    creator.partner_id,
                    'simple_notification',
                    {
                        'title': 'Thông báo bị từ chối',
                        'message': f'Thông báo "{self.name[:30]}..." đã bị từ chối',
                        'sticky': False,
                        'type': 'warning',
                    }
                )
            except Exception as e:
                _logger.error(f"Lỗi gửi popup notification: {str(e)}")


        except Exception as e:
            _logger.error(f"Lỗi khi gửi thông báo từ chối: {str(e)}")

    def action_send_notification(self):
        self.ensure_one()
        odoobot = self.env.ref('base.user_root')
        odoobot_partner = odoobot.partner_id

        self.write({'state': 'da_thong_bao'})

        # --- 1. LẤY DANH SÁCH NGƯỜI NHẬN ---
        users = self.env['res.users'].sudo()

        if self.send_all:
            # Lấy tất cả user active, không bao gồm system user và odoobot
            users = self.env['res.users'].sudo().search([
                ('active', '=', True),
                ('id', '!=', odoobot.id)
            ])
        else:
            if self.send_individual:
                users |= self.send_individual.sudo().filtered(lambda u: u.active and u != odoobot)
            if self.send_department:
                dept_users = self.env['hr.employee'].sudo().search([
                    ('department_id', 'in', self.send_department.ids),
                    ('user_id', '!=', False),
                    ('user_id.active', '=', True)
                ]).mapped('user_id')
                users |= dept_users.filtered(lambda u: u != odoobot)

        # Loại bỏ user trùng lặp và kiểm tra partner
        users = users.filtered(lambda u: u.partner_id and u.partner_id.id)
        users = users.sorted(key=lambda u: u.id)

        if not users:
            raise UserError("Chưa có đối tượng để gửi thông báo!")

        # --- 2. NỘI DUNG THÔNG BÁO ---
        content = self.content or ""
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        detail_url = f"{web_url}/web#id={self.id}&model={self._name}&view_type=form"

        body = f"""
            <p><strong>Bạn nhận được thông báo mới:</strong></p>
            <p><strong>{self.name}</strong></p>
            <p>{content}</p>
            <p>
                <a href="{detail_url}"
                   style="background:#875A7B;color:blue;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                    Xem chi tiết
                </a>
            </p>
        """

        # --- 3. HÀM TẠO KÊNH CHAT 1-1 VỚI TỪNG NGƯỜI ---
        def get_or_create_direct_chat(partner1, partner2):
            """Tạo kênh chat 1-1 giữa 2 partner"""
            try:
                # Tìm kênh chat hiện có
                domain = [
                    ('channel_type', '=', 'chat'),
                    ('channel_member_ids.partner_id', 'in', [partner1.id, partner2.id])
                ]
                channels = self.env['discuss.channel'].sudo().search(domain)

                for channel in channels:
                    member_partners = channel.channel_member_ids.mapped('partner_id')
                    if len(member_partners) == 2 and set(member_partners.ids) == {partner1.id, partner2.id}:
                        return channel

                # Tạo kênh chat mới - CHỈ 2 THÀNH VIÊN
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
                _logger.error(f"Lỗi tạo kênh chat giữa {partner1.name} và {partner2.name}: {str(e)}")
                return None

        # --- 4. GỬI THÔNG BÁO ĐẾN TỪNG NGƯỜI ---
        mail_mail_obj = self.env['mail.mail'].sudo()

        sent_users = []
        failed_users = []

        for user in users:
            partner = user.partner_id
            if not partner:
                failed_users.append(user.name)
                continue

            try:
                # Tạo hoặc lấy kênh chat 1-1 với odoobot
                channel = get_or_create_direct_chat(odoobot_partner, partner)
                if not channel:
                    failed_users.append(user.name)
                    continue

                # Gửi tin nhắn qua chat
                channel.sudo().message_post(
                    body=body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot_partner.id,
                    body_is_html=True,
                )

                # Gửi email (nếu có email)
                if partner.email:
                    mail_mail_obj.create({
                        'subject': self.name,
                        'body_html': body,
                        'email_to': partner.email,
                        'auto_delete': True,
                    }).send()

                sent_users.append(user.name)
                _logger.info(f"Đã gửi thông báo cho: {user.name}")

            except Exception as e:
                _logger.error(f"Lỗi khi gửi thông báo cho {user.name}: {str(e)}")
                failed_users.append(user.name)
                continue

        # --- 5. GỬI TÓM TẮT CHO NGƯỜI GỬI ---
        sender = self.env.user
        if sender != odoobot and sender.partner_id:
            try:
                # Tạo nội dung tóm tắt
                summary = f"Thông báo <strong>{self.name}</strong> đã được gửi đến {len(sent_users)} người"

                if sent_users:
                    # Hiển thị 5 người đầu tiên
                    summary += f": {', '.join(sent_users[:5])}"
                    if len(sent_users) > 5:
                        summary += f" và {len(sent_users) - 5} người khác"

                if failed_users:
                    summary += f"<br/>❌ Không gửi được cho {len(failed_users)} người"

                # Gửi tóm tắt qua kênh chat 1-1 với người gửi
                summary_channel = get_or_create_direct_chat(odoobot_partner, sender.partner_id)
                if summary_channel:
                    summary_channel.sudo().message_post(
                        body=summary,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=odoobot_partner.id,
                        body_is_html=True,
                    )

                # Gửi email tóm tắt cho người gửi
                if sender.partner_id.email:
                    mail_mail_obj.create({
                        'subject': f"📋 Tóm tắt: {self.name}",
                        'body_html': summary,
                        'email_to': sender.partner_id.email,
                        'auto_delete': True,
                    }).send()

            except Exception as e:
                _logger.error(f"Lỗi khi gửi tóm tắt: {str(e)}")

        # --- 6. CẬP NHẬT TRẠNG THÁI ---
        if sent_users:
            self.write({'sent': True})

            # Thông báo thành công
            message = f'✅ Đã gửi thông báo đến {len(sent_users)} người dùng'
            if failed_users:
                message += f'\n❌ Không gửi được cho {len(failed_users)} người'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Thành công!' if sent_users else 'Có lỗi',
                    'message': message,
                    'type': 'success' if sent_users else 'warning',
                    'sticky': True,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        else:
            error_msg = "Không thể gửi thông báo cho bất kỳ người dùng nào!"
            if failed_users:
                error_msg += f" Lỗi với {len(failed_users)} người dùng."
            raise UserError(error_msg)

    def approve(self):
        self.write({'state': 'da_duyet'})
        return True


class NotifyType(models.Model):
    _name = 'notify.type'

    name = fields.Char(string='Tên loại thông báo')
