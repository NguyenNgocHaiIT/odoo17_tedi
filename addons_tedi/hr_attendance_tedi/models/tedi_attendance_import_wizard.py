# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
from openpyxl import load_workbook
from datetime import datetime
from io import BytesIO
import pytz


class TediAttendanceImportWizard(models.TransientModel):
    _name = 'tedi.attendance.import.wizard'
    _description = 'Import Excel Chấm công'

    file = fields.Binary(string="Tệp Excel", required=True)
    filename = fields.Char(string="Tên file")
    # Thêm lựa chọn múi giờ để quy đổi giờ trong Excel sang UTC
    timezone = fields.Selection(
        '_get_timezones',
        string="Múi giờ trong Excel",
        default="Asia/Ho_Chi_Minh",
        required=True
    )

    @api.model
    def _get_timezones(self):
        return [(tz, tz) for tz in pytz.all_timezones]

    def convert_to_utc(self, dt_value, tz_name):
        """Chuyển đổi datetime từ Excel (Local) sang UTC (Odoo DB)"""
        if not dt_value:
            return False

        # Nếu Excel trả về string, parse nó
        if isinstance(dt_value, str):
            try:
                dt_value = datetime.strptime(dt_value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    dt_value = datetime.strptime(dt_value, "%Y-%m-%d %H:%M")
                except ValueError:
                    return False

        if isinstance(dt_value, datetime):
            local_tz = pytz.timezone(tz_name)
            # Gán múi giờ local cho biến datetime
            local_dt = local_tz.localize(dt_value, is_dst=None)
            # Chuyển sang UTC và bỏ thông tin tzinfo để lưu vào Odoo
            return local_dt.astimezone(pytz.utc).replace(tzinfo=None)

        return False

    def action_import(self):
        if not self.file:
            raise UserError(_("Vui lòng chọn file Excel!"))

        try:
            data = base64.b64decode(self.file)
            wb = load_workbook(filename=BytesIO(data), read_only=True, data_only=True)
            sheet = wb.active
        except Exception as e:
            raise UserError(_("Không thể đọc file. Vui lòng kiểm tra định dạng .xlsx. Chi tiết: %s") % str(e))

        Attendance = self.env['hr.attendance']  # Sửa thành model chuẩn
        Employee = self.env['hr.employee']

        success_count = 0
        errors = []
        row_index = 1  # Bắt đầu từ 1 để dễ debug

        # Giả sử cấu trúc file Excel:
        # Cột A: Mã NV
        # Cột B: Check In (yyyy-mm-dd HH:MM)
        # Cột C: Check Out (yyyy-mm-dd HH:MM)

        for row in sheet.iter_rows(min_row=2, values_only=True):
            row_index += 1
            # Lấy dữ liệu 3 cột đầu tiên, bỏ qua các cột sau nếu có
            if not row or row[0] is None:
                continue

            employee_code = str(row[0]).strip()
            raw_check_in = row[1]
            raw_check_out = row[2]

            # 1. Tìm nhân viên
            employee = Employee.search([('employee_code', '=', employee_code)], limit=1)
            if not employee:
                errors.append(f"Dòng {row_index}: Không tìm thấy nhân viên mã '{employee_code}'")
                continue

            # 2. Xử lý thời gian (Quan trọng)
            try:
                check_in_utc = self.convert_to_utc(raw_check_in, self.timezone)
                check_out_utc = self.convert_to_utc(raw_check_out, self.timezone)

                if not check_in_utc:
                    errors.append(f"Dòng {row_index}: Thiếu hoặc sai định dạng giờ vào (Check In)")
                    continue

            except Exception as e:
                errors.append(f"Dòng {row_index}: Lỗi xử lý ngày tháng - {str(e)}")
                continue

            # 3. Tạo dữ liệu
            # Không cần truyền status hay attendance_date, Odoo sẽ tự compute
            vals = {
                'employee_id': employee.id,
                'check_in': check_in_utc,
                'check_out': check_out_utc,
            }

            try:
                # Kiểm tra trùng lặp cơ bản (Optional)
                # Odoo gốc đã có constraints _check_validity nhưng check thủ công để báo lỗi rõ hơn
                domain = [
                    ('employee_id', '=', employee.id),
                    ('check_in', '=', check_in_utc)
                ]
                if Attendance.search_count(domain) > 0:
                    errors.append(
                        f"Dòng {row_index}: Dữ liệu đã tồn tại (Mã NV: {employee_code}, Giờ vào: {raw_check_in})")
                    continue

                Attendance.create(vals)
                success_count += 1

            except ValidationError as ve:
                errors.append(f"Dòng {row_index}: {str(ve)}")
            except Exception as e:
                errors.append(f"Dòng {row_index}: Lỗi hệ thống - {str(e)}")

        # Kết quả
        msg = f"Hoàn tất! Đã import thành công {success_count} dòng."
        if errors:
            msg += f"\n\nCó {len(errors)} dòng lỗi:\n" + "\n".join(errors[:20])  # Chỉ hiện 20 lỗi đầu tiên cho gọn
            if len(errors) > 20:
                msg += "\n... và các lỗi khác."

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cảnh báo Import',
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