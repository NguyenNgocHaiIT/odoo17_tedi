# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'
    _rec_name = 'code'

    # --- 1. MAPPING CÁC TRƯỜNG CUSTOM ---
    code = fields.Char(string="Mã phiếu", default='New', copy=False, readonly=True)

    requester_id = fields.Many2one('hr.employee', string="Người đề nghị",
                                   default=lambda self: self.env.user.employee_id, readonly=True)

    attachment_ids = fields.Many2many('ir.attachment', string="Tệp đính kèm")

    repair_line_ids = fields.One2many('fleet.service.line', 'service_id', string="Chi tiết sửa chữa")

    # --- QUAN TRỌNG: Cần set default cho service_type_id vì XML đã ẩn nó đi ---
    service_type_id = fields.Many2one(
        'fleet.service.type', 'Loại dịch vụ', required=True,
        default=lambda self: self.env['fleet.service.type'].search([], limit=1)
    )

    # --- 2. LOGIC TÍNH TOÁN ---
    amount = fields.Monetary(string='Tổng chi phí', compute='_compute_total_cost', store=True, readonly=False)

    @api.depends('repair_line_ids.price_unit')
    def _compute_total_cost(self):
        for rec in self:
            if rec.repair_line_ids:
                rec.amount = sum(line.price_unit for line in rec.repair_line_ids)
            elif not rec.amount:
                rec.amount = 0.0

    # --- 3. SEQUENCE ---
    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('fleet.vehicle.log.services.repair') or 'New'
        return super(FleetVehicleLogServices, self).create(vals)

    # --- 4. ACTION BUTTONS ---
    def action_approve(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reopen(self):
        self.write({
                       'state': 'new'})  # Odoo base state thường là 'new', 'running', 'done', 'cancelled'. Bạn check kỹ state gốc nhé.


# --- CLASS CON ---
class FleetServiceLine(models.Model):
    _name = "fleet.service.line"
    _description = "Chi tiết hạng mục dịch vụ/sửa chữa"
    _order = "sequence"

    service_id = fields.Many2one('fleet.vehicle.log.services', string="Phiếu dịch vụ", required=True,
                                 ondelete='cascade')
    sequence = fields.Integer(string='STT', default=10)

    # 1. Thêm trường trỏ đến danh mục dịch vụ của Odoo
    service_type = fields.Char("Hạng mục")

    price_unit = fields.Float(string="Thành tiền")


    note = fields.Text(string="Ghi chú")

