from odoo import models, fields, api, _

from odoo.exceptions import UserError

class AttendanceReport(models.Model):
    _name = 'hr.attendance.report'
    _description = 'Attendance Report'

    name = fields.Char(string='Tiêu đề', required=True)
    date_offer = fields.Date (string ="Ngày đề nghị", required=True)
