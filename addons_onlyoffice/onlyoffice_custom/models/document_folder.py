# -*- coding: utf-8 -*-
from odoo import api, models, fields


class DocumentFolder(models.Model):
    _inherit = 'documents.folder'

    user_access_ids = fields.Many2many('res.users',string='User Access')

    document_share_id = fields.Many2one('document.share',string='Share')

    def write(self, vals):
        res = super(DocumentFolder, self).write(vals)
        self.add_user_acces_child_folder()
        return res

    def add_user_acces_child_folder(self):
        if self.children_folder_ids:
            user_ids = list(map(lambda x: x.id, self.user_access_ids))
            for rec in self.children_folder_ids:
                rec.write({'user_access_ids': [(6,0,user_ids)]})

    def open_share_onlyoffice(self):
        view_id = self.env.ref('onlyoffice_custom.document_share_view_form_folder').id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Document Share',
            'res_model': 'document.share',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'view_mode': 'form',
            'res_id': self.document_share_id.id or False,
            'target': 'new',
            'context': {
                'default_folder_id': self.id
            },
        }
