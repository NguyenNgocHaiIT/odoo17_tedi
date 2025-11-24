from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
from openpyxl import load_workbook
from datetime import datetime
from io import BytesIO


class TediAttendanceImportWizard(models.TransientModel):
    _name = 'tedi.attendance.import.wizard'
    _description = 'Import Excel Chấm công'

    file = fields.Binary(string="Tệp Excel", required=True)
    filename = fields.Char(string="Tên file")

    def parse_dt(self, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M")
            except:
                return None
        return None

    def action_import(self):
        if not self.file:
            raise UserError("Vui lòng chọn file Excel!")

        data = base64.b64decode(self.file)
        wb = load_workbook(filename=BytesIO(data), read_only=True)

        sheet = wb.active

        Attendance = self.env['tedi.attendance']
        Employee = self.env['hr.employee']

        imported = 0
        errors = []

        for row in sheet.iter_rows(min_row=2, values_only=True):

            try:
                (employee_code, check_in, check_out, date,
                 job_code, job_name, description,
                 duration, status) = row

                employee = Employee.search([('employee_code', '=', employee_code)], limit=1)
                if not employee:
                    errors.append(f"Không tìm thấy nhân viên mã: {employee_code}")
                    continue

                Attendance.create({
                    'employee_id': employee.id,
                    'employee_code': employee_code,
                    'department_id': employee.department_id.id,

                    'check_in': self.parse_dt(check_in),
                    'check_out': self.parse_dt(check_out),

                    # date trong Excel đang là datetime ⇒ lấy .date()
                    'date': date.date() if isinstance(date, datetime) else date,

                    'job_code': job_code or '',
                    'job_name': job_name or '',
                    'description': description or '',
                    'duration': duration or 0,
                    'status': status or 'ontime',
                })

                imported += 1

            except Exception as e:
                errors.append(str(e))

        msg = f"Đã import thành công {imported} dòng."
        if errors:
            msg += "\nLỗi:\n" + "\n".join(errors)

        return {
            'effect': {
                'fadeout': 'slow',
                'message': msg,
                'type': 'rainbow_man',
            }
        }
