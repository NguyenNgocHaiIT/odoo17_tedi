from odoo import fields, models


class TrainingReview(models.Model):
    _name = 'training.review'
    _description = 'Training Review'

    training_plan_id = fields.Many2one(
        "training.plan",
        string="Tên kế hoạch",
    )

    training_plan_detail_id = fields.Many2one(
        "training.plan.detail",
        string="Tên khoá đào tạo",
        domain="[('plan_id', '=', training_plan_id)]",
    )

    training_center = fields.Selection(
        related='training_plan_detail_id.training_center',
        string="Cơ sở đào tạo",
        store=True,
        readonly=True,
    )

    start_date = fields.Datetime(string="Ngày bắt đầu")
    end_date = fields.Date(string="Ngày kết thúc")

    # Người đánh giá = chính học viên
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
    )

    note = fields.Char(string="Nhận xét khác")
