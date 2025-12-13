# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HrEmployeeTraining(models.Model):
    _name = "hr.employee.training"
    _description = "Quá trình đào tạo của nhân viên"

    stt = fields.Integer(string="STT", compute="_compute_stt", store=False)
    employee_id = fields.Many2one("hr.employee", string="Nhân viên", required=True, ondelete="cascade")

    name = fields.Char(string="Tên khóa đào tạo", required=True)
    training_type = fields.Selection([
        ('short_term', 'Ngắn hạn'),
        ('long_term', 'Dài hạn')
    ], string="Loại hình", default='short_term')
    facility = fields.Char(string="Cơ sở đào tạo")
    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")
    training_form = fields.Selection([
        ('offline', 'Trực tiếp'),
        ('online', 'Online')
    ], string="Hình thức đào tạo", default='offline')
    status = fields.Selection([
        ('completed', 'Hoàn thành'),
        ('in_progress', 'Đang học'),
        ('canceled', 'Hủy')
    ], string="Trạng thái", default='completed')

    @api.depends('employee_id.training_ids', 'employee_id.training_ids.name')
    def _compute_stt(self):
        for employee in self.mapped('employee_id'):
            for idx, line in enumerate(employee.training_ids):
                line.stt = idx + 1


class HrEmployeeTrainingTedi(models.Model):
    _name = "hr.employee.training.tedi"
    _description = "Quá trình đào tạo tại TEDI"

    stt = fields.Integer(string="STT", compute="_compute_stt", store=False)
    employee_id = fields.Many2one("hr.employee", string="Nhân viên", required=True, ondelete="cascade")

    name = fields.Char(string="Tên khóa đào tạo", required=True)

    training_type = fields.Selection([
        ('planned', 'Chưa bắt đầu'),
        ('short_term', 'Ngắn hạn'),
        ('long_term', 'Dài hạn')
    ], string="Loại hình", default='short_term')

    facility = fields.Char(string="Cơ sở đào tạo")
    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")

    # Map với training_type của Plan Detail
    training_form = fields.Selection([
        ('direct', 'Trực tiếp'),
        ('indirect', 'Gián tiếp'),
        ('offline', 'Trực tiếp (Cũ)'),
        ('online', 'Online (Cũ)')
    ], string="Hình thức đào tạo", default='direct')

    status = fields.Selection([
        ('completed', 'Hoàn thành'),
        ('in_progress', 'Đang học'),
        ('canceled', 'Hủy')
    ], string="Trạng thái", default='in_progress')

    # Link ngược về dòng chi tiết tham gia để đồng bộ
    source_detail_id = fields.Many2one(
        'training.plan.participation.detail',
        string="Nguồn dữ liệu",
        readonly=True,
        ondelete='cascade'
    )

    @api.depends('employee_id.tedi_training_history_ids')
    def _compute_stt(self):
        for employee in self.mapped('employee_id'):
            for idx, line in enumerate(employee.tedi_training_history_ids):
                line.stt = idx + 1