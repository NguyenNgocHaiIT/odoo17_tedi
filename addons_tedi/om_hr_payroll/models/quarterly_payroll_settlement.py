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
    lv_tt = fields.Float('Làm việc TT')
    le_tet = fields.Float('Lễ tết')
    phep = fields.Float('Phép')
    tong_cong = fields.Float('Tổng công')
    hs_lcd_pc = fields.Float('Hs lcd + pc')
    lv_tt_quy = fields.Float('Lương theo ngày lv TT trong quý')
    che_do_quy = fields.Float('Lương chế độ trong quý')
    tns_quy = fields.Float('TNS trong quý')
    kpi = fields.Float('Hs KPI')
    thuong = fields.Float('Hs thưởng')
    cong_1 = fields.Float('Cộng')
    tns_nhan = fields.Float('TNS được nhận')
    lcd_tns_quy = fields.Float('Tổng Lcđ + TNS trong quý')
    nlv_tt_nhan = fields.Float('Lương nlv TT đã nhận')
    lcd_nhan = fields.Float('Lương cđ đã nhận')
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
            record.kpi = 0
            record.cong_1 = 0
            record.thuong = 0
            record.tns_nhan = 0
            record.lcd_tns_quy = 0
            record.nlv_tt_nhan = 0
            record.lcd_nhan = 0
            record.tam_ung_tns = 0
            record.cong_2 = 0
            record.tns_con_nhan = 0
            record.nld_con_nhan = 0
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
                    record.lv_tt_quy = ((contract_id.salary_grade_id.luong_chuc_danh * len(payslip_ids))/sum(dv_dk.mapped('number_of_days'))) * record.lv_tt
                    record.che_do_quy = ((contract_id.salary_grade_id.luong_chuc_danh * len(payslip_ids))/sum(dv_dk.mapped('number_of_days'))) * (record.le_tet + record.phep)
                    if 'C' in (contract_id.salary_grade_id.code or ''):
                        record.tns_quy = contract_id.salary_grade_id.advance_amount - contract_id.salary_grade_id.luong_chuc_danh
                    elif 'B' in (contract_id.salary_grade_id.code or ''):
                        record.tns_quy = contract_id.salary_grade_id.luong_chuc_danh * contract_id.salary_grade_id.bonus_rate / 100
                    else:
                        record.tns_quy = 0
                    kpi = self.env['evaluation.kpi'].sudo().search([('employee_id', '=', record.employee_id.id),
                                                                    ('evaluate_kpi_id.quarter', '=', record.quarterly_payroll_settlement_id.quarter),
                                                                    ('evaluate_kpi_id.year', '=', record.quarterly_payroll_settlement_id.year)], limit=1)
                    record.kpi = kpi.k_coefficient
                    record.thuong = record.lv_tt * record.hs_lcd_pc * record.kpi
                    record.cong_1 = record.lv_tt_quy + record.che_do_quy + record.tns_quy
                    record.tns_nhan = (record.quarterly_payroll_settlement_id.quarterly_payroll_fund / sum(record.quarterly_payroll_settlement_id.line_ids.mapped('thuong'))) * record.thuong
                    record.lcd_tns_quy = record.lv_tt_quy + record.che_do_quy + record.tns_nhan
                    nlv_tt_nhan = payslip_ids.line_ids.filtered(lambda l: l.code == 'WORK_ATT')
                    record.nlv_tt_nhan = sum(nlv_tt_nhan.mapped('total'))
                    lcd_nhan = payslip_ids.line_ids.filtered(lambda l: l.code == 'LCĐ')
                    record.lcd_nhan = sum(lcd_nhan.mapped('total'))
                    tam_ung_tns = payslip_ids.line_ids.filtered(lambda l: l.code == 'TNS')
                    record.tam_ung_tns = sum(tam_ung_tns.mapped('total'))
                    record.cong_2 = record.nlv_tt_nhan + record.lcd_nhan + record.tam_ung_tns
                    record.tns_con_nhan = record.lcd_tns_quy - record.cong_2
                    record.nld_con_nhan = record.tns_con_nhan - record.kt_thue_2024 - record.kt_thue_2025


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

    def _compute_line_for_employee(self, line):
        self.ensure_one()

        # reset
        fields_reset = [
            'lv_tt', 'le_tet', 'phep', 'tong_cong', 'hs_lcd_pc',
            'lv_tt_quy', 'che_do_quy', 'tns_quy', 'kpi', 'thuong',
            'cong_1', 'tns_nhan', 'lcd_tns_quy',
            'nlv_tt_nhan', 'lcd_nhan', 'tam_ung_tns',
            'cong_2', 'tns_con_nhan', 'nld_con_nhan'
        ]
        for f in fields_reset:
            line[f] = 0

        if not line.employee_id:
            return

        date_from, date_to = get_quarter_date_range(self.year, int(self.quarter))

        payslips = self.env['hr.payslip'].sudo().search([
            ('employee_id', '=', line.employee_id.id),
            ('state', '=', 'done'),
            ('struct_id.pay_batch', '=', '2'),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
        ])

        if not payslips:
            return
        worked_days = payslips.worked_days_line_ids

        lv_tt = worked_days.filtered(lambda w: w.code == 'WORK_REAL')
        le_tet = worked_days.filtered(lambda w: w.code == 'LEAVE100')
        phep = worked_days.filtered(lambda w: w.code == 'LEAVE120')
        dv_dk = worked_days.filtered(lambda w: w.code == 'WORK100')

        line.lv_tt = sum(lv_tt.mapped('number_of_days'))
        line.le_tet = sum(le_tet.mapped('number_of_days'))
        line.phep = sum(phep.mapped('number_of_days'))
        line.tong_cong = line.lv_tt + line.le_tet + line.phep

        contract = line.employee_id.contract_id
        line.hs_lcd_pc = contract.salary_grade_id.salary_coefficient

        so_thang = len(payslips)
        so_cong_dk = sum(dv_dk.mapped('number_of_days')) or 1

        luong_cd = contract.salary_grade_id.luong_chuc_danh

        line.lv_tt_quy = (luong_cd * so_thang / so_cong_dk) * line.lv_tt
        line.che_do_quy = (luong_cd * so_thang / so_cong_dk) * (line.le_tet + line.phep)
        code = contract.salary_grade_id.code or ''

        if 'C' in code:
            line.tns_quy = contract.salary_grade_id.advance_amount - luong_cd
        elif 'B' in code:
            line.tns_quy = luong_cd * contract.salary_grade_id.bonus_rate / 100
        else:
            line.tns_quy = 0
        kpi = self.env['evaluation.kpi'].sudo().search([
            ('employee_id', '=', line.employee_id.id),
            ('evaluate_kpi_id.quarter', '=', self.quarter),
            ('evaluate_kpi_id.year', '=', self.year),
        ], limit=1)

        line.kpi = kpi.k_coefficient or 0
        line.thuong = line.lv_tt * line.hs_lcd_pc * line.kpi
        line.cong_1 = line.lv_tt_quy + line.che_do_quy + line.tns_quy

        tong_thuong = sum(self.line_ids.mapped('thuong')) or 1
        line.tns_nhan = (self.quarterly_payroll_fund / tong_thuong) * line.thuong

        line.lcd_tns_quy = line.lv_tt_quy + line.che_do_quy + line.tns_nhan
        slip_lines = payslips.line_ids

        line.nlv_tt_nhan = sum(slip_lines.filtered(lambda l: l.code == 'WORK_ATT').mapped('total'))
        line.lcd_nhan = sum(slip_lines.filtered(lambda l: l.code == 'LCĐ').mapped('total'))
        line.tam_ung_tns = sum(slip_lines.filtered(lambda l: l.code == 'TNS').mapped('total'))

        line.cong_2 = line.nlv_tt_nhan + line.lcd_nhan + line.tam_ung_tns
        line.tns_con_nhan = line.lcd_tns_quy - line.cong_2
        line.nld_con_nhan = line.tns_con_nhan - line.kt_thue_2024 - line.kt_thue_2025

    def action_compute_lines(self):
        for settlement in self:
            for line in settlement.line_ids:
                settlement._compute_line_for_employee(line)

    def action_add_employee(self):
        print('say hi')

