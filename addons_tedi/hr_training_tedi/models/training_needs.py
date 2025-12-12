from email.policy import default

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

HR_OFFICER          = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
PARTICIPANT         = "hr_training_tedi.group_training_participant"
UNIT_MANAGER        = "hr_training_tedi.group_training_unit_manager"
GENERAL_DIRECTOR    = "hr_training_tedi.group_training_general_director"
BASE                = "base.group_user"


class TrainingNeeds(models.Model):
    _name = 'trainings.needs'
    _description = 'Training Needs'

    name = fields.Many2one(
        "training.needs.survey",
        string="Tên đợt khảo sát",
        domain=[('state', '=', 'in_process')],
    )

    create_date = fields.Date(
        string="Ngày đăng ký",
        readonly=True,
        default= fields.Date.context_today,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Người đăng ký',
        default=lambda self: self.env.user
    )
    approver_id = fields.Many2one('res.users', string='Người phê duyệt')
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
    ], string="Trạng thái", default='draft')

    line_ids = fields.One2many(
        'trainings.needs.line',
        'training_needs_id',
        string='Chi tiết nhu cầu',
    )

    @api.constrains('line_ids')
    def _check_lines_unique_course(self):
        for rec in self:
            courses = rec.line_ids.mapped('course_id.id')
            if len(courses) != len(set(courses)):
                raise ValidationError(
                    _("Bạn không được chọn 2 khoá đào tạo giống nhau trong cùng một phiếu.")
                )

    @api.onchange('line_ids')
    def _onchange_line_ids_unique_course(self):
        if not self.line_ids:
            return

        courses = self.line_ids.mapped('course_id')
        if len(courses) != len(set(courses.ids)):
            return {
                'warning': {
                    'title': "Lỗi trùng khóa học",
                    'message': "Bạn không được chọn 2 khoá đào tạo giống nhau trong cùng một phiếu.",
                }
            }

    def _check_unique_course(self):
        for rec in self:
            courses = rec.line_ids.mapped('course_id')
            if len(courses) != len(set(courses.ids)):
                raise UserError(_("Bạn không được chọn 2 khoá đào tạo giống nhau trong cùng một phiếu."))

    @api.model
    def create(self, vals):
        """Tự gán người đăng ký = user tạo bản ghi nếu chưa set."""
        if not vals.get('user_id'):
            vals['user_id'] = self.env.uid
        res = super().create(vals)
        res._check_unique_course()
        return res

    def write(self, vals):
        res = super().write(vals)
        self._check_unique_course()
        return res
    # =========================
    #  ACTION: GỬI ĐĂNG KÝ (draft -> pending)
    # =========================
    def action_submit(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Chỉ được đăng ký khi phiếu đang ở trạng thái 'Dự thảo'."))

            if not rec.line_ids:
                raise UserError(_("Bạn phải nhập ít nhất 1 dòng nhu cầu đào tạo trước khi đăng ký."))

            # create_date: thời điểm bấm Đăng ký
            if not rec.create_date:
                rec.create_date = today

            rec.state = 'pending'


    def action_approve(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_("Chỉ được duyệt khi phiếu đang ở trạng thái 'Chờ duyệt'."))
            if not rec.line_ids:
                raise UserError(_("Bạn phải nhập ít nhất 1 dòng nhu cầu đào tạo trước khi duyệt."))
            rec.state = "approved"
            rec.approver_id = self.env.user.id

    # =========================
    #  ACTION: TỪ CHỐI (pending -> draft)
    # =========================
    def action_reject(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_("Chỉ được từ chối khi phiếu đang ở trạng thái 'Chờ duyệt'."))
            rec.state = "draft"

    # def unlink(self):
    #     for rec in self:
    #         if rec.state == 'approved':
    #             raise ValidationError(_("Không thể xoá yêu cầu đào tạo đã được duyệt."))
    #     return super().unlink()

    # =========================
    #  ACTION: ĐÁNH GIÁ KHÓA HỌC
    #  (ứng viên tự đánh giá) – giữ nguyên nếu bạn cần
    # =========================
    def action_open_course_review(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Đánh giá khoá đào tạo'),
            'res_model': 'training.review',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_user_id': self.env.user.id,
            },
        }


class TrainingNeedsLine(models.Model):
    _name = 'trainings.needs.line'
    _description = 'Training Needs Line'

    training_needs_id = fields.Many2one(
        'trainings.needs',
        string='Phiếu nhu cầu',
        ondelete='cascade',
    )

    course_id = fields.Many2one("training.course", string="Tên khoá đào tạo")
    training_field_id = fields.Many2one('training.field', string="Lĩnh vực")

    # Link đến chi tiết tham gia (được update khi Plan được tạo)
    participation_detail_id = fields.Many2one(
        'training.plan.participation.detail',
        string="Dòng đăng ký kế hoạch",
        readonly=True,
    )

    note = fields.Char(string="Ghi chú")

    # --- 1. FIELD CHECK TRẠNG THÁI ĐỂ HIỂN THỊ NÚT ---
    # Lấy trạng thái từ bên Plan Participation sang đây
    participation_state = fields.Selection(
        related='participation_detail_id.participation_id.state',
        string="Trạng thái đào tạo",
        readonly=True
    )

    # --- 2. ACTION MỞ FORM ĐÁNH GIÁ ---
    def action_open_review(self):
        self.ensure_one()

        # A. Check quyền: Chỉ người tạo phiếu nhu cầu mới được đánh giá
        # user_id là người tạo phiếu (được set default=uid khi create)
        if self.env.uid != self.training_needs_id.user_id.id:
            raise ValidationError(
                _("Chỉ người tạo phiếu đăng ký này (%s) mới có quyền đánh giá.") % self.training_needs_id.user_id.name)

        # B. Check trạng thái: Phải kết thúc mới được đánh giá
        if self.participation_state != 'finished':
            raise ValidationError(_("Khoá đào tạo chưa kết thúc, bạn chưa thể đánh giá lúc này."))

        # C. Check dữ liệu: Phải đã được xếp lớp
        if not self.participation_detail_id:
            raise ValidationError(_("Khoá học này chưa được xếp lớp vào kế hoạch đào tạo."))

        # D. Logic mở form
        Review = self.env['training.review']

        # Tìm xem đã đánh giá chưa (dựa vào participation_detail_id)
        existing_review = Review.search([
            ('participation_detail_id', '=', self.participation_detail_id.id),
            ('user_id', '=', self.env.uid)
        ], limit=1)

        if existing_review:
            # Nếu có rồi -> Mở ra xem/sửa
            return {
                'type': 'ir.actions.act_window',
                'name': _('Đánh giá khoá học'),
                'res_model': 'training.review',
                'view_mode': 'form',
                'res_id': existing_review.id,
                'target': 'new',  # Mở popup
            }
        else:
            # Nếu chưa có -> Mở form tạo mới (điền sẵn dữ liệu)
            plan_detail = self.participation_detail_id.training_plan_detail_id

            return {
                'type': 'ir.actions.act_window',
                'name': _('Đánh giá khoá học'),
                'res_model': 'training.review',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_user_id': self.env.uid,
                    'default_participation_detail_id': self.participation_detail_id.id,  # Quan trọng để link
                    'default_training_plan_detail_id': plan_detail.id,
                    'default_training_plan_id': plan_detail.plan_id.id,
                    # 'default_start_date': plan_detail.start_date, # Nếu review có field này
                }
            }
