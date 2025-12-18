from odoo import  models, fields, api
from odoo.exceptions import ValidationError


class TrainingPlanSchedule(models.Model):
    _name = 'training.plan.schedule'
    _description = 'Lịch đào tạo chi tiết'
    _order = 'date, start_hour'
    _rec_name = "date"

    participation_id = fields.Many2one('training.plan.participation', required=True, ondelete='cascade')


    date = fields.Date(string="Ngày", required=True)
    start_hour = fields.Float(string="Từ", required=True, default=8.0)
    end_hour = fields.Float(string="Đến", required=True, default=12.0)

    @api.onchange('start_hour', 'end_hour')
    def _onchange_check_hours(self):
        for rec in self:
            if rec.start_hour and rec.end_hour:
                if rec.start_hour >= rec.end_hour:
                    return {
                        'warning': {
                            'title': "Giờ không hợp lệ",
                            'message': "Giờ bắt đầu phải nhỏ hơn Giờ kết thúc.",
                        }
                    }

                # Check thêm: Giờ không được > 24
                if rec.start_hour >= 24 or rec.end_hour > 24:
                    return {
                        'warning': {
                            'title': "Giờ không hợp lệ",
                            'message': "Thời gian nhập vào không được vượt quá 24h.",
                        }
                    }

    # ---------------------------------------------------------
    # 2. CHECK NGÀY: TRONG KHOẢNG & KHÔNG TRÙNG
    # ---------------------------------------------------------
    @api.onchange('date')
    def _onchange_check_date(self):
        if not self.date or not self.participation_id:
            return

        parent = self.participation_id
        error_title = "Ngày không hợp lệ"

        # A. Kiểm tra ngày nằm trong khoảng Start/End của khóa học
        p_start = parent.start_date
        p_end = parent.end_date

        if p_start and self.date < p_start:
            self.date = False  # Reset field
            return {'warning': {
                'title': error_title,
                'message': f"Ngày học ({self.date}) không được nhỏ hơn ngày bắt đầu khóa học ({p_start})."
            }}

        if p_end and self.date > p_end:
            self.date = False  # Reset field
            return {'warning': {
                'title': error_title,
                'message': f"Ngày học ({self.date}) không được lớn hơn ngày kết thúc khóa học ({p_end})."
            }}

        # B. Kiểm tra trùng ngày (Duplicate) trong danh sách đang nhập
        # Lưu ý: self.participation_id.schedule_ids chứa cả các dòng đang có trong RAM (NewId)
        # Ta cần filter loại bỏ chính bản ghi đang sửa (self._origin hoặc so sánh object)

        duplicate = parent.schedule_ids.filtered(
            lambda line: line.date == self.date and line != self
        )

        if duplicate:
            self.date = False  # Reset field để bắt người dùng chọn lại
            return {'warning': {
                'title': "Trùng lịch học",
                'message': f"Ngày {self.date} đã tồn tại trong danh sách lịch trình. Vui lòng chọn ngày khác."
            }}

    # --- 1. RÀNG BUỘC: KHÔNG TRÙNG NGÀY ---
    _sql_constraints = [
        ('unique_date_participation', 'unique(participation_id, date)',
         'Ngày này đã có trong lịch đào tạo. Vui lòng kiểm tra lại!')
    ]
    attendance_ids = fields.One2many(
        'training.attendance',
        'schedule_id',
        string="Danh sách điểm danh"
    )

    def action_generate_students(self):
        """Nút: Lấy danh sách học viên vào bảng điểm danh"""
        self.ensure_one()
        Attendance = self.env['training.attendance']

        # 1. Lấy tất cả học viên của lớp
        all_students = self.participation_id.participation_detail_ids.mapped('user_id')

        # 2. Lấy những học viên ĐÃ có trong danh sách điểm danh ngày này
        existing_students = self.attendance_ids.mapped('student_id')

        # 3. Thêm những người chưa có
        new_lines = []
        for student in all_students:
            if student not in existing_students:
                new_lines.append({
                    'schedule_id': self.id,
                    'student_id': student.id,
                    'status': 'present',  # Mặc định Có mặt
                })

        if new_lines:
            Attendance.create(new_lines)

        # Tự động lưu form để cập nhật giao diện
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # --- 2. RÀNG BUỘC: THỜI GIAN (Logic Python) ---
    @api.constrains('date', 'start_hour', 'end_hour')
    def _check_schedule_logic(self):
        for rec in self:
            part = rec.participation_id

            # Check A: Ngày nằm trong khoảng khoá học
            # (part.start_date và part.end_date đã được đảm bảo có dữ liệu ở hàm action_open)
            if not (part.start_date <= rec.date <= part.end_date):
                raise ValidationError(
                    f"Ngày {rec.date.strftime('%d/%m/%Y')} không hợp lệ!\n"
                    f"Phải nằm trong khoảng thời gian khoá học: {part.start_date.strftime('%d/%m/%Y')} -> {part.end_date.strftime('%d/%m/%Y')}"
                )

            # Check B: Giờ kết thúc > Giờ bắt đầu
            if rec.start_hour >= rec.end_hour:
                raise ValidationError(
                    f"Dòng ngày {rec.date.strftime('%d/%m/%Y')}: Giờ kết thúc phải lớn hơn Giờ bắt đầu.")


class TrainingAttendance(models.Model):
    _name = 'training.attendance'
    _description = 'Lịch sử điểm danh (Lưu DB)'
    _rec_name = 'student_id'

    participation_id = fields.Many2one('training.plan.participation', string="Đợt đào tạo", ondelete='cascade')
    schedule_id = fields.Many2one('training.plan.schedule', string="Buổi học", required=True, ondelete='cascade')
    student_id = fields.Many2one('res.users', string="Họ và tên", required=True)

    status = fields.Selection([
        ('present', 'Có mặt'),
        ('absent', 'Vắng mặt')
    ], string="Trạng thái", default='present', required=True)


    _sql_constraints = [
        ('unique_attendance', 'unique(schedule_id, student_id)',
         'Học viên này đã được điểm danh trong buổi học này rồi!')
    ]


class TrainingAttendanceWizard(models.TransientModel):
    _name = 'training.attendance.wizard'
    _description = 'Wizard Điểm danh'

    participation_id = fields.Many2one('training.plan.participation', required=True, readonly=True)

    # Dropdown chọn ngày (Chỉ hiện các ngày đã tạo trong Lịch)
    schedule_id = fields.Many2one(
        'training.plan.schedule',
        string="Chọn ngày",
        required=True,
        domain="[('participation_id', '=', participation_id)]"
    )

    line_ids = fields.One2many('training.attendance.wizard.line', 'wizard_id', string="Danh sách điểm danh")

    # --- TỰ ĐỘNG LOAD DANH SÁCH KHI CHỌN NGÀY ---
    @api.onchange('schedule_id')
    def _onchange_schedule_id(self):
        # Xóa danh sách cũ nếu đổi ngày
        self.line_ids = [(5, 0, 0)]

        if not self.schedule_id:
            return

        AttendanceReal = self.env['training.attendance']
        lines = []

        # 1. Lấy danh sách học viên
        students = self.participation_id.participation_detail_ids.mapped('user_id')

        for student in students:
            # 2. Kiểm tra lịch sử điểm danh trong DB thật
            existing = AttendanceReal.search([
                ('schedule_id', '=', self.schedule_id.id),
                ('student_id', '=', student.id)
            ], limit=1)

            # 3. Tạo dòng dữ liệu cho Wizard
            val = {
                'student_id': student.id,
                'status': existing.status if existing else 'present',  # Mặc định Có mặt

            }
            lines.append((0, 0, val))

        self.line_ids = lines

    def action_confirm(self):
        """Lưu dữ liệu từ Wizard vào Model thật"""
        self.ensure_one()
        AttendanceReal = self.env['training.attendance']

        if not self.line_ids:
            raise ValidationError("Không có học viên nào trong danh sách để điểm danh.")

        for line in self.line_ids:
            # Tìm bản ghi cũ để cập nhật (tránh lỗi duplicate)
            domain = [
                ('schedule_id', '=', self.schedule_id.id),
                ('student_id', '=', line.student_id.id)
            ]
            existing = AttendanceReal.search(domain, limit=1)

            vals = {
                'schedule_id': self.schedule_id.id,
                'student_id': line.student_id.id,
                'status': line.status,
                # Nếu model thật cần participation_id thì thêm vào
                'participation_id': self.participation_id.id
            }

            if existing:
                existing.write(vals)
            else:
                AttendanceReal.create(vals)

        return {'type': 'ir.actions.act_window_close'}


class TrainingAttendanceWizardLine(models.TransientModel):
    _name = 'training.attendance.wizard.line'
    _description = 'Dòng chi tiết điểm danh (Wizard)'

    wizard_id = fields.Many2one('training.attendance.wizard')

    # Lưu ý: Không để readonly=True ở đây để tránh rắc rối, ta sẽ xử lý readonly ở XML
    student_id = fields.Many2one('res.users', string="Họ và tên", required=True)

    status = fields.Selection([
        ('present', 'Có mặt'),
        ('absent', 'Vắng mặt')
    ], string="Trạng thái", default='present', required=True)
