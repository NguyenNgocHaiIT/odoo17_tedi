# -*- coding: utf-8 -*-
from odoo import api, models, fields


class Directory(models.Model):
    _inherit = 'document.directory'

    document_share_id = fields.Many2one('document.share', string='Document Share', copy=False)

    def set_role_onlyoffice(self, dir):
        for rec in dir.attachment_ids:
            rec.document_share_id.unlink()
            self.env['document.share'].search([("document_id", '=', rec.id)]).unlink()

            link_share = self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url') + f"/onlyoffice/share/{rec.id}"
            list_role_user = []
            roll_access_public = []

            document_share = self.env['document.share'].create({
                "link_share": link_share,
                "document_id": rec.id,
                "public_access": self.document_share_id.public_access
            })
            if self.document_share_id.public_access:
                for roll_public in self.document_share_id.role_access_ids:
                    roll_access_public.append(roll_public.id)

            for role in self.document_share_id.user_role_permision_ids:
                list_role_user.append(self.env['user.role.permision'].create({
                    "user_id": role.user_id.id,
                    "role_access_ids": [(6, 0, role.role_access_ids.ids)],
                    "document_share_id": document_share.id
                }).id)
            document_share.write({"user_role_permision_ids": [(6, 0, list_role_user)], "role_access_ids":[(6, 0, roll_access_public)]})
            rec.write({"document_share_id": document_share.id})
        if self.id != dir.id:
            list_role_user = []
            user_ids = []
            for role in self.document_share_id.user_role_permision_ids:
                user_ids.append(role.user_id.id)
                list_role_user.append(self.env['user.role.permision'].create({
                    "user_id": role.user_id.id,
                    "role_access_ids": [(6, 0, role.role_access_ids.ids)]
                }).id)
            document_share = self.env['document.share'].create({
                "public_access": self.document_share_id.public_access,
                "user_role_permision_ids": [(6, 0, list_role_user)],
                "role_access_ids": [(6, 0, self.document_share_id.role_access_ids.ids)]
            })
            dir.write({
                "document_share_id": document_share, "user_ids": [(6, 0, user_ids)]
            })

    def set_role_child_dir(self, child_dir, update=True):
        if update:
            if not child_dir:
                if child_dir.child_ids:
                    return
            if self.id == child_dir.id:
                self.set_role_onlyoffice(self)
            for rec in child_dir.child_ids:
                self.set_role_onlyoffice(rec)
                self.set_role_child_dir(rec, rec.child_ids)

    def share_onlyoffice_document(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Document Share Folder',
            'res_model': 'document.share',
            'view_id': self.env.ref('onlyoffice_custom.document_share_view_form_folder').id,
            'view_mode': 'form',
            'res_id': self.document_share_id.id or False,
            'target': 'new',
            'context': {
                'default_folder_id': self.id
            },
        }
