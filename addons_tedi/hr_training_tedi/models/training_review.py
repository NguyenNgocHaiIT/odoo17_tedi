from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TrainingReview(models.Model):
    _name = 'training.review'
    _description = 'Training Review'
    _rec_name = 'participation_id'

    # --- TRẠNG THÁI ---
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Hoàn thành')
    ], string='Trạng thái', default='draft', required=True)

    # --- 1. CHỌN KHOÁ ĐÀO TẠO ---
    participation_id = fields.Many2one(
        'training.plan.participation',
        string="Khoá đào tạo",
        required=True,
        domain="[('state', 'in', ['in_progress', 'finished'])]"
    )

    # --- 2. CÁC THÔNG TIN TỰ ĐỘNG HIỂN THỊ ---
    training_plan_id = fields.Many2one(
        "training.plan",
        string="Kế hoạch",
        related='participation_id.training_plan_id',
        store=True,
        readonly=True,
    )

    training_plan_detail_id = fields.Many2one(
        "training.plan.detail",
        string="Tên khoá học (Gốc)",
        related='participation_id.training_plan_detail_id',
        store=True,
        readonly=True,
    )

    training_center = fields.Selection(
        related='participation_id.training_plan_detail_id.training_center',
        string="Cơ sở đào tạo",
        store=True,
        readonly=True,
    )

    start_date = fields.Date(
        string="Ngày bắt đầu",
        related='participation_id.start_date',
        readonly=True
    )

    end_date = fields.Date(
        string="Ngày kết thúc",
        related='participation_id.end_date',
        readonly=True
    )

    # --- 3. CÁC TRƯỜNG CƠ BẢN KHÁC ---
    user_id = fields.Many2one(
        'res.users',
        string="Người đánh giá",
        default=lambda self: self.env.user,
        readonly=True,  # Người tạo luôn cố định, không cho sửa
    )

    review_detail_ids = fields.One2many(
        "training.review.detail",
        "training_review_id",
        string="Nội dung đánh giá",
    )

    # --- HÀM XỬ LÝ NÚT XÁC NHẬN ---
    def action_confirm(self):
        for record in self:
            # Kiểm tra: Người nhấn nút phải là Người tạo (user_id)
            if record.user_id != self.env.user:
                raise UserError(
                    _("Bạn không có quyền xác nhận. Chỉ người tạo phiếu đánh giá này mới được phép xác nhận."))

            record.state = 'done'


class TrainingReviewDetail(models.Model):
    _name = 'training.review.detail'
    _description = 'Training Review Detail'

    training_review_id = fields.Many2one(
        "training.review",
        string="Đánh giá",
        ondelete="cascade",
    )

    review_content = fields.Char(string="Nội dung đánh giá")

    training_rating = fields.Selection(
        [
            ("poor", "Yếu"),
            ("fair", "Khá"),
            ("good", "Tốt"),
        ],
        string="Mức độ đánh giá",
        required=True
    )

    note = fields.Char(string="Nhận xét khác")