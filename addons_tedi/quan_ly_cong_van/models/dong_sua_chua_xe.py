# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrTediVehicleRepairLine(models.Model):
    _name = "hr_tedi.vehicle.repair.line"
    _description = "Dòng Phiếu sửa chữa xe"
    _order = "sequence"  # Sắp xếp theo STT

    # Trường liên kết về phiếu cha
    repair_id = fields.Many2one('hr_tedi.vehicle.repair', string="Phiếu sửa chữa", ondelete='cascade', required=True)

    # Các trường trên dòng
    sequence = fields.Integer(string='STT', compute='_compute_sequence', store=True, readonly=True)
    name = fields.Char(string="Hạng mục sửa chữa", required=True)
    price_unit = fields.Float(string="Chi phí")
    note = fields.Char(string="Ghi chú")

    @api.depends('repair_id', 'repair_id.repair_line_ids')
    def _compute_sequence(self):
        for order in self.mapped('repair_id'):
            for idx, line in enumerate(order.repair_line_ids, start=1):
                line.sequence = idx
