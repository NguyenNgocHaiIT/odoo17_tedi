from odoo import api, fields, models, _

class HREmployeeCertificate(models.Model):
    _inherit = "hr.employee.certificate"

    applicant_id = fields.Many2one("hr.applicant", ondelete="cascade")
    employee_id = fields.Many2one(required=False)

    @api.depends('employee_id.certificate_ids', 'applicant_id.certificate_ids')
    def _compute_stt(self):
        for rec in self:
            parent = rec.employee_id or rec.applicant_id
            if not parent:
                rec.stt = 0
                continue
            lines = parent.certificate_ids
            rec.stt = list(lines).index(rec) + 1

class HREmployeeTraining(models.Model):
    _inherit = "hr.employee.training"

    applicant_id = fields.Many2one("hr.applicant", ondelete="cascade")
    employee_id = fields.Many2one(required=False)

    @api.depends('employee_id.training_ids', 'applicant_id.training_ids')
    def _compute_stt(self):
        for rec in self:
            parent = rec.employee_id or rec.applicant_id
            if not parent:
                rec.stt = 0
                continue
            lines = parent.training_ids
            rec.stt = list(lines).index(rec) + 1


class HREmployeeWorkProcessOld(models.Model):
    _inherit = "hr.employee.work.process.old"

    applicant_id = fields.Many2one("hr.applicant", ondelete="cascade")
    employee_id = fields.Many2one(required=False)

    @api.depends('employee_id.experience_ids', 'applicant_id.experience_ids')
    def _compute_stt(self):
        for rec in self:
            parent = rec.employee_id or rec.applicant_id
            if not parent:
                rec.stt = 0
                continue
            lines = parent.experience_ids
            rec.stt = list(lines).index(rec) + 1



class HREmployeeEducation(models.Model):
    _inherit = "hr.employee.education"

    applicant_id = fields.Many2one("hr.applicant", ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", required=False)

    @api.depends('employee_id.education_ids', 'applicant_id.education_ids')
    def _compute_stt(self):
        for rec in self:
            # Xác định cha là employee hay applicant
            parent = rec.employee_id or rec.applicant_id
            if not parent:
                rec.stt = 0
                continue
            # Lấy danh sách đúng
            lines = parent.education_ids
            rec.stt = list(lines).index(rec) + 1