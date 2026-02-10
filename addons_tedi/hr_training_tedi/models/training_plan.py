from odoo import models, api, fields, exceptions, _
from odoo.exceptions import AccessError, ValidationError


PARTICIPANT         = "hr_training_tedi.group_training_participant"
UNIT_MANAGER        = "hr_training_tedi.group_training_unit_manager"
GENERAL_DIRECTOR    = "hr_training_tedi.group_training_general_director"
BASE                = "base.group_user"

MANAGER = "hr_training_tedi.group_training_manager" # Quản lý nghiệp vụ (tương đương HR Officer bên Tuyển dụng)
BOARD = "hr_training_tedi.group_training_board"

class TrainingPlan(models.Model):
    _name = 'training.plan'
    _description = 'Training Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tên kế hoạch', required=True)

    # Ngày tạo
    open_date = fields.Date(
        string='Ngày tạo',
        default=fields.Date.context_today,
        readonly=True,
    )

    note = fields.Text(string="Ghi chú")
    reject_reason = fields.Text(string="Lý do từ chối")

    # Thêm field ngày thực hiện để có thể check logic (nếu cần dùng cho KH Quý giống Tuyển dụng)
    # Nếu logic cũ bạn không dùng field này để tính toán thì để hiển thị thôi
    plan_execute_date = fields.Date(string="Ngày thực hiện", default=fields.Date.today)

    # Đợt khảo sát
    survey_id = fields.Many2one(
        'training.needs.survey',
        string="Đợt khảo sát",
        help="Mỗi kế hoạch chỉ ứng với 1 đợt khảo sát.",
    )

    detail_ids = fields.One2many(
        'training.plan.detail',
        'plan_id',
        string='Chi tiết kế hoạch'
    )

    # --- SỬA STATE THEO YÊU CẦU ---
    state = fields.Selection([
        ("draft", "Dự thảo"),
        ("notify", "Xác nhận"),  # Mới: Dành cho bước confirm của Quý
        ("director_approve", "TGĐ duyệt"),  # Cũ là pending
        ("board_approve", "HĐQT duyệt"),  # Mới: Dành cho KH Năm
        # ("approved", "Đã duyệt"),  # Đã duyệt nhưng chưa triển khai
        ("in_process", "Đang triển khai"),  # Đã bấm triển khai -> Sinh dữ liệu
        ("complete", "Hoàn thành"),
    ], string="Trạng thái", default='draft', tracking=True)

    # Cờ đánh dấu đã triển khai (để ẩn nút Triển khai)
    is_applied = fields.Boolean(string="Đã triển khai", default=False, readonly=True)



    # THỐNG KÊ
    student_count = fields.Integer(
        string='Số lượng học viên',
        compute='_compute_stats',
        store=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.ref("base.VND"),
        readonly=True,
    )

    total_fee = fields.Monetary(
        string='Tổng chi phí kế hoạch',
        currency_field='currency_id',
        compute='_compute_stats',
        store=True,
    )

    type = fields.Selection([
        ('year', 'Kế hoạch Năm'),
        ('quarter', 'Kế hoạch Quý'),
    ], string="Loại kế hoạch", default='year', required=True, tracking=True)

    is_user_director = fields.Boolean(compute='_compute_is_user_director', store=False)
    is_user_board = fields.Boolean(compute='_compute_is_user_board', store=False)

    def _compute_is_user_director(self):
        for rec in self:
            rec.is_user_director = self.env.user.has_group(GENERAL_DIRECTOR)

    def _compute_is_user_board(self):
        for rec in self:
            rec.is_user_board = self.env.user.has_group(BOARD)

    # Field liên kết cha-con (để biết kế hoạch Quý thuộc Kế hoạch Năm nào)
    parent_id = fields.Many2one('training.plan', string="Thuộc Kế hoạch Năm", readonly=True)

    # =========================================
    #      ====== FUNCTION LOGIC (GIỮ NGUYÊN) ======
    # =========================================

    @api.onchange('survey_id')
    def _onchange_survey_id(self):
        # ... (Giữ nguyên logic của bạn) ...
        self.detail_ids = [(5, 0, 0)]
        if not self.survey_id: return

        TrainingNeeds = self.env['trainings.needs']
        needs = TrainingNeeds.search([('name', '=', self.survey_id.id), ('state', '=', 'approved')])
        if not needs: return

        course_ids = set()
        for need in needs:
            for line in need.line_ids:
                if line.course_id:
                    course_ids.add(line.course_id.id)

        new_lines = []
        for c_id in course_ids:
            new_lines.append(
                (0, 0, {'course_id': c_id, 'execution_date': self.plan_execute_date or fields.Date.today()}))
        self.detail_ids = new_lines

    def _generate_participants_from_survey(self):
        Participation = self.env['training.plan.participation']
        ParticipationDetail = self.env['training.plan.participation.detail']
        TrainingNeeds = self.env['trainings.needs']

        for plan in self:
            if not plan.survey_id: continue
            needs = TrainingNeeds.search([('name', '=', plan.survey_id.id), ('state', '=', 'approved')])
            if not needs: continue

            course_map = {}
            for need in needs:
                student = need.user_id or need.create_uid or self.env.user
                for line in need.line_ids:
                    if not line.course_id: continue
                    course_id = line.course_id.id
                    course_map.setdefault(course_id, []).append((student, line))

            for course_id, items in course_map.items():
                detail = plan.detail_ids.filtered(lambda d: d.course_id.id == course_id)[:1]

                # --- ĐOẠN CẦN SỬA Ở ĐÂY ---
                if not detail:
                    # Nếu là Kế hoạch Quý:
                    # Bỏ qua các môn không có trong danh sách (vì đó là môn của Quý khác)
                    if plan.type == 'quarter':
                        continue

                        # Nếu là Kế hoạch Năm hoặc loại khác: Giữ nguyên logic cũ (tự tạo dòng)
                    detail = self.env['training.plan.detail'].create({
                        'plan_id': plan.id,
                        'course_id': course_id,
                        'execution_date': plan.plan_execute_date or fields.Date.today()
                    })
                # --------------------------

                participation = Participation.search([
                    ('training_plan_id', '=', plan.id),
                    ('training_plan_detail_id', '=', detail.id),
                ], limit=1)

                if not participation:
                    participation = Participation.create({
                        'training_plan_id': plan.id,
                        'training_plan_detail_id': detail.id,
                        'create_date': fields.Date.today(),
                        'state': 'draft',
                    })

                for student, line in items:
                    existing = ParticipationDetail.search(
                        [('participation_id', '=', participation.id), ('user_id', '=', student.id)], limit=1)
                    if not existing:
                        part_detail = ParticipationDetail.create({
                            'participation_id': participation.id,
                            'user_id': student.id,
                            'note': line.note,
                        })
                        line.participation_detail_id = part_detail.id

    def _generate_quarterly_plans(self):
        # ... (Giữ nguyên logic của bạn: Duyệt 4 quý, check field quarter) ...
        self.ensure_one()
        for q_num in range(1, 5):
            q_str = str(q_num)

            # GIỮ NGUYÊN LOGIC FILTER THEO QUÝ CỦA BẠN
            lines_in_quarter = self.detail_ids.filtered(
                lambda l: l.quarter == q_str
                          and l.state != 'rejected'
                          and l.expected_qty > 0
            )
            if not lines_in_quarter: continue

            plan_name = f"{self.name} - Quý {q_num}"
            existing = self.env['training.plan'].search([('parent_id', '=', self.id), ('name', '=', plan_name)],
                                                        limit=1)
            if existing: continue

            # Tạo Header
            plan_vals = {
                'name': plan_name,
                'type': 'quarter',
                'parent_id': self.id,
                'state': 'draft',  # Trạng thái ban đầu của con là Draft
                'open_date': fields.Date.today(),
                'survey_id': self.survey_id.id,
                'currency_id': self.currency_id.id,
            }

            # Tạo Lines
            detail_lines = []
            for line in lines_in_quarter:
                line_vals = {
                    'course_id': line.course_id.id,
                    'training_center': line.training_center,
                    'training_type': line.training_type,
                    'training_location': line.training_location,
                    'training_fee_per_person': line.training_fee_per_person,
                    'training_fee_source': line.training_fee_source,
                    'note': line.note,
                    'student_count': 0,
                    'expected_qty': line.expected_qty,
                    'execution_date': line.execution_date,  # Mang ngày sang để tính lại quý
                    'training_time':line.training_time,
                }
                detail_lines.append((0, 0, line_vals))

            if detail_lines:
                plan_vals['detail_ids'] = detail_lines
                self.env['training.plan'].create(plan_vals)

    @api.model
    def create(self, vals):
        return super().create(vals)

    def write(self, vals):
        return super().write(vals)

    @api.depends('detail_ids.participation_detail_ids.training_fee_per_person')
    def _compute_stats(self):
        ParticipationDetail = self.env['training.plan.participation.detail']
        for plan in self:
            if plan.detail_ids:
                participants = ParticipationDetail.search([
                    ('training_plan_detail_id', 'in', plan.detail_ids.ids)
                ])
                plan.student_count = len(participants)
                plan.total_fee = sum((line.training_fee_per_person or 0.0) for line in participants)
            else:
                plan.student_count = 0
                plan.total_fee = 0.0

    # =========================================
    #      ====== ACTION STATE (CẬP NHẬT) ======
    # =========================================

    # 1. Draft -> Director Approve (Năm) / Notify (Quý)
    def action_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_notify_quarter(self):  # Dành cho Quý
        for rec in self:
            if rec.type != 'quarter': raise ValidationError(_("Chỉ dành cho Kế hoạch Quý"))
            rec.state = 'notify'

    def action_submit(self):
        for rec in self:
            # Nếu là Quý: Notify -> Director Approve
            if rec.type == 'quarter':
                if rec.state != 'notify': raise ValidationError(_("Phải ở trạng thái Xác nhận."))
            # Nếu là Năm: Draft -> Director Approve
            else:
                if rec.state != "draft": raise ValidationError(_("Phải ở trạng thái Dự thảo."))

            rec.state = "director_approve"

    # 2. Director Approve -> Board Approve (Năm) / Approved (Quý)
    def action_director_approve(self):
        # Check quyền GENERAL_DIRECTOR (ở view hoặc check code)
        for rec in self:
            if rec.state != "director_approve":
                raise ValidationError(_("Chỉ duyệt khi đang chờ duyệt."))

            # Thay đổi: Dù là Năm hay Quý đều phải qua HĐQT
            rec.state = "board_approve"

    # 3. Board Approve -> Approved (Chỉ Năm)
    def action_board_approve(self):
        # Check quyền BOARD (ở view hoặc check code)
        for rec in self:
            if rec.state != "board_approve":
                raise ValidationError(_("Chỉ duyệt khi HĐQT đang xem xét."))

            # Xử lý Logic Triển khai (Idempotency check)
            if not rec.is_applied:

                # A. LOGIC CHO KẾ HOẠCH NĂM: Sinh 4 KH Quý
                if rec.type == 'year':
                    rec._generate_quarterly_plans()
                    msg = "HĐQT đã phê duyệt Kế hoạch Năm. Hệ thống đã sinh Kế hoạch Quý."

                # B. LOGIC CHO KẾ HOẠCH QUÝ: Sinh Học viên
                elif rec.type == 'quarter':
                    rec._generate_participants_from_survey()
                    # Đồng bộ lịch sử thay đổi (nếu có logic này)
                    for detail in rec.detail_ids:
                        for part_detail in detail.participation_detail_ids:
                            part_detail._sync_to_history()
                    msg = "HĐQT đã phê duyệt Kế hoạch Quý. Hệ thống đã chốt danh sách học viên."

                rec.is_applied = True
                rec.message_post(body=_(msg))

            # Chuyển trạng thái sang Đang triển khai
            rec.state = "in_process"

    # 4. Approved -> In Process (Triển khai - Nút này sẽ gọi Logic sinh dữ liệu)
    def action_deploy(self):
        # Đây là nút mới tách ra, thay vì để trong action_approve cũ
        for rec in self:
            if rec.state != "approved":
                raise ValidationError(_("Kế hoạch phải được phê duyệt trước khi triển khai."))
            if rec.is_applied:
                raise ValidationError(_("Kế hoạch đã được triển khai rồi."))

            # --- GỌI LOGIC CŨ CỦA BẠN TẠI ĐÂY ---
            if rec.type == 'year':
                rec._generate_quarterly_plans()  # Logic sinh quý (Giữ nguyên)
                # rec.message_post(body=_("Đã triển khai & Sinh kế hoạch Quý."))

            elif rec.type == 'quarter':
                rec._generate_participants_from_survey()  # Logic sinh học viên (Giữ nguyên)
                # Sync history
                for detail in rec.detail_ids:
                    for part_detail in detail.participation_detail_ids:
                        part_detail._sync_to_history()
                # rec.message_post(body=_("Đã triển khai & Sinh danh sách học viên."))

            rec.is_applied = True
            rec.state = "in_process"

    # 5. Complete
    def action_complete(self):
        for rec in self:
            if rec.state != "in_process":
                raise ValidationError(_("Chỉ hoàn thành khi đang triển khai."))
            rec.state = "complete"

    def action_reject(self):
        for rec in self:
            # Cho phép từ chối ở các bước duyệt
            if rec.state not in ['director_approve', 'board_approve']:
                raise ValidationError(_("Không thể từ chối ở trạng thái này."))
            rec.state = "draft"

    def action_open_reject_wizard(self):
        self.ensure_one()
        return {
            'name': _('Nhập lý do từ chối'),
            'type': 'ir.actions.act_window',
            'res_model': 'training.plan.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_plan_id': self.id,
                'default_reject_reason': self.reject_reason
            }
        }


class TrainingPlanDetail(models.Model):
    _name = 'training.plan.detail'
    _description = 'Training Plan Detail'
    _rec_name = 'course_id'

    plan_id = fields.Many2one(
        'training.plan',
        string='Kế hoạch đào tạo',
        ondelete='cascade'
    )

    course_id = fields.Many2one(
        "training.course",
        string="Khoá đào tạo"
    )

    training_center = fields.Selection(
        [
            ("place_1", "Cơ sở 1"),
            ("place_2", "Cơ sở 2"),
            ("place_3", "Cơ sở 3"),
        ],
        string="Cơ sở đào tạo",
    )
    training_time = fields.Char(string="Thời lượng đào tạo")

    state = fields.Selection([
        ("approved", "Đã phê duyệt"),
        ("rejected", "Từ chối")
    ], string="Trạng thái dòng", default="approved", readonly=True)

    reject_reason = fields.Text(string="Lý do từ chối", readonly=True)

    # Field này đã có trong code cũ của bạn, đảm bảo nó được store=True để dùng trong XML invisible
    plan_state = fields.Selection(
        related='plan_id.state',
        string="Trạng thái Plan",
        readonly=True,
        store=True
    )

    training_type = fields.Selection([
        ("direct", "Trực tiếp"),
        ("indirect", "Gián tiếp")
    ], string="Hình thức đào tạo", default='direct')

    time_of_execution = fields.Char(string="Thời gian thực hiện")
    start_date = fields.Date(string="Từ ngày")
    end_date = fields.Date(string="Đến ngày")

    training_location = fields.Char(string="Địa điểm đào tạo")

    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        default=lambda self: self.env.ref("base.VND"),
        readonly=True,
    )

    training_fee_per_person = fields.Monetary(
        string="Chi phí/người",
        currency_field="currency_id"
    )

    training_total_fee = fields.Monetary(
        string="Tổng chi phí",
        currency_field="currency_id",
        compute='_compute_student_and_total',
        store=True,
    )

    training_fee_source = fields.Char(string="Nguồn kinh phí")
    note = fields.Char(string="Ghi chú")

    participation_detail_ids = fields.One2many(
        'training.plan.participation.detail',
        'training_plan_detail_id',
        string='Danh sách đăng ký',
    )

    student_count = fields.Integer(
        string='Số lượng học viên',
        compute='_compute_student_and_total',
        store=True,
    )
    qty_q1 = fields.Integer(string="SL Quý 1", default=0)
    qty_q2 = fields.Integer(string="SL Quý 2", default=0)
    qty_q3 = fields.Integer(string="SL Quý 3", default=0)
    qty_q4 = fields.Integer(string="SL Quý 4", default=0)

    # Tổng dự kiến cả năm (dùng để check với student_count thực tế)
    total_expected_qty = fields.Integer(
        string="Tổng dự kiến",
        compute="_compute_total_expected",
        store=True
    )

    execution_date = fields.Date(string="Thời gian thực hiện", required=True, default=fields.Date.today)

    # --- 2. FIELD QUÝ (Tự động tính từ execution_date) ---
    quarter = fields.Selection([
        ('1', 'Quý 1'),
        ('2', 'Quý 2'),
        ('3', 'Quý 3'),
        ('4', 'Quý 4'),
    ], string="Quý", compute="_compute_quarter", store=True)

    # --- 3. FIELD SỐ LƯỢNG DỰ KIẾN ---
    expected_qty = fields.Integer(string="SL Dự kiến", default=1)

    @api.depends('execution_date')
    def _compute_quarter(self):
        for rec in self:
            if not rec.execution_date:
                rec.quarter = False
            else:
                # Công thức tính quý: (Tháng - 1) // 3 + 1
                # VD: Tháng 5 -> (4)//3 + 1 = 1 + 1 = 2
                q = (rec.execution_date.month - 1) // 3 + 1
                rec.quarter = str(q)


    def action_open_reject_wizard(self):
        self.ensure_one()
        return {
            'name': _('Từ chối Đào tạo'),
            'type': 'ir.actions.act_window',
            'res_model': 'training.plan.detail.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_detail_id': self.id},
        }

    def action_reset_approval(self):
        for rec in self:
            rec.write({
                'state': 'approved',
                'reject_reason': False
            })

    def action_toggle_state(self):
        self.ensure_one()
        # Logic: Chỉ cho bấm khi Plan ở trạng thái Chờ duyệt hoặc Đã duyệt
        # (Tùy nghiệp vụ của bạn, ở đây tôi để giống bên Tuyển dụng là cho phép sửa ở các bước sau)

        if self.state == 'approved':
            return self.action_open_reject_wizard()
        elif self.state == 'rejected':
            return self.action_reset_approval()

    @api.depends('qty_q1', 'qty_q2', 'qty_q3', 'qty_q4')
    def _compute_total_expected(self):
        for rec in self:
            rec.total_expected_qty = rec.qty_q1 + rec.qty_q2 + rec.qty_q3 + rec.qty_q4

    def open_participants(self):
        """
        Mở thẳng form view của training.plan.participation
        Tạo mới nếu chưa có participation cho khóa này.
        """
        self.ensure_one()

        Participation = self.env['training.plan.participation']

        # Tìm đợt participation tương ứng khóa này
        participation = Participation.search([
            ('training_plan_detail_id', '=', self.id)
        ], limit=1)

        # Nếu CHƯA có → tạo mới
        if not participation:
            participation = Participation.create({
                'training_plan_id': self.plan_id.id,
                'training_plan_detail_id': self.id,
            })

        return {
            'name': 'Danh sách học viên',
            'type': 'ir.actions.act_window',
            'res_model': 'training.plan.participation',
            'view_mode': 'form',
            'views': [
                (self.env.ref('hr_training_tedi.view_training_participation_form').id, 'form')
            ],
            'target': 'current',
            'res_id': participation.id,  # ← mở đúng record
        }

    @api.depends('participation_detail_ids', 'training_fee_per_person', 'expected_qty')
    def _compute_student_and_total(self):
        for detail in self:
            # Nếu là Plan Năm: Tính theo SL dự kiến
            if detail.plan_id.type == 'year':
                count = detail.expected_qty
            # Nếu là Plan Quý: Tính theo SL học viên thực tế
            else:
                count = len(detail.participation_detail_ids)

            detail.student_count = count
            detail.training_total_fee = (detail.training_fee_per_person or 0.0) * count

    # def _check_participant(self):
    #     if self.env.user.has_group(PARTICIPANT):
    #         raise AccessError(_("Participant không được thực hiện thao tác này"))

    @api.model
    def create(self, vals):
        # self._check_participant()
        return super().create(vals)

    def write(self, vals):
        res = super(TrainingPlanDetail, self).write(vals)

        # Nếu sửa thông tin quan trọng
        if any(f in vals for f in ['start_date', 'end_date', 'training_location', 'training_type', 'course_id']):
            for detail in self:
                # Logic này sẽ gọi _sync_to_history của từng học viên.
                # Nhờ có điều kiện chặn ở trên, nếu Plan chưa duyệt (ví dụ sửa lúc Draft),
                # nó sẽ tự động bỏ qua, không gây lỗi.
                for part_detail in detail.participation_detail_ids:
                    part_detail._sync_to_history()
        return res

class TrainingPlanDetailRejectWizard(models.TransientModel):
    _name = "training.plan.detail.reject.wizard"
    _description = "Wizard Từ chối chi tiết kế hoạch đào tạo"

    detail_id = fields.Many2one('training.plan.detail', string="Dòng chi tiết", required=True)
    reason = fields.Text(string="Lý do từ chối", required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        self.detail_id.write({
            'state': 'rejected',
            'reject_reason': self.reason
        })
        return {'type': 'ir.actions.act_window_close'}


class TrainingPlanRejectWizard(models.TransientModel):
    _name = 'training.plan.reject.wizard'
    _description = 'Wizard nhập lý do từ chối kế hoạch đào tạo'

    plan_id = fields.Many2one('training.plan', string="Kế hoạch", required=True)
    reject_reason = fields.Text(string="Lý do từ chối", required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        # Ghi đè lý do và trả về nháp
        self.plan_id.write({
            'reject_reason': self.reject_reason,
            'state': 'draft'
        })
        # Ghi log vào chatter
        self.plan_id.message_post(body=f"Đã từ chối. Lý do: {self.reject_reason}")
        return {'type': 'ir.actions.act_window_close'}