from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError

# ==== NHÓM ĐƯỢC PHÉP TẠO/SỬA ỨNG VIÊN ====
HR_OFFICER = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
COMMITTEE  = "quan_ly_tuyen_dung.group_recruitment_committee"
DIRECTOR   = "quan_ly_tuyen_dung.group_recruitment_director"
BOARD      = "quan_ly_tuyen_dung.group_recruitment_board"
BASE      = 'base.group_user'

def _user_is_applicant_editor(env):
    u = env.user
    return any([
        u.has_group(HR_OFFICER),
        u.has_group(COMMITTEE),
        u.has_group(DIRECTOR),
        u.has_group(BOARD),
        u.has_group(BASE)
    ])


QUAL_SELECTION = [
    ("bachelor", "Cử nhân"),
    ("engineer", "Kỹ sư"),
    ("master", "Thạc sĩ"),
    ("PhD", "Tiến sĩ"),
]

class Applicant(models.Model):
    _inherit = 'hr.applicant'
    _rec_name = "partner_name"

    # ==== THÔNG TIN BỔ SUNG ====
    dob = fields.Date(string="Sinh ngày")
    country_id = fields.Many2one('res.country', string="Quốc tịch")

    folk = fields.Char(string="Dân tộc")
    current_job = fields.Char(string="Nghề nghiệp")
    address = fields.Char(string="Địa chỉ")
    suitability = fields.Selection(
        [('yes', 'Có phù hợp'), ('no', 'Không phù hợp')],
        string='Khảo sát phù hợp'
    )

    suitability_doc_ids = fields.Many2many(
        "ir.attachment", "applicant_suitability_attachment_rel",
        "applicant_id", "attachment_id",
        string="Đính kèm"
    )

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "applicant_rate_attachment_rel",
        "applicant_id", "attachment_id",
        string="Tài liệu đánh giá ứng viên"
    )

    isEmp = fields.Boolean(string="Is Emp", default=False)

    recruitment_plan_id = fields.Many2one("recruitment.plan", string="Đợt tuyển dụng")

    education_level_ids = fields.One2many('education.level', 'applicant_id', string="Trình độ học vấn")
    old_work_process_ids = fields.One2many('old.work.process', 'applicant_id', string="Quá trình công tác cũ")
    professor_license_ids = fields.One2many('professor.license', 'applicant_id', string="Chứng chỉ hành nghề")
    training_process_ids = fields.One2many('training.process', 'applicant_id', string="Quá trình đào tạo")

    highest_professional_qualification = fields.Selection(
        selection=QUAL_SELECTION,
        string="Trình độ cao nhất",
        compute="_compute_highest_professional_qualification",
        store=True,
        index=True,
    )
    education_level_count = fields.Integer(
        string="Số bậc học",
        compute="_compute_edu_count",
        store=True,
    )

    # Đánh giá sau phỏng vấn
    professional_skill = fields.Char(string="Khả năng chuyên môn")
    work_experience = fields.Char(string="Kinh nghiệm công tác")
    other_check =fields.Char(string="Kiểm tra khác")
    appearance = fields.Char(string ="Ngoại hình")
    expression_skill = fields.Char(string = "Kỹ năng diễn đạt")
    communication_skill = fields.Char(string ="Kỹ năng giao tiếp")
    integration_skill = fields.Char(string = "Kỹ năng hội nhập")
    professional_knowledge = fields.Char(string="Khả năng hiểu biết về chuyên môn")
    career_objective= fields.Char(string ="Nguyện vọng của ứng viên")

    proposal_unit = fields.Text(string="Đề xuất (Đơn vị)")
    proposal_hr   = fields.Text(string="Đề xuất (Phòng TCCB - LD)")

    def action_open_applicant_evaluation_page(self):
        self.ensure_one()
        view = self.env.ref('quan_ly_tuyen_dung.hr_applicant_eval_form_standalone')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bảng đánh giá ứng viên sau phỏng vấn'),
            'res_model': 'hr.applicant',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'current',  # hoặc 'new'
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_submit_eval(self):
        self.ensure_one()
        # logic xử lý hoặc thông báo
        return self.env.ref(
            'quan_ly_tuyen_dung.action_report_applicant_evaluation'
        ).report_action(self)

    def action_print_applicant_evaluation(self):
        self.ensure_one()
        return self.env.ref(
            'quan_ly_tuyen_dung.action_report_applicant_evaluation'
        ).report_action(self)

    # ==== CỜ CHỐNG ĐẾM TRÙNG ====
    hired_counters_done = fields.Boolean(string="Đã cập nhật counters khi tuyển", default=False)

    # ================== ACTION: mở form trong modal ==================
    def action_open_applicant_from_wizard(self):
        self.ensure_one()
        view_id = self.env.context.get('form_view_ref') or 'hr_recruitment.hr_applicant_view_form'
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ứng viên',
            'res_model': 'hr.applicant',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(self.env.ref(view_id).id, 'form')],
            'target': 'new',
            'context': dict(self.env.context, active_id=self.id),
        }

    # ================== DOMAIN HELPER ==================
    def _get_job_domain(self):
        self.ensure_one()
        domain = [('active', '=', True)]
        if self.recruitment_plan_id:
            jobs_in_plan = self.recruitment_plan_id.recruitment_plan_detail_ids.mapped('recruitment_job').ids
            domain.append(('id', 'in', jobs_in_plan))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        return domain

    # ================== ONCHANGE / DOMAIN ==================
    @api.onchange('recruitment_plan_id')
    def _onchange_recruitment_plan_id(self):
        for rec in self:
            domain_plan = [('recruitment_status', '!=', 'complete')]
            if rec.job_id:
                jobs_in_plan = rec.recruitment_plan_id.recruitment_plan_detail_ids.mapped('recruitment_job')
                if rec.recruitment_plan_id and rec.job_id not in jobs_in_plan:
                    rec.job_id = False
            return {'domain': {
                'recruitment_plan_id': domain_plan,
                'job_id': rec._get_job_domain(),
            }}

    @api.onchange('department_id')
    def _onchange_department_id(self):
        for rec in self:
            if rec.job_id and rec.job_id.department_id != rec.department_id:
                rec.job_id = False
            return {'domain': {'job_id': rec._get_job_domain()}}

    @api.onchange('job_id')
    def _onchange_job_id(self):
        for rec in self:
            if rec.job_id:
                rec.department_id = rec.job_id.department_id.id

    # ================== RÀNG BUỘC PLAN/JOB/DEPT ==================
    @api.constrains('recruitment_plan_id', 'job_id', 'department_id')
    def _check_job_dept_in_plan(self):
        for rec in self:
            plan = rec.recruitment_plan_id
            if not plan:
                continue
            jobs_in_plan = plan.recruitment_plan_detail_ids.mapped('recruitment_job')
            if rec.job_id and rec.job_id not in jobs_in_plan:
                raise ValidationError(_("Vị trí tuyển dụng không thuộc kế hoạch đã chọn."))
            if rec.department_id:
                depts_in_plan = jobs_in_plan.mapped('department_id')
                if rec.job_id:
                    if rec.department_id != rec.job_id.department_id:
                        raise ValidationError(_("Phòng ban phải đúng với phòng ban của vị trí đã chọn."))
                else:
                    if rec.department_id not in depts_in_plan:
                        raise ValidationError(_("Phòng ban không thuộc các vị trí trong kế hoạch."))

    # ================== AUTO NAME ==================
    @api.model_create_multi
    def create(self, vals_list):
        # ---- ACL: chỉ 4 nhóm được tạo ----
        if not _user_is_applicant_editor(self.env):
            raise AccessError(_("Bạn không có quyền tạo hồ sơ ứng viên."))
        # ---- logic cũ: auto đặt name nếu trống ----
        for vals in vals_list:
            if not vals.get('name'):
                job = self.env['hr.job'].browse(vals.get('job_id')).name if vals.get('job_id') else ''
                partner = vals.get('partner_name') or ''
                vals['name'] = f"Ứng tuyển {job} – {partner}" if job and partner else job or partner
        return super().create(vals_list)

    @api.onchange('partner_name', 'job_id')
    def _onchange_auto_name(self):
        if self.partner_name or self.job_id:
            job = self.job_id.name or ''
            partner = self.partner_name or ''
            self.name = f"Ứng tuyển {job} – {partner}" if job and partner else job or partner

    # ================== COMPUTE EDU ==================
    @api.depends('education_level_ids.professional_qualification')
    def _compute_highest_professional_qualification(self):
        rank = {'bachelor': 1, 'engineer': 2, 'master': 3, 'PhD': 4}
        for rec in self:
            best_key, best_rank = False, 0
            for lvl in rec.education_level_ids:
                key = lvl.professional_qualification
                if key and rank.get(key, 0) > best_rank:
                    best_key, best_rank = key, rank[key]
            rec.highest_professional_qualification = best_key

    @api.depends('education_level_ids')
    def _compute_edu_count(self):
        for rec in self:
            rec.education_level_count = len(rec.education_level_ids)

    # ================== ACL CHUYỂN STAGE ==================
    def _user_can_move_to_stage(self, stage_name: str) -> bool:
        req_groups = STAGE_ACL.get(stage_name)
        if not req_groups:
            return True
        user = self.env.user
        return any(user.has_group(xmlid) for xmlid in req_groups)

    # ================== CORE WRITE ==================
    def write(self, vals):
        # ---- ACL: chỉ 4 nhóm được sửa ----
        if not _user_is_applicant_editor(self.env):
            raise AccessError(_("Bạn không có quyền sửa hồ sơ ứng viên."))

        # PHẦN 1: kiểm tra quyền chuyển stage (nếu có)
        if "stage_id" in vals:
            new_stage = self.env["hr.recruitment.stage"].browse(vals["stage_id"])
            stage_name = new_stage.with_context(lang=None).name
            for rec in self:
                if not rec._user_can_move_to_stage(stage_name):
                    raise AccessError(_("Bạn không có quyền chuyển ứng viên sang giai đoạn: %s") % stage_name)

        # PHẦN 2: snapshot trạng thái "đã tuyển" trước khi ghi
        old_hired_map = {rec.id: bool(rec.stage_id.hired_stage) for rec in self}

        res = super().write(vals)

        # PHẦN 3: sau khi ghi, áp dụng side-effects theo thay đổi stage
        if 'stage_id' in vals:
            for rec in self:
                new_hired = bool(rec.stage_id.hired_stage)
                old_hired = old_hired_map.get(rec.id, False)
                if new_hired and not old_hired:
                    rec._apply_hired_side_effects_once()
                elif not new_hired and old_hired:
                    rec._rollback_hired_side_effects_if_needed()

        return res

    def unlink(self):
        if not _user_is_applicant_editor(self.env):
            raise AccessError(_("Bạn không có quyền xóa hồ sơ ứng viên."))
        return super().unlink()

    # ================== KHÔNG CHO LÙI TỪ ĐÃ TUYỂN (NẾU ĐÃ TẠO EMPLOYEE) ==================
    @api.constrains('stage_id')
    def _check_no_back_from_hired(self):
        for rec in self:
            if rec._origin.stage_id and rec._origin.stage_id.hired_stage and not rec.stage_id.hired_stage:
                if rec.isEmp:
                    raise ValidationError(_("Ứng viên đã tạo Employee, không thể chuyển khỏi giai đoạn 'Đã tuyển'."))

    @api.onchange('stage_id')
    def _onchange_stage_id_acl(self):
        for rec in self:
            if not rec.stage_id:
                continue
            stage_name = rec.stage_id.with_context(lang=None).name
            if not rec._user_can_move_to_stage(stage_name):
                rec.stage_id = rec._origin.stage_id
                return {
                    'warning': {
                        'title': _('Không được phép'),
                        'message': _('Bạn không có quyền chuyển ứng viên sang giai đoạn: %s') % stage_name
                    }
                }

    # ================== SIDE-EFFECTS: KHI VÀO ĐÃ TUYỂN ==================
    def _apply_hired_side_effects_once(self):
        for app in self:
            if app.hired_counters_done:
                continue
            app._reduce_plan_quantity(app)
            app._update_job_counters_when_hired(app)
            app.sudo().write({'hired_counters_done': True})

    # ================== SIDE-EFFECTS: KHI RỜI KHỎI ĐÃ TUYỂN ==================
    def _rollback_hired_side_effects_if_needed(self):
        for app in self:
            if not app.hired_counters_done or app.isEmp:
                continue
            app._increase_plan_quantity(app)
            app._rollback_job_counters_when_unhired(app)
            app.sudo().write({'hired_counters_done': False})

    # ================== KẾ HOẠCH: TRỪ / CỘNG ==================
    @api.model
    def _reduce_plan_quantity(self, applicant):
        plan = applicant.recruitment_plan_id
        job = applicant.job_id
        if not (plan and job):
            return
        detail = self.env['recruitment.plan.detail'].search([
            ('plan_id', '=', plan.id),
            ('recruitment_job', '=', job.id)
        ], limit=1)
        if detail and detail.requested_quantity > 0:
            new_qty = max(detail.requested_quantity - 1, 0)
            detail.sudo().write({'requested_quantity': new_qty})
            plan.message_post(body=_(
                "Ứng viên <b>%s</b> đã được tuyển. "
                "Giảm số lượng của công việc <b>%s</b> trong kế hoạch <b>%s</b> xuống còn <b>%s</b>."
            ) % (
                applicant.partner_name or applicant.name,
                job.display_name,
                plan.plan_code or plan.display_name,
                new_qty
            ))

    @api.model
    def _increase_plan_quantity(self, applicant):
        plan = applicant.recruitment_plan_id
        job = applicant.job_id
        if not (plan and job):
            return
        detail = self.env['recruitment.plan.detail'].search([
            ('plan_id', '=', plan.id),
            ('recruitment_job', '=', job.id)
        ], limit=1)
        if detail:
            new_qty = (detail.requested_quantity or 0) + 1
            detail.sudo().write({'requested_quantity': new_qty})
            plan.message_post(body=_(
                "Ứng viên <b>%s</b> rời giai đoạn 'Đã tuyển'. "
                "Khôi phục số lượng tuyển của công việc <b>%s</b> trong kế hoạch <b>%s</b> lên <b>%s</b>."
            ) % (
                applicant.partner_name or applicant.name,
                job.display_name,
                plan.plan_code or plan.display_name,
                new_qty
            ))

    # ================== HR.JOB COUNTERS ==================
    def _update_job_counters_when_hired(self, applicant):
        job = applicant.job_id
        if not job:
            return
        vals = {
            'no_of_hired_employee': (job.no_of_hired_employee or 0) + 1,
        }
        if (job.no_of_recruitment or 0) > 0:
            vals['no_of_recruitment'] = max((job.no_of_recruitment or 0) - 1, 0)
        job.sudo().write(vals)
        job.message_post(body=_(
            "Tuyển 1 ứng viên: <b>%s</b>. Target còn <b>%s</b>, Hired = <b>%s</b>."
        ) % (
            applicant.partner_name or applicant.name,
            job.no_of_recruitment,
            job.no_of_hired_employee,
        ))

    def _rollback_job_counters_when_unhired(self, applicant):
        job = applicant.job_id
        if not job:
            return
        vals = {
            'no_of_hired_employee': max((job.no_of_hired_employee or 0) - 1, 0),
            'no_of_recruitment': (job.no_of_recruitment or 0) + 1,
        }
        job.sudo().write(vals)
        job.message_post(body=_(
            "Rollback tuyển ứng viên <b>%s</b>. Target = <b>%s</b>, Hired = <b>%s</b>."
        ) % (
            applicant.partner_name or applicant.name,
            job.no_of_recruitment,
            job.no_of_hired_employee,
        ))

    # ================== HOOK CHUẨN ODOO: TẠO EMPLOYEE ==================
    def create_employee_from_applicant(self):
        res = super().create_employee_from_applicant()
        self._apply_hired_side_effects_once()
        return res


# ============= ACL THEO STAGE =============
STAGE_ACL = {
    "New": [
        "quan_ly_tuyen_dung.group_recruitment_hr_officer",
        "quan_ly_tuyen_dung.group_recruitment_committee",
        "base.group_user",
    ],
    "Initial Qualification": [
        "quan_ly_tuyen_dung.group_recruitment_hr_officer",
        "quan_ly_tuyen_dung.group_recruitment_committee",
        "base.group_user",
    ],
    "First Interview": [
        "quan_ly_tuyen_dung.group_recruitment_hr_officer",
        "quan_ly_tuyen_dung.group_recruitment_committee",
        "base.group_user",
    ],
    "Second Interview": [
        "quan_ly_tuyen_dung.group_recruitment_hr_officer",
        "quan_ly_tuyen_dung.group_recruitment_committee",
        "quan_ly_tuyen_dung.group_recruitment_director",
        "base.group_user",
    ],
    "Contract Proposal": [
        "quan_ly_tuyen_dung.group_recruitment_director",
        "quan_ly_tuyen_dung.group_recruitment_board",
        "base.group_user",
    ],
    "Contract Signed": [
        "quan_ly_tuyen_dung.group_recruitment_director",
        "quan_ly_tuyen_dung.group_recruitment_board",
        "base.group_user",
    ],
}
