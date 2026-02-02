# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)
class HolidaysAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    # --- 1. ĐỔI TÊN CÁC TRẠNG THÁI (STATE) ---
    state = fields.Selection([
        ('confirm', 'Chờ phân bổ'),  # Trạng thái chờ xử lý
        ('refuse', 'Hủy'),  # Vẫn giữ định nghĩa để tránh lỗi hệ thống nhưng luồng sẽ ít dùng
        ('validate', 'Đã phân bổ')  # Đã phê duyệt cấp phát
    ], string='Trạng thái', readonly=True, tracking=True, copy=False, default='confirm')

    # --- 2. SỬA LUỒNG NÚT HỦY ---
    # def action_refuse(self):
    #     current_employee = self.env.user.employee_id
    #
    #     # Kiểm tra điều kiện trạng thái trước khi cho phép "Hủy & Làm lại"
    #     if any(allocation.state not in ['confirm', 'validate'] for allocation in self):
    #         raise UserError(
    #             _('Đơn phân bổ phải ở trạng thái Chờ phân bổ hoặc Đã phân bổ mới có thể thực hiện thao tác này.'))
    #
    #     # Lấy dữ liệu số ngày đã nghỉ của nhân viên
    #     days_per_allocation = self.employee_id._get_consumed_leaves(self.holiday_status_id)[0]
    #
    #     for allocation in self:
    #         # Giữ nguyên logic base: Nếu đã có ngày nghỉ thực tế (virtual_leaves_taken > 0) thì KHÔNG cho phép chuyển trạng thái
    #         days_taken = days_per_allocation[allocation.employee_id][allocation.holiday_status_id][allocation][
    #             'virtual_leaves_taken']
    #         if days_taken > 0:
    #             raise UserError(
    #                 _('Bạn không thể hủy/làm lại đơn này vì nhân viên đã sử dụng ngày nghỉ từ đợt phân bổ này. Vui lòng hủy các đơn xin nghỉ liên quan trước.'))
    #
    #     # --- ĐOẠN THAY ĐỔI QUAN TRỌNG ---
    #     # Thay vì viết 'state': 'refuse', ta viết 'state': 'confirm'
    #     self.write({
    #         'state': 'confirm',
    #         'approver_id': current_employee.id
    #     })
    #
    #     # Xử lý các yêu cầu liên kết (nếu có)
    #     linked_requests = self.mapped('linked_request_ids')
    #     if linked_requests:
    #         linked_requests.action_refuse()
    #
    #     self.activity_update()
    #     return True

    def _send_allocation_mail_notification(self, template_xml_id):
        """ Hàm tiện ích để gửi mail dựa trên template ID """
        template = self.env.ref(template_xml_id, raise_if_not_found=False)
        if not template:
            _logger.warning("Không tìm thấy Email Template: %s", template_xml_id)
            return

        for allocation in self:
            if allocation.employee_id and allocation.employee_id.work_email:
                template.sudo().send_mail(allocation.id, force_send=True)

    def action_validate(self):
        # Gọi hàm validate gốc của Odoo
        res = super(HolidaysAllocation, self).action_validate()
        # Gửi thông báo phê duyệt
        self._send_allocation_mail_notification('hr_attendance_tedi.email_template_allocation_validate')
        return res

    def action_refuse(self):
        current_employee = self.env.user.employee_id

        if any(allocation.state not in ['confirm', 'validate'] for allocation in self):
            raise UserError(
                _('Đơn phân bổ phải ở trạng thái Chờ phân bổ hoặc Đã phân bổ mới có thể thực hiện thao tác này.'))

        # Check số ngày đã nghỉ (Logic giữ nguyên của bạn)
        for allocation in self:
            days_per_allocation = allocation.employee_id._get_consumed_leaves(allocation.holiday_status_id)[0]
            days_taken = days_per_allocation[allocation.employee_id][allocation.holiday_status_id][allocation][
                'virtual_leaves_taken']
            if days_taken > 0:
                raise UserError(_('Bạn không thể hủy/làm lại đơn này vì nhân viên đã sử dụng ngày nghỉ...'))

        # Thực hiện chuyển trạng thái
        self.write({
            'state': 'confirm',
            'approver_id': current_employee.id
        })

        # Gửi thông báo hủy/điều chỉnh cho người được cấp phát
        self._send_allocation_mail_notification('hr_attendance_tedi.email_template_allocation_refuse')

        # Logic xử lý liên kết (Giữ nguyên của bạn)
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_refuse()

        self.activity_update()
        return True

