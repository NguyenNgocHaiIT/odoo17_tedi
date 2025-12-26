from odoo import models, fields, api
from odoo.exceptions import UserError
import odoo
import logging

_logger = logging.getLogger(__name__)


class ExtraCost(models.Model):
    _name = "extra.cost"
    _description = "Phiếu chi phí phát sinh"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Mã phiếu")
    date = fields.Date(default=fields.Date.today, string="Ngày tạo")

    employee_id = fields.Many2one(
        "hr.employee",
        string="Người tạo",
        default=lambda self: self._get_default_employee(),
        required=True
    )

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        string="Công ty"
    )

    department_id = fields.Many2one(
        "hr.department",
        compute="_compute_department",
        store=True,
        string="Đơn vị/Phòng ban"
    )

    reference = fields.Char(string="Tham chiếu / Ghi chú")

    cost_type_id = fields.Many2one(
        "extra.cost.type",
        string="Loại chi phí phát sinh",
        required=True,
        default=lambda self: self._get_default_cost_type()
    )

    # Vé máy bay
    airline = fields.Selection([
        ('Vietnam Airlines', 'Vietnam Airlines'),
        ('Bamboo Airways', 'Bamboo Airways '),
        ('Vietjet Air', 'Vietjet Air'),
        ('SunPhuQuoc Airways', 'SunPhuQuoc Airways'),
    ], string="Hãng hàng không")
    flight_code = fields.Char("Mã chuyến bay")
    flight_date = fields.Date("Ngày bay")
    flight_time = fields.Char("Giờ bay")
    passenger_count = fields.Integer("Số người bay", default=1)

    # File đính kèm
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'extra_cost_attachment_rel',
        'cost_id',
        'attachment_id',
        string='File đính kèm'
    )

    amount = fields.Monetary("Số tiền", required=True)
    tax_amount = fields.Monetary("Thuế / phí", default=0)

    total_amount = fields.Monetary(
        compute="_compute_total",
        store=True,
        string="Tổng tiền"
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id
    )

    state = fields.Selection([
        ("draft", "Soạn thảo"),
        ("submitted", "Chờ duyệt"),
        ("approved", "Đã duyệt"),
        ("rejected", "Từ chối"),
    ], default="draft", tracking=True)

    def _get_default_employee(self):
        """Lấy employee mặc định theo user hiện tại"""
        employee = self.env['hr.employee'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        return employee.id if employee else False

    def _get_default_cost_type(self):
        """Lấy hoặc tạo mặc định loại 'Mua vé máy bay'"""
        cost_type = self.env['extra.cost.type'].search([
            ('name', 'ilike', 'Mua vé máy bay')
        ], limit=1)

        if not cost_type:
            cost_type = self.env['extra.cost.type'].create({
                'name': 'Mua vé máy bay'
            })

        return cost_type.id

    @api.depends("employee_id")
    def _compute_department(self):
        for rec in self:
            rec.department_id = rec.employee_id.department_id.id if rec.employee_id else False

    @api.depends("amount", "tax_amount")
    def _compute_total(self):
        for rec in self:
            rec.total_amount = (rec.amount or 0) + (rec.tax_amount or 0)

    def action_submit(self):
        self.state = "submitted"

    def action_approve(self):
        self.state = "approved"

    def action_reject(self):
        self.state = "rejected"

    @api.model
    def create(self, vals):
        if vals.get("name") == "New" or not vals.get("name"):
            vals["name"] = self.env["ir.sequence"].next_by_code("extra.cost") or "New"

        # Nếu chưa có cost_type_id, thêm mặc định
        if not vals.get('cost_type_id'):
            vals['cost_type_id'] = self._get_default_cost_type()

        return super().create(vals)


class ExtraCostType(models.Model):
    _name = "extra.cost.type"
    _description = "Loại chi phí phát sinh"

    name = fields.Char(string="Tên loại chi phí", required=True)