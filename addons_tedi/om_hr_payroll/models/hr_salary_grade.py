from odoo import models, fields, api


class HrSalaryGrade(models.Model):
    _name = "hr.salary.grade"
    _description = "Bậc lương nhân viên"

    name = fields.Char('Tên')
    code = fields.Char('Mã')
    salary_coefficient = fields.Float('Hệ số')
    advance_amount = fields.Float('Giá trị tạm ứng')
    bonus_rate = fields.Float("Tỉ lệ thưởng")
    salary_grade = fields.Float('Giá trị lương theo bậc')

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Mã bậc lương phải là duy nhất!'),
    ]

