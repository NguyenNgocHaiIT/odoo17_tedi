from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from datetime import datetime, date

HR_OFFICER = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
COMMITTEE = 'quan_ly_tuyen_dung.group_recruitment_committee'
DIRECTOR = 'quan_ly_tuyen_dung.group_recruitment_director'
BOARD = 'quan_ly_tuyen_dung.group_recruitment_board'
BASE = 'base.group_user'

COMPLETE_EDITORS = {HR_OFFICER, COMMITTEE, DIRECTOR, BOARD}


class RecruitmentPlan(models.Model):
    _name = "recruitment.plan"
    _description = "Recruitment Plan"
    _rec_name = "plan_name"
    _order = "sequence"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    sequence = fields.Integer(string="STT sắp xếp", default=10)
    stt = fields.Integer(string="STT", compute="_compute_stt", store=False, readonly=True)

    plan_code = fields.Char(
        string="Số kế hoạch", required=True, readonly=True, copy=False,
        default=lambda self: _('New'), tracking=True
    )
    plan_execute_date = fields.Date(string="Ngày thực hiện", tracking=True, default=fields.Date.today,)
    plan_name = fields.Char(string="Tên kế hoạch", tracking=True)
    people_suggestion = fields.Many2one(
        "hr.employee",
        string="Người đề nghị",
        ondelete="set null",
        default=lambda self: self.env.user.employee_id.id,)
    plan_purpose = fields.Char(string="Mục đích")

    # --- FIELD MỚI: CHỌN ĐỢT KHẢO SÁT ---
    survey_id = fields.Many2one(
        'recruitment.survey',
        string="Đợt khảo sát",
        domain="[('state', 'in', ['in_process', 'end'])]",
        tracking=True
    )

    total_applicant_request = fields.Integer(
        string="Tổng số lượng cần tuyển",
        compute="_compute_total_applicant_request",
        store=True, readonly=True,
    )

    plan_fund = fields.Monetary(string="Kinh phí", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Tiền tệ",
                                  default=lambda self: self.env.ref("base.VND"), readonly=True)

    recruitment_status = fields.Selection([
        ("draft", "Dự thảo"),
        ("board_approve", "HĐQT duyệt"),
        ("director_approve", "GD/PGD duyệt"),
        ("complete", "Hoàn thành"),
    ], string="Trạng thái", default="draft", index=True, required=True, tracking=True)

    is_applied_to_jobs = fields.Boolean(string="Đã áp dụng sang Job", default=False, readonly=True)
    department_responsible = fields.Many2one(
        "hr.department",
        string="Phòng ban phụ trách",
        ondelete="set null",
        default=lambda self: self.env.user.employee_id.department_id.id,)

    recruitment_plan_detail_ids = fields.One2many(
        "recruitment.plan.detail", "plan_id", string="Thông tin chi tiết"
    )

    # ----------------- TỔNG HỢP NHU CẦU (LOGIC CHÍNH) -----------------
    @api.onchange('survey_id')
    def _onchange_survey_id(self):
        """
        Khi chọn Đợt khảo sát:
        1. Tìm các phiếu Nhu cầu (recruitment.needs) thuộc đợt này & đã Confirmed.
        2. Duyệt qua từng dòng chi tiết của từng phiếu.
        3. Đẩy thẳng vào recruitment_plan_detail_ids (KHÔNG cộng dồn/gom nhóm).
        """
        if not self.survey_id:
            return

        # 1. Tìm các phiếu nhu cầu hợp lệ
        needs = self.env['recruitment.needs'].search([
            ('name', '=', self.survey_id.id),
            ('state', '=', 'confirmed')
        ])

        # Xóa dữ liệu cũ trên giao diện trước khi load mới
        # (Lệnh (5, 0, 0) xóa sạch các dòng trong One2many)
        if not needs:
            self.recruitment_plan_detail_ids = [(5, 0, 0)]
            return

        new_lines = []

        # 2. Duyệt qua từng phiếu nhu cầu
        for need in needs:
            dept = need.department_id
            if not dept:
                continue

            # 3. Duyệt qua từng dòng chi tiết trong phiếu (Line)
            for line in need.line_ids:
                if not line.job_id:
                    continue

                # Tạo dòng dữ liệu tương ứng 1-1
                val = {
                    'department_request': dept.id,
                    'recruitment_job': line.job_id.id,
                    'requested_quantity': line.amount or 0,
                    'experient_request_id': line.experience_id.id if line.experience_id else False,
                    'professional_qualification': line.professional_qualification,
                    'note': line.note or '',
                }

                # Thêm vào danh sách lệnh tạo mới (0, 0, {values})
                new_lines.append((0, 0, val))

        # 4. Cập nhật vào One2many
        # [(5, 0, 0)] để xóa dòng cũ, sau đó nối với danh sách dòng mới
        self.recruitment_plan_detail_ids = [(5, 0, 0)] + new_lines

    # ----------------- Quyền cơ bản -----------------
    def _check_committee(self):
        if not self.env.user.has_group(COMMITTEE):
            raise AccessError(_("Chỉ Ủy ban mới được thực hiện thao tác này."))

    def _check_board(self):
        if not self.env.user.has_group(BOARD):
            raise AccessError(_("Chỉ HĐQT mới được thực hiện thao tác này."))

    def _check_director(self):
        if not self.env.user.has_group(DIRECTOR):
            raise AccessError(_("Chỉ Giám đốc mới được thực hiện thao tác này."))

    # ----------------- Edit rules -----------------
    def _can_edit_plan_in_state(self, state, op, vals=None):
        u = self.env.user
        is_committee = u.has_group(COMMITTEE)
        is_board = u.has_group(BOARD)
        is_director = u.has_group(DIRECTOR)
        is_base = u.has_group(BASE)

        if state == 'draft':
            return is_committee or is_board or is_director or is_base

        if state == 'board_approve':
            return is_board

        if state == 'director_approve':
            return is_director

        if state == 'complete':
            return False

        return False

    def _check_plan_edit_permission(self, op, vals=None):
        if op == 'create':
            state = (vals or {}).get('recruitment_status') or 'draft'
            if not self._can_edit_plan_in_state(state, 'create', vals):
                raise AccessError(_("Bạn không có quyền tạo Kế hoạch ở trạng thái '%s'.") % state)
            return
        for rec in self:
            if not self._can_edit_plan_in_state(rec.recruitment_status, op, vals):
                action_name = {'create': 'tạo', 'write': 'sửa', 'unlink': 'xóa'}[op]
                raise AccessError(_("Không được %s Kế hoạch khi ở trạng thái '%s'.")
                                  % (action_name, rec.recruitment_status))

    # ----------------- Actions -----------------
    def action_submit(self):
        """COMMITTEE: draft -> waiting"""
        self._check_committee()
        for rec in self:
            if rec.recruitment_status != "draft":
                raise ValidationError(_("Chỉ có thể trình duyệt từ trạng thái 'Dự thảo'."))
            rec.recruitment_status = "board_approve"

    def action_board_approve(self):
        """BOARD: waiting -> board_approve"""
        self._check_board()
        for rec in self:
            if rec.recruitment_status != "board_approve":
                raise ValidationError(_("HĐQT chỉ duyệt được khi trạng thái là 'HĐQT duyệt'."))
            rec.recruitment_status = "director_approve"

    def _apply_if_needed(self):
        for rec in self:
            if not rec.is_applied_to_jobs:
                rec._apply_recruitment_to_jobs()
                rec.is_applied_to_jobs = True

    def action_director_approve(self):
        """DIRECTOR: board_approve -> complete"""
        self._check_director()
        for rec in self:
            if rec.recruitment_status != "director_approve":
                raise ValidationError(_("Giám đốc chỉ phê duyệt được khi trạng thái là 'HĐQT duyệt'."))
            rec._apply_if_needed()
            rec.recruitment_status = "complete"

    # ----------------- Compute / helpers -----------------
    @api.depends("sequence")
    def _compute_stt(self):
        all_ids = self.search([], order="sequence, id").ids
        index_map = {rid: idx for idx, rid in enumerate(all_ids, start=1)}
        for rec in self:
            rec.stt = index_map.get(rec.id, 0)

    @api.depends("recruitment_plan_detail_ids.requested_quantity")
    def _compute_total_applicant_request(self):
        for plan in self:
            plan.total_applicant_request = sum(plan.recruitment_plan_detail_ids.mapped("requested_quantity"))

    def _apply_recruitment_to_jobs(self):
        """Gộp theo job và GHI ĐÈ nhu cầu."""
        self.ensure_one()
        lines = self.recruitment_plan_detail_ids.filtered(lambda l: l.recruitment_job and l.requested_quantity > 0)
        if not lines:
            return
        totals = {}
        for ln in lines:
            jid = ln.recruitment_job.id
            totals[jid] = totals.get(jid, 0) + (ln.requested_quantity or 0)

        jobs = self.env['hr.job'].browse(list(totals.keys()))
        for job in jobs:
            job.no_of_recruitment = totals[job.id]


    # Ngày thực hiện không chọn trong quá khứ
    @api.constrains('plan_execute_date')
    def _check_plan_execute_date(self):
        for rec in self:
            if rec.plan_execute_date:
                # Chuyển str -> date nếu cần
                if isinstance(rec.plan_execute_date, str):
                    plan_date = datetime.strptime(rec.plan_execute_date, '%Y-%m-%d').date()
                else:
                    plan_date = rec.plan_execute_date
                if plan_date < date.today():
                    raise ValidationError("Ngày thực hiện không được nhỏ hơn ngày hiện tại.")

    # ----------------- Overrides -----------------
    @api.model
    def create(self, vals):
        self._check_plan_edit_permission('create', vals)
        if vals.get('plan_code', _('New')) == _('New'):
            vals['plan_code'] = self.env['ir.sequence'].next_by_code('recruitment.plan.code') or _('New')
        return super().create(vals)

    def write(self, vals):
        self._check_plan_edit_permission('write', vals)
        return super().write(vals)

    def unlink(self):
        self._check_plan_edit_permission('unlink')
        return super().unlink()