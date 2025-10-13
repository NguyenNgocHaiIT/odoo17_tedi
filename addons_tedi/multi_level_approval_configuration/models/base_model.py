##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

from odoo import models


class BaseModel(models.AbstractModel):
    _inherit = "base"

    def write(self, vals):
        self.env["multi.approval.type"].check_rule(self, vals)
        res = super().write(vals)
        return res

    def _compute_field_value(self, field):
        """
        Check computed fields which stored=True
        """
        if field.store and any(self._ids):
            # check constraints of the fields that have been computed
            fake_vals = {f.name: 1 for f in self.pool.field_computed[field]}
            records = self.filtered("id")
            self.env["multi.approval.type"].check_rule(records, fake_vals)
        return super()._compute_field_value(field)
