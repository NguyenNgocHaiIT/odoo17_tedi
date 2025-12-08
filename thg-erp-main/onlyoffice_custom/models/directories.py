# -*- coding: utf-8 -*-
from odoo import api, models, fields

class Directory(models.Model):
    _inherit = 'document.directory'

    role_access_ids = fields.Many2many('role.onlyoffice', string='Role Access')
    public_access = fields.Boolean("Public", default=False)

    def create(self, vals_list):
        record = super(Directory, self).create(vals_list)
        record.set_role_child_dir(child_dir = record)
        return record

    def write(self, vals_list):
        record = super(Directory, self).write(vals_list)
        self.set_role_child_dir(child_dir = self)
        return record

    def set_role_onlyoffice(self, dir):
        for rec in dir.attachment_ids:
            rec.document_share_id.unlink()
            self.env['document.share'].search([("document_id",'=', rec.id)]).unlink()

            link_share = self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url') + f"/onlyoffice/editor/{rec.id}"
            document_share = self.env['document.share'].create({
                "link_share": link_share,
                "user_ids": [(6, 0, self.user_ids.ids)],
                "document_id": rec.id,
                "role_access_ids": [(6, 0, self.role_access_ids.ids)],
                "public_access": dir.public_access
            })
            rec.write({'document_share_id': document_share.id})

    def set_role_child_dir(self, child_dir, update=True):
        if update:
            if not child_dir:
                if  child_dir.child_ids:
                    return
            if self.id == child_dir.id:
                self.set_role_onlyoffice(self)
            for rec in child_dir.child_ids:
                self.set_role_onlyoffice(rec)
                self.set_role_child_dir(rec, True)