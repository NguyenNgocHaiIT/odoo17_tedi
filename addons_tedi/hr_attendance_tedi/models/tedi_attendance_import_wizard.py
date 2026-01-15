# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import io
import openpyxl
from datetime import datetime
import pytz
import logging
import calendar

_logger = logging.getLogger(__name__)


class TediAttendanceImportWizard(models.TransientModel):
    _name = 'tedi.attendance.import.wizard'
    _description = 'Import Chấm công & Nghỉ phép'

    file = fields.Binary(string='File Excel', required=True)
    filename = fields.Char(string='Tên file')

    month = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'), ('4', 'Tháng 4'),
        ('5', 'Tháng 5'), ('6', 'Tháng 6'), ('7', 'Tháng 7'), ('8', 'Tháng 8'),
        ('9', 'Tháng 9'), ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12')
    ], string='Tháng', required=True, default=lambda self: str(fields.Date.today().month))

    year = fields.Integer(string='Năm', required=True, default=lambda self: fields.Date.today().year)
    sheet_name = fields.Char(string='Tên Sheet', default='Tháng', required=True)
    header_row = fields.Integer(string='Dòng tiêu đề ngày', default=6)

    # ========================================================
    # 1. CẤU HÌNH & HELPER TÌM KIẾM
    # ========================================================

    def _get_attendance_symbols(self):
        """Nhóm (1): Ký hiệu tạo Chấm công"""
        return ['+', '-']

    def _get_public_holiday_symbols(self):
        """Nhóm (2): Ký hiệu Lễ Tết -> BỎ QUA"""
        return ['L', 'TET', 'GIO_TO', 'ND', 'QP', 'LE']

    def _find_leave_type_by_code(self, symbol):
        """Tìm hr.leave.type theo Code"""
        if not symbol: return False

        clean_code = symbol.strip().upper()
        # Mapping sửa lỗi nhập liệu thường gặp
        MAPPING = {
            'VRO': 'RO',
            'CV': 'CVD',
            'OM': 'O'
        }
        search_code = MAPPING.get(clean_code, clean_code)

        # Ưu tiên tìm theo Code
        leave_type = self.env['hr.leave.type'].search([('code', '=', search_code)], limit=1)

        # Fallback tìm theo work_entry_type
        if not leave_type:
            leave_type = self.env['hr.leave.type'].search([('work_entry_type_id.code', '=', search_code)], limit=1)

        return leave_type.id if leave_type else False

    # ========================================================
    # 2. LOGIC LẤY GIỜ TỪ HỢP ĐỒNG
    # ========================================================
    def _get_work_hours_from_contract(self, employee, current_date):
        """
        Trả về tuple (Giờ vào, Giờ ra, Giờ nghỉ trưa) dạng float
        HOẶC False nếu không có hợp đồng/ngày nghỉ.
        """
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['open', 'close']),
            ('date_start', '<=', current_date),
            '|', ('date_end', '=', False), ('date_end', '>=', current_date)
        ], limit=1)

        if not contract:
            return False

        if contract and contract.resource_calendar_id:
            day_of_week = current_date.weekday()
            attendances = contract.resource_calendar_id.attendance_ids.filtered(
                lambda a: a.dayofweek == str(day_of_week) and a.display_type != 'line_section'
            )

            if attendances:
                h_start = min(attendances.mapped('hour_from'))
                h_end = max(attendances.mapped('hour_to'))

                morning_shift = attendances.filtered(lambda a: a.day_period == 'morning')
                if morning_shift:
                    h_noon = max(morning_shift.mapped('hour_to'))
                else:
                    h_noon = h_start + (h_end - h_start) / 2

                return h_start, h_end, h_noon

        return False

    # ========================================================
    # 3. LOGIC IMPORT CHÍNH
    # ========================================================
    def action_import(self):
        self.ensure_one()
        if not self.file: raise UserError(_("Vui lòng chọn file Excel."))

        try:
            file_data = base64.b64decode(self.file)
            data_file = io.BytesIO(file_data)
            wb = openpyxl.load_workbook(data_file, data_only=True)
            sheet = wb[self.sheet_name] if self.sheet_name in wb.sheetnames else wb.active
        except Exception as e:
            raise UserError(_("Lỗi đọc file: %s") % e)

        Attendance = self.env['hr.attendance']
        Leave = self.env['hr.leave']
        Employee = self.env['hr.employee']

        ATT_SYMBOLS = self._get_attendance_symbols()
        PUB_SYMBOLS = self._get_public_holiday_symbols()

        local_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        utc_tz = pytz.utc

        COL_EMP = 1
        COL_START_DAY = 3
        START_ROW = self.header_row + 1
        last_day = calendar.monthrange(self.year, int(self.month))[1]

        cnt_att = 0
        cnt_leave = 0
        cnt_skipped = 0
        errors = []

        # --- LOOP ROWS ---
        for row_idx, row in enumerate(sheet.iter_rows(min_row=START_ROW, values_only=True), start=START_ROW):
            emp_code = row[COL_EMP]
            if not emp_code: continue

            employee = Employee.search([('employee_code', '=', str(emp_code).strip())], limit=1)
            if not employee: continue

            # --- LOOP DAYS ---
            for day in range(1, last_day + 1):
                col_idx = COL_START_DAY + (day - 1)
                if col_idx >= len(row): break
                raw_val = row[col_idx]
                if not raw_val: continue

                val = str(raw_val).strip().upper()
                try:
                    curr_date = datetime(self.year, int(self.month), day)
                except:
                    continue

                work_hours = self._get_work_hours_from_contract(employee, curr_date.date())
                if not work_hours: continue

                h_start_float, h_end_float, h_noon_float = work_hours
                is_half = True if ('/2' in val or val == '-') else False
                base_symbol = val.replace('/2', '') if '/2' in val else ('-' if val == '-' else val)

                # === 1. CHẤM CÔNG ===
                if base_symbol in ATT_SYMBOLS or ':' in val:
                    check_in_dt = False
                    if ':' in val:
                        times = val.replace('\n', ' ').split()
                        valid_times = [t for t in times if ':' in t]
                        if valid_times:
                            try:
                                check_in_dt = self._parse_to_utc(curr_date, valid_times[0], local_tz, utc_tz)
                                if len(valid_times) > 1:
                                    check_out_dt = self._parse_to_utc(curr_date, valid_times[-1], local_tz, utc_tz)
                                else:
                                    h_to_temp = h_noon_float if is_half else h_end_float
                                    check_out_dt = self._make_utc_from_float(curr_date, h_to_temp, local_tz, utc_tz)
                            except:
                                continue
                    else:
                        h_to_temp = h_noon_float if is_half else h_end_float
                        check_in_dt = self._make_utc_from_float(curr_date, h_start_float, local_tz, utc_tz)
                        check_out_dt = self._make_utc_from_float(curr_date, h_to_temp, local_tz, utc_tz)

                    if check_in_dt and check_out_dt:
                        start_d = check_in_dt.replace(hour=0, minute=0)
                        end_d = check_in_dt.replace(hour=23, minute=59)
                        if not Attendance.search_count([('employee_id', '=', employee.id), ('check_in', '>=', start_d),
                                                        ('check_in', '<=', end_d)]):
                            Attendance.create({
                                'employee_id': employee.id,
                                'check_in': check_in_dt,
                                'check_out': check_out_dt,
                                'attendance_type': 'attendance'
                            })
                            cnt_att += 1

                # === 2. LỄ TẾT ===
                elif base_symbol in PUB_SYMBOLS:
                    cnt_skipped += 1
                    continue

                # === 3. NGHỈ PHÉP (AUTO DUYỆT FULL) ===
                else:
                    leave_type_id = self._find_leave_type_by_code(val)
                    if not leave_type_id:
                        errors.append(f"Dòng {row_idx} ({emp_code}): Không tìm thấy loại nghỉ '{val}'")
                        continue

                    domain = [
                        ('employee_id', '=', employee.id),
                        ('state', 'in', ['confirm', 'validate1', 'validate']),
                        ('request_date_from', '<=', curr_date.date()),
                        ('request_date_to', '>=', curr_date.date())
                    ]

                    if not Leave.search_count(domain):
                        h_to_temp = h_noon_float if is_half else h_end_float

                        dt_f = self._make_utc_from_float(curr_date, h_start_float, local_tz, utc_tz)
                        dt_t = self._make_utc_from_float(curr_date, h_to_temp, local_tz, utc_tz)

                        try:
                            vals = {
                                'employee_id': employee.id,
                                'holiday_status_id': int(leave_type_id),
                                'date_from': dt_f,
                                'date_to': dt_t,
                                'request_date_from': curr_date.date(),
                                'request_date_to': curr_date.date(),
                                'request_unit_hours': True,
                                'request_unit_half': False,
                                'number_of_days': 0.5 if is_half else 1,
                                'state': 'confirm',  # Tạo ở trạng thái chờ duyệt
                                'name': f'Import {val}',
                                'is_imported': True
                            }

                            # 1. Tạo đơn (Sudo để vượt quyền)
                            leave = Leave.sudo().create(vals)

                            # 2. Xử lý DUYỆT TỰ ĐỘNG (Dù 1 hay 2 cấp)
                            # Sử dụng context 'bypass_manager_check' đã định nghĩa bên hr_leave.py
                            # để bỏ qua các check quyền tùy chỉnh
                            leave_sudo = leave.with_context(bypass_manager_check=True)

                            # Bước 1: Duyệt lần đầu (Confirm -> Validate1 hoặc Validate)
                            if leave_sudo.state == 'confirm':
                                leave_sudo.action_approve()

                            # Bước 2: Duyệt lần hai (Nếu workflow yêu cầu 2 cấp - Validate1 -> Validate)
                            if leave_sudo.state == 'validate1':
                                leave_sudo.action_validate()

                            # Bước 3: Safety Net - Nếu vì lý do gì đó mà vẫn chưa Validate
                            # (Ví dụ: Odoo standard chặn cùng 1 user duyệt 2 lần)
                            if leave_sudo.state != 'validate':
                                # Cưỡng chế gán trạng thái và chạy hàm tạo Work Entry
                                leave_sudo.write({'state': 'validate'})
                                leave_sudo._validate_leave_request()

                            cnt_leave += 1
                        except Exception as ex:
                            errors.append(f"Lỗi tạo nghỉ {val} NV {emp_code}: {ex}")

        msg = f"Hoàn tất!\n- Chấm công: {cnt_att}\n- Nghỉ Phép: {cnt_leave}\n- Bỏ qua: {cnt_skipped}"
        if errors:
            unique_err = list(set(errors))
            msg += f"\n\n--- CÓ LỖI ({len(unique_err)}) ---\n" + "\n".join(unique_err[:15])

        type_msg = 'warning' if errors else 'success'
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': 'Import Kết quả', 'message': msg, 'type': type_msg, 'sticky': True}
        }

    # --- HELPERS ---
    def _make_utc_from_float(self, date_obj, float_time, l_tz, u_tz):
        try:
            hours = int(float_time)
            minutes = int((float_time * 60) % 60)
            ldt = datetime(date_obj.year, date_obj.month, date_obj.day, hours, minutes)
            return l_tz.localize(ldt).astimezone(u_tz).replace(tzinfo=None)
        except:
            return False

    def _parse_to_utc(self, date_obj, t_str, l_tz, u_tz):
        try:
            t_str = t_str.replace(';', ':').replace('.', ':')[:5]
            parts = t_str.split(':')
            float_val = int(parts[0]) + int(parts[1]) / 60.0
            return self._make_utc_from_float(date_obj, float_val, l_tz, u_tz)
        except:
            return False