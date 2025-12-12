# -*- coding: utf-8 -*-

from odoo import _, api, models, fields
from odoo.exceptions import UserError
from odoo.http import request


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    document_share_id = fields.Many2one('document.share', string='Document Share', copy=False)

    def create_onlyoffice_document(self):
        try:
            self.env["onlyoffice.odoo.documents.access"].create({
                "document_id": self.id,
                "internal_users": "none",
                "link_access": "viewer",
            })
            self.env["onlyoffice.odoo.documents.access.user"].create({
                "document_id": self.id,
                "user_id": self.env.user.id,
                "role": "editor",
            })
            return {
                'type': 'ir.actions.act_url',
                'url': f'/onlyoffice/share/{self.id}',
                'target': 'new',
            }
        except Exception as ex:
            return {"error": _(f"Failed to create document: {ex}")}

    def share_onlyoffice_document(self):

        return {
            'type': 'ir.actions.act_window',
            'name': 'Document Share',
            'res_model': 'document.share',
            'view_id': self.env.ref('onlyoffice_custom.document_share_view_form').id,
            'view_mode': 'form',
            'res_id': self.document_share_id.id or False,
            'target': 'new',
            'context': {
                'default_document_id': self.id
            },
        }
