# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import UserError
from datetime import datetime, time
import pytz


class ResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    work_entry_type_id = fields.Many2one('hr.work.entry.type', string="Loại công việc")

    def action_generate_work_entries_for_holiday(self):
        self.ensure_one()
        # 1. VALIDATE
        if not self.work_entry_type_id:
            raise UserError(_("Vui lòng chọn 'Loại công việc' trước."))
        if not self.date_from or not self.date_to:
            raise UserError(_("Vui lòng nhập thời gian."))

        # KHÔNG lấy .date() ở đây vì self.date_from đang là UTC
        # Chúng ta sẽ xử lý ngày bên trong vòng lặp theo múi giờ của từng lịch

        # 2. TÌM HỢP ĐỒNG
        # Dùng date_to của wizard (dù là UTC) để search contract vẫn ổn
        # hoặc cẩn thận hơn thì convert nhưng thường sai số search contract chấp nhận được
        domain = [
            ('state', 'in', ['open', 'close']),
            ('date_start', '<=', self.date_to.date()),
            '|', ('date_end', '=', False), ('date_end', '>=', self.date_from.date())
        ]
        if self.company_id:
            domain.append(('company_id', '=', self.company_id.id))

        contracts = self.env['hr.contract'].search(domain)
        if not contracts:
            raise UserError(_("Không tìm thấy hợp đồng nào."))

        vals_list = []
        entries_to_archive = self.env['hr.work.entry']

        # 3. DUYỆT HỢP ĐỒNG
        for contract in contracts:
            employee = contract.employee_id
            calendar = contract.resource_calendar_id
            resource = employee.resource_id

            if not calendar or not resource:
                continue

            # Múi giờ của lịch làm việc (VD: Asia/Ho_Chi_Minh)
            tz_name = calendar.tz or 'UTC'
            calendar_tz = pytz.timezone(tz_name)

            # --- SỬA LỖI TẠI ĐÂY ---
            # 1. Chuyển thời gian nhập từ form (UTC) sang múi giờ của Lịch (Local)
            dt_from_local = self.date_from.astimezone(calendar_tz)
            dt_to_local = self.date_to.astimezone(calendar_tz)

            # 2. Lấy ngày thực tế theo giờ địa phương (Sẽ ra đúng 11/12 thay vì 10/12)
            d_from_local_date = dt_from_local.date()
            d_to_local_date = dt_to_local.date()

            # 3. Tạo khung giờ quét từ 00:00 ngày đầu đến 23:59 ngày cuối (Local Time)
            local_start = calendar_tz.localize(datetime.combine(d_from_local_date, time.min))
            local_stop = calendar_tz.localize(datetime.combine(d_to_local_date, time.max))

            # 4. Đổi ngược lại sang UTC để query DB và tính toán
            start_dt_utc = local_start.astimezone(pytz.utc)
            stop_dt_utc = local_stop.astimezone(pytz.utc)

            # --- BƯỚC 2: TÌM WORK ENTRY CŨ ĐỂ XÓA ---
            conflicting_entries = self.env['hr.work.entry'].search([
                ('employee_id', '=', employee.id),
                ('date_stop', '>', start_dt_utc),
                ('date_start', '<', stop_dt_utc),
                ('state', '!=', 'validated'),
                ('active', '=', True)
            ])
            entries_to_archive |= conflicting_entries

            # --- BƯỚC 3: TÍNH TOÁN GIỜ LÀM VIỆC ---
            work_intervals = calendar._attendance_intervals_batch(
                start_dt_utc,
                stop_dt_utc,
                resources=resource,
                tz=calendar_tz
            )[resource.id]

            for start, stop, meta in work_intervals:
                # start, stop là 'datetime aware'

                # --- BƯỚC QUAN TRỌNG 4: STRICT FILTER ---
                # Chuyển giờ bắt đầu của ca làm việc về múi giờ Local
                start_in_local_tz = start.astimezone(calendar_tz)

                # So sánh với ngày local đã tính đúng ở trên
                if start_in_local_tz.date() < d_from_local_date or start_in_local_tz.date() > d_to_local_date:
                    continue

                    # Chuẩn bị dữ liệu lưu (Lưu DB bắt buộc là UTC Naive)
                start_naive = start.astimezone(pytz.utc).replace(tzinfo=None)
                stop_naive = stop.astimezone(pytz.utc).replace(tzinfo=None)

                duration = (stop - start).total_seconds() / 3600

                vals_list.append({
                    'name': f"{self.name or 'Nghỉ lễ'}",
                    'employee_id': employee.id,
                    'contract_id': contract.id,
                    'company_id': contract.company_id.id,
                    'date_start': start_naive,
                    'date_stop': stop_naive,
                    'duration': duration,
                    'work_entry_type_id': self.work_entry_type_id.id,
                    'state': 'draft',
                })

        # 4. THỰC THI
        if entries_to_archive:
            entries_to_archive.write({'active': False})

        if vals_list:
            self.env['hr.work.entry'].create(vals_list)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Hoàn tất'),
                'message': _('Đã xử lý xong.'),
                'type': 'success',
                'sticky': False,
            }
        }