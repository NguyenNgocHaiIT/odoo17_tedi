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
    open_date = fields.Date(
        string='Ngày tạo',
        default=fields.Date.context_today,
        readonly=True,
    )
    director_note = fields.Text(string="Giám đôc ghi chú")

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
            if rec.plan_execute_date and rec.plan_execute_date < fields.Date.context_today(rec):
                pass
                # Đã bỏ validate chặn ngày theo yêu cầu xóa ràng buộc
                # raise ValidationError("Ngày thực hiện không được nhỏ hơn ngày hiện tại!")

    @api.onchange('plan_execute_date')
    def _onchange_plan_execute_date(self):
        if self.plan_execute_date and self.plan_execute_date < fields.Date.context_today(self):
            self.plan_execute_date = fields.Date.context_today(self)
            return {
                'warning': {
                    'title': "Cảnh báo ngày tháng",
                    'message': "Ngày thực hiện không được nhỏ hơn ngày hiện tại!"
                }
            }

    plan_name = fields.Char(string="Tên kế hoạch", tracking=True)

    def _get_default_people_suggestion(self):
        # Tìm bản ghi trong cấu hình Constant
        # Lưu ý: Nếu bạn muốn tìm theo code cụ thể, sửa domain thành [('code', '=', 'YOUR_CODE')]
        constant = self.env['recruitment.constant'].search([('code', '=', 'DEFAULT_CREATE')], limit=1)
        if constant:
            return constant.employee_id.id
        # Fallback: Nếu không có cấu hình thì lấy user hiện tại
        return self.env.user.employee_id.id

    def _get_default_department_responsible(self):
        # 1. Tìm cấu hình
        constant = self.env['recruitment.constant'].search([('code', '=', 'DEFAULT_CREATE')], limit=1)

        # 2. Nếu tìm thấy cấu hình + có nhân viên + nhân viên đó có phòng ban -> Lấy phòng ban đó
        if constant and constant.employee_id and constant.employee_id.department_id:
            return constant.employee_id.department_id.id

        # 3. Fallback: Lấy phòng ban của user hiện tại đang tạo phiếu
        return self.env.user.employee_id.department_id.id

    people_suggestion = fields.Many2one(
        "hr.employee",
        string="Người đề nghị",
        ondelete="set null",
        default=_get_default_people_suggestion  # Gọi hàm default mới
    )
    plan_purpose = fields.Char(string="Mục đích")

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

    note = fields.Text(string="Ghi chú")
    reject_reason = fields.Text(string="Lý do")

    reason = fields.Text(string="Lý do từ chối", required=True)

    @api.depends('recruitment_plan_detail_ids.total_line_fund')
    def _compute_plan_fund(self):
        for rec in self:
            rec.plan_fund = sum(rec.recruitment_plan_detail_ids.mapped('total_line_fund'))

    currency_id = fields.Many2one("res.currency", string="Tiền tệ",
                                  default=lambda self: self.env.ref("base.VND"), readonly=True)

    # --- TRẠNG THÁI (ĐÃ BỎ APPROVED) ---
    recruitment_status = fields.Selection([
        ("draft", "Dự thảo"),
        ("notify", "Xác nhận"),  # State cho bước Committee thông báo
        ("director_approve", "TGĐ duyệt"),  # Chờ GD duyệt
        ("board_approve", "HĐQT duyệt"),  # Chờ HĐQT duyệt (Năm)
        # ("approved", "Đã duyệt"),  <-- ĐÃ XÓA
        ("in_process", "Triển khai"),
        ("complete", "Hoàn thành"),
    ], string="Trạng thái", default="draft", index=True, required=True, tracking=True)

    is_applied_to_jobs = fields.Boolean(string="Đã triển khai (Update Job)", default=False, readonly=True)

    department_responsible = fields.Many2one(
        "hr.department",
        string="Phòng ban phụ trách",
        ondelete="set null",
        # Thay đổi từ lambda sang gọi hàm logic mới
        default=_get_default_department_responsible
    )

    recruitment_plan_detail_ids = fields.One2many(
        "recruitment.plan.detail", "plan_id", string="Thông tin chi tiết"
    )

    type = fields.Selection([
        ('year', 'Kế hoạch Năm'),
        ('quarter', 'Kế hoạch Quý'),
    ], string="Loại kế hoạch", default='year', required=True, tracking=True)

    parent_id = fields.Many2one('recruitment.plan', string="Thuộc Kế hoạch Năm", readonly=True)

    is_user_director = fields.Boolean(compute='_compute_is_user_director', store=False)
    is_user_board = fields.Boolean(compute='_compute_is_user_board', store=False)  # <--- MỚI

    def _compute_is_user_director(self):
        for rec in self:
            rec.is_user_director = self.env.user.has_group('quan_ly_tuyen_dung.group_recruitment_director')

    # <--- MỚI: Hàm check quyền HĐQT
    def _compute_is_user_board(self):
        for rec in self:
            rec.is_user_board = self.env.user.has_group('quan_ly_tuyen_dung.group_recruitment_board')

    @api.onchange('people_suggestion')
    def _onchange_people_suggestion(self):
        """
        Khi thay đổi Người đề nghị:
        - Nếu có chọn nhân viên -> Tự động điền Phòng ban của nhân viên đó.
        - Nếu xóa nhân viên -> Xóa luôn Phòng ban (hoặc bạn có thể bỏ dòng else nếu muốn giữ lại giá trị cũ).
        """
        if self.people_suggestion:
            self.department_responsible = self.people_suggestion.department_id
        else:
            self.department_responsible = False



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
                val = {
                    'department_request': dept.id,
                    'recruitment_job': line.job_id.id,
                    'requested_quantity': line.amount or 0,
                    'experient_request_id': line.experience_id.id if line.experience_id else False,
                    'professional_qualification': line.professional_qualification,
                    'note': line.note or '',
                    'expense_per_head': 0,
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

    # ----------------- ACTION FLOW (LUỒNG MỚI ĐÃ GỘP) -----------------

    # 1. Committee: Draft -> Director Approve
    def action_submit(self):
        for rec in self:
            if rec.recruitment_status != "draft":
                raise ValidationError(_("Chỉ có thể trình duyệt từ trạng thái 'Dự thảo'."))
            rec.recruitment_status = "director_approve"

    def action_draft(self):
        for rec in self.sudo():
            if rec.recruitment_status == "draft":
                raise ValidationError(_("Không thể thực hiện từ trạng thái 'Dự thảo'."))
            rec.sudo().write({'recruitment_status': "draft"})

    # 2. Director: Director Approve -> Board Approve (Năm)
    def action_director_approve_new(self):
        self._check_director()
        for rec in self:
            if rec.recruitment_status != "director_approve":
                raise ValidationError(_("Giám đốc chỉ duyệt được khi trạng thái là 'GD duyệt'."))
            rec.recruitment_status = "board_approve"

    # 3. Board: Board Approve -> IN PROCESS (NĂM) - DUYỆT LÀ CHẠY LUÔN
    def action_board_approve(self):
        self._check_board()
        for rec in self:
            if rec.recruitment_status != "board_approve":
                raise ValidationError(_("HĐQT chỉ duyệt được khi trạng thái là 'HĐQT duyệt'."))

            # A. Cập nhật vào Job ngay lập tức
            if not rec.is_applied_to_jobs:
                rec._apply_recruitment_to_jobs()
                rec.is_applied_to_jobs = True

                # B. Sinh 4 Kế hoạch Quý ngay lập tức
                if rec.type == 'year':
                    rec._generate_quarterly_plans()

            rec.recruitment_status = "in_process"
            rec.message_post(body=_("HĐQT đã phê duyệt. Kế hoạch chính thức được triển khai."))

    # 4. Director: Approve -> IN PROCESS (QUÝ) - DUYỆT LÀ CHẠY LUÔN
    def action_director_approve_quarter(self):
        self._check_director()
        for rec in self:
            if rec.type != 'quarter':
                raise ValidationError(_("Hành động này chỉ dành cho Kế hoạch Quý."))

            if rec.recruitment_status != 'director_approve':
                raise ValidationError(_("Chỉ có thể phê duyệt khi kế hoạch đang ở trạng thái 'Chờ duyệt'."))

            # A. Cập nhật vào Job ngay lập tức
            if not rec.is_applied_to_jobs:
                rec._apply_recruitment_to_jobs()
                rec.is_applied_to_jobs = True

            rec.recruitment_status = "in_process"
            rec.message_post(body=_("Giám đốc đã phê duyệt. Kế hoạch Quý chính thức được triển khai."))

    # --- HÀM TẠO 4 KẾ HOẠCH CON ---
    def _generate_quarterly_plans(self):
        self.ensure_one()
        base_year = self.plan_execute_date.year if self.plan_execute_date else fields.Date.today().year
        quarters_config = {
            1: {'field': 'qty_q1', 'month': 1},
            2: {'field': 'qty_q2', 'month': 4},
            3: {'field': 'qty_q3', 'month': 7},
            4: {'field': 'qty_q4', 'month': 10}
        }

        for q_num, config in quarters_config.items():
            field_qty = config['field']
            start_month = config['month']
            plan_name = f"{self.plan_name} - Quý {q_num}"

            existing = self.env['recruitment.plan'].search([
                ('parent_id', '=', self.id), ('plan_name', '=', plan_name)
            ], limit=1)
            if existing: continue

            q_execute_date = date(base_year, start_month, 1)

            plan_vals = {
                'plan_name': plan_name,
                'type': 'quarter',
                'parent_id': self.id,
                'recruitment_status': 'draft',
                'plan_execute_date': q_execute_date,
                'people_suggestion': self.people_suggestion.id,
                'department_responsible': self.department_responsible.id,
                'plan_purpose': f"Triển khai Quý {q_num} theo kế hoạch năm: {self.plan_code}",
                'open_date': fields.Date.today(),
            }

            detail_lines = []
            for line in self.recruitment_plan_detail_ids:
                if line.state == 'rejected':
                    continue
                qty_in_quarter = getattr(line, field_qty, 0)
                if qty_in_quarter > 0:
                    line_vals = {
                        'department_request': line.department_request.id,
                        'recruitment_job': line.recruitment_job.id,
                        'experient_request_id': line.experient_request_id.id,
                        'professional_qualification': line.professional_qualification,
                        'note': line.note,
                        'requested_quantity': qty_in_quarter,
                        'expense_per_head': line.expense_per_head,
                    }
                    detail_lines.append((0, 0, line_vals))

            if detail_lines:
                plan_vals['recruitment_plan_detail_ids'] = detail_lines
                self.env['recruitment.plan'].create(plan_vals)

    # 5. Complete
    def action_complete(self):
        for rec in self:
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

    # ----------------- CÁC HÀM XỬ LÝ LUỒNG QUÝ (PHỤ) -----------------
    def action_notify_quarter(self):
        self._check_committee()
        for rec in self:
            if rec.type != 'quarter':
                raise ValidationError(_("Hành động này chỉ dành cho Kế hoạch Quý."))
            if rec.recruitment_status != 'draft':
                raise ValidationError(_("Chỉ có thể thông báo khi kế hoạch đang ở 'Dự thảo'."))
            rec.recruitment_status = 'notify'
            rec.message_post(body=_("Committee đã gửi thông báo kế hoạch quý."))

    def action_submit_quarter(self):
        self._check_committee()
        for rec in self:
            if rec.type != 'quarter':
                raise ValidationError(_("Hành động này chỉ dành cho Kế hoạch Quý."))
            if rec.recruitment_status != 'notify':
                raise ValidationError(_("Chỉ có thể trình duyệt từ trạng thái 'Thông báo'."))
            rec.recruitment_status = 'director_approve'
            rec.message_post(body=_("Committee đã trình duyệt kế hoạch lên Giám đốc."))

    def action_complete_quarter(self):
        self._check_director()
        for rec in self:
            if rec.type != 'quarter':
                raise ValidationError(_("Hành động này chỉ dành cho Kế hoạch Quý."))
            if rec.recruitment_status != "in_process":
                raise ValidationError(_("Chỉ hoàn thành được khi trạng thái là 'Đang triển khai'."))
            rec.recruitment_status = "complete"
            rec.message_post(body=_("Giám đốc xác nhận hoàn thành kế hoạch quý."))

    # ----------------- CRUD OVERRIDES (BỎ RÀNG BUỘC) -----------------
    @api.model
    def create(self, vals):
        if vals.get('plan_code', _('New')) == _('New'):
            vals['plan_code'] = self.env['ir.sequence'].next_by_code('recruitment.plan.code') or _('New')
        return super().create(vals)

    def write(self, vals):
        # ĐÃ BỎ RÀNG BUỘC CHECK QUYỀN ĐỂ TRÁNH LỖI "Invalid Operation"
        return super().write(vals)

    def unlink(self):
        # ĐÃ BỎ RÀNG BUỘC CHECK QUYỀN
        return super().unlink()

    def action_open_reject_wizard(self):
        return {
            'name': _('Nhập lý do từ chối'),
            'type': 'ir.actions.act_window',
            'res_model': 'recruitment.plan.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_plan_id': self.id,
                # Truyền giá trị hiện tại của reject_reason vào modal (nếu muốn sửa lại lý do cũ)
                'default_reject_reason': self.reject_reason
            }
        }


class RecruitmentPlanRejectWizard(models.TransientModel):
    _name = 'recruitment.plan.reject.wizard'
    _description = 'Wizard nhập lý do từ chối'

    plan_id = fields.Many2one('recruitment.plan', string="Kế hoạch", required=True)

    # Đặt tên giống hệt field bên model chính
    reject_reason = fields.Text(string="Lý do từ chối", required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        # Ghi đè giá trị từ Wizard vào Model chính
        self.plan_id.sudo().write({
            'reject_reason': self.reject_reason,  # Map 1-1
            'recruitment_status': 'draft'  # Trả về nháp
        })
        # Log chatter
        self.plan_id.message_post(body=f"Đã từ chối. Lý do: {self.reject_reason}")
        return {'type': 'ir.actions.act_window_close'}