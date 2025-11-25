from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

HR_OFFICER          = "quan_ly_tuyen_dung.group_recruitment_hr_officer"
PARTICIPANT         = "hr_training_tedi.group_training_participant"
UNIT_MANAGER        = "hr_training_tedi.group_training_unit_manager"
GENERAL_DIRECTOR    = "hr_training_tedi.group_training_general_director"
BASE                = "base.group_user"



class TrainingCourse(models.Model):
    _name = 'training.course'
    _description = 'Training Course'

    name = fields.Char(string='Tên khoá đào tạo')
    type = fields.Selection([
        ("long-term", "Dài hạn"),
        ("short-term", "Ngắn hạn")
    ] , string = "Loại hình")
    training_field_ids = fields.Many2many("training.field",
                                          "training_course_field_rel",
                                          "training_course_id",
                                          "training_field_id",
                                            string = "Lĩnh vực")

    def _check_participant(self):
        if self.env.user.has_group(PARTICIPANT):
            raise AccessError(_("Participant không được thực hiện thao tác này"))

    @api.model
    def create(self, vals):
        self._check_participant()
        return super().create(vals)



class TrainingField(models.Model):
    _name = 'training.field'
    _description = 'Training Field'

    name = fields.Char(string ="Tên lĩnh vực")
    active = fields.Boolean(default=True)
