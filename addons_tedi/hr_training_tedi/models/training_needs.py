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

    type = fields.Selection([
        ('year', 'Nhu cầu Năm'),
        ('actual', 'Nhu cầu Thực tế'),
    ], string="Loại nhu cầu", default='year', required=True)

    # Chọn Lớp học (Đã được tạo từ Kế hoạch Quý)
    participation_id = fields.Many2one(
        "training.plan.participation",
        string="Lớp học (Đợt đào tạo)",
        # Chỉ lấy các lớp chưa kết thúc để bổ sung
        domain="[('state', 'in', ['not_started', 'in_progress'])]",
    )

    # Đợt khảo sát (Chỉ bắt buộc cho Nhu cầu Năm)
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
    is_valid_approver = fields.Boolean(
        string="Là người được duyệt",
        compute='_compute_is_valid_approver',
        store=False  # Bắt buộc False để luôn tính lại mỗi khi mở form
    )

    @api.depends('user_id')
    @api.depends('user_id', 'state')
    def _compute_is_valid_approver(self):
        # Lấy user đang login
        current_user = self.env.user
        current_dept = current_user.employee_id.department_id

        for rec in self:
            rec.is_valid_approver = False

            # 1. Nếu không phải trạng thái chờ duyệt -> False luôn
            if rec.state != 'pending':
                continue

            # 2. Nếu User không có quyền Trưởng đơn vị -> False
            if not current_user.has_group('hr_training_tedi.group_training_unit_manager'):
                continue

            # 3. LOGIC CỐT LÕI: SO SÁNH PHÒNG BAN
            # Lấy phòng ban của người tạo đơn
            owner_dept = rec.user_id.employee_id.department_id

            if current_dept and owner_dept:
                # Kiểm tra: Phòng ban người tạo (owner) có thuộc nhánh con (hoặc chính nó)
                # của phòng ban User đang login (current) không?
                # Toán tử 'child_of' trong domain xử lý việc này.
                is_sub_branch = self.env['hr.department'].search_count([
                    ('id', '=', owner_dept.id),
                    ('id', 'child_of', current_dept.id)
                ])

                if is_sub_branch > 0:
                    rec.is_valid_approver = True

            # (Tùy chọn) Nếu là Admin hệ thống (id=1 hoặc group Admin) thì luôn cho duyệt?
            # Nếu bạn muốn Admin cũng bị chặn nếu khác phòng ban thì bỏ đoạn dưới đi.
            if current_user.has_group('base.group_system'):
                rec.is_valid_approver = True

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
    @api.model
    def create(self, vals):
        if vals.get('type') == 'year' and not vals.get('name'):
            raise UserError(_("Với Nhu cầu Năm, bạn phải chọn Đợt khảo sát."))
        if vals.get('type') == 'actual' and not vals.get('participation_id'):
            raise UserError(_("Với Nhu cầu Thực tế, bạn phải chọn Lớp học."))

        return super().create(vals)

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

            # --- XỬ LÝ NHU CẦU THỰC TẾ: THÊM NGƯỜI VÀO LỚP ---
            if rec.type == 'actual' and rec.participation_id:
                rec._add_students_to_participation()

            # --- XỬ LÝ QUYỀN DUYỆT CŨ CỦA BẠN ---
            if self.env.user.has_group('hr_training_tedi.group_training_unit_manager') and \
                    not self.env.user.has_group('hr_training_tedi.group_training_manager'):
                if not rec.is_valid_approver:
                    raise UserError(_("Bạn không có quyền duyệt yêu cầu của phòng ban khác."))

            rec.state = "approved"
            rec.approver_id = self.env.user.id

    def _add_students_to_participation(self):
        self.ensure_one()
        ParticipationDetail = self.env['training.plan.participation.detail']

        # Lớp học đích
        participation = self.participation_id

        # Danh sách người đăng ký (lấy từ line_ids hoặc user_id của phiếu)
        # TH1: Nếu TrainingNeedsLine có field user_id (đăng ký hộ nhiều người) -> Duyệt qua line
        # TH2: Nếu TrainingNeedsLine chỉ chọn khóa học, người học là chủ phiếu (user_id) -> Add 1 lần

        # Giả sử cấu trúc hiện tại của bạn:
        # TrainingNeeds = 1 người đăng ký (user_id) đăng ký nhiều khóa (line_ids)
        # Nhưng ở Type Actual -> 1 Phiếu chỉ chọn 1 Lớp (participation_id) -> Các dòng line có thể thừa?
        # -> Giải pháp tốt nhất: Ở Type Actual, ẩn tab chi tiết line_ids đi, hoặc tự động tạo line cho khớp.

        # Cách xử lý đơn giản: Lấy user_id của phiếu add vào lớp
        student_user = self.user_id

        # Kiểm tra đã có trong lớp chưa
        existing = ParticipationDetail.search([
            ('participation_id', '=', participation.id),
            ('user_id', '=', student_user.id)
        ], limit=1)

        if not existing:
            ParticipationDetail.create({
                'participation_id': participation.id,
                'user_id': student_user.id,
                'note': _("Bổ sung từ Nhu cầu thực tế: %s") % self.display_name,
            })

            # Ghi log vào lớp học
            participation.message_post(body=_(
                "Đã bổ sung học viên <b>%s</b> từ phiếu nhu cầu thực tế."
            ) % student_user.name)
    # =========================
    #  ACTION: TỪ CHỐI (pending -> draft)
    # =========================
    def action_reject(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_("Chỉ được từ chối khi phiếu đang ở trạng thái 'Chờ duyệt'."))

            # CHECK QUYỀN TƯƠNG TỰ DUYỆT
            if self.env.user.has_group('hr_training_tedi.group_training_unit_manager') and \
                    not self.env.user.has_group('hr_training_tedi.group_training_manager'):
                if not rec.is_valid_approver:
                    raise UserError(_("Bạn không có quyền từ chối yêu cầu của phòng ban khác."))

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
