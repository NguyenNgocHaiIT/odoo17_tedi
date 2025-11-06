from odoo import models, fields , api,_
from odoo.exceptions import ValidationError,AccessError

HR_OFFICER = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
COMMITTEE = 'quan_ly_tuyen_dung.group_recruitment_committee'
DIRECTOR  = 'quan_ly_tuyen_dung.group_recruitment_director'
BOARD     = 'quan_ly_tuyen_dung.group_recruitment_board'
BASE      = 'base.group_user'

class RecruitmentPlanDetail(models.Model):
    _name = "recruitment.plan.detail"
    _description = "Recruitment Plan Detail"
    _order = "sequence, id"

    # ➜ Tự tính theo thứ tự trong plan (không lưu DB)
    sequence = fields.Integer(string="STT", default=10)
    stt = fields.Integer(string="STT hiển thị", compute="_compute_stt", store=False, readonly=True)

    plan_id = fields.Many2one("recruitment.plan", string="Kế hoạch", required=True, ondelete="cascade")

    department_request = fields.Many2one(
        'hr.department',
        string="Phòng ban yêu cầu",
        related='recruitment_job.department_id',
        store=True, readonly=False
    )
    recruitment_job = fields.Many2one(
        "hr.job",
        string="Vị trí tuyển dụng",
        domain="[('department_id', '=', department_request)]",  # ← domain tĩnh theo field
        required=True,
    )
    experient_request_id = fields.Many2one("experience.request" , string= "Yêu cầu kinh nghiệm")
    requested_quantity = fields.Integer(string="Số lượng cần tuyển", required=True, default=1)
    professional_qualification = fields.Selection([
        ("bachelor", "Cử nhân"),
        ("engineer", "Kỹ sư"),
        ("master", "Thạc sĩ"),
        ("PhD", "Tiến sĩ"),
    ])


    note = fields.Char(string="Ghi chú")

    nomination_ids = fields.Many2many(
        "hr.applicant",
        "recruitment_plan_detail_nomination_rel",
        "detail_id", "applicant_id",
        string="Ứng viên cũ được đề cử"
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "recruitment_plan_detail_attachment_rel",
        "detail_id", "attachment_id",
        string="Tài liệu mô tả công việc"
    )



    @api.constrains('nomination_ids')
    def _check_nomination_ids_refused_or_archived(self):
        for rec in self:
            # Hợp lệ khi: có refuse_reason_id hoặc active = False
            apps = rec.with_context(active_test=False).nomination_ids
            wrong = apps.filtered(lambda a: not (a.refuse_reason_id or a.active is False))
            if wrong:
                # cố gắng lấy tên ứng viên cho thông báo
                names = ", ".join(wrong.mapped('partner_name') or wrong.mapped('name'))
                raise ValidationError(_(
                    "Chỉ được chọn ứng viên có lý do từ chối (refuse_reason_id) "
                    "hoặc đã lưu trữ (archived). Ứng viên không hợp lệ: %s"
                ) % names)

    @api.constrains("requested_quantity")
    def _check_requested_quantity(self):
        for rec in self:
            if rec.requested_quantity < 0:
                raise ValidationError(_("Requested Quantity must be > 0."))


    # ====== Core: tính số thứ tự theo plan + sequence ======
    @api.depends(
        "plan_id",
        "plan_id.recruitment_plan_detail_ids",
        "plan_id.recruitment_plan_detail_ids.sequence",
    )
    def _compute_stt(self):
        # tính theo từng kế hoạch để set đồng loạt, tránh tính lặp
        for plan in self.mapped('plan_id'):
            lines = plan.recruitment_plan_detail_ids.sorted(
                key=lambda r: (r.sequence or 0)  # KHÔNG đụng tới r.id để tránh NewId
            )
            for idx, line in enumerate(lines, start=1):
                line.stt = idx

        # những dòng chưa có kế hoạch thì cho 0
        for rec in self.filtered(lambda r: not r.plan_id):
            rec.stt = 0

    @api.onchange('recruitment_job')
    def _onchange_recruitment_job(self):
        """Chọn job → tự set phòng ban theo job.department_id"""
        for rec in self:
            if rec.recruitment_job:
                rec.department_request = rec.recruitment_job.department_id

    @api.onchange('department_request')
    def _onchange_department_request(self):
        """
        Chọn/đổi phòng ban → giới hạn domain job và
        nếu job đang chọn không thuộc phòng ban đó thì xóa.
        """
        for rec in self:
            # Nếu đang có job nhưng lệch phòng ban thì reset
            if rec.recruitment_job and rec.recruitment_job.department_id != rec.department_request:
                rec.recruitment_job = False

            # Trả domain động (hữu ích cả khi field không khai báo domain trong XML)
            domain = [('active', '=', True)]
            if rec.department_request:
                domain.append(('department_id', '=', rec.department_request.id))
            return {'domain': {'recruitment_job': domain}}

    def action_open_old_applicant_wizard(self):
        self.ensure_one()
        action = self.env.ref(
            'quan_ly_tuyen_dung.action_old_applicant_suggest_wizard'
        ).read()[0]
        # Bắt buộc phải bật active_test=False để thấy cả archived
        action['context'] = {
            'default_detail_id': self.id,
            'active_test': False,
        }
        return action


    # === NEW: chỉ cho 4 group được phép chỉnh nomination_ids ===
    def _user_can_edit_nomination(self):
        u = self.env.user
        return any([
            u.has_group(HR_OFFICER),
            u.has_group(COMMITTEE),
            u.has_group(DIRECTOR),
            u.has_group(BOARD),
            u.has_group(BASE)
        ])

    # ===== Permission helpers for lines =====
    def _can_edit_in_state(self, state, op, vals=None):
        is_committee = self.env.user.has_group(COMMITTEE)
        is_director  = self.env.user.has_group(DIRECTOR)
        is_board     = self.env.user.has_group(BOARD)
        is_base      = self.env.user.has_group(BASE)

        if state == 'draft':
            return is_committee or is_director or is_board or is_base

        if state == 'waiting':
            return is_board or is_base

        if state == 'complete':
            if op in ('create', 'unlink'):
                return False
            if op == 'write':
                if not vals:
                    return False
                allowed = {'nomination_ids', 'requested_quantity'}
                return set(vals.keys()).issubset(allowed)
        return False

    def _check_edit_permission(self, op, vals=None):
        # 1) Check theo state (rule bạn đã có)
        if op == 'create':
            plan_id = (vals or {}).get('plan_id')
            plan = plan_id and self.env['recruitment.plan'].browse(plan_id) or False
            if not plan:
                raise AccessError(_("Không xác định được Kế hoạch để kiểm tra quyền."))
            if not self._can_edit_in_state(plan.recruitment_status, 'create'):
                raise AccessError(_("Bạn không có quyền thêm dòng trong trạng thái '%s'.") % plan.recruitment_status)
        else:
            for rec in self:
                state = rec.plan_id.recruitment_status
                if not self._can_edit_in_state(state, op, vals):
                    vn = {'create': 'tạo', 'write': 'sửa', 'unlink': 'xóa'}
                    raise AccessError(_("Không được %s dòng khi Kế hoạch ở trạng thái '%s'.") % (vn[op], state))

        # 2) NEW: nếu có đụng tới nomination_ids → chỉ 4 group mới được phép
        if vals and 'nomination_ids' in vals:
            if not self._user_can_edit_nomination():
                raise AccessError(_("Bạn không có quyền thêm/xóa/sửa 'Ứng viên đề cử' (nomination_ids)."))

    # --- Overrides ---
    @api.model
    def create(self, vals):
        # chặn theo state + nomination_ids ACL
        self._check_edit_permission('create', vals)
        return super().create(vals)

    def write(self, vals):
        # chặn theo state + nomination_ids ACL
        self._check_edit_permission('write', vals)
        return super().write(vals)

    def unlink(self):
        self._check_edit_permission('unlink')
        return super().unlink()