from odoo import models, fields, api
from odoo.exceptions import UserError

class HrExpense(models.Model):
    _inherit = "hr.expense"

    passenger_count = fields.Integer(
        string="Số người bay",
        default=1
    )

    product_code = fields.Char(
        string="Mã loại chi phí",
        related="product_id.default_code",
        store=False,
        readonly=True
    )

    predict_amount = fields.Monetary(string="Chi phí dự kiến")

    department_id = fields.Many2one('hr.department', string="Đơn vị")
    # ==========================
    # PRODUCT: VÉ MÁY BAY
    # ==========================
    def _get_airline_product(self):
        Product = self.env['product.product']

        product = Product.search(
            [('default_code', '=', 'AIRLINES')],
            limit=1
        )

        if not product:
            product = Product.create({
                'name': 'Vé máy bay',
                'default_code': 'AIRLINES',
            })

        return product


    def action_submit(self):
        self.ensure_one()
        self.state = 'submitted'
        return True

    def action_approve_expense(self):
        self.ensure_one()
        self.state = 'approved'
        return True

    def action_refuse_expense(self):
        self.ensure_one()
        self.state = 'refused'
        return True

    @api.model
    def create(self, vals):
        if not vals.get('product_id'):
            product = self._get_airline_product()
            vals['product_id'] = product.id

        return super().create(vals)