# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HolidaysAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    # --- 1. ĐỔI TÊN CÁC TRẠNG THÁI (STATE) ---
    state = fields.Selection([
        ('confirm', 'Chờ phân bổ'),  # Trạng thái chờ xử lý
        ('refuse', 'Hủy'),  # Vẫn giữ định nghĩa để tránh lỗi hệ thống nhưng luồng sẽ ít dùng
        ('validate', 'Đã phân bổ')  # Đã phê duyệt cấp phát
    ], string='Trạng thái', readonly=True, tracking=True, copy=False, default='confirm')

    # --- 2. SỬA LUỒNG NÚT HỦY ---
    def action_refuse(self):
        current_employee = self.env.user.employee_id

        # Kiểm tra điều kiện trạng thái trước khi cho phép "Hủy & Làm lại"
        if any(allocation.state not in ['confirm', 'validate'] for allocation in self):
            raise UserError(
                _('Đơn phân bổ phải ở trạng thái Chờ phân bổ hoặc Đã phân bổ mới có thể thực hiện thao tác này.'))

        # Lấy dữ liệu số ngày đã nghỉ của nhân viên
        days_per_allocation = self.employee_id._get_consumed_leaves(self.holiday_status_id)[0]

        for allocation in self:
            # Giữ nguyên logic base: Nếu đã có ngày nghỉ thực tế (virtual_leaves_taken > 0) thì KHÔNG cho phép chuyển trạng thái
            days_taken = days_per_allocation[allocation.employee_id][allocation.holiday_status_id][allocation][
                'virtual_leaves_taken']
            if days_taken > 0:
                raise UserError(
                    _('Bạn không thể hủy/làm lại đơn này vì nhân viên đã sử dụng ngày nghỉ từ đợt phân bổ này. Vui lòng hủy các đơn xin nghỉ liên quan trước.'))

        # --- ĐOẠN THAY ĐỔI QUAN TRỌNG ---
        # Thay vì viết 'state': 'refuse', ta viết 'state': 'confirm'
        self.write({
            'state': 'confirm',
            'approver_id': current_employee.id
        })

        # Xử lý các yêu cầu liên kết (nếu có)
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_refuse()

        self.activity_update()
        return True