# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    document_directory_id = fields.Many2one('document.directory', string='Directory',
                                index=True)
    document_tag_ids = fields.Many2many(
        comodel_name='document.tag',
        relation='ir_attachment_document_tag_rel', column1='attachment_id', column2='tag_id',
        string="Document Tags")
    directory_tag_ids = fields.Many2many(related="document_directory_id.tag_ids",
                                         string="Directory Tags", readonly=True)
    user_ids = fields.Many2many(related="document_directory_id.user_ids",
                                         string="Users", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super().create(vals_list)
        directory_model = self.env['document.directory']
        for attachment in attachments:
            if attachment.res_model:
                records = directory_model.search([('model_id.model', '=', attachment.res_model)])
                if records and len(records) > 0:
                    attachment.document_directory_id = records[0].id
        return attachments

    def _check_for_message_composer(self):
        """ Purpose of this method is to actualize visitor model prior to contacting
        him. Used notably for inheritance purpose, when dealing with leads that
        could update the visitor model. """
        return bool(self.env.user.partner_id and self.env.user.partner_id.email)

    def _prepare_send_email_context(self):
        return {
            'default_model': 'res.partner',
            'default_res_ids': self.env.user.partner_id.ids,
            'default_partner_ids': [self.env.user.partner_id.id],
            'default_subject': self.name,
            'default_body': '<p>Please input content email!</p>',
            'default_attachment_ids': [(4, self.id)],
        }

    def action_send_mail(self):
        self.ensure_one()
        if not self._check_for_message_composer():
            raise UserError(_("There are no contact and/or no email linked to this visitor."))
        visitor_composer_ctx = self._prepare_send_email_context()
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        compose_ctx = dict()
        compose_ctx.update(**visitor_composer_ctx)
        return {
            'name': _('Send Email'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': compose_ctx,
        }
