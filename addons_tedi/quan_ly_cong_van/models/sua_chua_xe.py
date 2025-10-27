# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrTediVehicleRepair(models.Model):
    """
    Định nghĩa model cho Phiếu Sửa Chữa Xe
    """
    _name = "hr_tedi.vehicle.repair"
    _description = "Phiếu sửa chữa xe"

    # Mã phiếu tự động
    name = fields.Char(
        string="Mã phiếu",
        default=lambda self: self.env['ir.sequence'].next_by_code('hr_tedi.vehicle.repair') or 'New',
        readonly=True
    )

    # Thông tin xe
    vehicle_id = fields.Many2one(
        'hr_tedi.vehicle.record',
        string="Thông tin xe",
        required=True
    )

    # Người đề nghị
    requester_id = fields.Many2one(
        'hr.employee',
        string="Người đề nghị",
        default=lambda self: self.env.user.employee_id,
        readonly=True
    )

    # Ngày đề nghị
    request_date = fields.Date(
        string="Ngày đề nghị",
        default=fields.Date.context_today
    )

    # Số Km trên đồng hồ
    odometer = fields.Float(string="Số Km trên đồng hồ")

    # Tổng chi phí (tính tự động từ các dòng con)
    cost = fields.Float(
        string="Tổng chi phí",
        compute='_compute_total_cost',
        store=True,
        readonly=True
    )

    # Ghi chú thêm
    note = fields.Text(string="Ghi chú thêm")

    # Tệp đính kèm
    attachment_ids = fields.Many2many('ir.attachment', string="Tệp đính kèm")

    # Trạng thái
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('approved', 'Đã duyệt'),
        ('cancel', 'Đã hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    # Nội dung sửa chữa (One2many)
    repair_line_ids = fields.One2many(
        'hr_tedi.vehicle.repair.line',
        'repair_id',
        string="Nội dung sửa chữa"
    )

    # Hàm tính tổng chi phí
    @api.depends('repair_line_ids.price_unit')
    def _compute_total_cost(self):
        """Hàm tự động tính Tổng chi phí từ các dòng con"""
        for rec in self:
            rec.cost = sum(rec.repair_line_ids.mapped('price_unit'))

    # Hàm cho nút "Duyệt"
    def action_approve(self):
        self.write({'state': 'approved'})
        return True

    # Hàm cho nút "Hủy"
    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True
