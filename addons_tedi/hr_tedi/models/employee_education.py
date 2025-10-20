# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HREmployeeEducation(models.Model):
    _name = "hr.employee.education"
    _description = "Employee Education"
    _order = "id asc"  # stt không lưu DB nên không dùng trong order

    # Không cần compute vì đã dùng onchange
    stt = fields.Integer(string="STT", compute="_compute_stt", store=False)

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    school = fields.Char(string="Đơn vị đào tạo", required=True)
    major = fields.Char(string="Chuyên ngành")
    years = fields.Char(string="Số năm đào tạo")
    degree = fields.Char(string="Trình độ")
    issue_date = fields.Date(string="Ngày cấp")
    attachment_ids = fields.Many2many(
        "ir.attachment", string="Đính kèm",
        relation="edu_ir_attachments_rel", column1="edu_id", column2="att_id"
    )

    # Đơn giản hóa depends: chỉ cần phụ thuộc vào danh sách one2many trên model cha.
    # Khi danh sách này thay đổi (thêm, xóa, sửa), Odoo sẽ gọi lại hàm này cho TẤT CẢ các dòng liên quan.
    @api.depends('employee_id.education_ids')
    def _compute_stt(self):
        """
        Tính toán lại STT cho các dòng dựa trên vị trí của chúng trong danh sách.
        """
        # Duyệt qua từng nhân viên có trong các dòng đang được tính toán
        for employee in self.mapped('employee_id'):
            # Lấy danh sách các dòng one2many theo đúng thứ tự trên giao diện
            lines_in_order = employee.education_ids
            for idx, line in enumerate(lines_in_order):
                # Gán trực tiếp STT, Odoo sẽ tự biết `line` nào tương ứng với `rec` nào
                line.stt = idx + 1
