# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    # --- 1. Set mặc định TRUE cho các hành động đóng (ẩn trên UI nhưng vẫn chạy ngầm) ---
    def default_get(self, fields_list):
        defaults = super(HrDepartureWizard, self).default_get(fields_list)
        defaults.update({
            'archive_private_address': True,  # Lưu trữ địa chỉ
            'set_date_end': True,  # Kết thúc hợp đồng
            'cancel_leaves': True,  # Hủy phép tương lai
            'archive_allocation': True,  # Lưu trữ phân bổ
            # 'release_company_car': True,    # Bỏ comment nếu dùng hr_fleet
        })
        return defaults

    # --- 2. Logic xử lý khi bấm nút (Code cũ của bạn + logic chuẩn) ---
    def action_register_departure(self):
        # Gọi hàm gốc của Odoo để nó xử lý các logic Contract, Leaves...
        super(HrDepartureWizard, self).action_register_departure()

        # Logic ép buộc Archive nhân viên (như code cũ của bạn)
        if self.employee_id.active:
            _logger.info(f"DEBUG: TEDI - Ép buộc Archive nhân viên {self.employee_id.name}...")
            self.employee_id.write({'active': False})

        # Reload giao diện
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }