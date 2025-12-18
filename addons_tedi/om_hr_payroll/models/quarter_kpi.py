from odoo import models, fields, api


class QuarterKpiLine(models.Model):
    _name = 'quarter.kpi.line'
    _description = 'Chi tiết bảng KPI quý'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên')
    kpi = fields.Float('Hệ số K')
    rate = fields.Selection([()], string='Xếp loại hoàn thành')
    note = fields.Text('Ghi chú')
    quarter_kpi_id = fields


class QuarterKpi(models.Model):
    _name = 'quarter.kpi'
    _description = "KPI quý"

    name = fields.Char('Tên')
    quarter = fields.Selection([('1', 'Quý 1'),
                                ('2', 'Quý 2'),
                                ('3', 'Quý 3'),
                                ('4', 'Quý 4')], string='Chọn chu kỳ tính KPI')
    year = fields.Integer(
        string='Năm',
        required=True,
        default=lambda self: fields.Date.today().year
    )
    state = fields.Selection([('1', 'Đang xử lý'),
                              ('2', 'Chờ phê duyệt'),
                              ('3', 'Đã phê duyệt')], string='Trạng thái', default='1')
    line_ids = fields.One2many('quarter.kpi.line', '')