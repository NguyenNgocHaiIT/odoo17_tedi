from odoo import fields, models


class TrainingReview(models.Model):
    _name = 'training.review'
    _description = 'Training Review'
    _rec_name = 'training_plan_detail_id'

    # --- QUAN TRỌNG: Link ngược lại dòng tham gia để tránh trùng lặp ---
    participation_detail_id = fields.Many2one(
        'training.plan.participation.detail',
        string="Chi tiết tham gia",
        readonly=True
    )

    training_plan_id = fields.Many2one(
        "training.plan",
        string="Tên kế hoạch",
        readonly=True,
    )

    training_plan_detail_id = fields.Many2one(
        "training.plan.detail",
        string="Tên khoá đào tạo",
        readonly=True,
    )

    training_center = fields.Selection(
        related='training_plan_detail_id.training_center',
        string="Cơ sở đào tạo",
        store=True,
        readonly=True,
    )

    start_date = fields.Date(string="Ngày bắt đầu", related='training_plan_detail_id.start_date', readonly=True)
    end_date = fields.Date(string="Ngày kết thúc", related='training_plan_detail_id.end_date', readonly=True)

    user_id = fields.Many2one(
        'res.users',
        string="Người đánh giá",
        default=lambda self: self.env.user,
        readonly=True,
    )

    review_detail_ids = fields.One2many(
        "training.review.detail",
        "training_review_id",
        string="Nội dung đánh giá",
    )


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