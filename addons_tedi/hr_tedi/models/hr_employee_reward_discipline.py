# -*- coding: utf-8 -*-
from odoo import models, fields, api  # Đảm bảo bạn đã import 'api'

class HREmployeeRewardDiscipline(models.Model):
    _name = "hr.employee.reward.discipline"
    _description = "Khen thưởng - Kỷ luật của nhân viên"
    _order = "decision_date desc, id desc"

    # 1. TRƯỜNG employee_id (SỬA LỖI KeyError)
    # Đây là trường bắt buộc để khớp với One2many
    employee_id = fields.Many2one(
        "hr.employee", string="Nhân viên", required=True, ondelete="cascade")

    # 2. TRƯỜNG DROPDOWN (Many2one)
    decision_id = fields.Many2one(
        "hr.decision", string="Quyết định", required=True)

    # 3. CÁC TRƯỜNG THÔNG THƯỜNG (KHÔNG DÙNG RELATED)
    # Chúng ta sẽ điền dữ liệu vào đây bằng hàm onchange
    decision_no = fields.Char(string="Số quyết định")
    decision_date = fields.Date(string="Ngày quyết định")
    decision_level = fields.Char(string="Cấp quyết định")
    content = fields.Text(string="Nội dung")

    # 4. HÀM ONCHANGE ĐỂ "IMPORT" DỮ LIỆU
    @api.onchange('decision_id')
    def _onchange_decision_id(self):
        if self.decision_id:
            # Tự động điền thông tin từ quyết định đã chọn
            self.decision_no = self.decision_id.decision_no
            self.decision_date = self.decision_id.decision_date
            self.decision_level = self.decision_id.decision_level
            self.content = self.decision_id.content
        else:
            # Xóa trắng các trường
            self.decision_no = False
            self.decision_date = False
            self.decision_level = False
            self.content = False