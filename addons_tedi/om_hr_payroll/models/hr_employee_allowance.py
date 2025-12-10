from odoo import models, fields, api


class HrEmployeeAllowance(models.Model):
    _name = "hr.employee.allowance"
    _description = "Phụ cấp nhân viên"

    type = fields.Selection([('meal', 'Ăn ca')], string='Phân loại')
    code = fields.Char('Mã phụ cấp')
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

    salary_allowance = fields.Monetary(
        string="Số tiền phụ cấp", currency_id="currency_id")

    @api.depends('employee_id', 'month', 'year', 'salary_allowance', 'currency_id', 'type')
    def _compute_display_name(self):
        for rec in self:
            month = rec.month or ''
            year = rec.year or ''
            emp = rec.employee_id.name or ''
            salary_allowance = rec.salary_allowance or 0.0
            currency_name = rec.currency_id.name or ''
            type_name = dict(rec._fields['type'].selection).get(rec.type, '')
            rec.display_name = f"[{month}/{year}][{type_name}] {emp}: {salary_allowance:,.0f}{currency_name}"