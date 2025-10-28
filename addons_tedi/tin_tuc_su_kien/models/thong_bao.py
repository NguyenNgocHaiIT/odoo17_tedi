from odoo import api, models, fields
from odoo.exceptions import UserError


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
    send_indivisual = fields.Many2many(
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

        # --- 1. LẤY DANH SÁCH NGƯỜI NHẬN ---
        users = self.env['res.users'].sudo()

        if self.send_all:
            users = self.env['res.users'].sudo().search([])
        else:
            if self.send_indivisual:
                users |= self.send_indivisual.sudo()
            if self.send_department:
                dept_users = self.env['hr.employee'].sudo().search([
                    ('department_id', 'in', self.send_department.ids),
                    ('user_id', '!=', False)
                ]).mapped('user_id')
                users |= dept_users

        # LOẠI TRÙNG + LOẠI ODOOBOT
        users = (users - odoobot).browse(set(users.ids))

        if not users:
            raise UserError("Chưa có đối tượng để gửi thông báo!")

        # --- 2. NỘI DUNG ---
        content = self.content or ""
        body = f"""
            <p><strong>Bạn nhận được thông báo mới:</strong></p>
            <p><strong>{self.name}</strong></p>
            <p>{content}</p>
            <p><a href="/web#id={self.id}&model={self._name}&view_type=form"
                  style="background:#875A7B;color:black;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                Xem chi tiết
            </a></p>
        """

        # --- 3. GỬI 1-1 CHO TỪNG NGƯỜI ---
        for user in users:
            if not user.partner_id:
                continue

            # TÌM CHANNEL CHAT CHỈ VỚI 2 NGƯỜI
            channel = self.env['discuss.channel'].sudo().search([
                ('channel_type', '=', 'chat'),
                ('channel_partner_ids', 'in', [odoobot.partner_id.id, user.partner_id.id]),
                ('channel_partner_ids', '=', 2),  # BẮT BUỘC 2 NGƯỜI
            ], limit=1)

            # TẠO MỚI NẾU CHƯA CÓ
            if not channel:
                channel = self.env['discuss.channel'].sudo().with_context(
                    mail_create_nosubscribe=True,
                    odoobot_no_welcome_message=True
                ).create({
                    'name': f"Thông báo với {user.name}",
                    'channel_type': 'chat',
                    'channel_partner_ids': [(4, odoobot.partner_id.id), (4, user.partner_id.id)],
                })

            # GỬI TIN NHẮN
            channel.sudo().message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=odoobot.partner_id.id,
                body_is_html='True',
            )

            # GỬI EMAIL
            if user.partner_id.email:
                self.env['mail.mail'].sudo().create({
                    'subject': self.name,
                    'body_html': body,
                    'email_to': user.partner_id.email,
                    'auto_delete': True,
                }).send()

        # --- 4. GỬI TÓM TẮT CHO NGƯỜI GỬI ---
        sender = self.env.user
        if sender != odoobot and sender.partner_id:
            summary = f"Thông báo <strong>{self.name}</strong> đã gửi đến: " + ", ".join(users.mapped('name'))

            # Tìm channel 1-1 với người gửi
            summary_channel = self.env['discuss.channel'].sudo().search([
                ('channel_type', '=', 'chat'),
                ('channel_partner_ids', 'in', [odoobot.partner_id.id, sender.partner_id.id]),
                ('channel_partner_ids', '=', 2),
            ], limit=1)

            if not summary_channel:
                summary_channel = self.env['discuss.channel'].sudo().create({
                    'name': f"Tóm tắt với {sender.name}",
                    'channel_type': 'chat',
                    'channel_partner_ids': [(4, odoobot.partner_id.id), (4, sender.partner_id.id)],
                })

            summary_channel.sudo().message_post(
                body=summary,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=odoobot.partner_id.id,
                body_is_html='True',
            )

            if sender.partner_id.email:
                self.env['mail.mail'].sudo().create({
                    'subject': f"Tóm tắt: {self.name}",
                    'body_html': summary,
                    'email_to': sender.partner_id.email,
                    'auto_delete': True,
                }).send()

        self.write({'sent': True})
        return True

    def approve(self):
        self.write({'state': 'da_duyet'})
        return True


class NotifyType(models.Model):
    _name = 'notify.type'

    name = fields.Char(string='Tên loại thông báo')
