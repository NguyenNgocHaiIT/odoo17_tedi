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

    _sql_constraints = [
        ('survey_unique',
         'unique(survey_id)',
         'Mỗi đợt khảo sát chỉ được gắn với một kế hoạch đào tạo.'),
    ]

    # =========================================
    #      ====== FUNCTION TỔNG HỢP ======
    # =========================================

    def _generate_from_survey(self):
        """
        Gom toàn bộ nhu cầu đào tạo đã duyệt từ đợt khảo sát.
        Dùng chung cho onchange, create, write.
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
                continue  # KHÔNG raise lỗi trong onchange

            course_map = {}

            # gom nhu cầu theo khóa học
            for need in needs:
                student = need.user_id or need.create_uid or self.env.user
                for line in need.line_ids:
                    if not line.course_id:
                        continue

                    course_id = line.course_id.id
                    course_map.setdefault(course_id, []).append((student, line))

            if not course_map:
                continue

            for course_id, items in course_map.items():

                # tìm hoặc tạo detail
                detail = plan.detail_ids.filtered(lambda d: d.course_id.id == course_id)[:1]
                if not detail:
                    detail = self.env['training.plan.detail'].create({
                        'plan_id': plan.id,
                        'course_id': course_id,
                    })

                # tìm hoặc tạo participation
                participation = Participation.search([
                    ('training_plan_id', '=', plan.id),
                    ('training_plan_detail_id', '=', detail.id),
                ], limit=1)
                if not participation:
                    participation = Participation.create({
                        'training_plan_id': plan.id,
                        'training_plan_detail_id': detail.id,
                    })

                # tạo hoặc cập nhật chi tiết học viên
                for student, line in items:
                    existing = ParticipationDetail.search([
                        ('participation_id', '=', participation.id),
                        ('user_id', '=', student.id),
                    ], limit=1)

                    if existing:
                        line.participation_detail_id = existing.id
                    else:
                        part_detail = ParticipationDetail.create({
                            'participation_id': participation.id,
                            'user_id': student.id,
                            'note': line.note,
                        })
                        line.participation_detail_id = part_detail.id




    # =========================================
    #      ====== CREATE - WRITE ======
    # =========================================

    def _check_participant(self):
        if self.env.user.has_group(PARTICIPANT):
            raise AccessError(_("Participant không được thực hiện thao tác này"))


    def create(self, vals):
        self._check_participant()
        rec = super().create(vals)
        if vals.get('survey_id'):
            rec._generate_from_survey()
        return rec

    # def unlink(self):
    #     for rec in self:
    #         if rec.state == 'approved':
    #             raise ValidationError(_("Không thể xoá kế hoạch đã được duyệt."))
    #     return super().unlink()

    def write(self, vals):
        res = super().write(vals)

        if 'survey_id' in vals:
            for rec in self:
                if rec.survey_id:
                    rec._generate_from_survey()

        return res

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
            rec.state = "approved"

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

    def _check_participant(self):
        if self.env.user.has_group(PARTICIPANT):
            raise AccessError(_("Participant không được thực hiện thao tác này"))

    @api.model
    def create(self, vals):
        self._check_participant()
        return super().create(vals)