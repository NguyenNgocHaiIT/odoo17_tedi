from odoo import models, api, fields
from datetime import date


class QuarterlyPayrollSettlementLine(models.Model):
    _name = "quarterly.payroll.settlement.line"
    _description = "Quyết toán lương quý (Chi tiết)"

    quarterly_payroll_settlement_id = fields.Many2one('quarterly.payroll.settlement')
    employee_id = fields.Many2one('hr.employee', 'Họ và tên')
    lv_tt = fields.Float('Làm việc TT', compute='get_info_by_employee', store=True)
    le_tet = fields.Float('Lễ tết', compute='get_info_by_employee', store=True)
    phep = fields.Float('Phép', compute='get_info_by_employee', store=True)
    tong_cong = fields.Float('Tổng công', compute='get_info_by_employee', store=True)
    hs_lcd_pc = fields.Float('Hs lcd + pc', compute='get_info_by_employee', store=True)
    lv_tt_quy = fields.Float('Lương theo ngày lv TT trong quý')
    che_do_quy = fields.Float('Lương chế độ trong quý')
    tns_quy = fields.Float('TNS trong quý')
    kpi = fields.Float('Hs KPI')
    thuong = fields.Float('Hs thưởng')
    cong_1 = fields.Float('Cộng')
    tns_nhan = fields.Float('TNS được nhận')
    lcd_tns_quy = fields.Float('Tổng Lcd + TNS trong quý')
    nlv_tt_nhan = fields.Float('Lương nlv TT đã nhận')
    ncd_nhan = fields.Float('Lương ncđ đã nhận')
    tam_ung_tns = fields.Float('Tạm ứng TNS')
    cong_2 = fields.Float('Cộng')
    tns_con_nhan = fields.Float('TNS còn được nhận')
    kt_thue_2024 = fields.Float('KT thuế 2024')
    kt_thue_2025 = fields.Float('KT thuế 2025')
    nld_con_nhan = fields.Float('NLĐ còn được lĩnh')

    @api.depends('employee_id')
    def get_info_by_employee(self):
        for record in self:
            record.lv_tt = 0
            record.le_tet = 0
            record.phep = 0
            record.tong_cong = 0
            record.hs_lcd_pc = 0
            if record.employee_id:
                payslip_ids = self.env['hr.payslip'].sudo().search([('employee_id', '=', record.employee_id.id), ('state', '=', 'done'), ('struct_id.pay_batch', '=', '2')])
                if payslip_ids:
                    lv_tt = payslip_ids.worked_days_line_ids.filtered(lambda w: w.code == 'WORK_REAL')
                    record.lv_tt = sum(lv_tt.mapped('number_of_days'))
                    record.le_tet = sum(lv_tt.mapped('number_of_days'))
                    record.tong_cong = sum(lv_tt.mapped('number_of_days'))
                    record.phep = sum(lv_tt.mapped('number_of_days'))
                    record.hs_lcd_pc = sum(lv_tt.mapped('number_of_days'))


class QuarterlyPayrollSettlement(models.Model):
    _name = "quarterly.payroll.settlement"
    _description = "Quyết toán lương quý"

    name = fields.Char('Mô tả')
    quarter = fields.Selection(
        [
            ('1', 'Quý 1'),
            ('2', 'Quý 2'),
            ('3', 'Quý 3'),
            ('4', 'Quý 4'),
        ],
        string='Mời chọn quý trong năm',
        default=lambda self: str((fields.Date.today().month - 1) // 3 + 1),
    )
    year = fields.Integer(
        string='Năm',
        default=lambda self: date.today().year,
    )
    quarterly_payroll_fund = fields.Monetary('Quỹ lương', currency_field='currency_id')
    currency_id = fields.Many2one(comodel_name='res.currency', default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many('quarterly.payroll.settlement.line', 'quarterly_payroll_settlement_id', 'Chi tiết')
    state = fields.Selection(
        [
            ('draft', 'NHÁP'),
            ('approve', 'ĐÃ DUYỆT')
        ],
        string='Trạng thái', default='draft'
    )
