from odoo import models, fields, api


class HrSalaryGrade(models.Model):
    _name = "hr.salary.grade"
    _description = "Bậc lương nhân viên"

    name = fields.Char('Chức danh')
    code = fields.Char('Mã')
    salary_coefficient = fields.Float('Hệ số')
    advance_amount = fields.Float('Giá trị tạm ứng')
    bonus_rate = fields.Float("Tỉ lệ thưởng")
    salary_grade = fields.Float('Giá trị lương theo bậc')
    luong_chuc_danh = fields.Float(compute='luong_chuc_danh_compute', store=True)
    salary_increment_period = fields.Integer(string="Thời hạn nâng lương")

    @api.depends('salary_grade', 'salary_coefficient')
    def luong_chuc_danh_compute(self):
        for record in self:
            record.luong_chuc_danh = 0
            if record.salary_grade and record.salary_coefficient:
                record.luong_chuc_danh = record.salary_coefficient * record.salary_grade

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Mã bậc lương phải là duy nhất!'),
    ]

