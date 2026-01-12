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

        # THÊM field mới

    user_ids = fields.Many2many(
        'res.users',
        'documents_folder_write_users_rel',
        'folder_id', 'user_id',
        string="Write Users",
        help='Users able to see the workspace and read/create/edit its documents.'
    )

    read_user_ids = fields.Many2many(
        'res.users',
        'documents_folder_read_users_rel',
        'folder_id', 'user_id',
        string="Read Users",
        help='Users able to see the workspace and read its documents without create/edit rights.'
    )

    # ẨN field cũ
    group_ids = fields.Many2many(groups='base.group_no_one')  # Chỉ superuser mới thấy
    read_group_ids = fields.Many2many(groups='base.group_no_one')  # Chỉ superuser mới thấy

    @api.depends('user_ids', 'read_user_ids')
    @api.depends_context('uid')
    def _compute_has_write_access(self):
        """Override để tính toán quyền dựa trên user thay vì group"""
        current_user = self.env.user
        has_write_access = self.user_has_groups('documents.group_documents_manager')

        if has_write_access:
            self.has_write_access = True
            return

        for record in self:
            # Kiểm tra quyền dựa trên user
            folder_has_users = not record.user_ids and not record.read_user_ids or (current_user in record.user_ids)
            record.has_write_access = folder_has_users

    def _get_inherited_settings_as_vals(self):
        """Override để kế thừa cài đặt user thay vì group"""
        res = super()._get_inherited_settings_as_vals()
        self.ensure_one()
        res.update({
            'user_ids': [(6, 0, self.user_ids.ids)],
            'read_user_ids': [(6, 0, self.read_user_ids.ids)],
        })
        return res

    def copy(self, default=None):
        """Override copy để sao chép user_ids"""
        folder = super().copy(default)
        # Sao chép user_ids và read_user_ids từ folder gốc
        folder.write({
            'user_ids': [(6, 0, self.user_ids.ids)],
            'read_user_ids': [(6, 0, self.read_user_ids.ids)],
        })
        return folder

    @api.depends('user_ids', 'read_user_ids')
    def _compute_debug_access(self):
        for folder in self:
            folder.debug_user_ids = folder.user_ids.ids
            folder.debug_read_user_ids = folder.read_user_ids.ids
            folder.debug_current_user = self.env.user.id
            folder.debug_user_has_write = self.env.user in folder.user_ids
            folder.debug_user_has_read = self.env.user in folder.read_user_ids

    debug_user_ids = fields.Text(compute='_compute_debug_access')
    debug_read_user_ids = fields.Text(compute='_compute_debug_access')
    debug_current_user = fields.Integer(compute='_compute_debug_access')
    debug_user_has_write = fields.Boolean(compute='_compute_debug_access')
    debug_user_has_read = fields.Boolean(compute='_compute_debug_access')