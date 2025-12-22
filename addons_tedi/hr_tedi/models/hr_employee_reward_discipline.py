# -*- coding: utf-8 -*-
from odoo import models, fields, api


# --- CLASS MỚI: DANH MỤC QUYỀN LỢI ---
class HrRewardBenefit(models.Model):
    _name = "hr.reward.benefit"
    _description = "Danh mục Quyền lợi Khen thưởng/Kỷ luật"
    _order = "name"

    name = fields.Char(string="Tên quyền lợi", required=True)
    code = fields.Char(string="Mã quyền lợi")
    description = fields.Text(string="Mô tả chi tiết")

    # Optional: Giá trị quy đổi ra tiền (nếu cần thống kê)
    value = fields.Float(string="Giá trị tham khảo")


# --- CLASS CŨ ĐÃ SỬA ĐỔI ---
class HREmployeeRewardDiscipline(models.Model):
    _name = "hr.employee.reward.discipline"
    _description = "Khen thưởng - Kỷ luật của nhân viên"
    _order = "decision_date desc, id desc"

    employee_id = fields.Many2one(
        "hr.employee", string="Nhân viên", required=True, ondelete="cascade")

    decision_id = fields.Many2one(
        "hr.decision", string="Quyết định", required=True)

    # Thêm trường này vào để liên kết với danh mục bên trên
    # Dùng Many2many để có thể chọn nhiều quyền lợi cùng lúc (VD: Tiền mặt + Bằng khen)
    benefit_ids = fields.Many2many(
        "hr.reward.benefit",
        string="Quyền lợi / Hình thức",
        help="Chọn các quyền lợi hoặc hình thức xử lý từ danh mục"
    )

    decision_no = fields.Char(string="Số quyết định")
    decision_date = fields.Date(string="Ngày quyết định")
    decision_level = fields.Char(string="Cấp quyết định")
    content = fields.Text(string="Nội dung")

    @api.onchange('decision_id')
    def _onchange_decision_id(self):
        if self.decision_id:
            self.decision_no = self.decision_id.decision_no
            self.decision_date = self.decision_id.decision_date
            self.decision_level = self.decision_id.decision_level
            self.content = self.decision_id.content
        else:
            self.decision_no = False
            self.decision_date = False
            self.decision_level = False
            self.content = False