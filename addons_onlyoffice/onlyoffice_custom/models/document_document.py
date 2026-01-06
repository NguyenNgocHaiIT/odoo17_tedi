# -*- coding: utf-8 -*-
from odoo import api, models, fields, _


class Documents(models.Model):
    _inherit = 'documents.document'

    document_share_id = fields.Many2one("document.share")
    download = fields.Boolean("Download", default=True)
    edit = fields.Boolean("Edit", default=True)
    view = fields.Boolean("View", default=True)

    def open_share_onlyoffice(self):
        view_id = self.env.ref('onlyoffice_custom.document_share_view_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Document Share'),
            'res_model': 'document.share',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'view_mode': 'form',
            'res_id': self.document_share_id.id or False,
            'target': 'new',
            'context': {
                'default_document_id': self.id
            },
        }
