from odoo import models, fields, api


class SendPushWizard(models.TransientModel):
    _name = 'send.push.wizard'
    _description = 'Wizard gửi thông báo'

    template_id = fields.Many2one('web.push.template', string="Mẫu tin nhắn")
    title = fields.Char(string="Tiêu đề", required=True)
    body = fields.Text(string="Nội dung", required=True)

    # Thêm lựa chọn chế độ gửi
    send_all = fields.Boolean(string="Gửi cho tất cả người dùng", default=False)
    user_ids = fields.Many2many('res.users', string="Người nhận")

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.title = self.template_id.title
            self.body = self.template_id.body

    def action_send(self):
        if self.send_all:
            recipients = self.env['res.users'].search([('active', '=', True)])
        else:
            recipients = self.user_ids

        if not recipients:
            raise models.ValidationError("Không tìm thấy người nhận nào!")

        # Gọi hàm gửi đã có
        recipients.send_push_notification(self.title, self.body)
        return {'type': 'ir.actions.act_window_close'}

