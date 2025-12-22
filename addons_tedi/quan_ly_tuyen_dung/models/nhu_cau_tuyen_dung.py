# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, AccessError, UserError


class RecruitmentNeeds(models.Model):
    _name = "recruitment.needs"
    _description = "Recruitment Needs"

    name = fields.Many2one(
        "recruitment.survey",
        string="Tên đợt khảo sát",
        domain=[('state', '=', 'in_process')],
    )

    create_date = fields.Date(
        string="Ngày đăng ký",
        readonly=True,
        default=fields.Date.context_today,
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban đăng ký',
        default=lambda self: self.env.user.employee_id.department_id
    )

    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('confirmed', 'Đã xác nhận'),
    ], string="Trạng thái", default='draft')

    line_ids = fields.One2many(
        'recruitment.needs.line',
        'recruitment_needs_id',
        string='Chi tiết nhu cầu',
    )

    def _check_unique_job(self):
        for rec in self:
            jobs = rec.line_ids.mapped('job_id')
            if len(jobs) != len(set(jobs.ids)):
                raise UserError(_("Bạn không được chọn 2 vị trí tuyển dụng giống nhau trong cùng một phiếu."))

    @api.model
    def create(self, vals):
        if not vals.get('department_id'):
            employee = self.env.user.employee_id
            if employee and employee.department_id:
                vals['department_id'] = employee.department_id.id
        res = super().create(vals)
        res._check_unique_job()
        return res

    def write(self, vals):
        res = super().write(vals)
        self._check_unique_job()
        return res

    def action_approve(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Chỉ được duyệt khi phiếu đang ở trạng thái 'Dự thảo'."))
            if not rec.line_ids:
                raise UserError(_("Bạn phải nhập ít nhất 1 dòng nhu cầu tuyển dụng trước khi xác nhận."))
            rec.state = "confirmed"


class RecruitmentNeedsLine(models.Model):
    _name = 'recruitment.needs.line'
    _description = "Recruitment Needs Line"

    job_id = fields.Many2one("hr.job", string="Vị trí tuyển dụng", required=True)
    experience_id = fields.Many2one("experience.request", string="Yêu cầu kinh nghiệm")

    amount = fields.Integer(string="Số lượng cần tuyển", default=1)

    # 1. MỨC LƯƠNG DỰ KIẾN
    expected_salary = fields.Float(string="Mức lương dự kiến", default=0)

    # 2. CÁC TRƯỜNG LƯU TRỮ TIẾN TRÌNH (Ẩn trên view, hiện trên popup)
    qty_q1 = fields.Integer(string="Quý 1", default=0)
    qty_q2 = fields.Integer(string="Quý 2", default=0)
    qty_q3 = fields.Integer(string="Quý 3", default=0)
    qty_q4 = fields.Integer(string="Quý 4", default=0)

    current_employee_count = fields.Integer(
        string="Nhân sự hiện có",
        compute="_compute_current_employee_count"
    )

    professional_qualification = fields.Selection([
        ("bachelor", "Cử nhân"),
        ("engineer", "Kỹ sư"),
        ("master", "Thạc sĩ"),
        ("PhD", "Tiến sĩ"),
    ], string="Yêu cầu chuyên môn")

    note = fields.Char("Ghi chú")

    recruitment_needs_id = fields.Many2one("recruitment.needs", string="Nhu cầu tuyển dụng")

    # --- SQL CONSTRAINT: CHECK LƯƠNG > 0 ---
    _sql_constraints = [
        ('check_expected_salary_positive',
         'CHECK(expected_salary > 0)',
         'Mức lương dự kiến phải lớn hơn 0.')
    ]

    @api.depends('job_id', 'recruitment_needs_id.department_id')
    def _compute_current_employee_count(self):
        for rec in self:
            department = rec.recruitment_needs_id.department_id
            job = rec.job_id
            if department and job:
                count = self.env['hr.employee'].search_count([
                    ('department_id', '=', department.id),
                    ('job_id', '=', job.id),
                    ('active', '=', True)
                ])
                rec.current_employee_count = count
            else:
                rec.current_employee_count = 0

    # --- ACTION MỞ POPUP ---
    def action_open_progress_wizard(self):
        self.ensure_one()
        return {
            'name': _('Cấu hình tiến trình bổ sung'),
            'type': 'ir.actions.act_window',
            'res_model': 'recruitment.progress.wizard',
            'view_mode': 'form',
            'target': 'new',  # Hiển thị dạng Popup
            'context': {
                'default_line_id': self.id,
                'default_amount_total': self.amount,
                # Truyền giá trị hiện tại vào wizard
                'default_qty_q1': self.qty_q1,
                'default_qty_q2': self.qty_q2,
                'default_qty_q3': self.qty_q3,
                'default_qty_q4': self.qty_q4,
            }
        }


# --- MODEL WIZARD (POPUP) ---
class RecruitmentProgressWizard(models.TransientModel):
    _name = 'recruitment.progress.wizard'
    _description = 'Cấu hình tiến trình tuyển dụng theo quý'

    line_id = fields.Many2one('recruitment.needs.line', string="Dòng nhu cầu", required=True)
    amount_total = fields.Integer(string="Tổng số lượng cần tuyển", readonly=True)

    qty_q1 = fields.Integer(string="Quý 1")
    qty_q2 = fields.Integer(string="Quý 2")
    qty_q3 = fields.Integer(string="Quý 3")
    qty_q4 = fields.Integer(string="Quý 4")

    # Validation (Tùy chọn): Kiểm tra tổng 4 quý có khớp tổng số lượng không
    @api.constrains('qty_q1', 'qty_q2', 'qty_q3', 'qty_q4')
    def _check_total_qty(self):
        for rec in self:
            total_plan = rec.qty_q1 + rec.qty_q2 + rec.qty_q3 + rec.qty_q4
            if total_plan > rec.amount_total:
                raise UserError(
                    _("Tổng số lượng phân bổ 4 quý (%s) không được lớn hơn số lượng cần tuyển (%s).") % (total_plan,
                                                                                                         rec.amount_total))

    def action_confirm(self):
        """Lưu dữ liệu từ Wizard về Line gốc"""
        self.ensure_one()
        self.line_id.write({
            'qty_q1': self.qty_q1,
            'qty_q2': self.qty_q2,
            'qty_q3': self.qty_q3,
            'qty_q4': self.qty_q4,
        })
        return {'type': 'ir.actions.act_window_close'}