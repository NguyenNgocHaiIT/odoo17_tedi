# -*- coding:utf-8 -*-

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    _description = 'Employee'

    slip_ids = fields.One2many('hr.payslip', 'employee_id', string='Payslips', readonly=True)
    payslip_count = fields.Integer(compute='_compute_payslip_count', string='Payslip Count',
                                   groups="om_om_hr_payroll.group_hr_payroll_user")

    def _compute_payslip_count(self):
        for employee in self:
            employee.payslip_count = len(employee.slip_ids)


    # kpi_manager_review = fields.Boolean(string="Yêu cầu QLTT đánh giá?", default=True)
    # kpi_council_review = fields.Boolean(string="Yêu cầu TĐV đánh giá?", default=True)
    # kpi_director_review = fields.Boolean(string="Yêu cầu TGĐ đánh giá?", default=True)