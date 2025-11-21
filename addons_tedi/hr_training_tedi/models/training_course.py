from odoo import api, fields, models

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



class TrainingField(models.Model):
    _name = 'training.field'
    _description = 'Training Field'

    name = fields.Char(string ="Tên lĩnh vực")
    active = fields.Boolean(default=True)
