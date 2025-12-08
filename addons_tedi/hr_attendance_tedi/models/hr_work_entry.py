from odoo import models, fields, api


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    def action_sync_attendance(self):
        # --- PHẦN 1: XỬ LÝ WORK ENTRY LÀ NGHỈ PHÉP (LEAVE) ---
        # Logic mới:
        # 1. Nếu không có chấm công -> Validate (Bình thường).
        # 2. Nếu có chấm công đè lên giờ nghỉ -> Chuyển sang Conflict (Để HR kiểm tra lại).

        leaves_to_check = self.filtered(
            lambda w: w.state != 'validated' and w.work_entry_type_id.is_leave
        )

        for leave_entry in leaves_to_check:
            # Tìm xem có chấm công nào chen vào giờ nghỉ này không
            has_attendance = self.env['hr.attendance'].search_count([
                ('employee_id', '=', leave_entry.employee_id.id),
                ('check_in', '<', leave_entry.date_stop),  # Vào trước khi hết giờ nghỉ
                ('check_out', '>', leave_entry.date_start),  # Ra sau khi bắt đầu giờ nghỉ
            ])

            if has_attendance:
                # Có đơn nghỉ nhưng lại có đi làm -> XUNG ĐỘT
                leave_entry.write({'state': 'conflict'})
            else:
                # Nghỉ thật, không đi làm -> DUYỆT
                leave_entry.write({'state': 'validated'})

        # --- PHẦN 2: XỬ LÝ WORK ENTRY LÀ ĐI LÀM (ATTENDANCE) ---
        # (Giữ nguyên logic cũ của bạn)

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
                entry.write({
                    'date_start': final_start,
                    'date_stop': final_end,
                    'duration': duration,
                    'state': 'validated'
                })