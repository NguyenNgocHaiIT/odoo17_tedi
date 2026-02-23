from odoo import models, api, fields
from datetime import date
import calendar


def get_quarter_date_range(year: int, quarter: int):
    if quarter not in (1, 2, 3, 4):
        raise ValueError("Quarter must be between 1 and 4")

    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2

    date_from = date(year, start_month, 1)
    last_day = calendar.monthrange(year, end_month)[1]
    date_to = date(year, end_month, last_day)
    return date_from, date_to


class EmployeeTax(models.Model):
    _name = 'employee.tax'
    _description = 'Khấu trừ thuế theo nhân viên'

    employee_id = fields.Many2one('hr.employee', 'Họ và tên')
    month = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'), ('4', 'Tháng 4'),
        ('5', 'Tháng 5'), ('6', 'Tháng 6'), ('7', 'Tháng 7'), ('8', 'Tháng 8'),
        ('9', 'Tháng 9'), ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12'),
    ], string='Tháng', default=lambda self: str(date.today().month))
    year = fields.Integer(string='Năm', default=lambda self: date.today().year)
    nguoi_pt = fields.Integer(string='Người PT')
    currency_id = fields.Many2one(comodel_name='res.currency', default=lambda self: self.env.company.currency_id)
    tl_truoc_thue = fields.Monetary('TL trước thuế', currency_field='currency_id')
    giam_tru_ban_than = fields.Monetary('Giảm trừ bản thân', currency_field='currency_id')
    giam_tru_gia_canh = fields.Monetary('Giảm trừ gia cảnh', currency_field='currency_id')
    thu_nhap_tinh_thue = fields.Monetary('Thu nhập tính thuế', currency_field='currency_id')
    thue_tncn = fields.Monetary('Thuế TNCN', currency_field='currency_id')
    deducted = fields.Boolean('Đã KT')
    quarterly_settlement_id = fields.Many2one(
        'quarterly.payroll.settlement',
        string='Quyết toán quý'
    )


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
    kt_thue_ky_truoc = fields.Float('KT thuế kỳ trước')
    kt_thue_ky_nay = fields.Float('KT thuế kỳ này')
    nld_con_nhan = fields.Float('NLĐ còn được lĩnh')


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
        string='Trạng thái', default='draft')

    # def _compute_line_for_employee(self, line):
    #     self.ensure_one()
    #
    #     # reset
    #     fields_reset = [
    #         'lv_tt', 'le_tet', 'phep', 'tong_cong', 'hs_lcd_pc',
    #         'lv_tt_quy', 'che_do_quy', 'tns_quy', 'kpi', 'thuong',
    #         'cong_1', 'tns_nhan', 'lcd_tns_quy',
    #         'nlv_tt_nhan', 'lcd_nhan', 'tam_ung_tns',
    #         'cong_2', 'tns_con_nhan', 'nld_con_nhan'
    #     ]
    #     for f in fields_reset:
    #         line[f] = 0
    #
    #     if not line.employee_id:
    #         return
    #
    #     date_from, date_to = get_quarter_date_range(self.year, int(self.quarter))
    #
    #     payslips = self.env['hr.payslip'].sudo().search([
    #         ('employee_id', '=', line.employee_id.id),
    #         ('state', '=', 'done'),
    #         ('struct_id.pay_batch', '=', '2'),
    #         ('date_from', '>=', date_from),
    #         ('date_to', '<=', date_to),
    #     ])
    #
    #     if not payslips:
    #         return
    #     worked_days = payslips.worked_days_line_ids
    #
    #     lv_tt = worked_days.filtered(lambda w: w.code == 'WORK_REAL')
    #     le_tet = worked_days.filtered(lambda w: w.code == 'LEAVE100')
    #     phep = worked_days.filtered(lambda w: w.code == 'LEAVE120')
    #     dv_dk = worked_days.filtered(lambda w: w.code == 'WORK100')
    #
    #     line.lv_tt = sum(lv_tt.mapped('number_of_days'))
    #     line.le_tet = sum(le_tet.mapped('number_of_days'))
    #     line.phep = sum(phep.mapped('number_of_days'))
    #     line.tong_cong = line.lv_tt + line.le_tet + line.phep
    #
    #     contract = line.employee_id.contract_id
    #     line.hs_lcd_pc = contract.salary_grade_id.salary_coefficient
    #
    #     so_thang = len(payslips)
    #     so_cong_dk = sum(dv_dk.mapped('number_of_days')) or 1
    #
    #     luong_cd = contract.salary_grade_id.luong_chuc_danh
    #
    #     line.lv_tt_quy = (luong_cd * so_thang / so_cong_dk) * line.lv_tt
    #     line.che_do_quy = (luong_cd * so_thang / so_cong_dk) * (line.le_tet + line.phep)
    #     code = contract.salary_grade_id.code or ''
    #
    #     if 'C' in code:
    #         line.tns_quy = contract.salary_grade_id.advance_amount - luong_cd
    #     elif 'B' in code:
    #         line.tns_quy = luong_cd * contract.salary_grade_id.bonus_rate / 100
    #     else:
    #         line.tns_quy = 0
    #     kpi = self.env['evaluation.kpi'].sudo().search([
    #         ('employee_id', '=', line.employee_id.id),
    #         ('evaluate_kpi_id.quarter', '=', self.quarter),
    #         ('evaluate_kpi_id.year', '=', self.year),
    #     ], limit=1)
    #
    #     line.kpi = kpi.k_coefficient or 0
    #     line.thuong = line.lv_tt * line.hs_lcd_pc * line.kpi
    #     line.cong_1 = line.lv_tt_quy + line.che_do_quy + line.tns_quy
    #
    #     tong_thuong = sum(self.line_ids.mapped('thuong')) or 1
    #     line.tns_nhan = (self.quarterly_payroll_fund / tong_thuong) * line.thuong
    #
    #     line.lcd_tns_quy = line.lv_tt_quy + line.che_do_quy + line.tns_nhan
    #     slip_lines = payslips.line_ids
    #
    #     line.nlv_tt_nhan = sum(slip_lines.filtered(lambda l: l.code == 'WORK_ATT').mapped('total'))
    #     line.lcd_nhan = sum(slip_lines.filtered(lambda l: l.code == 'LCĐ').mapped('total'))
    #     line.tam_ung_tns = sum(slip_lines.filtered(lambda l: l.code == 'TNS').mapped('total'))
    #
    #     line.cong_2 = line.nlv_tt_nhan + line.lcd_nhan + line.tam_ung_tns
    #     line.tns_con_nhan = line.lcd_tns_quy - line.cong_2
    #     line.nld_con_nhan = line.tns_con_nhan - line.kt_thue_2024 - line.kt_thue_2025
    #
    # def action_compute_lines(self):
    #     for settlement in self:
    #         for line in settlement.line_ids:
    #             settlement._compute_line_for_employee(line)

    def _month_index(self, year, month):
        return year * 12 + int(month)

    def action_compute_lines(self):
        for settlement in self:
            settlement._compute_lines_fast()

    def _compute_lines_fast(self):
        self.ensure_one()

        lines = self.line_ids.filtered(lambda l: l.employee_id)
        if not lines:
            return

        emp_ids = lines.mapped('employee_id').ids

        # index quý hiện tại
        current_q_end = self._month_index(
            self.year,
            (int(self.quarter) - 1) * 3 + 3
        )

        # ------------------------------------------------
        # PAYSLIP
        # ------------------------------------------------
        date_from, date_to = get_quarter_date_range(self.year, int(self.quarter))

        payslips = self.env['hr.payslip'].sudo().search([
            ('employee_id', 'in', emp_ids),
            ('state', '=', 'done'),
            ('struct_id.pay_batch', '=', '2'),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
        ])

        worked_days_map = {}
        slip_line_map = {}
        payslip_by_emp = {}

        for slip in payslips:
            eid = slip.employee_id.id
            payslip_by_emp.setdefault(eid, self.env['hr.payslip'])
            payslip_by_emp[eid] |= slip

            for wd in slip.worked_days_line_ids:
                worked_days_map[(eid, wd.code)] = worked_days_map.get((eid, wd.code), 0) + wd.number_of_days

            for sl in slip.line_ids:
                slip_line_map[(eid, sl.code)] = slip_line_map.get((eid, sl.code), 0) + sl.total

        # ------------------------------------------------
        # KPI
        # ------------------------------------------------
        kpis = self.env['evaluation.kpi'].sudo().search([
            ('employee_id', 'in', emp_ids),
            ('evaluate_kpi_id.quarter', '=', self.quarter),
            ('evaluate_kpi_id.year', '=', self.year)
        ])
        kpi_map = {k.employee_id.id: k.k_coefficient for k in kpis}

        # ------------------------------------------------
        # EMPLOYEE TAX (ALL PAST)
        # ------------------------------------------------
        tax_lines = self.env['employee.tax'].sudo().search([
            ('employee_id', 'in', emp_ids),
            ('deducted', '=', False),
        ])

        tax_prev = {}
        tax_curr = {}

        for t in tax_lines:
            eid = t.employee_id.id
            idx = self._month_index(t.year, t.month)

            if idx <= current_q_end:
                if t.year == self.year and int(t.month) >= (int(self.quarter) - 1) * 3 + 1:
                    tax_curr[eid] = tax_curr.get(eid, 0) + t.thue_tncn
                else:
                    tax_prev[eid] = tax_prev.get(eid, 0) + t.thue_tncn

        # ------------------------------------------------
        # TÍNH THƯỞNG
        # ------------------------------------------------
        thuong_map = {}
        tong_thuong = 0

        for line in lines:
            eid = line.employee_id.id
            contract = line.employee_id.contract_id
            grade = contract.salary_grade_id

            lv_tt = worked_days_map.get((eid, 'WORK_REAL'), 0)
            le_tet = worked_days_map.get((eid, 'LEAVE100'), 0)
            phep = worked_days_map.get((eid, 'LEAVE120'), 0)
            dv_dk = worked_days_map.get((eid, 'WORK100'), 0) or 1

            line.lv_tt = lv_tt
            line.le_tet = le_tet
            line.phep = phep
            line.tong_cong = lv_tt + le_tet + phep

            line.hs_lcd_pc = grade.salary_coefficient or 0

            so_thang = len(payslip_by_emp.get(eid, []))
            luong_cd = grade.luong_chuc_danh or 0

            line.lv_tt_quy = (luong_cd * so_thang / dv_dk) * lv_tt
            line.che_do_quy = (luong_cd * so_thang / dv_dk) * (le_tet + phep)

            line.kpi = kpi_map.get(eid, 0)
            line.thuong = lv_tt * line.hs_lcd_pc * line.kpi

            thuong_map[eid] = line.thuong
            tong_thuong += line.thuong

        tong_thuong = tong_thuong or 1

        # ------------------------------------------------
        # FINAL
        # ------------------------------------------------
        for line in lines:
            eid = line.employee_id.id

            line.tns_nhan = (self.quarterly_payroll_fund / tong_thuong) * thuong_map.get(eid, 0)
            line.lcd_tns_quy = line.lv_tt_quy + line.che_do_quy + line.tns_nhan

            line.nlv_tt_nhan = slip_line_map.get((eid, 'WORK_ATT'), 0)
            line.lcd_nhan = slip_line_map.get((eid, 'LCĐ'), 0)
            line.tam_ung_tns = slip_line_map.get((eid, 'TNS'), 0)

            line.cong_2 = line.nlv_tt_nhan + line.lcd_nhan + line.tam_ung_tns
            line.tns_con_nhan = line.lcd_tns_quy - line.cong_2

            line.kt_thue_ky_truoc = tax_prev.get(eid, 0)
            line.kt_thue_ky_nay = tax_curr.get(eid, 0)

            line.nld_con_nhan = line.tns_con_nhan - line.kt_thue_ky_truoc - line.kt_thue_ky_nay

    # def _compute_lines_fast(self):
    #     self.ensure_one()
    #
    #     lines = self.line_ids.filtered(lambda l: l.employee_id)
    #     if not lines:
    #         return
    #
    #     employees = lines.mapped('employee_id')
    #     emp_ids = employees.ids
    #
    #     date_from, date_to = get_quarter_date_range(self.year, int(self.quarter))
    #
    #     # ------------------------------------------------
    #     # 1. PAYSLIP (1 QUERY)
    #     # ------------------------------------------------
    #     payslips = self.env['hr.payslip'].sudo().search([
    #         ('employee_id', 'in', emp_ids),
    #         ('state', '=', 'done'),
    #         ('struct_id.pay_batch', '=', '2'),
    #         ('date_from', '>=', date_from),
    #         ('date_to', '<=', date_to),
    #     ])
    #
    #     payslip_by_emp = {}
    #     worked_days_map = {}
    #     slip_line_map = {}
    #
    #     for slip in payslips:
    #         eid = slip.employee_id.id
    #         payslip_by_emp.setdefault(eid, self.env['hr.payslip'])
    #         payslip_by_emp[eid] |= slip
    #
    #         for wd in slip.worked_days_line_ids:
    #             key = (eid, wd.code)
    #             worked_days_map[key] = worked_days_map.get(key, 0) + wd.number_of_days
    #
    #         for line in slip.line_ids:
    #             key = (eid, line.code)
    #             slip_line_map[key] = slip_line_map.get(key, 0) + line.total
    #
    #     # ------------------------------------------------
    #     # 2. KPI (1 QUERY)
    #     # ------------------------------------------------
    #     kpis = self.env['evaluation.kpi'].sudo().search([
    #         ('employee_id', 'in', emp_ids),
    #         ('evaluate_kpi_id.quarter', '=', self.quarter),
    #         ('evaluate_kpi_id.year', '=', self.year)
    #     ])
    #     kpi_map = {k.employee_id.id: k.k_coefficient for k in kpis}
    #
    #     # ------------------------------------------------
    #     # 3. TÍNH THƯỞNG & TỔNG THƯỞNG
    #     # ------------------------------------------------
    #     thuong_map = {}
    #     tong_thuong = 0
    #
    #     for line in lines:
    #         eid = line.employee_id.id
    #         contract = line.employee_id.contract_id
    #         grade = contract.salary_grade_id
    #
    #         lv_tt = worked_days_map.get((eid, 'WORK_REAL'), 0)
    #         le_tet = worked_days_map.get((eid, 'LEAVE100'), 0)
    #         phep = worked_days_map.get((eid, 'LEAVE120'), 0)
    #         dv_dk = worked_days_map.get((eid, 'WORK100'), 0) or 1
    #
    #         line.lv_tt = lv_tt
    #         line.le_tet = le_tet
    #         line.phep = phep
    #         line.tong_cong = lv_tt + le_tet + phep
    #
    #         line.hs_lcd_pc = grade.salary_coefficient or 0
    #
    #         so_thang = len(payslip_by_emp.get(eid, []))
    #         luong_cd = grade.luong_chuc_danh or 0
    #
    #         line.lv_tt_quy = (luong_cd * so_thang / dv_dk) * lv_tt
    #         line.che_do_quy = (luong_cd * so_thang / dv_dk) * (le_tet + phep)
    #
    #         code = grade.code or ''
    #         if 'C' in code:
    #             line.tns_quy = (grade.advance_amount or 0) - luong_cd
    #         elif 'B' in code:
    #             line.tns_quy = luong_cd * (grade.bonus_rate or 0) / 100
    #         else:
    #             line.tns_quy = 0
    #
    #         line.kpi = kpi_map.get(eid, 0)
    #         line.thuong = lv_tt * line.hs_lcd_pc * line.kpi
    #         line.cong_1 = line.lv_tt_quy + line.che_do_quy + line.tns_quy
    #
    #         thuong_map[eid] = line.thuong
    #         tong_thuong += line.thuong
    #
    #     tong_thuong = tong_thuong or 1
    #
    #     # ------------------------------------------------
    #     # 4. CHIA QUỸ + QUYẾT TOÁN
    #     # ------------------------------------------------
    #     for line in lines:
    #         eid = line.employee_id.id
    #
    #         line.tns_nhan = (self.quarterly_payroll_fund / tong_thuong) * thuong_map.get(eid, 0)
    #         line.lcd_tns_quy = line.lv_tt_quy + line.che_do_quy + line.tns_nhan
    #
    #         line.nlv_tt_nhan = slip_line_map.get((eid, 'WORK_ATT'), 0)
    #         line.lcd_nhan = slip_line_map.get((eid, 'LCĐ'), 0)
    #         line.tam_ung_tns = slip_line_map.get((eid, 'TNS'), 0)
    #
    #         line.cong_2 = line.nlv_tt_nhan + line.lcd_nhan + line.tam_ung_tns
    #         line.tns_con_nhan = line.lcd_tns_quy - line.cong_2
    #         line.nld_con_nhan = line.tns_con_nhan - line.kt_thue_2024 - line.kt_thue_2025

    def action_add_employee(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Thêm nhân sự',
            'res_model': 'hr.settlement.employees',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_quarter_settlement_id': self.id
            },
        }

    # def action_approve(self):
    #     if self.state == 'draft':
    #         self.state = 'approve'

    def action_approve(self):
        for rec in self:
            if rec.state == 'draft':
                emp_ids = rec.line_ids.mapped('employee_id').ids
                current_q_end = rec._month_index(rec.year, (int(rec.quarter) - 1) * 3 + 3)

                taxes = self.env['employee.tax'].sudo().search([
                    ('employee_id', 'in', emp_ids),
                    ('deducted', '=', False),
                ])

                mark = taxes.filtered(
                    lambda t: rec._month_index(t.year, t.month) <= current_q_end
                )

                mark.write({
                    'deducted': True,
                    'quarterly_settlement_id': rec.id
                })

                rec.state = 'approve'

    def action_draft(self):
        for rec in self:
            taxes = self.env['employee.tax'].sudo().search([
                ('quarterly_settlement_id', '=', rec.id)
            ])

            taxes.write({
                'deducted': False,
                'quarterly_settlement_id': False
            })

            rec.state = 'draft'


