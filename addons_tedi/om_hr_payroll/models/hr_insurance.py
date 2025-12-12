from odoo import models, fields, api


class HrEmployeeInsurance(models.Model):
    _name = "hr.employee.insurance"
    _description = "Quỹ lương tính BHXH theo tháng"

    employee_id = fields.Many2one(
        'hr.employee',
        string='Nhân viên',
        required=True,
    )

    month = fields.Selection(
        [(str(i), f'Tháng {i}') for i in range(1, 13)],
        string='Tháng',
        required=True
    )

    year = fields.Integer(
        string='Năm',
        required=True,
        default=lambda self: fields.Date.today().year
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True
    )

    salary_bhxh = fields.Monetary(
        string="Lương tính BHXH", currency_id="currency_id",
        help="Mức lương làm căn cứ đóng BHXH của nhân viên trong tháng."
    )

    @api.depends('employee_id', 'month', 'year', 'salary_bhxh', 'currency_id')
    def _compute_display_name(self):
        for rec in self:
            month = rec.month or ''
            year = rec.year or ''
            emp = rec.employee_id.name or ''
            salary_bhxh = rec.salary_bhxh or 0.0
            currency_name = rec.currency_id.name or ''

            rec.display_name = f"[{month}/{year}] {emp}: {salary_bhxh:,.0f}{currency_name}"