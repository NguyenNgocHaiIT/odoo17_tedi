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

    # SỬA: Thay user_id bằng department_id
    # Mặc định lấy phòng ban của nhân viên gắn với user đang login
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

    # ---------------------------------------------------------
    # HÀM CHECK TRÙNG LẶP (ĐÃ SỬA)
    # ---------------------------------------------------------
    def _check_unique_job(self):
        for rec in self:
            # SỬA: Đổi course_id thành job_id
            jobs = rec.line_ids.mapped('job_id')

            # Logic: Nếu số lượng job khác số lượng job duy nhất -> có trùng
            if len(jobs) != len(set(jobs.ids)):
                raise UserError(_("Bạn không được chọn 2 vị trí tuyển dụng giống nhau trong cùng một phiếu."))

    @api.model
    def create(self, vals):
        """Tự gán phòng ban của user hiện tại nếu chưa set."""
        if not vals.get('department_id'):
            # Lấy phòng ban từ employee của user đang đăng nhập
            employee = self.env.user.employee_id
            if employee and employee.department_id:
                vals['department_id'] = employee.department_id.id

        res = super().create(vals)

        # SỬA: Gọi đúng tên hàm _check_unique_job
        res._check_unique_job()
        return res

    def write(self, vals):
        res = super().write(vals)

        # SỬA: Gọi đúng tên hàm _check_unique_job
        self._check_unique_job()
        return res

    # =========================

    def action_approve(self):
        for rec in self:
            # SỬA: State của bạn là 'draft', không phải 'pending'
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

    professional_qualification = fields.Selection([
        ("bachelor", "Cử nhân"),
        ("engineer", "Kỹ sư"),
        ("master", "Thạc sĩ"),
        ("PhD", "Tiến sĩ"),
    ], string="Yêu cầu chuyên môn")

    note = fields.Char("Ghi chú")

    recruitment_needs_id = fields.Many2one("recruitment.needs", string="Nhu cầu tuyển dụng")