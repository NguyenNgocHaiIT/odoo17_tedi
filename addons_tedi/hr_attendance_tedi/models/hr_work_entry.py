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
        Đồng bộ:
        1. Entry là Nghỉ phép + Không có chấm công -> Validate.
        2. Entry là Nghỉ phép + Có chấm công -> Conflict.
        3. Entry là Công thường + Có chấm công -> Cập nhật giờ & Validate.
        """
        # 1. Dùng sudo để bypass quyền (Quan trọng)
        sudo_self = self.sudo()
        Attendance = self.env['hr.attendance'].sudo()
        WorkEntry = self.env['hr.work.entry'].sudo()

        # Lấy loại công Attendance để dùng khi tạo Conflict
        attendance_type = self.env.ref('hr_work_entry.work_entry_type_attendance', raise_if_not_found=False)
        if not attendance_type:
            attendance_type = self.env['hr.work.entry.type'].search([('is_leave', '=', False)], limit=1)

        # ==================================================================
        # PHẦN 1: XỬ LÝ WORK ENTRY LÀ NGHỈ PHÉP (LEAVES)
        # ==================================================================
        # Logic lọc mở rộng: Lấy entry nếu loại là 'is_leave' HOẶC đã gắn 'leave_id'
        leave_entries = sudo_self.filtered(
            lambda w: w.state in ['draft', 'conflict'] and (w.work_entry_type_id.is_leave or w.leave_id)
        )

        for leave_entry in leave_entries:
            # Tìm xem có chấm công nào chen vào giờ nghỉ không
            # Logic Overlap: (CheckIn < EndLeave) và (CheckOut > StartLeave)
            attendances = Attendance.search([
                ('employee_id', '=', leave_entry.employee_id.id),
                ('check_in', '<', leave_entry.date_stop),
                ('check_out', '>', leave_entry.date_start),
            ])

            if attendances:
                # [CASE 1.A] CÓ XUNG ĐỘT (Vừa nghỉ vừa đi làm)
                if leave_entry.state != 'conflict':
                    leave_entry.write({'state': 'conflict'})

                for att in attendances:
                    # Tính toán giao điểm
                    real_start_utc = max(leave_entry.date_start, att.check_in)
                    real_end_utc = min(leave_entry.date_stop, att.check_out)

                    if real_start_utc >= real_end_utc:
                        continue

                    # Tạo tên hiển thị
                    att_start_local = self._get_user_tz_datetime(att.check_in)
                    att_end_local = self._get_user_tz_datetime(att.check_out)
                    entry_name = f"Thực tế: {att_start_local.strftime('%H:%M')} - {att_end_local.strftime('%H:%M')}"

                    # Tạo Conflict Entry (nếu chưa có)
                    existing_conflict = WorkEntry.search_count([
                        ('employee_id', '=', leave_entry.employee_id.id),
                        ('date_start', '=', real_start_utc),
                        ('work_entry_type_id', '=', attendance_type.id),
                        ('state', '=', 'conflict')
                    ])

                    if existing_conflict == 0:
                        WorkEntry.create({
                            'name': entry_name,
                            'employee_id': leave_entry.employee_id.id,
                            'date_start': real_start_utc,
                            'date_stop': real_end_utc,
                            'work_entry_type_id': attendance_type.id,
                            'state': 'conflict',
                            'duration': (real_end_utc - real_start_utc).total_seconds() / 3600,
                            'contract_id': leave_entry.contract_id.id,
                            'company_id': leave_entry.company_id.id,
                        })
            else:
                # [CASE 1.B] KHÔNG CÓ XUNG ĐỘT (Nghỉ êm đẹp)
                # -> VALIDATE NGAY LẬP TỨC
                leave_entry.write({'state': 'validated'})

        # ==================================================================
        # PHẦN 2: XỬ LÝ WORK ENTRY LÀ CÔNG THƯỜNG (ATTENDANCE/GENERIC)
        # ==================================================================
        # Lấy tất cả các entry còn lại (không phải leave)
        attendance_entries = sudo_self - leave_entries

        # Chỉ xử lý những cái đang Draft hoặc Conflict
        attendance_entries = attendance_entries.filtered(lambda w: w.state in ['draft', 'conflict'])

        for entry in attendance_entries:
            attendances = Attendance.search([
                ('employee_id', '=', entry.employee_id.id),
                ('check_in', '<', entry.date_stop),
                ('check_out', '>', entry.date_start),
                ('check_out', '!=', False)
            ])

            if not attendances:
                # Nếu là công thường mà không có chấm công -> Bỏ qua (Vẫn để Draft hoặc chuyển Cancel tùy logic công ty)
                continue

            # ... (Giữ nguyên logic tính toán giờ thực tế của bạn) ...
            valid_starts = []
            valid_ends = []
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
                att_start_local = self._get_user_tz_datetime(final_start)
                att_end_local = self._get_user_tz_datetime(final_end)
                new_name = f"{entry.work_entry_type_id.name} ({att_start_local.strftime('%H:%M')} - {att_end_local.strftime('%H:%M')})"

                entry.write({
                    'name': new_name,
                    'date_start': final_start,
                    'date_stop': final_end,
                    'duration': duration,
                    'state': 'validated'  # Chốt công
                })

        return True