# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrQuarterSettlementEmployees(models.TransientModel):
    _name = 'hr.settlement.employees'
    _description = 'Thêm nhân viên vào bảng quyết toán lương quý'

    employee_ids = fields.Many2many('hr.employee', 'hr_employee_quarter_settlement_rel', string='Employees')
    quarter_settlement_id = fields.Many2one('quarterly.payroll.settlement')

    def confirm(self):
        vals = [(5, 0, 0)]
        for e in self.employee_ids:
            vals.append((0, 0, {
                'employee_id': e.id
            }))
        self.quarter_settlement_id.line_ids = vals
        return {'type': 'ir.actions.act_window_close'}
