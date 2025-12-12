from odoo import models, fields

class RecruitmentJob(models.Model):
    _inherit = 'hr.job'

    email_alias = fields.Char(string='Email Alias')
    work_location_id = fields.Many2one(
        'hr.work.location',
        string='Nơi làm việc'
    )

    recruiter_id = fields.Many2one(
        "hr.employee",
        string="Người tuyển dụng",
        help="Nhân viên phụ trách tuyển dụng cho vị trí này."
    )

    dot_tuyen_dung = fields.Many2one(
        "recruitment.plan",
        string="Đợt tuyển dụng",
        domain="[('recruitment_status', 'in', ['director_approve'])]")



