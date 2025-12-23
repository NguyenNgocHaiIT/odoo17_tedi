from odoo import models, api, fields, _
from odoo.exceptions import AccessError, ValidationError


class TrainingPlanParticipation(models.Model):
    _name = 'training.plan.participation'
    _description = 'Training Plan Participation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "name"

    # =========================================================
    # 1. LOGIC TRẠNG THÁI (CORE)
    # =========================================================
    name = fields.Char(string="Mô tả", compute="_compute_name", store=True)

    @api.depends('training_plan_detail_id', 'training_plan_id.name')
    def _compute_name(self):
        for rec in self:
            # Lấy tên khóa học (từ detail)
            detail_name = rec.training_plan_detail_id.display_name or _("Chưa chọn khóa")
            # Lấy tên Plan
            plan_name = rec.training_plan_id.name or ""

            # Gán format: "Tên khóa - Tên Plan"
            rec.name = f"{detail_name} - {plan_name}"


    # [MỚI] Field cờ đánh dấu đã bấm nút Kết thúc thủ công
    is_manually_ended = fields.Boolean(
        string="Đã kết thúc thủ công",
        default=False,
        copy=False
    )

    state = fields.Selection([
        ('not_started', 'Chưa bắt đầu'),
        ('in_progress', 'Đang diễn ra'),
        ('finished', 'Đã kết thúc')
    ], string="Trạng thái", compute="_compute_state", store=True, readonly=False)

    plan_state = fields.Selection(
        related='training_plan_id.state',
        string="Trạng thái Plan",
        readonly=True
    )

    def action_open_result_wizard_bulk(self):
        """Mở Wizard cập nhật hàng loạt từ Header"""
        self.ensure_one()
        if not self.participation_detail_ids:
            raise ValidationError(_("Không có học viên nào để cập nhật kết quả."))

        return {
            'name': 'Cập nhật kết quả đào tạo',
            'type': 'ir.actions.act_window',
            'res_model': 'training.result.wizard',
            'view_mode': 'form',
            'target': 'new',  # Popup
            'context': {
                'active_id': self.id,  # Truyền ID của đợt này sang wizard
                'active_model': 'training.plan.participation'
            }
        }

    # Thêm is_manually_ended vào depends để trigger tính toán lại
    @api.depends('start_date', 'end_date', 'training_plan_id.state', 'is_manually_ended')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec._update_state_logic(today)

    def _update_state_logic(self, today_date):
        self.ensure_one()

        # 1. Ưu tiên cao nhất: Nếu Plan chưa duyệt -> Luôn là Chưa bắt đầu
        if self.training_plan_id.state != 'approved':
            self.state = 'not_started'
            return

        # 2. Ưu tiên nhì: Nếu đã bấm nút Kết thúc thủ công -> Finished ngay lập tức
        # (Giúp xử lý trường hợp Start = End = Today mà bấm End vẫn về Finished)
        if self.is_manually_ended:
            self.state = 'finished'
            return

        # 3. Logic ngày tháng tự động
        if not self.start_date:
            self.state = 'not_started'
        elif not self.end_date:
            # Nếu chưa có ngày kết thúc, chỉ cần đến ngày bắt đầu là In Progress
            self.state = 'in_progress' if today_date >= self.start_date else 'not_started'
        else:
            # Logic: Start <= Today <= End
            if today_date < self.start_date:
                self.state = 'not_started'
            elif self.start_date <= today_date <= self.end_date:
                self.state = 'in_progress'
            else:
                self.state = 'finished'

    # =========================================================
    # 2. RÀNG BUỘC DỮ LIỆU
    # =========================================================

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            # Cho phép start_date == end_date (chỉ raise lỗi khi start > end)
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(_("Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu!"))

    # =========================================================
    # 3. CRON JOB (CHẠY TỰ ĐỘNG)
    # =========================================================

    @api.model
    def _cron_update_training_state(self):
        """
        Scheduled Action gọi hàm này mỗi ngày.
        """
        today = fields.Date.context_today(self)
        # Chỉ quét các bản ghi chưa 'finished'
        records = self.search([('state', '!=', 'finished')])
        for rec in records:
            rec._update_state_logic(today)

    # =========================================================
    # 4. ACTION BUTTONS (THỦ CÔNG)
    # =========================================================

    def action_start(self):
        """Nút Bắt đầu"""
        for rec in self:
            if rec.training_plan_id.state != 'approved':
                raise ValidationError(_("Không thể bắt đầu đào tạo khi Kế hoạch chưa được duyệt!"))

        today = fields.Date.context_today(self)
        for rec in self:
            # [QUAN TRỌNG] Reset cờ thủ công để tính lại theo ngày tháng
            rec.is_manually_ended = False

            if rec.training_plan_detail_id:
                rec.training_plan_detail_id.write({'start_date': today})

    def action_end(self):
        """Nút Kết thúc"""
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.training_plan_detail_id:
                # Kiểm tra logic: Không cho phép kết thúc nếu ngày bắt đầu (dự kiến) nằm ở tương lai
                # start_date > today: Lỗi
                # start_date == today: OK (cho phép sáng bắt đầu, chiều kết thúc)
                if rec.start_date and rec.start_date > today:
                    raise ValidationError(_("Không thể kết thúc vì ngày bắt đầu (dự kiến) lớn hơn hôm nay."))

                # Ghi ngày kết thúc
                rec.training_plan_detail_id.write({'end_date': today})

                # [QUAN TRỌNG] Đánh dấu đã kết thúc thủ công -> Để ép state về 'finished'
                rec.is_manually_ended = True

                # Gọi lại compute ngay lập tức để cập nhật giao diện
                rec._compute_state()

    # =========================================================
    # 5. CÁC FIELDS KHÁC (GIỮ NGUYÊN)
    # =========================================================

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

    start_date = fields.Date(
        string="Từ ngày",
        related='training_plan_detail_id.start_date',
        store=True,
        readonly=True
    )

    end_date = fields.Date(
        string="Đến ngày",
        related='training_plan_detail_id.end_date',
        store=True,
        readonly=True
    )

    training_location = fields.Char(
        string="Địa điểm đào tạo",
        related='training_plan_detail_id.training_location',
        readonly=True
    )

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

    participation_detail_ids = fields.One2many(
        "training.plan.participation.detail",
        "participation_id",
        string="Danh sách đăng ký",
    )

    def write(self, vals):
        res = super(TrainingPlanParticipation, self).write(vals)
        if 'state' in vals:
            for rec in self:
                for line in rec.participation_detail_ids:
                    line._sync_to_history()
        return res

    schedule_ids = fields.One2many(
        'training.plan.schedule',
        'participation_id',
        string="Lịch trình chi tiết"
    )

    def action_open_schedule_popup(self):

        self.ensure_one()

        # Kiểm tra trước khi mở
        if not self.start_date or not self.end_date:
            raise ValidationError("Vui lòng cập nhật Từ ngày - Đến ngày cho khoá học trước khi tạo lịch.")

        view_id = self.env.ref('hr_training_tedi.view_training_schedule_popup_form').id

        return {
            'name': 'Lịch đào tạo',
            'type': 'ir.actions.act_window',
            'res_model': 'training.plan.participation',  # Mở chính model này
            'res_id': self.id,  # Mở đúng bản ghi này
            'view_mode': 'form',
            'views': [(view_id, 'form')],  # Ép dùng view popup mình tạo bên dưới
            'target': 'new',  # Mở dạng Popup
            'flags': {'mode': 'edit'},  # Mở ở chế độ Sửa luôn
        }

    def action_open_attendance_popup(self):
        """Hàm mở popup giống hình"""
        self.ensure_one()

        # Kiểm tra điều kiện
        if not self.schedule_ids:
            raise ValidationError("Chưa có lịch học nào để điểm danh. Vui lòng tạo Lịch đào tạo trước!")

        # Mở Wizard
        return {
            'name': 'DANH SÁCH ĐIỂM DANH',
            'type': 'ir.actions.act_window',
            'res_model': 'training.attendance.wizard',
            'view_mode': 'form',
            'target': 'new',  # Mở dạng Popup
            'context': {'default_participation_id': self.id}
        }



class TrainingPlanParticipationDetail(models.Model):
    _name = 'training.plan.participation.detail'
    _description = 'Training Plan Participation Detail'

    participation_id = fields.Many2one(
        'training.plan.participation',
        string="Đợt tham gia",
        ondelete="cascade",
    )

    # Sử dụng compute + store để xử lý field này thay vì related trực tiếp
    training_plan_detail_id = fields.Many2one(
        'training.plan.detail',
        string="Khoá đào tạo",
        compute='_compute_training_plan_detail_id',
        store=True,
        readonly=False
    )

    @api.depends('participation_id.training_plan_detail_id')
    def _compute_training_plan_detail_id(self):
        for rec in self:
            rec.training_plan_detail_id = rec.participation_id.training_plan_detail_id or False

    user_id = fields.Many2one('res.users', string="Họ và tên")

    department_id = fields.Many2one(
        'hr.department',
        string="Đơn vị",
        related='user_id.employee_id.department_id',
        store=True,
        readonly=True,
    )

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

    training_time = fields.Char(
        string="Thời gian",
        related='training_plan_detail_id.time_of_execution',
        store=True,
        readonly=True,
    )

    start_date = fields.Date(related='training_plan_detail_id.start_date', string="Từ ngày", readonly=True)
    end_date = fields.Date(related='training_plan_detail_id.end_date', string="Đến ngày", readonly=True)

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

    note = fields.Char(
        string="Ghi chú",
        related='training_plan_detail_id.note',
        store=True,
        readonly=True
    )
    training_result = fields.Selection([
        ('pass', 'Đạt'),
        ('fail', 'Không đạt')
    ], string="Kết quả")

    # Hàm mở Popup
    def action_open_result_wizard(self):
        self.ensure_one()
        view_id = self.env.ref('hr_training_tedi.view_training_result_wizard_form').id
        return {
            'name': 'Cập nhật kết quả đào tạo',
            'type': 'ir.actions.act_window',
            'res_model': 'training.result.wizard',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'new',
            'context': {
                'default_participation_detail_id': self.id,
                'default_training_result': self.training_result  # Load giá trị cũ nếu có
            }
        }

    # CẬP NHẬT HÀM ĐỒNG BỘ (_sync_to_history) ĐỂ ĐẨY KẾT QUẢ SANG TAB QUÁ TRÌNH ĐÀO TẠO
    def _sync_to_history(self):
        History = self.env['hr.employee.training.tedi']
        for rec in self:
            if rec.training_plan_detail_id.plan_id.state != 'approved':
                continue

            employee = rec.user_id.employee_id
            if not employee:
                continue

            plan_detail = rec.training_plan_detail_id
            participation_state = rec.participation_id.state

            target_status = 'planned'
            if participation_state == 'finished':
                target_status = 'completed'
            elif participation_state == 'in_progress':
                target_status = 'in_progress'
            elif participation_state == 'not_started':
                target_status = 'planned'

            data_vals = {
                'employee_id': employee.id,
                'name': plan_detail.course_id.name if plan_detail.course_id else (
                            plan_detail.plan_id.name or 'Khóa học'),
                'facility': plan_detail.training_location,
                'date_from': plan_detail.start_date,
                'date_to': plan_detail.end_date,
                'training_form': plan_detail.training_type,
                'status': target_status,
                'source_detail_id': rec.id,
                # --- MỚI: Đồng bộ kết quả ---
                'training_result': rec.training_result
            }

            existing = History.search([('source_detail_id', '=', rec.id)], limit=1)
            if existing:
                existing.write(data_vals)
            else:
                data_vals['source_detail_id'] = rec.id
                History.create(data_vals)

    @api.model
    def create(self, vals):
        record = super(TrainingPlanParticipationDetail, self).create(vals)
        record._sync_to_history()
        return record

    # 2. SỬA HỌC VIÊN (VÍ DỤ ĐỔI NGƯỜI) -> CẬP NHẬT LỊCH SỬ
    def write(self, vals):
        res = super(TrainingPlanParticipationDetail, self).write(vals)
        for rec in self:
            rec._sync_to_history()
        return res

    # 3. XÓA HỌC VIÊN -> XÓA LỊCH SỬ (Đã xử lý bằng ondelete='cascade' ở model đích, nhưng thêm cho chắc)
    def unlink(self):
        history_recs = self.env['hr.employee.training.tedi'].search([('source_detail_id', 'in', self.ids)])
        history_recs.unlink()
        return super(TrainingPlanParticipationDetail, self).unlink()


