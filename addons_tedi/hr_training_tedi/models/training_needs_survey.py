from pygments.lexer import default

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError , AccessError


HR_OFFICER          = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
PARTICIPANT         = "hr_training_tedi.group_training_participant"
UNIT_MANAGER        = "hr_training_tedi.group_training_unit_manager"
GENERAL_DIRECTOR    = "hr_training_tedi.group_training_general_director"
BASE                = "base.group_user"

class TrainingNeedsSurvey(models.Model):
    _name = 'training.needs.survey'
    _description = 'Training Needs Survey'
    _order = "id desc"

    # ----------------------------------------------------
    #   FIELDS
    # ----------------------------------------------------
    name = fields.Char(string='Name')

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
        ("in_process", "Đang khảo sát"),
        ("end", "Kết thúc"),
    ], string="Trạng thái", default="draft")


    def _check_participant(self):
        if self.env.user.has_group(PARTICIPANT):
            raise AccessError(_("Participant không được thực hiện thao tác này"))

    # ----------------------------------------------------
    #   BUTTON: SUBMIT (draft → confirmed)
    # ----------------------------------------------------
    def _check_and_update_state_on_date_change(self):
        """Kiểm tra và cập nhật trạng thái cho bản ghi hiện tại."""
        today = fields.Date.context_today(self)

        for rec in self:
            # Điều kiện 1: confirmed → in_process (Chuyển ngay nếu hôm nay là ngày bắt đầu)
            if rec.state == 'confirmed' and rec.start_date and rec.start_date <= today:
                rec.state = 'in_process'

            # Điều kiện 2: in_process → end
            elif rec.state == 'in_process' and rec.end_date and rec.end_date < today:
                rec.state = 'end'


    def action_start_survey(self):
        # 1. Kiểm tra quyền
        self._check_participant()

        today = fields.Date.context_today(self)

        for rec in self:
            # 2. Kiểm tra tính hợp lệ của ngày tháng
            # Vì start_date sẽ gán bằng hôm nay, nên phải đảm bảo end_date (nếu có) phải >= hôm nay
            if rec.end_date and rec.end_date < today:
                raise ValidationError(_(
                    "Không thể bắt đầu ngay vì Ngày kết thúc (%s) đang ở quá khứ. "
                    "Vui lòng chỉnh sửa Ngày kết thúc ít nhất là từ hôm nay trở đi."
                ) % rec.end_date)

            # 3. Cập nhật dữ liệu
            rec.start_date = today
            rec.state = 'in_process'


    def action_end(self):
        self._check_participant()

        # Lấy ngày hiện tại
        today = fields.Date.context_today(self)

        for rec in self:
            # 2. Cập nhật trạng thái
            rec.state = 'end'

            if not rec.end_date or rec.end_date > today:
                rec.end_date = today

    def action_submit(self):
        today = fields.Date.context_today(self)
        for rec in self:
            # Kiểm tra ngày tháng trước khi chuyển trạng thái: Nếu đã quá hạn thì báo lỗi
            if rec.start_date and rec.end_date and rec.end_date < today:
                raise ValidationError(_(
                    "Không thể xác nhận khảo sát vì Ngày kết thúc (%s) đã qua." % rec.end_date
                ))

            # Chuyển trạng thái sang Confirmed
            rec.state = "confirmed"

            # TỰ ĐỘNG CHUYỂN SANG IN_PROCESS nếu đã đến hoặc quá ngày bắt đầu
            if rec.start_date and rec.start_date <= today:
                rec.state = 'in_process'

        # Sau khi submit, cần kiểm tra lại cả trạng thái end (đề phòng trường hợp end_date = today)
        self._check_and_update_state_on_date_change()

    # ----------------------------------------------------
    #   VALIDATION: start_date < end_date
    # ----------------------------------------------------
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_(
                    "Ngày kết thúc (%s) không được nhỏ hơn ngày bắt đầu (%s)." %
                    (rec.end_date, rec.start_date)
                ))
    @api.model
    def create(self, vals):
        self._check_participant()
        return super().create(vals)


    # ----------------------------------------------------
    #   CRON: auto update trạng thái
    # ----------------------------------------------------
    @api.model
    def _cron_update_survey_states(self):
        today = fields.Date.context_today(self)

        # 1. confirmed → in_process khi đến ngày bắt đầu
        surveys_to_start = self.search([
            ('state', '=', 'confirmed'),
            ('start_date', '!=', False),
            ('start_date', '<=', today),
        ])
        surveys_to_start.write({'state': 'in_process'})

        # 2. in_process → end nếu quá hạn
        surveys_to_end = self.search([
            ('state', '=', 'in_process'),
            ('end_date', '!=', False),
            ('end_date', '<', today),
        ])
        surveys_to_end.write({'state': 'end'})

    # ----------------------------------------------------
    #   INIT: chạy khi server start để đồng bộ trạng thái
    # ----------------------------------------------------
    def init(self):
        self._cron_update_survey_states()

    def unlink(self):
        # for rec in self:
        #     if rec.state == 'end':
        #         raise ValidationError(_("Không thể xoá khảo sát đã kết thúc."))
        return super().unlink()


