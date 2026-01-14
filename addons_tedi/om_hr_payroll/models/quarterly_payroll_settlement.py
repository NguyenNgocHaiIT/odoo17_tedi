from odoo import models, api, fields
from datetime import date
import calendar


def get_quarter_date_range(year: int, quarter: int):
    """
    Trả về (date_from, date_to) của quý
    """
    if quarter not in (1, 2, 3, 4):
        raise ValueError("Quarter must be between 1 and 4")

    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2

    date_from = date(year, start_month, 1)
    last_day = calendar.monthrange(year, end_month)[1]
    date_to = date(year, end_month, last_day)

    return date_from, date_to


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

    @api.depends(
        'employee_id',
        'quarterly_payroll_settlement_id.year',
        'quarterly_payroll_settlement_id.quarter'
    )
    def get_info_by_employee(self):
        for record in self:
            record.lv_tt = 0
            record.le_tet = 0
            record.phep = 0
            record.tong_cong = 0
            record.hs_lcd_pc = 0
            record.lv_tt_quy = 0
            record.che_do_quy = 0
            record.tns_quy = 0
            if record.employee_id:
                settlement = record.quarterly_payroll_settlement_id
                date_from, date_to = get_quarter_date_range(settlement.year, int(settlement.quarter))

                def count_months(date_from: date, date_to: date) -> int:
                    if date_from > date_to:
                        return 0
                    return (date_to.year - date_from.year) * 12 + (date_to.month - date_from.month) + 1
                payslip_ids = self.env['hr.payslip'].sudo().search([('employee_id', '=', record.employee_id.id),
                                                                    ('state', '=', 'done'),
                                                                    ('struct_id.pay_batch', '=', '2'),
                                                                    ('date_from', '>=', date_from),
                                                                    ('date_to', '<=', date_to),])
                if payslip_ids:
                    dv_dk = payslip_ids.worked_days_line_ids.filtered(lambda w: w.code == 'WORK100')
                    lv_tt = payslip_ids.worked_days_line_ids.filtered(lambda w: w.code == 'WORK_REAL')
                    record.lv_tt = sum(lv_tt.mapped('number_of_days'))
                    le_tet = payslip_ids.worked_days_line_ids.filtered(lambda w: w.code == 'LEAVE100')
                    record.le_tet = sum(le_tet.mapped('number_of_days'))
                    phep = payslip_ids.worked_days_line_ids.filtered(lambda w: w.code == 'LEAVE120')
                    record.phep = sum(phep.mapped('number_of_days'))
                    record.tong_cong = record.lv_tt + record.le_tet + record.phep
                    contract_id = record.employee_id.contract_id
                    record.hs_lcd_pc = contract_id.salary_grade_id.salary_coefficient
                    # record.lv_tt_quy = ((contract_id.salary_grade_id.luong_chuc_danh * count_months(date_from, date_to))/sum(dv_dk.mapped('number_of_days'))) * record.lv_tt
                    # record.lv_tt_quy = ((contract_id.salary_grade_id.luong_chuc_danh * len(payslip_ids))/sum(dv_dk.mapped('number_of_days'))) * record.lv_tt
                    lv_tt_quy = payslip_ids.line_ids.filtered(lambda l: l.code == 'WORK_ATT')
                    record.lv_tt_quy = sum(lv_tt_quy.mapped('total'))
                    # record.che_do_quy = ((contract_id.salary_grade_id.luong_chuc_danh * len(payslip_ids))/sum(dv_dk.mapped('number_of_days'))) * (record.le_tet + record.phep)
                    che_do_quy = payslip_ids.line_ids.filtered(lambda l: l.code == 'LCĐ')
                    record.che_do_quy = sum(che_do_quy.mapped('total'))
                    tns_quy = payslip_ids.line_ids.filtered(lambda l: l.code == 'TNS')
                    record.tns_quy = sum(tns_quy.mapped('total'))

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
