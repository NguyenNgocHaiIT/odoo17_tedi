from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError

COMMITTEE = 'quan_ly_tuyen_dung.group_recruitment_committee'
DIRECTOR  = 'quan_ly_tuyen_dung.group_recruitment_director'
BOARD     = 'quan_ly_tuyen_dung.group_recruitment_board'
BASE      = 'base.group_user'

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
    plan_execute_date = fields.Date(string="Ngày thực hiện", tracking=True)
    plan_name = fields.Char(string="Tên kế hoạch", tracking=True)
    people_suggestion = fields.Many2one("hr.employee", string="Người đề nghị", ondelete="set null")
    plan_purpose = fields.Char(string="Mục đích")

    total_applicant_request = fields.Integer(
        string="Tổng số lượng cần tuyển",
        compute="_compute_total_applicant_request",
        store=True, readonly=True,
    )

    plan_fund = fields.Monetary(string="Kinh phí", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Tiền tệ",
        default=lambda self: self.env.ref("base.VND"), readonly=True)

    # Flow: draft -> waiting -> board_approve -> complete
    recruitment_status = fields.Selection([
        ("draft", "Dự thảo"),
        ("board_approve", "HĐQT duyệt"),
        ("director_approve", "GD/PGD duyệt"),
        ("complete", "Hoàn thành"),
    ], string="Trạng thái", default="draft", index=True, required=True, tracking=True)

    is_applied_to_jobs = fields.Boolean(string="Đã áp dụng sang Job", default=False, readonly=True)
    department_responsible = fields.Many2one("hr.department", string="Phòng ban phụ trách", ondelete="set null")

    recruitment_plan_detail_ids = fields.One2many(
        "recruitment.plan.detail", "plan_id", string="Thông tin chi tiết"
    )

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
            return is_board  # CHỈ BOARD ĐƯỢC SỬA Ở TRẠNG THÁI 'waiting'

        if state == 'director_approve':
            return is_director  # CHỈ DIRECTOR ĐƯỢC SỬA

        if state == 'complete':
            return False  # Không ai được sửa

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
            # rec.message_post(body=_("Ủy ban đã trình duyệt kế hoạch."))

    def action_board_approve(self):
        """BOARD: waiting -> board_approve"""
        self._check_board()
        for rec in self:
            if rec.recruitment_status != "board_approve":
                raise ValidationError(_("HĐQT chỉ duyệt được khi trạng thái là 'HĐQT duyệt'."))
            rec.recruitment_status = "director_approve"
            # rec.message_post(body=_("HĐQT đã duyệt kế hoạch (Board Approved)."))

    def _apply_if_needed(self):
        for rec in self:
            if not rec.is_applied_to_jobs:
                rec._apply_recruitment_to_jobs()
                rec.is_applied_to_jobs = True

    def action_director_approve(self):
        """DIRECTOR: board_approve -> complete (và áp nhu cầu sang Job nếu chưa)"""
        self._check_director()
        for rec in self:
            if rec.recruitment_status != "director_approve":
                raise ValidationError(_("Giám đốc chỉ phê duyệt được khi trạng thái là 'HĐQT duyệt'."))
            rec._apply_if_needed()
            rec.recruitment_status = "complete"
            # rec.message_post(body=_("Giám đốc đã phê duyệt. Kế hoạch chuyển sang 'Hoàn thành'."))

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
        """Gộp theo job và GHI ĐÈ nhu cầu = tổng requested_quantity của chính kế hoạch này."""
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

        # self.message_post(body=_("Đã áp dụng nhu cầu sang Job: %s")
        #                   % ", ".join(f"{j.display_name}={totals[j.id]}" for j in jobs))

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
