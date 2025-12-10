from odoo import models, fields, api
from datetime import datetime, timedelta


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    def get_conflict_data(self):
        """
        Tìm tất cả các work entry đang xung đột với entry hiện tại (self).
        Trả về danh sách dữ liệu để hiển thị lên Modal React/Owl.
        """
        self.ensure_one()

        # Tìm các entry chồng lấn thời gian với entry này
        # Logic: Start A < End B  VÀ  End A > Start B
        conflicts = self.env['hr.work.entry'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_start', '<', self.date_stop),
            ('date_stop', '>', self.date_start),
            ('id', '!=', self.id),  # Trừ chính nó ra
            ('active', '=', True),
            ('state', 'not in', ['cancelled'])  # Bỏ qua các cái đã hủy
        ])

        # Gom chính nó và các đối thủ vào 1 danh sách
        all_entries = self | conflicts

        result = []
        for entry in all_entries:
            # Lấy tên nguồn gốc để hiển thị cho dễ hiểu
            source_label = 'Không xác định'
            if entry.work_entry_type_id.is_leave:
                source_label = 'Đơn nghỉ phép'
            elif entry.work_entry_type_id.code == 'WORK100' or 'attendance' in entry.work_entry_type_id.code.lower():
                source_label = 'Máy chấm công'
            else:
                source_label = 'Lịch làm việc'

            result.append({
                'id': entry.id,
                'name': entry.name or entry.work_entry_type_id.name,
                'type': entry.work_entry_type_id.name,
                'start': entry.date_start,
                'stop': entry.date_stop,
                'duration': entry.duration,
                'source': source_label,
                'state': entry.state,
                'color': entry.color,
            })

        return result

    def action_resolve_conflict_git_style(self):
        """
        Hàm này được gọi khi người dùng chọn 'Giữ cái này'.
        Self chính là cái được chọn (Winner).
        Các cái còn lại (Losers) sẽ bị hủy.
        """
        self.ensure_one()

        # 1. Tìm các entry chồng lấn (Losers)
        losers = self.env['hr.work.entry'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_start', '<', self.date_stop),
            ('date_stop', '>', self.date_start),
            ('id', '!=', self.id),
            ('active', '=', True)
        ])

        # 2. Xử lý kẻ thua cuộc (Archive hoặc Cancel)
        if losers:
            losers.write({'active': False, 'state': 'cancelled'})

        # 3. Xử lý người chiến thắng (Validate luôn)
        self.write({'state': 'validated'})

        return True

    def action_sync_attendance(self):
        """
        Đồng bộ dữ liệu từ hr.attendance vào hr.work.entry.
        Xử lý 2 trường hợp:
        1. Đơn nghỉ phép bị trùng với giờ chấm công -> Tạo Conflict.
        2. Lịch làm việc dự kiến (Draft) -> Cập nhật theo giờ thực tế (Validated).
        """

        # --- LẤY LOẠI CÔNG 'ATTENDANCE' ĐỂ DÙNG KHI TẠO MỚI ---
        # Cố gắng tìm loại công có external id chuẩn, hoặc tìm theo code, hoặc lấy cái đầu tiên không phải nghỉ
        attendance_type = self.env.ref('hr_work_entry.work_entry_type_attendance', raise_if_not_found=False)
        if not attendance_type:
            attendance_type = self.env['hr.work.entry.type'].search([('is_leave', '=', False)], limit=1)

        # =======================================================
        # PHẦN 1: XỬ LÝ WORK ENTRY LÀ NGHỈ PHÉP (LEAVE)
        # =======================================================
        leaves_to_check = self.filtered(
            lambda w: w.state != 'validated' and w.work_entry_type_id.is_leave
        )

        for leave_entry in leaves_to_check:
            # Tìm xem có chấm công nào chen vào giờ nghỉ này không
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', leave_entry.employee_id.id),
                ('check_in', '<', leave_entry.date_stop),  # Vào trước khi hết giờ nghỉ
                ('check_out', '>', leave_entry.date_start),  # Ra sau khi bắt đầu giờ nghỉ
            ])

            if attendances:
                # -> TRƯỜNG HỢP XUNG ĐỘT: Có đơn nghỉ nhưng vẫn đi làm

                # B1: Đánh dấu entry nghỉ phép là Conflict
                leave_entry.write({'state': 'conflict'})

                # B2: Tạo các Work Entry đại diện cho việc đi làm thực tế
                # (Để khi mở modal lên, người dùng thấy được cả 2 dòng: Nghỉ vs Đi làm)
                for att in attendances:
                    # Tính toán giao điểm thời gian (Intersection)
                    real_start = max(leave_entry.date_start, att.check_in)
                    real_end = min(leave_entry.date_stop, att.check_out)

                    # Bỏ qua nếu tính toán sai (Start >= End)
                    if real_start >= real_end:
                        continue

                    # Kiểm tra xem đã tồn tại entry chấm công conflict này chưa (tránh tạo trùng lặp)
                    existing_conflict = self.env['hr.work.entry'].search_count([
                        ('employee_id', '=', leave_entry.employee_id.id),
                        ('date_start', '=', real_start),
                        ('date_stop', '=', real_end),
                        ('work_entry_type_id', '=', attendance_type.id),
                        ('state', '=', 'conflict')
                    ])

                    if existing_conflict == 0:
                        self.env['hr.work.entry'].create({
                            'name': f"Đi làm thực tế ({att.check_in.strftime('%H:%M')} - {att.check_out.strftime('%H:%M')})",
                            'employee_id': leave_entry.employee_id.id,
                            'date_start': real_start,
                            'date_stop': real_end,
                            'work_entry_type_id': attendance_type.id,
                            'state': 'conflict',  # Quan trọng: Set conflict để hiện đỏ
                            'duration': (real_end - real_start).total_seconds() / 3600,
                            'contract_id': leave_entry.contract_id.id,
                            'company_id': leave_entry.company_id.id,
                        })

            else:
                # -> TRƯỜNG HỢP HỢP LỆ: Nghỉ thật, không đi làm
                leave_entry.write({'state': 'validated'})

        # =======================================================
        # PHẦN 2: XỬ LÝ WORK ENTRY LÀ ĐI LÀM (ATTENDANCE/DRAFT)
        # =======================================================
        # Lấy các entry dự kiến (Draft) hoặc đang Conflict mà không phải là nghỉ phép
        attendance_entries = self.filtered(
            lambda w: w.state in ['draft', 'conflict'] and not w.work_entry_type_id.is_leave
        )

        for entry in attendance_entries:
            # Tìm chấm công khớp với khung giờ này
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', entry.employee_id.id),
                ('check_in', '<', entry.date_stop),
                ('check_out', '>', entry.date_start),
                ('check_out', '!=', False)
            ])

            if not attendances:
                # Nếu không có chấm công -> Có thể là vắng mặt không phép hoặc quên chấm công
                # Ở đây giữ nguyên state Draft hoặc chuyển sang Conflict tùy nhu cầu
                continue

            # Tính toán tổng thời gian đi làm thực tế nằm trong khung giờ quy định
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

            # Lấy khoảng thời gian bao phủ (đơn giản hóa: lấy min start và max end)
            final_start = min(valid_starts)
            final_end = max(valid_ends)

            duration = (final_end - final_start).total_seconds() / 3600

            # Cập nhật lại entry theo giờ thực tế và Validate luôn
            if duration > 0:
                entry.write({
                    'date_start': final_start,
                    'date_stop': final_end,
                    'duration': duration,
                    'state': 'validated'
                })

        return True