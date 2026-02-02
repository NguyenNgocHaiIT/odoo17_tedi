# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HolidaysAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    # --- 1. ĐỔI TÊN CÁC TRẠNG THÁI (STATE) ---
    state = fields.Selection([
        ('confirm', 'Chờ phân bổ'),   # Cũ: To Approve -> Mới: Chờ phân bổ
        ('refuse', 'Hủy'),            # Cũ: Refused -> Mới: Hủy
        ('validate', 'Đã phân bổ')    # Cũ: Approved -> Mới: Đã phân bổ
    ], string='Trạng thái', readonly=True, tracking=True, copy=False, default='confirm',
    help="Trạng thái của đơn phân bổ.")

    # --- 2. GIỮ LẠI HÀM ACTION_DRAFT (ĐỂ FIX LỖI CŨ) ---
    def action_draft(self):
        if any(allocation.state not in ['confirm', 'refuse'] for allocation in self):
            raise UserError(_('Chỉ có thể đưa đơn về nháp khi đang ở trạng thái Chờ phân bổ hoặc Hủy.'))
        self.write({'state': 'confirm'})
        return True