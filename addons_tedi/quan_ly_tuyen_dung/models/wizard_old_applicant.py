# models/wizard_old_applicant.py
from odoo import models, fields, api, _

class OldApplicantSuggestWizard(models.TransientModel):
    _name = "old.applicant.suggest.wizard"
    _description = "Chọn ứng viên cũ"

    detail_id = fields.Many2one("recruitment.plan.detail", required=True)
    applicant_ids = fields.Many2many(
        "hr.applicant",
        string="Ứng viên đủ điều kiện",
        domain=['|', ('refuse_reason_id', '!=', False), ('active', '=', False)],
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        detail_id = self.env.context.get('default_detail_id') or res.get('detail_id')
        if detail_id:
            detail = self.env['recruitment.plan.detail'].browse(detail_id)
            # ⬇️ nạp sẵn các ứng viên đã chọn trước đó
            res['applicant_ids'] = [(6, 0, detail.with_context(active_test=False).nomination_ids.ids)]
        return res

    def action_confirm(self):
        self.ensure_one()
        detail = self.detail_id
        # Hợp nhất: đã có + vừa chọn
        new_ids = (detail.nomination_ids | self.applicant_ids).ids
        detail.nomination_ids = [(6, 0, new_ids)]
        return {'type': 'ir.actions.act_window_close'}
