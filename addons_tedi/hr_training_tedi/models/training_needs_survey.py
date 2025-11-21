from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    create_date = fields.Date(string="Ngày tạo")

    start_date = fields.Date(string="Ngày bắt đầu")
    end_date = fields.Date(string="Ngày kết thúc")

    state = fields.Selection([
        ("draft", "Dự thảo"),
        ("confirmed", "Đã xác nhận"),
        ("in_process", "Đang khảo sát"),
        ("end", "Kết thúc"),
    ], string="Trạng thái", default="draft")

    # ----------------------------------------------------
    #   BUTTON: SUBMIT (draft → confirmed)
    # ----------------------------------------------------
    def action_submit(self):
        for rec in self:
            rec.state = "confirmed"

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
        for rec in self:
            if rec.state == 'end':
                raise ValidationError(_("Không thể xoá khảo sát đã kết thúc."))
        return super().unlink()

    # ----------------------------------------------------
    #   WRITE RULES (hạn chế sửa khi end)
    # ----------------------------------------------------
    def write(self, vals):
        for rec in self:
            # Không cho sửa thời gian nếu đã kết thúc
            if rec.state == 'end':
                if 'start_date' in vals or 'end_date' in vals:
                    raise ValidationError(_("Không thể sửa thời gian khi khảo sát đã kết thúc."))

        return super(TrainingNeedsSurvey, self).write(vals)
