from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError

class EvaluateApplicant:
    _name = "evaluate.applicant"
    _description = "Evaluate Applicant"

    applicant_id = fields.Many2one("hr.applicant", string="Ứng viên" )


