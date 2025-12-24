from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError

# --- CẬP NHẬT CONSTANTS THEO PHÂN QUYỀN MỚI ---
# MANAGER = Quản lý nghiệp vụ (Cấp cao hơn Unit Manager)
MANAGER             = "hr_training_tedi.group_training_manager"
PARTICIPANT         = "hr_training_tedi.group_training_participant"
UNIT_MANAGER        = "hr_training_tedi.group_training_unit_manager"
GENERAL_DIRECTOR    = "hr_training_tedi.group_training_general_director"
BASE                = "base.group_user"
import logging
_logger = logging.getLogger(__name__)
class TrainingNeedsSurvey(models.Model):
    _name = 'training.needs.survey'
    _description = 'Training Needs Survey'
    _order = "id desc"

    # ----------------------------------------------------
    #   FIELDS
    # ----------------------------------------------------
    name = fields.Char(string='Name', required=True) # Nên để required

    user_id = fields.Many2one(
        'res.users',
        string='Người tạo',
        default=lambda self: self.env.user
    )

    create_date = fields.Date(
        string="Ngày tạo",
        default=fields.Date.context_today
    )

    start_date = fields.Date(
        string="Ngày bắt đầu",
        required=True,
        default=fields.Date.context_today
    )

    end_date = fields.Date(string="Ngày kết thúc")

    state = fields.Selection([
        ("draft", "Dự thảo"),
        ("confirmed", "Đã xác nhận"),
        ("in_process", "Đang mở đăng ký"),
        ("end", "Kết thúc"),
    ], string="Trạng thái", default="draft")

    # ----------------------------------------------------
    #   PERMISSION CHECK (LOGIC MỚI)
    # ----------------------------------------------------
    def _check_manager_access(self):
        """
        Hàm này kiểm tra xem User hiện tại có thuộc nhóm Manager (hoặc cao hơn) không.
        Vì General Director và Admin kế thừa Manager, nên check Manager là đủ.
        """
        if not self.env.user.has_group(MANAGER):
            raise AccessError(_("Bạn không có quyền thực hiện thao tác này. Chỉ Quản lý nghiệp vụ trở lên mới được phép."))

    # ----------------------------------------------------
    #   OVERRIDES & ACTIONS
    # ----------------------------------------------------

    @api.model
    def create(self, vals):
        # 1. Kiểm tra quyền ngay khi tạo
        self._check_manager_access()
        return super().create(vals)

    def unlink(self):
        # 1. Kiểm tra quyền khi xóa
        self._check_manager_access()
        return super().unlink()

    def action_start_survey(self):
        # 1. Kiểm tra quyền
        self._check_manager_access()

        today = fields.Date.context_today(self)

        for rec in self:
            # 2. Kiểm tra tính hợp lệ của ngày tháng
            if rec.end_date and rec.end_date < today:
                raise ValidationError(_(
                    "Không thể bắt đầu ngay vì Ngày kết thúc (%s) đang ở quá khứ. "
                    "Vui lòng chỉnh sửa Ngày kết thúc ít nhất là từ hôm nay trở đi."
                ) % rec.end_date)

            # 3. Cập nhật dữ liệu
            rec.start_date = today
            rec.state = 'in_process'

    def action_end(self):
        # 1. Kiểm tra quyền
        self._check_manager_access()

        today = fields.Date.context_today(self)
        for rec in self:
            rec.state = 'end'
            # Nếu chưa có ngày kết thúc hoặc ngày kết thúc > hôm nay -> gán lại bằng hôm nay
            if not rec.end_date or rec.end_date > today:
                rec.end_date = today

    def action_submit(self):
        # 1. Kiểm tra quyền
        self._check_manager_access()

        today = fields.Date.context_today(self)
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < today:
                raise ValidationError(_(
                    "Không thể xác nhận khảo sát vì Ngày kết thúc (%s) đã qua." % rec.end_date
                ))

            rec.state = "confirmed"

            if rec.start_date and rec.start_date <= today:
                rec.state = 'in_process'

        # Check lại logic ngày tháng
        self._check_and_update_state_on_date_change()

    # ----------------------------------------------------
    #   HELPER LOGIC
    # ----------------------------------------------------
    def _check_and_update_state_on_date_change(self):
        """Kiểm tra và cập nhật trạng thái cho bản ghi hiện tại."""
        today = fields.Date.context_today(self)

        for rec in self:
            if rec.state == 'confirmed' and rec.start_date and rec.start_date <= today:
                rec.state = 'in_process'
            elif rec.state == 'in_process' and rec.end_date and rec.end_date < today:
                rec.state = 'end'

    # ----------------------------------------------------
    #   VALIDATION
    # ----------------------------------------------------
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_(
                    "Ngày kết thúc (%s) không được nhỏ hơn ngày bắt đầu (%s)." %
                    (rec.end_date, rec.start_date)
                ))

    # ----------------------------------------------------
    #   CRON JOB
    # ----------------------------------------------------
    @api.model
    def _cron_update_survey_states(self):
        # 1. Log ra terminal để biết cron đã được gọi
        _logger.info("============== START CRON: UPDATE SURVEY STATES ==============")

        # 2. Lấy ngày hôm nay
        today = fields.Date.context_today(self)
        _logger.info(f"Check Date: {today}")

        # 3. Logic 1: Confirmed -> In Process
        # Dùng sudo() để đảm bảo tìm thấy tất cả bản ghi bất chấp quyền
        surveys_to_start = self.sudo().search([
            ('state', '=', 'confirmed'),
            ('start_date', '!=', False),
            ('start_date', '<=', today),
        ])

        if surveys_to_start:
            _logger.info(f"Starting {len(surveys_to_start)} surveys: {surveys_to_start.ids}")
            surveys_to_start.write({'state': 'in_process'})
        else:
            _logger.info("No surveys to start.")

        # 4. Logic 2: In Process -> End
        # Lưu ý: end_date < today nghĩa là ngày kết thúc LÀ HÔM QUA
        surveys_to_end = self.sudo().search([
            ('state', '=', 'in_process'),
            ('end_date', '!=', False),
            ('end_date', '<', today),
        ])

        if surveys_to_end:
            _logger.info(f"Ending {len(surveys_to_end)} surveys: {surveys_to_end.ids}")
            surveys_to_end.write({'state': 'end'})
        else:
            _logger.info("No surveys to end.")

        _logger.info("============== END CRON ==============")