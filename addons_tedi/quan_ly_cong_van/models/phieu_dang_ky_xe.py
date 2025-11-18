# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrTediVehicleRegistration(models.Model):
    _name = "hr_tedi.vehicle.registration"
    _description = "Phiếu đăng ký xe"

    # Thông tin xe (không dùng vehicle_id vì có assigned_vehicle_id)
    vehicle_id = fields.Many2one(
        "hr_tedi.vehicle.record",
        string="Thông tin xe")

    # Người đề nghị
    requester_id = fields.Many2one(
        'hr.employee',
        string="Người đề nghị",
        default=lambda self: self.env.user.employee_id,
        readonly=True
    )

    # Thời gian
    start_date = fields.Datetime(string="Thời gian bắt đầu", required=True)
    end_date = fields.Datetime(string="Thời gian kết thúc", required=True)

    # Loại công tác
    trip_type = fields.Selection(
        selection=[
            ('noi_thanh', 'Nội thành'),
            ('ngoai_thanh', 'Ngoại thành'),
        ],
        string="Loại công tác"
    )

    # Địa điểm
    destination = fields.Selection([
        ('hanoi', 'Hà Nội'),
        ('haiphong', 'Hải Phòng'),
        ('quangninh', 'Quảng Ninh'),
        ('ninhbinh', 'Ninh Bình'),
        ('khac', 'Khác')
    ], string="Địa điểm", default='hanoi')

    # Xe được phân công
    assigned_vehicle_id = fields.Many2one(
        'hr_tedi.vehicle.record',
        string="Phân công xe"
    )

    # Lái xe (lấy từ xe được phân công)
    driver_id = fields.Many2one(
        'hr.employee',
        string="Lái xe",
        related='assigned_vehicle_id.driver_id',
        readonly=True,
        store=True
    )

    # Nội dung công việc
    work_content = fields.Text(string="Nội dung công việc")

    # Số km
    distance_km = fields.Float(string="Số km")

    # Số người đi kèm
    num_passengers = fields.Integer(string="Số người đi kèm")

    # Tệp đính kèm
    attachment_ids = fields.Many2many('ir.attachment', string="Tệp đính kèm")

    # Trạng thái
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('assigned', 'Đã phân xe'),
        ('done', 'Hoàn thành'),
        ('rejected', 'Từ chối'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    # Hàm duyệt
    def action_approve(self):
        for rec in self:
            rec.state = 'approved'
        return True