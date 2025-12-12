from odoo import models, api, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, vals):
        group_documents_user = self.env.ref('windx_documents_management_preview.group_documents_user', raise_if_not_found=False)
        if group_documents_user:
            if 'groups_id' in vals:
                vals['groups_id'].append((4, group_documents_user.id))
            else:
                vals['groups_id'] = [(4, group_documents_user.id)]
        return super().create(vals)
