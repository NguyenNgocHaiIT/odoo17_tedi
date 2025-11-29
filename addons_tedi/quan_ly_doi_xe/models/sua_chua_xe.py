# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrTediVehicleRepair(models.Model):
    _name = "hr_tedi.vehicle.repair"
    _description = "Phiếu sửa chữa xe"

    name = fields.Char(
        string="Mã phiếu",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'New',
        help="Tự động sinh bằng sequence dạng SC001, SC002..."
    )

    vehicle_id = fields.Many2one(
        'hr_tedi.vehicle.record',
        string="Thông tin xe",
        required=True
    )

    requester_id = fields.Many2one(
        'hr.employee',
        string="Người đề nghị",
        default=lambda self: self.env.user.employee_id,
        readonly=True
    )

    request_date = fields.Date(
        string="Ngày đề nghị",
        default=fields.Date.context_today
    )

    odometer = fields.Float(string="Số Km trên đồng hồ")

    cost = fields.Float(
        string="Tổng chi phí",
        compute='_compute_total_cost',
        store=True,
        readonly=True
    )

    note = fields.Text(string="Ghi chú thêm")

    attachment_ids = fields.Many2many('ir.attachment', string="Tệp đính kèm")

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('approved', 'Đã duyệt'),
        ('cancel', 'Đã hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    repair_line_ids = fields.One2many(
        'hr_tedi.vehicle.repair.line',
        'repair_id',
        string="Nội dung sửa chữa"
    )

    @api.depends('repair_line_ids.price_unit')
    def _compute_total_cost(self):
        for rec in self:
            rec.cost = sum(line.price_unit for line in rec.repair_line_ids)

    @api.model
    def create(self, vals):
        """
        Sinh mã bằng ir.sequence khi tạo mới.
        Giữ default='New' để tránh gọi sequence khi load module.
        """
        if vals.get('name', 'New') in (False, '', 'New'):
            seq = self.env['ir.sequence'].next_by_code('hr_tedi.vehicle.repair')
            if not seq:
                # Thông báo rõ ràng nếu sequence chưa được định nghĩa
                raise UserError(_("Sequence 'hr_tedi.vehicle.repair' chưa được cấu hình. Vui lòng cài file data/ir_sequence_repair.xml trước."))
            vals['name'] = seq
        return super(HrTediVehicleRepair, self).create(vals)

    def action_approve(self):
        return self.write({'state': 'approved'})

    def action_cancel(self):
        return self.write({'state': 'cancel'})