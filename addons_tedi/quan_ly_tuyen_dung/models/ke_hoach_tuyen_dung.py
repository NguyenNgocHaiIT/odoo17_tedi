from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError

COMMITTEE = 'quan_ly_tuyen_dung.group_recruitment_committee'
DIRECTOR  = 'quan_ly_tuyen_dung.group_recruitment_director'
BOARD     = 'quan_ly_tuyen_dung.group_recruitment_board'
HR        = 'quan_ly_tuyen_dung.group_recruitment_hr_officer'
BASE      = 'base.group_user'


class RecruitmentPlan(models.Model):
    _name = "recruitment.plan"
    _description = "Recruitment Plan"
    _rec_name = "plan_name"
    _order = "sequence"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ----- Fields -----
    sequence = fields.Integer(string="STT sắp xếp", default=10)
    stt = fields.Integer(string="STT", compute="_compute_stt", store=False, readonly=True)

    plan_code = fields.Char(
        string="Số kế hoạch",
        required=True, readonly=True, copy=False,
        default=lambda self: _('New'),
        tracking=True
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
    currency_id = fields.Many2one(
        "res.currency", string="Tiền tệ",
        default=lambda self: self.env.ref("base.VND"),
        readonly=True,
    )

    recruitment_status = fields.Selection(
        [("draft", "Dự thảo"),
         ("waiting", "Trình duyệt"),
         ("complete", "Hoàn thành")],
        string="Trạng thái", default="draft", index=True, required=True,
        tracking=True
    )

    is_applied_to_jobs = fields.Boolean(string="Đã áp dụng sang Job", default=False, readonly=True)
    department_responsible = fields.Many2one("hr.department", string="Phòng ban phụ trách", ondelete="set null")

    recruitment_plan_detail_ids = fields.One2many(
        "recruitment.plan.detail", "plan_id", string="Thông tin chi tiết"
    )

    # ----- Helpers: quyền -----
    def _has_any_group(self, *xmlids):
        user = self.env.user
        return any(user.has_group(x) for x in xmlids)

    def _check_submit_groups(self):
        # Ủy ban, Giám đốc, HĐQT đều được submit (OR)
        if not self._has_any_group(COMMITTEE, DIRECTOR, BOARD, BASE):
            raise AccessError(_("Bạn không có quyền 'Trình duyệt' kế hoạch này."))

    def _check_complete_groups(self):
        # Chỉ HĐQT (và BASE nếu bạn vẫn muốn) được hoàn thành
        if not self._has_any_group(BOARD, BASE):
            raise AccessError(_("Bạn không có quyền 'Hoàn thành' kế hoạch này."))

    # ====== Kiểm quyền tổng cho Plan theo trạng thái ======
    def _can_edit_plan_in_state(self, state, op, vals=None):
        """
        state: 'draft' | 'waiting' | 'complete'
        op: 'create' | 'write' | 'unlink'
        """
        is_committee = self.env.user.has_group(COMMITTEE)
        is_director  = self.env.user.has_group(DIRECTOR)
        is_board     = self.env.user.has_group(BOARD)
        is_base      = self.env.user.has_group(BASE)

        if state == 'draft':
            # chỉ 3 nhóm này mới được thao tác
            return is_committee or is_director or is_board or is_base

        if state == 'waiting':
            # chỉ BOARD mới được write/unlink (create không phát sinh tại đây)
            return is_board or is_base

        if state == 'complete':
            # cấm mọi chỉnh sửa/xóa
            return False

        return False

    def _check_plan_edit_permission(self, op, vals=None):
        """
        Áp vào create/write/unlink của Plan.
        """
        if op == 'create':
            # tạo Plan mặc định là draft (nếu không truyền), áp rule draft
            state = (vals or {}).get('recruitment_status') or 'draft'
            if not self._can_edit_plan_in_state(state, 'create', vals):
                raise AccessError(_("Bạn không có quyền tạo Kế hoạch ở trạng thái '%s'.") % state)
            return

        # write/unlink: kiểm từng bản ghi
        for rec in self:
            state = rec.recruitment_status
            if not self._can_edit_plan_in_state(state, op, vals):
                action_name = {'create': 'tạo', 'write': 'sửa', 'unlink': 'xóa'}[op]
                raise AccessError(_("Không được %s Kế hoạch khi ở trạng thái '%s'.") % (action_name, state))

    # ----- Actions -----
    def action_submit(self):
        self._check_submit_groups()
        for rec in self:
            if rec.recruitment_status != "draft":
                raise ValidationError(_("Chỉ có thể trình duyệt từ trạng thái 'Dự thảo'."))
            rec.recruitment_status = "waiting"
            rec.message_post(body=_("Đã trình duyệt kế hoạch."))

    def action_complete(self):
        self._check_complete_groups()
        for rec in self:
            if rec.recruitment_status != "waiting":
                raise ValidationError(_("Chỉ có thể hoàn thành từ trạng thái 'Trình duyệt'."))
            if not rec.is_applied_to_jobs:
                rec._apply_recruitment_to_jobs()
                rec.is_applied_to_jobs = True
            rec.recruitment_status = "complete"
            rec.message_post(body=_("Đã hoàn thành kế hoạch."))

    # ----- Compute / helpers -----
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
        """Gộp theo job và GHI ĐÈ nhu cầu = tổng requested_quantity của CHÍNH kế hoạch này."""
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

        self.message_post(body=_("Đã áp dụng nhu cầu sang Job: %s")
                               % ", ".join(f"{j.display_name}={totals[j.id]}" for j in jobs))

    # ====== OVERRIDES: gộp kiểm quyền vào create/write/unlink ======
    @api.model
    def create(self, vals):
        self._check_plan_edit_permission('create', vals)
        # logic cũ: cấp số
        if vals.get('plan_code', _('New')) == _('New'):
            vals['plan_code'] = self.env['ir.sequence'].next_by_code('recruitment.plan.code') or _('New')
        return super().create(vals)

    def write(self, vals):
        self._check_plan_edit_permission('write', vals)
        return super().write(vals)

    def unlink(self):
        self._check_plan_edit_permission('unlink')
        return super().unlink()
