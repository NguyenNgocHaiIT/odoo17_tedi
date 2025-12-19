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

            # Lấy danh sách lines tương ứng
            lines = parent.certificate_ids

            try:
                # Cố gắng tìm vị trí của rec trong lines
                rec.stt = list(lines).index(rec) + 1
            except ValueError:
                # Nếu rec chưa có trong danh sách (lỗi đang gặp), gán tạm STT bằng độ dài list + 1
                rec.stt = len(lines) + 1


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

            try:
                rec.stt = list(lines).index(rec) + 1
            except ValueError:
                rec.stt = len(lines) + 1


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

            try:
                rec.stt = list(lines).index(rec) + 1
            except ValueError:
                rec.stt = len(lines) + 1


class HREmployeeEducation(models.Model):
    _inherit = "hr.employee.education"

    applicant_id = fields.Many2one("hr.applicant", ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", required=False)

    @api.depends('employee_id.education_ids', 'applicant_id.education_ids')
    def _compute_stt(self):
        for rec in self:
            parent = rec.employee_id or rec.applicant_id
            if not parent:
                rec.stt = 0
                continue

            lines = parent.education_ids

            try:
                rec.stt = list(lines).index(rec) + 1
            except ValueError:
                rec.stt = len(lines) + 1

class HrExternalExperience(models.Model):
    _inherit = "hr.external.experience"

    applicant_id = fields.Many2one("hr.applicant", ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", required=False)

    @api.depends('employee_id.external_experience_ids', 'applicant_id.external_experience_ids')
    def _compute_stt(self):
        for rec in self:
            parent = rec.employee_id or rec.applicant_id
            if not parent:
                rec.stt = 0
                continue

            lines = parent.external_experience_ids

            try:
                rec.stt = list(lines).index(rec) + 1
            except ValueError:
                rec.stt = len(lines) + 1

# hr.external.experience