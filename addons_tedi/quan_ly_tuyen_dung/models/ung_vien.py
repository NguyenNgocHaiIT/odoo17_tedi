from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError
import re

# ==== NHÓM ĐƯỢC PHÉP TẠO/SỬA ỨNG VIÊN ====
HR_OFFICER = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
COMMITTEE  = "quan_ly_tuyen_dung.group_recruitment_committee"
DIRECTOR   = "quan_ly_tuyen_dung.group_recruitment_director"
BOARD      = "quan_ly_tuyen_dung.group_recruitment_board"
BASE       = "base.group_user"

def _user_is_applicant_editor(env):
    u = env.user
    return any([
        u.has_group(HR_OFFICER),
        u.has_group(COMMITTEE),
        u.has_group(DIRECTOR),
        u.has_group(BOARD),
        u.has_group(BASE)
    ])

EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
# Cho VN: 0xxxxxxxxx (10 số, đầu 03/05/07/08/09) hoặc E.164: +84xxxxxxxxx
VN_LOCAL_RE = re.compile(r"^(0)(2|3|5|7|8|9)\d{8}$")
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")  # ITU E.164: 8–15 digits, không bắt đầu bằng 0

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

class ResEthnic(models.Model):
    _name = 'res.ethnic'
    _description = 'Danh mục Dân tộc'
    _order = 'name'

    name = fields.Char(string="Tên dân tộc", required=True)
    code = fields.Char(string="Mã", help="Ví dụ: KINH, TAY, THAI...")
    active = fields.Boolean(string="Đang sử dụng", default=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tên dân tộc đã tồn tại!'),
        ('code_uniq', 'unique (code)', 'Mã dân tộc phải là duy nhất!')
    ]

class Applicant(models.Model):
    _inherit = 'hr.applicant'
    _rec_name = "partner_name"

    # ==== THÔNG TIN BỔ SUNG ====
    dob = fields.Date(string="Sinh ngày")
    country_id = fields.Many2one(
        'res.country',
        string="Quốc tịch",
        default=lambda self: self.env['res.country'].search([('code', '=', 'VN')], limit=1)
    )

    folk_id = fields.Many2one(
        'res.ethnic',
        string="Dân tộc",
        help="Chọn dân tộc từ danh mục"
    )
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
        string="Link hồ sơ"
    )
    attachment=fields.Char(string="Link hồ sơ")

    isEmp = fields.Boolean(string="Is Emp", default=False)

    recruitment_plan_id = fields.Many2one("recruitment.plan", string="Đợt tuyển dụng")

    # ====== (MỚI) Danh sách job hợp lệ theo Plan/Dept để domain job_id ======
    available_job_ids = fields.Many2many(
        'hr.job',
        string='Jobs in Plan (computed)',
        compute='_compute_available_job_ids',
        store=False,
    )

    # Các bộ sưu tập trên Applicant (mapping sang Employee)
    certificate_ids = fields.One2many(
        "hr.employee.certificate", "applicant_id", string="Chứng chỉ (ứng viên)"
    )
    training_ids = fields.One2many(
        "hr.employee.training", "applicant_id", string="Đào tạo (ứng viên)"
    )
    experience_ids = fields.One2many(
        "hr.employee.work.process.old", "applicant_id", string="Quá trình công tác cũ (ứng viên)"
    )
    education_ids = fields.One2many(
        "hr.employee.education", "applicant_id", string="Trình độ học vấn (ứng viên)"
    )
    descriptions = fields.Text(string="Đánh giá sau phỏng vấn")

    # Đánh giá sau phỏng vấn
    professional_skill = fields.Char(string="Khả năng chuyên môn")
    work_experience = fields.Char(string="Kinh nghiệm công tác")
    other_check = fields.Char(string="Kiểm tra khác")
    appearance = fields.Char(string="Ngoại hình")
    expression_skill = fields.Char(string="Kỹ năng diễn đạt")
    communication_skill = fields.Char(string="Kỹ năng giao tiếp")
    integration_skill = fields.Char(string="Kỹ năng hội nhập")
    professional_knowledge = fields.Char(string="Khả năng hiểu biết về chuyên môn")
    career_objective = fields.Char(string="Nguyện vọng của ứng viên")

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
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_submit_eval(self):
        self.ensure_one()
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

    @api.onchange('availability')
    def _onchange_availability(self):
        """
        Kiểm tra nếu ngày chọn nhỏ hơn ngày hiện tại
        thì cảnh báo và xóa giá trị.
        """
        if self.availability:
            # Lấy ngày hôm nay
            today = fields.Date.today()

            # So sánh
            if self.availability < today:
                # 1. Reset lại giá trị (để người dùng phải chọn lại)
                self.availability = False

                # 2. Trả về cảnh báo (Popup)
                return {
                    'warning': {
                        'title': "Ngày không hợp lệ",
                        'message': "Thời gian bắt đầu không được nhỏ hơn ngày hiện tại!"
                    }
                }

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


    # ================== (MỚI) COMPUTE available_job_ids ==================
    @api.depends('recruitment_plan_id')  # <-- bỏ department_id ở đây
    def _compute_available_job_ids(self):
        Job = self.env['hr.job']
        for rec in self:
            jobs = Job.browse()
            if rec.recruitment_plan_id:
                # LẤY HẾT job trong plan, KHÔNG lọc theo department
                jobs = rec.recruitment_plan_id.recruitment_plan_detail_ids.mapped('recruitment_job')
            else:
                # Không có plan: nếu muốn vẫn hỗ trợ chọn theo phòng ban khi KHÔNG có plan
                if rec.department_id:
                    jobs = Job.search([('active', '=', True),
                                       ('department_id', '=', rec.department_id.id)])
            rec.available_job_ids = jobs

    # ================== ONCHANGE / DOMAIN ==================
    @api.onchange('recruitment_plan_id')
    def _onchange_recruitment_plan_id(self):
        for rec in self:
            if rec.recruitment_plan_id and rec.job_id:
                jobs_in_plan = rec.recruitment_plan_id.recruitment_plan_detail_ids.mapped('recruitment_job')
                if rec.job_id not in jobs_in_plan:
                    rec.job_id = False
        # chỉ thống nhất domain của PLAN (trùng XML), KHÔNG trả domain job_id để tránh “đua”
        return {'domain': {'recruitment_plan_id': [('recruitment_status', '=', 'complete')]}}

    @api.onchange('department_id')
    def _onchange_department_id(self):
        for rec in self:
            if rec.department_id and rec.job_id:
                # Nếu job đang chọn không thuộc phòng ban mới -> xóa
                if rec.job_id.department_id != rec.department_id:
                    rec.job_id = False

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

        self = self.with_context(mail_create_nolog=True,
                                 mail_auto_subscribe_no_notify=True)
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
                # ĐÃ chạy counters rồi; nhưng nếu giờ mới có emp_id thì vẫn sync 1 lần
                if app.emp_id and not app.applicant_sync_done:
                    app._sync_to_employee_if_any(force=False)
                continue
            app._reduce_plan_quantity(app)
            app._update_job_counters_when_hired(app)
            app.sudo().write({'hired_counters_done': True})
            # nếu đã có emp thì sync ngay
            if app.emp_id:
                app._sync_to_employee_if_any(False)

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

    _APPLICANT_TO_EMPLOYEE_FIELD_MAP = [
        # (applicant_field, employee_field)
        ("email_from", "work_email"),
        ("partner_mobile", "mobile_phone"),
        ("address", "household_address"),
        ("folk", "ethnicity"),
        ("current_job", "occupation"),
        ("dob", "birthday"),
        # ("email_from", "email_personal"),
    ]

    # ======== Copy các trường đơn (char/date/m2o...) ========
    def _copy_simple_fields_to_employee(self, employee):
        write_vals = {}
        for a_field, e_field in self._APPLICANT_TO_EMPLOYEE_FIELD_MAP:
            if a_field in self._fields and e_field in employee._fields:
                write_vals[e_field] = self[a_field]
        if write_vals:
            employee.sudo().write(write_vals)

        # ======== Clone các bộ sưu tập O2M (đào tạo/chứng chỉ/kinh nghiệm/trình độ) ========
    def _copy_collections_to_employee(self, employee):
        def _copy_lines(o2m_recs):
            for line in o2m_recs:
                # CHỈ ĐỊNH NGHĨA NHỮNG TRƯỜNG CẦN THAY ĐỔI
                # Odoo sẽ tự động copy các trường dữ liệu khác (như work_position, school, date...)
                vals = {
                    'employee_id': employee.id,
                    'applicant_id': False,  # Ngắt liên kết với ứng viên ở dòng mới (nếu model có field này)
                }

                # Thực hiện copy
                new_line = line.copy(default=vals)

                # Xử lý riêng cho Many2many (Attachment) để đảm bảo copy đúng
                if 'attachment_ids' in line._fields and line.attachment_ids:
                    new_line.write({'attachment_ids': [(6, 0, line.attachment_ids.ids)]})

            # Thực hiện copy cho từng bảng
        _copy_lines(self.certificate_ids)
        _copy_lines(self.training_ids)
        _copy_lines(self.experience_ids)
        _copy_lines(self.education_ids)
    # ======== Đồng bộ tổng (idempotent nhẹ bằng cờ) ========
    applicant_sync_done = fields.Boolean(string="Đã đồng bộ sang nhân viên", default=False)

    def _sync_to_employee_if_any(self, force=False):
        for app in self:
            employee = app.emp_id
            if not employee:
                continue
            if app.applicant_sync_done and not force:
                continue
            app._copy_simple_fields_to_employee(employee)
            app._copy_collections_to_employee(employee)
            app.sudo().write({'applicant_sync_done': True})
            app.message_post(body=_("Đã đồng bộ dữ liệu hồ sơ ứng viên sang nhân viên %s.") % (employee.name,))

    # ================== HOOK CHUẨN ODOO: TẠO EMPLOYEE ==================
    def create_employee_from_applicant(self):
        res = super().create_employee_from_applicant()
        # giữ logic của bạn
        self._apply_hired_side_effects_once()

        # bổ sung đồng bộ Applicant -> Employee
        self._sync_to_employee_if_any(force=False)

        # cập nhật cờ isEmp (bạn đang dùng ở constraint không cho lùi từ đã tuyển)
        self.filtered(lambda a: a.emp_id and not a.isEmp).sudo().write({'isEmp': True})
        return res

    # ---- Helpers ----
    def _norm_phone(self, s):
        if not s:
            return s
        p = re.sub(r"[^\d+]", "", s.strip())
        if p.startswith('84') and not p.startswith('+'):
            p = '+' + p
        if VN_LOCAL_RE.match(p):        # 0xxxxxxxxx -> +84xxxxxxxxx
            p = '+84' + p[1:]
        return p

    def _is_valid_email(self, s):
        return bool(s and EMAIL_RE.match(s))

    def _is_valid_phone(self, s):
        if not s:
            return False
        p = self._norm_phone(s)
        return bool(VN_LOCAL_RE.match(s) or E164_RE.match(p))

    # ====== ONCHANGE: phản hồi ngay khi sửa trường ======
    @api.onchange('email_from')
    def _onchange_email_from(self):
        if self.email_from:
            self.email_from = self.email_from.strip()
            if not self._is_valid_email(self.email_from):
                return {
                    'warning': {
                        'title': _('Email không hợp lệ'),
                        'message': _('Vui lòng nhập đúng định dạng email (vd: ten@domain.com).')
                    }
                }

    @api.onchange('partner_mobile')
    def _onchange_partner_mobile(self):
        if self.partner_mobile:
            norm = self._norm_phone(self.partner_mobile)
            if not self._is_valid_phone(self.partner_mobile):
                return {
                    'warning': {
                        'title': _('Số điện thoại không hợp lệ'),
                        'message': _('Chấp nhận 0xxxxxxxxx (VN) hoặc E.164 như +84xxxxxxxxx.')
                    }
                }
            self.partner_mobile = norm
    def _safe_write_partner(self, partner, vals):
        """Chỉ ghi các trường an toàn; tránh đụng Users.
        Tùy chính sách, có thể sudo() hoặc bỏ qua khi partner gắn user."""
        # Nếu partner gắn với user nội bộ ⇒ tránh ghi để không kéo theo res.users
        if partner.user_ids:
            # CHÍNH SÁCH 1 (an toàn): KHÔNG ghi gì để tránh đụng Users
            # return

            # CHÍNH SÁCH 2 (ép ghi): ghi bằng sudo, chấp nhận sync sang Users
            # partner.sudo().write(vals)
            return
        partner.write(vals)

    def _inverse_partner_email(self):
        """Override để tránh gây write vào res.users khi HR chỉ nhập email/điện thoại ứng viên."""
        for app in self:
            email = (app.email_from or '').strip()
            if not email:
                continue

            # Tạo partner nếu chưa có (hành vi gốc)
            if not app.partner_id:
                if not app.partner_name:
                    # Giữ nguyên thông báo như base
                    raise UserError(_('You must define a Contact Name for this applicant.'))
                # find_or_create có thể trả về partner liên kết user -> sẽ xử lý ở dưới
                app.partner_id = app.env['res.partner'].with_context(default_lang=app.env.lang).find_or_create(email)

            partner = app.partner_id

            # Chỉ khi thực sự khác mới tính chuyện ghi
            vals = {}
            if app.partner_name and not partner.name:
                vals['name'] = app.partner_name
            # CHÚ Ý: Đừng ép đồng bộ email nếu điều đó kéo theo write Users
            # So sánh normalize để tránh ghi không cần thiết (giống base)
            from odoo import tools
            if tools.email_normalize(email) != tools.email_normalize(partner.email):
                vals['email'] = email

            # Điện thoại
            if app.partner_mobile:
                vals['mobile'] = app.partner_mobile
            if app.partner_phone:
                vals['phone'] = app.partner_phone

            if vals:
                try:
                    self._safe_write_partner(partner, vals)
                except AccessError:
                    # fallback im lặng: không cập nhật partner nếu không đủ quyền
                    # (tránh nổ khi HR không có quyền Users)
                    pass