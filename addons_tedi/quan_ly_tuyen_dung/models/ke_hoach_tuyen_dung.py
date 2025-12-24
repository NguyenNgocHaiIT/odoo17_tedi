from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from datetime import datetime, date

# Định nghĩa các nhóm quyền
HR_OFFICER = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
COMMITTEE = 'quan_ly_tuyen_dung.group_recruitment_committee'
DIRECTOR = 'quan_ly_tuyen_dung.group_recruitment_director'
BOARD = 'quan_ly_tuyen_dung.group_recruitment_board'
BASE = 'base.group_user'


class RecruitmentPlan(models.Model):
    _name = "recruitment.plan"
    _description = "Recruitment Plan"
    _rec_name = "plan_name"
    _order = "sequence"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- CÁC FIELD CƠ BẢN ---
    sequence = fields.Integer(string="STT sắp xếp", default=10)
    stt = fields.Integer(string="STT", compute="_compute_stt", store=False, readonly=True)

    plan_code = fields.Char(
        string="Số kế hoạch", required=True, readonly=True, copy=False,
        default=lambda self: _('New'), tracking=True
    )
    plan_execute_date = fields.Date(string="Ngày thực hiện", tracking=True, default=fields.Date.today)
    @api.constrains('plan_execute_date')
    def _check_plan_execute_date(self):
        for rec in self:
            # Nếu có chọn ngày VÀ ngày đó nhỏ hơn ngày hiện tại
            if rec.plan_execute_date and rec.plan_execute_date < fields.Date.context_today(rec):
                raise ValidationError("Ngày thực hiện không được nhỏ hơn ngày hiện tại!")

    @api.onchange('plan_execute_date')
    def _onchange_plan_execute_date(self):
        if self.plan_execute_date and self.plan_execute_date < fields.Date.context_today(self):
            # Reset về ngày hiện tại để người dùng không giữ giá trị sai
            self.plan_execute_date = fields.Date.context_today(self)
            return {
                'warning': {
                    'title': "Cảnh báo ngày tháng",
                    'message': "Ngày thực hiện không được nhỏ hơn ngày hiện tại!"
                }
            }
    plan_name = fields.Char(string="Tên kế hoạch", tracking=True)

    people_suggestion = fields.Many2one(
        "hr.employee",
        string="Người đề nghị",
        ondelete="set null",
        default=lambda self: self.env.user.employee_id.id
    )
    plan_purpose = fields.Char(string="Mục đích")

    # Field chọn đợt khảo sát
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

    plan_fund = fields.Monetary(
        string="Kinh phí",
        currency_field="currency_id",
        compute="_compute_plan_fund",
        store=True,
        readonly=True
    )

    @api.depends('recruitment_plan_detail_ids.total_line_fund')
    def _compute_plan_fund(self):
        for rec in self:
            # Tổng thành tiền của tất cả các dòng
            rec.plan_fund = sum(rec.recruitment_plan_detail_ids.mapped('total_line_fund'))

    currency_id = fields.Many2one("res.currency", string="Tiền tệ",
                                  default=lambda self: self.env.ref("base.VND"), readonly=True)

    # --- TRẠNG THÁI (ĐÃ CẬP NHẬT THEO LUỒNG MỚI) ---
    recruitment_status = fields.Selection([
        ("draft", "Dự thảo"),
        ("notify", "Thông báo"),  # <-- MỚI: State cho bước Committee thông báo
        ("director_approve", "Chờ duyệt"),  # Dùng lại key cũ cho bước "Chờ GD duyệt"
        ("board_approve", "HĐQT duyệt"),  # Dùng cho kế hoạch Năm
        ("approved", "Đã duyệt"),
        ("in_process", "Đang triển khai"),
        ("complete", "Hoàn thành"),
    ], string="Trạng thái", default="draft", index=True, required=True, tracking=True)

    is_applied_to_jobs = fields.Boolean(string="Đã triển khai (Update Job)", default=False, readonly=True)

    department_responsible = fields.Many2one(
        "hr.department",
        string="Phòng ban phụ trách",
        ondelete="set null",
        default=lambda self: self.env.user.employee_id.department_id.id
    )

    recruitment_plan_detail_ids = fields.One2many(
        "recruitment.plan.detail", "plan_id", string="Thông tin chi tiết"
    )

    type = fields.Selection([
        ('year', 'Kế hoạch Năm'),
        ('quarter', 'Kế hoạch Quý'),
    ], string="Loại kế hoạch", default='year', required=True, tracking=True)

    # Field liên kết cha-con (để biết kế hoạch Quý thuộc Kế hoạch Năm nào)
    parent_id = fields.Many2one('recruitment.plan', string="Thuộc Kế hoạch Năm", readonly=True)

    # ----------------- LOGIC TỰ ĐỘNG LẤY DỮ LIỆU TỪ KHẢO SÁT -----------------
    @api.onchange('survey_id')
    def _onchange_survey_id(self):
        if not self.survey_id:
            return

        needs = self.env['recruitment.needs'].search([
            ('name', '=', self.survey_id.id),
            ('state', '=', 'confirmed')
        ])

        if not needs:
            self.recruitment_plan_detail_ids = [(5, 0, 0)]
            return

        new_lines = []
        for need in needs:
            dept = need.department_id
            if not dept: continue
            for line in need.line_ids:
                if not line.job_id: continue

                # Mapping dữ liệu
                val = {
                    'department_request': dept.id,
                    'recruitment_job': line.job_id.id,
                    'requested_quantity': line.amount or 0,
                    'experient_request_id': line.experience_id.id if line.experience_id else False,
                    'professional_qualification': line.professional_qualification,
                    'note': line.note or '',

                    # --- (MỚI) LẤY CHI PHÍ TỪ EXPECTED SALARY ---
                    # 'expense_per_head': line.expected_salary,
                    'expense_per_head': 0,

                    # # Mapping Quý
                    'qty_q1': line.qty_q1,
                    'qty_q2': line.qty_q2,
                    'qty_q3': line.qty_q3,
                    'qty_q4': line.qty_q4,
                }
                new_lines.append((0, 0, val))

        self.recruitment_plan_detail_ids = [(5, 0, 0)] + new_lines

    # ----------------- KIỂM TRA QUYỀN (HELPER) -----------------
    def _check_committee(self):
        if not self.env.user.has_group(COMMITTEE):
            raise AccessError(_("Chỉ Ủy ban (Committee) mới được thực hiện thao tác này."))

    def _check_board(self):
        if not self.env.user.has_group(BOARD):
            raise AccessError(_("Chỉ HĐQT (Board) mới được thực hiện thao tác này."))

    def _check_director(self):
        if not self.env.user.has_group(DIRECTOR):
            raise AccessError(_("Chỉ Giám đốc (Director) mới được thực hiện thao tác này."))

    # ----------------- QUYỀN SỬA ĐỔI (EDIT RULES) -----------------
    def _can_edit_plan_in_state(self, state, op, vals=None):
        u = self.env.user
        is_committee = u.has_group(COMMITTEE)
        is_director = u.has_group(DIRECTOR)
        is_board = u.has_group(BOARD)


        # Committee sửa khi Draft
        if state == 'draft':
            return is_committee or u.has_group(BASE)

        # Giám đốc sửa khi đang chờ Giám đốc duyệt (để điều chỉnh trước khi duyệt)
        if state == 'director_approve':
            return is_director

        # HĐQT sửa khi đang chờ HĐQT duyệt
        if state == 'board_approve':
            return is_board

        # Khi đã duyệt hoặc hoàn thành -> Không ai sửa
        return False

    def _check_plan_edit_permission(self, op, vals=None):
        if op == 'create':
            state = (vals or {}).get('recruitment_status') or 'draft'
            if not self._can_edit_plan_in_state(state, 'create', vals):
                raise AccessError(_("Bạn không có quyền tạo Kế hoạch ở trạng thái '%s'.") % state)
            return
        # for rec in self:
        #     if not self._can_edit_plan_in_state(rec.recruitment_status, op, vals):
        #         action_name = {'create': 'tạo', 'write': 'sửa', 'unlink': 'xóa'}[op]
        #         raise AccessError(_("Không được %s Kế hoạch khi ở trạng thái '%s'.")
        #                           % (action_name, rec.recruitment_status))

    # ----------------- ACTION FLOW (LUỒNG MỚI) -----------------

    # 1. Committee: Draft -> Director Approve
    def action_submit(self):
        self._check_committee()
        for rec in self:
            if rec.recruitment_status != "draft":
                raise ValidationError(_("Chỉ có thể trình duyệt từ trạng thái 'Dự thảo'."))
            rec.recruitment_status = "director_approve"

    # 2. Director: Director Approve -> Board Approve
    def action_director_approve_new(self):
        self._check_director()
        for rec in self:
            if rec.recruitment_status != "director_approve":
                raise ValidationError(_("Giám đốc chỉ duyệt được khi trạng thái là 'GD duyệt'."))
            rec.recruitment_status = "board_approve"

    # 3. Board: Board Approve -> Approved (Chờ triển khai)
    def action_board_approve(self):
        self._check_board()
        for rec in self:
            if rec.recruitment_status != "board_approve":
                raise ValidationError(_("HĐQT chỉ duyệt được khi trạng thái là 'HĐQT duyệt'."))
            rec.recruitment_status = "approved"

    # 4. Director: Bắt đầu (Triển khai) -> Update Jobs
    def action_director_start_deploy(self):
        # ... (Giữ nguyên logic check quyền cũ) ...
        self._check_director()
        for rec in self:
            if rec.recruitment_status != "approved":
                raise ValidationError(_("Chỉ có thể triển khai khi Kế hoạch đã được HĐQT phê duyệt."))
            if rec.is_applied_to_jobs:
                raise ValidationError(_("Kế hoạch này đã được triển khai."))

            # A. Cập nhật vào Job (Logic cũ)
            rec._apply_recruitment_to_jobs()
            rec.is_applied_to_jobs = True

            # B. Nếu là Kế hoạch Năm -> Tự động sinh 4 Kế hoạch Quý
            if rec.type == 'year':
                rec._generate_quarterly_plans()

            rec.message_post(body=_("Giám đốc đã bắt đầu triển khai kế hoạch."))
            rec.recruitment_status = "in_process"

    def action_director_approve_quarter(self):
        """
        Kế hoạch Quý: Giám đốc duyệt thẳng từ Dự thảo -> Đã duyệt.
        Bỏ qua bước Trình duyệt và HĐQT.
        """
        self._check_director()
        for rec in self:
            if rec.type != 'quarter':
                raise ValidationError(_("Hành động này chỉ dành cho Kế hoạch Quý."))

            if rec.recruitment_status != 'draft':
                raise ValidationError(_("Chỉ có thể duyệt khi kế hoạch đang ở trạng thái 'Dự thảo'."))

            # Chuyển thẳng sang Approved
            rec.recruitment_status = "approved"

            # Log lại
            rec.message_post(body=_("Giám đốc đã phê duyệt Kế hoạch Quý (Duyệt nhanh)."))

    # --- HÀM TẠO 4 KẾ HOẠCH CON ---
    def _generate_quarterly_plans(self):
        self.ensure_one()
        quarters_map = {1: 'qty_q1', 2: 'qty_q2', 3: 'qty_q3', 4: 'qty_q4'}

        for q_num, field_qty in quarters_map.items():
            plan_name = f"{self.plan_name} - Quý {q_num}"

            # Check tồn tại
            existing = self.env['recruitment.plan'].search([
                ('parent_id', '=', self.id), ('plan_name', '=', plan_name)
            ], limit=1)
            if existing: continue

            # Tạo Header Quý
            plan_vals = {
                'plan_name': plan_name,
                'type': 'quarter',
                'parent_id': self.id,
                'recruitment_status': 'draft',
                'plan_execute_date': self.plan_execute_date,
                'people_suggestion': self.people_suggestion.id,
                'department_responsible': self.department_responsible.id,
                'plan_purpose': f"Triển khai Quý {q_num} theo kế hoạch năm: {self.plan_code}",
            }

            # Tạo Lines Quý
            detail_lines = []
            for line in self.recruitment_plan_detail_ids:

                # --- UPDATE: Bỏ qua dòng đã bị Từ chối ---
                if line.state == 'rejected':
                    continue
                # -----------------------------------------

                qty_in_quarter = getattr(line, field_qty, 0)
                if qty_in_quarter > 0:
                    line_vals = {
                        'department_request': line.department_request.id,
                        'recruitment_job': line.recruitment_job.id,
                        'experient_request_id': line.experient_request_id.id,
                        'professional_qualification': line.professional_qualification,
                        'note': line.note,

                        # --- QUAN TRỌNG: TRUYỀN SỐ LƯỢNG VÀ ĐƠN GIÁ ---
                        'requested_quantity': qty_in_quarter,
                        'expense_per_head': line.expense_per_head,
                        # ---------------------------------------------
                    }
                    detail_lines.append((0, 0, line_vals))

            # Chỉ tạo kế hoạch quý nếu có ít nhất 1 dòng chi tiết hợp lệ
            if detail_lines:
                plan_vals['recruitment_plan_detail_ids'] = detail_lines
                self.env['recruitment.plan'].create(plan_vals)

    # 5. Committee: Complete
    def action_complete(self):
        self._check_committee()
        for rec in self:
            if rec.recruitment_status != "approved":
                raise ValidationError(_("Chỉ hoàn thành được khi trạng thái là 'Đã duyệt'."))

            # (Tùy chọn) Kiểm tra xem Giám đốc đã triển khai chưa?
            # if not rec.is_applied_to_jobs:
            #     raise ValidationError(_("Kế hoạch chưa được triển khai (Cập nhật Job). Vui lòng chờ Giám đốc bấm 'Bắt đầu'."))

            rec.recruitment_status = "complete"

    # ----------------- LOGIC CẬP NHẬT JOB -----------------
    def _apply_recruitment_to_jobs(self):
        """Gộp theo job và GHI ĐÈ nhu cầu (số lượng tuyển) vào model hr.job"""
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
            # Ghi đè số lượng tuyển dụng mục tiêu của Job
            job.no_of_recruitment = totals[job.id]

    # ----------------- COMPUTE & CONSTRAINTS -----------------
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

    @api.constrains('plan_execute_date')
    def _check_plan_execute_date(self):
        for rec in self:
            if rec.plan_execute_date:
                if isinstance(rec.plan_execute_date, str):
                    plan_date = datetime.strptime(rec.plan_execute_date, '%Y-%m-%d').date()
                else:
                    plan_date = rec.plan_execute_date
                if plan_date < date.today():
                    raise ValidationError("Ngày thực hiện không được nhỏ hơn ngày hiện tại.")

        # ----------------- CÁC HÀM XỬ LÝ LUỒNG QUÝ (MỚI) -----------------

        # BƯỚC 1: Committee: Draft -> Notify

    def action_notify_quarter(self):
        self._check_committee()
        for rec in self:
            if rec.type != 'quarter':
                raise ValidationError(_("Hành động này chỉ dành cho Kế hoạch Quý."))
            if rec.recruitment_status != 'draft':
                raise ValidationError(_("Chỉ có thể thông báo khi kế hoạch đang ở 'Dự thảo'."))

            rec.recruitment_status = 'notify'
            rec.message_post(body=_("Committee đã gửi thông báo kế hoạch quý."))

        # BƯỚC 2: Committee: Notify -> Director Approve (Trình duyệt -> Chờ duyệt)
    def action_submit_quarter(self):
        self._check_committee()
        for rec in self:
            if rec.type != 'quarter':
                raise ValidationError(_("Hành động này chỉ dành cho Kế hoạch Quý."))
            if rec.recruitment_status != 'notify':
                raise ValidationError(_("Chỉ có thể trình duyệt từ trạng thái 'Thông báo'."))

            rec.recruitment_status = 'director_approve'
            rec.message_post(body=_("Committee đã trình duyệt kế hoạch lên Giám đốc."))

        # BƯỚC 3: Director: Director Approve -> Approved (Phê duyệt)
    def action_director_approve_quarter(self):
        self._check_director()
        for rec in self:
            if rec.type != 'quarter':
                raise ValidationError(_("Hành động này chỉ dành cho Kế hoạch Quý."))

                # Sửa logic: Phải từ 'director_approve' (Chờ duyệt) mới được duyệt
            if rec.recruitment_status != 'director_approve':
                 raise ValidationError(_("Chỉ có thể phê duyệt khi kế hoạch đang ở trạng thái 'Chờ duyệt'."))

            rec.recruitment_status = "approved"
            rec.message_post(body=_("Giám đốc đã phê duyệt Kế hoạch Quý."))

    # BƯỚC 4: Director: Approved -> In Process (Triển khai)
        # (Dùng lại hàm action_director_start_deploy cũ, logic không đổi)

        # BƯỚC 5: Director: In Process -> Complete (Hoàn thành)
    def action_complete_quarter(self):
        self._check_director()  # Yêu cầu Director (theo đề bài)
        for rec in self:
            if rec.type != 'quarter':
                raise ValidationError(_("Hành động này chỉ dành cho Kế hoạch Quý."))

            if rec.recruitment_status != "in_process":
                raise ValidationError(_("Chỉ hoàn thành được khi trạng thái là 'Đang triển khai'."))

            rec.recruitment_status = "complete"
            rec.message_post(body=_("Giám đốc xác nhận hoàn thành kế hoạch quý."))



    # ----------------- CRUD OVERRIDES (PHÂN QUYỀN) -----------------
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