# -*- coding: utf-8 -*-
from odoo import models, fields, api


# --- MODEL MỚI: DANH MỤC CHUYÊN NGÀNH ---
class HrEducationMajor(models.Model):
    _name = "hr.education.major"
    _description = "Danh mục Chuyên ngành đào tạo"
    _rec_name = 'name'

    name = fields.Char(string="Tên chuyên ngành", required=True)
    description = fields.Text(string="Mô tả")
    active = fields.Boolean(default=True, string="Đang dùng")


# --- MODEL CŨ ĐÃ SỬA ---
class HREmployeeEducation(models.Model):
    _name = "hr.employee.education"
    _description = "Employee Education"
    _order = "id asc"

    stt = fields.Integer(string="STT", compute="_compute_stt", store=False)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")

    school = fields.Char(string="Đơn vị đào tạo", required=True)

    # --- THAY ĐỔI TẠI ĐÂY ---
    # Thay fields.Char cũ bằng fields.Many2one
    major_id = fields.Many2one(
        "hr.education.major",
        string="Chuyên ngành",
        required=True
    )
    # ------------------------

    years = fields.Char(string="Số năm đào tạo")
    degree = fields.Char(string="Trình độ")
    issue_date = fields.Date(string="Ngày cấp")
    attachment_ids = fields.Many2many(
        "ir.attachment", string="Đính kèm",
        relation="edu_ir_attachments_rel", column1="edu_id", column2="att_id"
    )

    @api.depends('employee_id.education_ids')
    def _compute_stt(self):
        for employee in self.mapped('employee_id'):
            lines_in_order = employee.education_ids
            for idx, line in enumerate(lines_in_order):
                line.stt = idx + 1