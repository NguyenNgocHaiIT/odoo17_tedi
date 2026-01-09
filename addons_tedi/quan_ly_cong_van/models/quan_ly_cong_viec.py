from datetime import timedelta

from pkg_resources import require

from odoo import models, fields, api
from odoo.exceptions import UserError
import odoo
import logging

_logger = logging.getLogger(__name__)


class OfficeTask(models.Model):
    _inherit = 'project.task'

    don_vi = fields.Many2one('hr.department', string='Đơn vị')

    task_type = fields.Selection([
        ('cong_van_di', 'Công việc của công văn đi'),
        ('quyet_dinh', 'công việc của quyết định'),
        ('cong_van_di_noi_bo', 'công việc của công văn đi nội bộ'),
        ('van_ban_hdqt', 'công việc của văn bản HĐQT'),
    ], string='Loại công việc')

    da_giao_viec = fields.Boolean(string="Đã giao việc", default=False)
    da_tao_cong_van = fields.Boolean(string="Đã tạo công văn", default=False)

    @api.model
    def create(self, vals):
        return super().create(vals)


    def write(self, vals):
        return super().write(vals)

    def action_create_document(self):
        outgoing_form_id = self.env.ref('quan_ly_cong_van.office_document_outgoing_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo công văn đi',
            'res_model': 'office.document',
            'view_mode': 'form',
            'view_id': outgoing_form_id,
            'target': 'new',
            'context': {
                'default_document_type': 'outgoing',
                'default_task_id': self.id,
                'default_trich_yeu': self.name,
            },
        }

    def action_create_resolution(self):
        resolution_form_id = self.env.ref('quan_ly_cong_van.office_document_resolution_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo quyết định',
            'res_model': 'office.document',
            'view_mode': 'form',
            'view_id': resolution_form_id,
            'target': 'new',
            'context': {
                'default_document_type': 'resolution',
                'default_task_id': self.id,
                'default_trich_yeu': self.name,
            },
        }

    def action_create_internal_document(self):
        outgoing_form_id = self.env.ref('quan_ly_cong_van.office_document_outgoing_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo công văn đi',
            'res_model': 'office.document',
            'view_mode': 'form',
            'view_id': outgoing_form_id,
            'target': 'new',
            'context': {
                'default_document_type': 'outgoing_internal',
                'default_task_id': self.id,
                'default_trich_yeu': self.name,
            },
        }

    def action_create_director_document(self):
        director_form_id = self.env.ref('quan_ly_cong_van.office_document_resolution_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo công văn',
            'res_model': 'office.document',
            'view_mode': 'form',
            'view_id': director_form_id,
            'target': 'new',
            'context': {
                'default_document_type': 'director',
                'default_task_id': self.id,
                'default_trich_yeu': self.name,
            },
        }

    def action_confirm_task(self):
        self.ensure_one()
        if not self.don_vi:
            raise UserError("Vui lòng chọn đơn vị xử lý để giao việc")

        # 1. Đổi trạng thái task
        self.da_giao_viec = True

        # 2. Lấy manager của đơn vị
        manager_partner = False
        if self.don_vi.manager_id and self.don_vi.manager_id.user_id and self.don_vi.manager_id.user_id.partner_id:
            manager_partner = self.don_vi.manager_id.user_id.partner_id

        if manager_partner:
            odoobot = self.env.ref('base.user_root').partner_id
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

            # 3. Gửi notification popup qua bus
            self.env['bus.bus']._sendone(
                manager_partner,
                'simple_notification',
                {
                    'title': '📌 Giao việc mới',
                    'message': f"Đơn vị của bạn nhận được task: {self.name}",
                    'sticky': False,
                    'type': 'info',
                }
            )

            # 4. Gửi tin nhắn chat qua OdooBot
            try:
                # Tìm hoặc tạo kênh chat 1-1
                domain = [
                    ('channel_type', '=', 'chat'),
                    ('channel_member_ids.partner_id', 'in', [odoobot.id, manager_partner.id])
                ]
                channels = self.env['discuss.channel'].sudo().search(domain)
                channel = False
                for ch in channels:
                    members = ch.channel_member_ids.mapped('partner_id')
                    if set(members.ids) == {odoobot.id, manager_partner.id}:
                        channel = ch
                        break
                if not channel:
                    channel = self.env['discuss.channel'].sudo().create({
                        'name': f"Giao task: {self.name}",
                        'channel_type': 'chat',
                        'channel_member_ids': [
                            (0, 0, {'partner_id': odoobot.id}),
                            (0, 0, {'partner_id': manager_partner.id}),
                        ]
                    })
                channel.sudo().message_post(
                    body=f"📌 Task '{self.name}' đã được giao cho đơn vị {self.don_vi.name}.",
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot.id,
                    body_is_html=False,
                )
            except Exception as e:
                _logger.error(f"Lỗi gửi chat cho {manager_partner.name}: {str(e)}")

            # 5. Gửi email thông báo
            if manager_partner.email:
                subject = f"Giao việc: {self.name}"
                body_html = f"""
                    <p>Kính gửi {manager_partner.name},</p>
                    <p>Đơn vị của bạn đã nhận task: <b>{self.name}</b></p>
                    <p>Chi tiết:</p>
                    <ul>
                        <li>Nội dung: {self.name}</li>
                        <li>Thời hạn: {self.date_deadline if self.date_deadline else 'Chưa có'}</li>
                        <li>Loại công việc: {self.task_type}</li>
                    </ul>
                    <p>Xem chi tiết tại: <a href="{web_url}/web#id={self.id}&model=project.task&view_type=form">{self.name}</a></p>
                    <p>Trân trọng,</p>
                    <p>{self.env.user.name}</p>
                """
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': manager_partner.email,
                }).send()

        return True

    def action_delete_task(self):
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Công việc',
            'res_model': 'project.task',
            'view_mode': 'tree',
            'views': [
                (self.env.ref('quan_ly_cong_van.view_office_task_tree').id, 'tree'),
            ],
            'target': 'main',
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'task_type' in fields_list and self._context.get('task_type'):
            res['task_type'] = self._context.get('task_type')
        return res