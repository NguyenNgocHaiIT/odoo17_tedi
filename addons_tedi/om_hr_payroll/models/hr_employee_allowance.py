from odoo import models, fields, api


class HrEmployeeAllowance(models.Model):
    _name = "hr.employee.allowance"
    _description = "Phụ cấp nhân viên"

    type = fields.Selection([('meal', 'Ăn ca')], string='Phân loại')
    allowance_type_id = fields.Many2one(
        'hr.allowance.type',
        string='Loại phụ cấp',
        required=True,
        ondelete='restrict'
    )
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


class HrAllowanceType(models.Model):
    _name = "hr.allowance.type"
    _description = "Danh mục Loại Phụ cấp"
    _order = "sequence, id"

    name = fields.Char(string="Tên phụ cấp", required=True)
    code = fields.Char(string="Mã loại", required=True)
    sequence = fields.Integer(string="Thứ tự", default=10)

    # Không còn lưu tiền hay phương thức tính ở đây nữa

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'Mã loại phụ cấp phải là duy nhất!')
    ]



# class HrAllowanceStep(models.Model):
#     _name = "hr.allowance.step"
#     _description = "Chi tiết Bậc Phụ cấp (Cấu hình)"
#     _order = "sequence, id"
#
#     allowance_id = fields.Many2one("hr.allowance.type", string="Loại phụ cấp", ondelete="cascade")
#     name = fields.Char(string="Tên bậc", required=True, help="VD: Bậc 1, Bậc 2...")
#     sequence = fields.Integer(string="Thứ tự", default=10)
#
#     currency_id = fields.Many2one(related="allowance_id.currency_id", string="Tiền tệ")
#     amount = fields.Monetary(string="Số tiền quy định", currency_field="currency_id", required=True)




class HrContractAllowance(models.Model):
    _name = "hr.contract.allowance"
    _description = "Chi tiết Phụ cấp trên Hợp đồng"

    contract_id = fields.Many2one('hr.contract', string="Hợp đồng", required=True, ondelete='cascade')

    # 1. Chọn loại phụ cấp (chỉ để lấy tên hiển thị)
    allowance_type_id = fields.Many2one("hr.allowance.type", string="Loại phụ cấp", required=True)

    currency_id = fields.Many2one('res.currency', related='contract_id.currency_id', store=True)

    # 2. Số tiền: Người dùng tự nhập tay
    amount = fields.Monetary(string="Số tiền", currency_field="currency_id", required=True, default=0)

    note = fields.Char(string="Ghi chú")

