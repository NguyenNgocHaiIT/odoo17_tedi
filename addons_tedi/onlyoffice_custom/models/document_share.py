# -*- coding: utf-8 -*-
from odoo import api, models, fields


class DocumentShare(models.Model):
    _name = 'document.share'
    _description = "Document Share"

    link_share = fields.Char("Link Share", readonly=True)
    user_ids = fields.Many2many('res.users', string='Users')
    document_id = fields.Many2one('ir.attachment', string='Document')
    public_access = fields.Boolean("Public", default=False)
    role_access_ids = fields.Many2many('role.onlyoffice', string='Role Access')
    user_role_permision_ids = fields.One2many('user.role.permision', 'document_share_id', string='User role permision')

    def create(self, vals):
        id_doc = self.env.context.get('default_document_id')
        record = super(DocumentShare, self).create(vals)
        if id_doc:
            link_share = self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url') + f"/onlyoffice/share/{id_doc}"
            doc = self.env['ir.attachment'].browse(id_doc)
            doc.write({"document_share_id": record})
            record.write({"document_id": id_doc, "link_share": link_share})
        return record

    @api.onchange('public_access')
    def change_role_access(self):
        if not self.public_access:
            self.role_access_ids = [(5,)]

    def action_share_document(self):
        id_folder = self.env.context.get('default_folder_id')
        if id_folder:
            direc = self.env['document.directory'].browse(id_folder)
            direc.set_role_child_dir(direc)
