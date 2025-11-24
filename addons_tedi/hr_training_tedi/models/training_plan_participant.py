from odoo import models, api, fields, _
from odoo.exceptions import AccessError
HR_OFFICER          = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
PARTICIPANT         = "hr_training_tedi.group_training_participant"
UNIT_MANAGER        = "hr_training_tedi.group_training_unit_manager"
GENERAL_DIRECTOR    = "hr_training_tedi.group_training_general_director"
BASE                = "base.group_user"

class TrainingPlanParticipation(models.Model):
    _name = 'training.plan.participation'
    _description = 'Training Plan Participation'

    training_plan_id = fields.Many2one(
        "training.plan",
        string="Tên kế hoạch",
        ondelete="cascade",  # ← thêm dòng này
    )

    training_plan_detail_id = fields.Many2one(
        "training.plan.detail",
        string="Tên khoá đào tạo",
        domain="[('plan_id', '=', training_plan_id)]",
    )

    open_date = fields.Date(
        "Ngày mở đăng ký",
        related="training_plan_id.open_date",
        store=True,
        readonly=True,
    )

    participation_detail_ids = fields.One2many(
        "training.plan.participation.detail",
        "participation_id",
        string="Danh sách đăng ký",
    )
    def _check_participant(self):
        if self.env.user.has_group(PARTICIPANT):
            raise AccessError(_("Participant không được thực hiện thao tác này"))

    @api.model
    def create(self, vals):
        self._check_participant()
        return super().create(vals)


class TrainingPlanParticipationDetail(models.Model):
    _name = 'training.plan.participation.detail'
    _description = 'Training Plan Participation Detail'

    participation_id = fields.Many2one(
        'training.plan.participation',
        string="Đợt tham gia",
        ondelete="cascade",
    )

    # Nếu mỗi đợt participation chỉ chọn 1 khóa đào tạo,
    # thì detail cứ related thẳng theo participation_id.training_plan_detail_id
    training_plan_detail_id = fields.Many2one(
        'training.plan.detail',
        string="Khoá đào tạo",
        related='participation_id.training_plan_detail_id',
        store=True,
        readonly=True,
    )

    user_id = fields.Many2one('res.users', string="Họ và tên")

    # ===== Cơ sở đào tạo lấy từ plan_detail =====
    training_center = fields.Selection(
        related='training_plan_detail_id.training_center',
        string="Cơ sở đào tạo",
        store=True,
        readonly=True,
    )



    # ===== Hình thức đào tạo lấy từ plan_detail =====
    training_type = fields.Selection(
        [
            ("direct", "Trực tiếp"),
            ("indirect", "Gián tiếp"),
        ],
        related="training_plan_detail_id.training_type",
        string="Hình thức đào tạo",
        store=True,
        readonly=True,
    )

    # ===== Tiền tệ & Chi phí/người lấy từ plan_detail =====
    currency_id = fields.Many2one(
        'res.currency',
        related='training_plan_detail_id.currency_id',
        string="Tiền tệ",
        store=True,
        readonly=True,
    )

    training_fee_per_person = fields.Monetary(
        string="Chi phí/người",
        currency_field="currency_id",
        related='training_plan_detail_id.training_fee_per_person',
        store=True,
        readonly=True,
    )

    training_time = fields.Char(
        string="Thời gian" ,
        related='training_plan_detail_id.time_of_execution',
        store=True,
        readonly=True,
    )
    note = fields.Char(string="Ghi chú")

    def _check_participant(self):
        if self.env.user.has_group(PARTICIPANT):
            raise AccessError(_("Participant không được thực hiện thao tác này"))

    @api.model
    def create(self, vals):
        self._check_participant()
        return super().create(vals)
