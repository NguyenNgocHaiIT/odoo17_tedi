from odoo import models, fields, api
from datetime import datetime, timedelta
import pytz  # [QUAN TRỌNG] Cần thư viện này để xử lý múi giờ


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    def _get_user_tz_datetime(self, dt_utc):
        """
        Hàm phụ trợ: Chuyển đổi datetime từ UTC sang múi giờ của user hiện tại.
        Để hiển thị text cho đúng (VD: 08:00 thay vì 01:00)
        """
        if not dt_utc:
            return False
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        return pytz.utc.localize(dt_utc).astimezone(user_tz)

    def get_conflict_data(self):
        self.ensure_one()

        # 1. Lấy múi giờ user
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')

        conflicts = self.env['hr.work.entry'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_start', '<', self.date_stop),
            ('date_stop', '>', self.date_start),
            ('id', '!=', self.id),
            ('active', '=', True),
            ('state', 'not in', ['cancelled'])
        ])

        all_entries = self | conflicts
        result = []

        for entry in all_entries:
            source_label = 'Không xác định'
            if entry.work_entry_type_id.is_leave:
                source_label = 'Đơn nghỉ phép'
            elif entry.work_entry_type_id.code == 'WORK100' or 'attendance' in (
                    entry.work_entry_type_id.code or '').lower():
                source_label = 'Dữ liệu chấm công'
            else:
                source_label = 'Lịch làm việc'

            # --- [SỬA ĐOẠN NÀY] ---
            # Convert từ UTC sang giờ User ngay tại Server để đồng bộ hiển thị
            start_local = pytz.utc.localize(entry.date_start).astimezone(user_tz)
            stop_local = pytz.utc.localize(entry.date_stop).astimezone(user_tz)

            # Format thành chuỗi: 03:00 30-12
            start_str = start_local.strftime('%H:%M %d-%m')
            stop_str = stop_local.strftime('%H:%M %d-%m')
            # ----------------------

            result.append({
                'id': entry.id,
                'name': entry.name,
                'type': entry.work_entry_type_id.name,
                'start_formatted': start_str,  # Gửi chuỗi đã format
                'stop_formatted': stop_str,  # Gửi chuỗi đã format
                'duration': entry.duration,
                'source': source_label,
                'state': entry.state,
                'color': entry.color,
            })

        return result

    def action_resolve_conflict_git_style(self):
        self.ensure_one()
        # 1. Tìm phe thua cuộc
        losers = self.env['hr.work.entry'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_start', '<', self.date_stop),
            ('date_stop', '>', self.date_start),
            ('id', '!=', self.id),
            ('active', '=', True)
        ])
        # 2. Hủy phe thua
        if losers:
            losers.write({'active': False, 'state': 'cancelled'})
        # 3. Duyệt phe thắng
        self.write({'state': 'validated'})
        return True

    def action_sync_attendance(self):
        """
        Đồng bộ Attendance -> Work Entry.
        Sửa lỗi hiển thị thời gian bằng cách convert Timezone.
        """

        # Lấy loại công Attendance
        attendance_type = self.env.ref('hr_work_entry.work_entry_type_attendance', raise_if_not_found=False)
        if not attendance_type:
            attendance_type = self.env['hr.work.entry.type'].search([('is_leave', '=', False)], limit=1)

        # --- PHẦN 1: XỬ LÝ CONFLICT GIỮA NGHỈ PHÉP & CHẤM CÔNG ---
        leaves_to_check = self.filtered(
            lambda w: w.state != 'validated' and w.work_entry_type_id.is_leave
        )

        for leave_entry in leaves_to_check:
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', leave_entry.employee_id.id),
                ('check_in', '<', leave_entry.date_stop),
                ('check_out', '>', leave_entry.date_start),
            ])

            if attendances:
                # Có xung đột -> Đánh dấu Leave là Conflict
                leave_entry.write({'state': 'conflict'})

                for att in attendances:
                    # 1. Tính toán giao điểm (Intersection) để lưu vào DB (Dùng cho payroll)
                    # Mục đích: Work Entry không được phép dài hơn khoảng thời gian gốc quá nhiều gây chồng chéo dây chuyền
                    real_start_utc = max(leave_entry.date_start, att.check_in)
                    real_end_utc = min(leave_entry.date_stop, att.check_out)

                    if real_start_utc >= real_end_utc:
                        continue

                    # 2. Xử lý hiển thị Tên (Name): Convert sang giờ địa phương cho dễ đọc
                    # Đây là bước sửa lỗi "hiển thị không đúng"
                    att_start_local = self._get_user_tz_datetime(att.check_in)
                    att_end_local = self._get_user_tz_datetime(att.check_out)

                    # Format đẹp: "Đi làm thực tế (07:55 - 17:05)"
                    entry_name = f"Thực tế: {att_start_local.strftime('%H:%M')} - {att_end_local.strftime('%H:%M')}"

                    # Kiểm tra trùng lặp trước khi tạo
                    existing_conflict = self.env['hr.work.entry'].search_count([
                        ('employee_id', '=', leave_entry.employee_id.id),
                        ('date_start', '=', real_start_utc),
                        ('work_entry_type_id', '=', attendance_type.id),
                        ('state', '=', 'conflict')
                    ])

                    if existing_conflict == 0:
                        self.env['hr.work.entry'].create({
                            'name': entry_name,  # Tên hiển thị giờ thực tế (VD: 07:55)
                            'employee_id': leave_entry.employee_id.id,
                            'date_start': real_start_utc,  # Giờ lưu DB là giờ cắt (VD: 08:00 UTC)
                            'date_stop': real_end_utc,
                            'work_entry_type_id': attendance_type.id,
                            'state': 'conflict',
                            'duration': (real_end_utc - real_start_utc).total_seconds() / 3600,
                            'contract_id': leave_entry.contract_id.id,
                            'company_id': leave_entry.company_id.id,
                        })
            else:
                leave_entry.write({'state': 'validated'})

        # --- PHẦN 2: XỬ LÝ WORK ENTRY THƯỜNG (DRAFT) ---
        attendance_entries = self.filtered(
            lambda w: w.state in ['draft', 'conflict'] and not w.work_entry_type_id.is_leave
        )

        for entry in attendance_entries:
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', entry.employee_id.id),
                ('check_in', '<', entry.date_stop),
                ('check_out', '>', entry.date_start),
                ('check_out', '!=', False)
            ])

            if not attendances:
                continue

            valid_starts = []
            valid_ends = []

            # Logic này để gom nhiều lần checkin trong 1 ca (VD: Sáng checkin, trưa checkout đi ăn, chiều checkin lại)
            for att in attendances:
                real_start = max(entry.date_start, att.check_in)
                real_end = min(entry.date_stop, att.check_out)
                if real_start < real_end:
                    valid_starts.append(real_start)
                    valid_ends.append(real_end)

            if not valid_starts:
                continue

            final_start = min(valid_starts)
            final_end = max(valid_ends)
            duration = (final_end - final_start).total_seconds() / 3600

            if duration > 0:
                # Cập nhật tên theo giờ thực tế luôn cho đẹp
                att_start_local = self._get_user_tz_datetime(final_start)
                att_end_local = self._get_user_tz_datetime(final_end)
                new_name = f"{entry.work_entry_type_id.name} ({att_start_local.strftime('%H:%M')} - {att_end_local.strftime('%H:%M')})"

                entry.write({
                    'name': new_name,
                    'date_start': final_start,
                    'date_stop': final_end,
                    'duration': duration,
                    'state': 'validated'
                })

        return True