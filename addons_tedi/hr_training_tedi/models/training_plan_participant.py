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
        ondelete="cascade",
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

    # --- CÁC TRƯỜNG BỔ SUNG (Lấy từ Detail) ---

    start_date = fields.Date(
        string="Từ ngày",
        related='training_plan_detail_id.start_date',
        readonly=True
    )

    end_date = fields.Date(
        string="Đến ngày",
        related='training_plan_detail_id.end_date',
        readonly=True
    )

    training_location = fields.Char(
        string="Địa điểm đào tạo",
        related='training_plan_detail_id.training_location',
        readonly=True
    )

    # Cần trường này để hiển thị đơn vị tiền tệ (VND/USD)
    currency_id = fields.Many2one(
        'res.currency',
        related='training_plan_detail_id.currency_id',
        string="Tiền tệ",
        readonly=True
    )

    training_fee_per_person = fields.Monetary(
        string="Chi phí/người",
        related='training_plan_detail_id.training_fee_per_person',
        currency_field='currency_id',
        readonly=True
    )

    training_total_fee = fields.Monetary(
        string="Tổng chi phí",
        related='training_plan_detail_id.training_total_fee',
        currency_field='currency_id',
        readonly=True
    )

    # -------------------------------------------

    participation_detail_ids = fields.One2many(
        "training.plan.participation.detail",
        "participation_id",
        string="Danh sách đăng ký",
    )

    @api.model
    def create(self, vals):
        return super().create(vals)


class TrainingPlanParticipationDetail(models.Model):
    _name = 'training.plan.participation.detail'
    _description = 'Training Plan Participation Detail'

    participation_id = fields.Many2one(
        'training.plan.participation',
        string="Đợt tham gia",
        ondelete="cascade",
    )

    training_plan_detail_id = fields.Many2one(
        'training.plan.detail',
        string="Khoá đào tạo",
        related='participation_id.training_plan_detail_id',
        store=True,
        readonly=True,
    )

    user_id = fields.Many2one('res.users', string="Họ và tên")

    # --- 1. ĐƠN VỊ (Lấy từ phòng ban của User/Nhân viên) ---
    department_id = fields.Many2one(
        'hr.department',
        string="Đơn vị",
        related='user_id.employee_id.department_id',
        store=True,
        readonly=True,
    )

    # --- 2. HÌNH THỨC ĐÀO TẠO (Lấy từ Plan Detail) ---
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

    # --- 3. THỜI GIAN (Lấy từ Plan Detail) ---
    # Lấy text thời gian thực hiện
    training_time = fields.Char(
        string="Thời gian",
        related='training_plan_detail_id.time_of_execution',
        store=True,
        readonly=True,
    )

    # Nếu muốn hiển thị rõ Từ ngày - Đến ngày thì dùng 2 field dưới (Tuỳ chọn)
    start_date = fields.Date(related='training_plan_detail_id.start_date', string="Từ ngày", readonly=True)
    end_date = fields.Date(related='training_plan_detail_id.end_date', string="Đến ngày", readonly=True)

    # --- 4. KINH PHÍ (Lấy từ Plan Detail) ---
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

    # --- 5. GHI CHÚ (Lấy từ Plan Detail theo yêu cầu) ---
    note = fields.Char(
        string="Ghi chú",
        related='training_plan_detail_id.note',
        store=True,
        readonly=True
    )

    @api.model
    def create(self, vals):
        return super().create(vals)