# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
from openpyxl import load_workbook
from io import BytesIO


class TediAllowanceImportWizard(models.TransientModel):
    _name = 'tedi.allowance.import.wizard'
    _description = 'Import Phụ cấp từ Excel'

    file = fields.Binary(string="Tệp Excel", required=True)
    filename = fields.Char(string="Tên file")

    def action_import(self):
        if not self.file:
            raise UserError(_("Vui lòng chọn file Excel!"))

        try:
            data = base64.b64decode(self.file)
            wb = load_workbook(filename=BytesIO(data), read_only=True, data_only=True)
            sheet = wb.active
        except Exception as e:
            raise UserError(_("Không thể đọc file. Vui lòng kiểm tra định dạng .xlsx. Chi tiết: %s") % str(e))

        Allowance = self.env['hr.employee.allowance']
        Employee = self.env['hr.employee']

        success_count = 0
        errors = []
        row_index = 1  # Bắt đầu từ 1 (Header)

        # Cấu trúc file Excel yêu cầu:
        # Col 0: Month
        # Col 1: Year
        # Col 2: Type (VD: meal)
        # Col 3: Code (Mã phụ cấp)
        # Col 4: Employee Code
        # Col 5: Salary Allowance

        # Lấy danh sách các key hợp lệ của field type (VD: ['meal', ...])
        valid_types = [key for key, label in Allowance._fields['type'].selection]

        for row in sheet.iter_rows(min_row=2, values_only=True):
            row_index += 1

            # Kiểm tra dòng trống hoặc thiếu mã nhân viên (Cột 4 là index 4)
            if not row or len(row) < 5 or row[4] is None:
                continue

            try:
                # 1. Lấy dữ liệu thô
                raw_month = row[0]
                raw_year = row[1]
                raw_type = str(row[2]).strip() if row[2] else False
                raw_code = str(row[3]).strip() if row[3] else False
                employee_code = str(row[4]).strip()
                raw_salary = row[5]

                # 2. Xử lý Month/Year
                if not raw_month or not raw_year:
                    errors.append(f"Dòng {row_index}: Thiếu Tháng hoặc Năm")
                    continue

                try:
                    month_str = str(int(raw_month))
                    year_int = int(raw_year)
                except ValueError:
                    errors.append(f"Dòng {row_index}: Tháng/Năm phải là số")
                    continue

                if month_str not in [str(i) for i in range(1, 13)]:
                    errors.append(f"Dòng {row_index}: Tháng '{raw_month}' không hợp lệ")
                    continue

                # 3. Kiểm tra Loại phụ cấp (Type)
                if raw_type not in valid_types:
                    errors.append(
                        f"Dòng {row_index}: Loại phụ cấp '{raw_type}' không hợp lệ (Chấp nhận: {', '.join(valid_types)})")
                    continue

                # 4. Tìm nhân viên
                employee = Employee.search([('employee_code', '=', employee_code)], limit=1)
                if not employee:
                    errors.append(f"Dòng {row_index}: Không tìm thấy nhân viên mã '{employee_code}'")
                    continue

                # 5. Kiểm tra trùng lặp
                # Tiêu chí duy nhất: Nhân viên + Tháng + Năm + Loại + Mã
                domain = [
                    ('employee_id', '=', employee.id),
                    ('month', '=', month_str),
                    ('year', '=', year_int),
                    ('type', '=', raw_type),
                    ('code', '=', raw_code)
                    # Nếu code trong DB là False/Null thì cần xử lý thêm nếu Excel để trống, nhưng ở đây giả sử nhập khớp
                ]

                # Nếu code trống, tìm bản ghi có code=False
                if not raw_code:
                    domain[-1] = ('code', '=', False)

                existing_rec = Allowance.search(domain, limit=1)

                vals = {
                    'employee_id': employee.id,
                    'month': month_str,
                    'year': year_int,
                    'type': raw_type,
                    'code': raw_code,
                    'salary_allowance': float(raw_salary or 0),
                    'currency_id': self.env.company.currency_id.id
                }

                if existing_rec:
                    existing_rec.write(vals)
                else:
                    Allowance.create(vals)

                success_count += 1

            except Exception as e:
                errors.append(f"Dòng {row_index}: Lỗi xử lý - {str(e)}")

        # Kết quả trả về
        msg = f"Hoàn tất! Đã xử lý thành công {success_count} dòng."
        if errors:
            msg += f"\n\nCó {len(errors)} dòng lỗi:\n" + "\n".join(errors[:20])
            if len(errors) > 20:
                msg += "\n... và các lỗi khác."

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Kết quả Import Phụ cấp',
                    'message': msg,
                    'type': 'warning',
                    'sticky': True,
                }
            }

        return {
            'effect': {
                'fadeout': 'slow',
                'message': msg,
                'type': 'rainbow_man',
            }
        }