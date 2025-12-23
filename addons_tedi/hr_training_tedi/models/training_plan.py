from odoo import models, api, fields, exceptions, _
from odoo.exceptions import AccessError, ValidationError

HR_OFFICER          = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
PARTICIPANT         = "hr_training_tedi.group_training_participant"
UNIT_MANAGER        = "hr_training_tedi.group_training_unit_manager"
GENERAL_DIRECTOR    = "hr_training_tedi.group_training_general_director"
BASE                = "base.group_user"


class TrainingPlan(models.Model):
    _name = 'training.plan'
    _description = 'Training Plan'

    name = fields.Char(string='Tên kế hoạch', required=True)

    # Ngày tạo
    open_date = fields.Date(
        string='Ngày tạo',
        default=fields.Date.context_today,
        readonly=True,
    )

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

    state = fields.Selection([
        ("draft", "Dự thảo"),
        ("pending", "Chờ duyệt"),
        ("approved", "Đã duyệt"),
    ], string="Trạng thái", default='draft')

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

    # Field liên kết cha-con (để biết kế hoạch Quý thuộc Kế hoạch Năm nào)
    parent_id = fields.Many2one('recruitment.plan', string="Thuộc Kế hoạch Năm", readonly=True)

    _sql_constraints = [
        ('survey_unique',
         'unique(survey_id)',
         'Mỗi đợt khảo sát chỉ được gắn với một kế hoạch đào tạo.'),
    ]

    # =========================================
    #      ====== FUNCTION TỔNG HỢP ======
    # =========================================

    @api.onchange('survey_id')
    def _onchange_survey_id(self):
        """
        Khi thay đổi Đợt khảo sát trên giao diện:
        1. Xóa hết các dòng chi tiết cũ.
        2. Quét survey để lấy danh sách khóa học.
        3. Điền ngay vào detail_ids (hiển thị luôn cho người dùng thấy).
        """
        # 1. Xóa dữ liệu detail cũ (nếu có) để tránh trộn lẫn khi đổi survey khác
        # Mã lệnh (5, 0, 0) là lệnh xóa sạch các dòng trong One2many
        self.detail_ids = [(5, 0, 0)]

        if not self.survey_id:
            return

        TrainingNeeds = self.env['trainings.needs']

        # Tìm các phiếu nhu cầu đã duyệt thuộc đợt khảo sát này
        needs = TrainingNeeds.search([
            ('name', '=', self.survey_id.id),
            ('state', '=', 'approved'),
        ])

        if not needs:
            return

        # 2. Lấy danh sách các Course ID (duy nhất)
        course_ids = set()
        for need in needs:
            for line in need.line_ids:
                if line.course_id:
                    course_ids.add(line.course_id.id)

        # 3. Tạo dữ liệu cho detail_ids (trong bộ nhớ giao diện)
        new_lines = []
        for c_id in course_ids:
            # Mã lệnh (0, 0, values) là lệnh tạo dòng mới
            new_lines.append((0, 0, {
                'course_id': c_id,
                # Bạn có thể set mặc định các giá trị khác ở đây nếu muốn
                # 'training_type': 'direct',
            }))

        self.detail_ids = new_lines

    def _generate_participants_from_survey(self):
        """
        Hàm này giữ nguyên như câu trả lời trước.
        Chỉ chạy khi bấm nút DUYỆT để tạo danh sách học viên.
        """
        Participation = self.env['training.plan.participation']
        ParticipationDetail = self.env['training.plan.participation.detail']
        TrainingNeeds = self.env['trainings.needs']

        for plan in self:
            if not plan.survey_id:
                continue

            needs = TrainingNeeds.search([
                ('name', '=', plan.survey_id.id),
                ('state', '=', 'approved'),
            ])

            if not needs:
                continue

            course_map = {}
            for need in needs:
                student = need.user_id or need.create_uid or self.env.user
                for line in need.line_ids:
                    if not line.course_id:
                        continue
                    course_id = line.course_id.id
                    course_map.setdefault(course_id, []).append((student, line))

            for course_id, items in course_map.items():
                # Tìm detail (Lúc này detail đã được tạo bởi onchange và đã lưu)
                detail = plan.detail_ids.filtered(lambda d: d.course_id.id == course_id)[:1]

                # Fallback: Nếu lỡ người dùng xóa tay detail thì tạo lại
                if not detail:
                    detail = self.env['training.plan.detail'].create({
                        'plan_id': plan.id,
                        'course_id': course_id,
                    })

                # Tạo Participation
                participation = Participation.search([
                    ('training_plan_id', '=', plan.id),
                    ('training_plan_detail_id', '=', detail.id),
                ], limit=1)

                if not participation:
                    participation = Participation.create({
                        'training_plan_id': plan.id,
                        'training_plan_detail_id': detail.id,
                    })

                # Tạo danh sách học viên
                for student, line in items:
                    existing = ParticipationDetail.search([
                        ('participation_id', '=', participation.id),
                        ('user_id', '=', student.id),
                    ], limit=1)

                    if not existing:
                        part_detail = ParticipationDetail.create({
                            'participation_id': participation.id,
                            'user_id': student.id,
                            'note': line.note,
                        })
                        line.participation_detail_id = part_detail.id



    # =========================================
    #      ====== CREATE - WRITE ======
    # =========================================


    @api.model
    def create(self, vals):
        return super().create(vals)

    def write(self, vals):
        return super().write(vals)

    # =========================================
    #      ====== COMPUTE ======
    # =========================================

    @api.depends('detail_ids.participation_detail_ids.training_fee_per_person')
    def _compute_stats(self):
        ParticipationDetail = self.env['training.plan.participation.detail']
        for plan in self:
            if plan.detail_ids:
                participants = ParticipationDetail.search([
                    ('training_plan_detail_id', 'in', plan.detail_ids.ids)
                ])
                plan.student_count = len(participants)
                plan.total_fee = sum(
                    (line.training_fee_per_person or 0.0)
                    for line in participants
                )
            else:
                plan.student_count = 0
                plan.total_fee = 0.0

    # =========================================
    #      ====== ACTION STATE ======
    # =========================================

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise ValidationError(_("Chỉ có thể đăng ký từ trạng thái 'Dự thảo'."))
            rec.state = "pending"

    def action_approve(self):
        for rec in self:
            if rec.state != "pending":
                raise ValidationError(_("Chỉ có thể duyệt từ trạng thái 'Chờ duyệt'."))

            # --- LOGIC MỚI: PHÂN LOẠI XỬ LÝ ---
            if rec.type == 'year':
                # Nếu là Kế hoạch Năm -> Tạo ra 4 Kế hoạch Quý
                rec._generate_quarterly_plans()
                rec.message_post(body=_("Đã duyệt Kế hoạch Năm và sinh ra các Kế hoạch Quý tương ứng."))

            elif rec.type == 'quarter':
                # Nếu là Kế hoạch Quý -> Tạo danh sách học viên (Lớp học)
                rec._generate_participants_from_survey()
                rec.message_post(body=_("Đã duyệt Kế hoạch Quý và khởi tạo danh sách học viên."))

                # Trigger đồng bộ lịch sử (chỉ chạy khi thực sự có học viên)
                for detail in rec.detail_ids:
                    for part_detail in detail.participation_detail_ids:
                        part_detail._sync_to_history()

            rec.state = "approved"

    def _generate_quarterly_plans(self):
        self.ensure_one()
        # Mapping: Quý -> Trường số lượng tương ứng
        quarters_map = {1: 'qty_q1', 2: 'qty_q2', 3: 'qty_q3', 4: 'qty_q4'}

        for q_num, field_qty in quarters_map.items():
            plan_name = f"{self.name} - Quý {q_num}"

            # Kiểm tra xem đã tạo chưa để tránh trùng lặp
            existing = self.env['training.plan'].search([
                ('parent_id', '=', self.id),
                ('name', '=', plan_name)
            ], limit=1)

            if existing:
                continue

            # 1. Tạo Header Kế hoạch Quý
            plan_vals = {
                'name': plan_name,
                'type': 'quarter',
                'parent_id': self.id,
                'state': 'draft',  # Để draft cho HR kiểm tra lại rồi mới trình duyệt
                'open_date': fields.Date.today(),
                # Copy Survey ID để quý con cũng biết nó thuộc đợt khảo sát nào (nếu cần mapping lại user)
                'survey_id': self.survey_id.id,
                'currency_id': self.currency_id.id,
            }

            # 2. Tạo Lines
            detail_lines = []
            for line in self.detail_ids:
                qty_in_quarter = getattr(line, field_qty, 0)

                # Chỉ tạo dòng nếu quý đó có học viên
                if qty_in_quarter > 0:
                    line_vals = {
                        'course_id': line.course_id.id,
                        'training_center': line.training_center,
                        'training_type': line.training_type,
                        'training_location': line.training_location,
                        'training_fee_per_person': line.training_fee_per_person,
                        'training_fee_source': line.training_fee_source,
                        'note': line.note,
                        # Lưu ý: Ở quý con, ta chưa có học viên cụ thể ngay lập tức,
                        # nhưng có thể lưu số lượng dự kiến vào note hoặc một field expected_qty
                        # Ở đây ta chỉ tạo khung detail để HR add người vào sau.
                    }
                    detail_lines.append((0, 0, line_vals))

            if detail_lines:
                plan_vals['detail_ids'] = detail_lines
                self.env['training.plan'].create(plan_vals)

    def action_reject(self):
        for rec in self:
            if rec.state != "pending":
                raise ValidationError(_("Chỉ có thể từ chối khi trạng thái là 'Chờ duyệt'."))
            rec.state = "draft"



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

    @api.depends('participation_detail_ids', 'training_fee_per_person')
    def _compute_student_and_total(self):
        for detail in self:
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