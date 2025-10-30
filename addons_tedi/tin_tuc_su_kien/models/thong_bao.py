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
        ('da_duyet', 'Đã duyệt')
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
        return True

    def action_save_draft(self):
        # logic lưu nháp
        self.write({'state': 'draft'})
        return True

    def action_send_notification(self):
        self.ensure_one()
        odoobot = self.env.ref('base.user_root')
        odoobot_partner = odoobot.partner_id

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
