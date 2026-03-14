from odoo import models, fields, api


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

    dot_tuyen_dung_quy = fields.Many2one(
        "recruitment.plan",
        string="Đợt tuyển dụng",
        domain="[('recruitment_status', 'in', ['director_approve'])]"
    )

    # --- TRƯỜNG MỚI ĐỂ HIỂN THỊ TÊN KÈM QUÝ TRÊN KANBAN ---
    job_kanban_name = fields.Char(
        string="Tên Kanban", compute="_compute_job_kanban_name")

    @api.depends('name')
    def _compute_job_kanban_name(self):
        # Lấy ngày hiện tại của hệ thống để suy ra Quý
        today = fields.Date.context_today(self)
        current_year = today.year

        for job in self:
            if job.name:
                job.job_kanban_name = f"{job.name} - Năm {current_year}"
            else:
                job.job_kanban_name = ""


class RecruitmentConstant(models.Model):
    _name = 'recruitment.constant'
    _description = 'Recruitment Constant'

    code = fields.Char(string='Code')
    name = fields.Char(string='Name')
    employee_id = fields.Many2one('hr.employee', string="Nhân viên phụ trách")
