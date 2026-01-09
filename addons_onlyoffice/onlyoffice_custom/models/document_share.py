# -*- coding: utf-8 -*-
from odoo import api, models, fields
import uuid

class DocumentShare(models.Model):
    _name = 'document.share'
    _description = "Document Share"

    link_share = fields.Char("Link Share", readonly=True, compute='_compute_full_url_share_onlyoffice')
    access_token = fields.Char(required=True, default=lambda x: str(uuid.uuid4()), groups="documents.group_documents_user")
    user_ids = fields.Many2many('res.users', string='Users')
    document_id = fields.Many2one('documents.document', string='Document')
    folder_id = fields.Many2one('documents.folder', string='Document Folder')
    user_role_permision_ids = fields.One2many('user.role.permision', 'document_share_id', string='User role permision')
    all_user = fields.Boolean('Set all Users')
    is_dow = fields.Boolean("Download")
    is_view = fields.Boolean("View")
    is_edit = fields.Boolean("Edit")

    @api.depends('access_token')
    def _compute_full_url_share_onlyoffice(self):
        for record in self:
            record.link_share = (f'{record.get_base_url()}/onlyoffice/share/'
                               f'{self.document_id.id}')

    def create(self, vals):
        id_doc = self.env.context.get('default_document_id')
        record = super(DocumentShare, self).create(vals)
        if id_doc:
            doc = self.env['documents.document'].browse(id_doc)
            doc.write({"document_share_id": record})
            record.write({"document_id": id_doc})
        return record

    def action_share_document(self, id_child=False):
        id_folder = self.env.context.get('default_folder_id') if not id_child else id_child
        if id_folder:
            folder = self.env['documents.folder'].browse(id_folder)

            for rec in folder.document_ids:
                role_permision = []
                document_share = self.env['document.share'].search([('document_id', '=', rec.id)])
                if document_share:
                    document_share.unlink()
                document_share_new = self.env['document.share'].create({
                    "document_id": rec.id,
                    "link_share": f'{rec.get_base_url()}/onlyoffice/share/{rec.id}'
                })

                for role in self.user_role_permision_ids:
                    role_permision.append(self.env['user.role.permision'].create({
                        "user_id": role.user_id.id,
                        "role_access_ids": [(6, 0, role.role_access_ids.ids)],
                        "document_share_id": document_share_new.id
                    }).id)
                rec.write({"document_share_id": document_share_new.id})
                document_share_new.write({"user_role_permision_ids": [(6, 0, role_permision)]})

            folder.write({"document_share_id": self.id})
            self.write({"folder_id": id_folder})
            for rec in self.user_role_permision_ids:
                rec.write({"document_share_id": self.id})
            if folder.children_folder_ids:
                for rec in folder.children_folder_ids:
                    self.action_share_document(rec.id)
