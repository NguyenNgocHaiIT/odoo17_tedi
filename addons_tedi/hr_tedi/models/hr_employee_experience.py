from odoo import models, fields


# --- MỚI: Class Loại Dự án ---
class HrExperienceProjectType(models.Model):
    _name = "hr.experience.project.type"
    _description = "Loại Dự án Kinh nghiệm"
    _rec_name = 'name'

    name = fields.Char(string="Tên loại dự án", required=True)
    code = fields.Char(string="Mã loại", help="Ví dụ: OUTSRC, PRODUCT, MAINT...")
    description = fields.Text(string="Mô tả")
    active = fields.Boolean(default=True, string="Đang dùng")


class HrExperiencePosition(models.Model):
    _name = "hr.experience.position"
    _description = "Chức danh"
    _rec_name = 'name'

    name = fields.Char(string="Tên chức danh", required=True)
    description = fields.Text(string="Mô tả")
    active = fields.Boolean(default=True, string="Đang dùng")


class HREmployeeExperience(models.Model):
    _name = "hr.employee.experience"
    _description = "Kinh nghiệm công việc tại tedi"
    _order = "date_from desc, id desc"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")

    project_name = fields.Char(string="Tên dự án", required=True)

    # --- ĐÃ SỬA: Thay Char bằng Many2one liên kết với bảng Loại dự án ---
    project_type = fields.Many2one(
        "hr.experience.project.type",
        string="Loại dự án"
    )

    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")

    position = fields.Many2one(
        "hr.experience.position",
        string="Vị trí/Chức danh",
        required=True
    )

    status = fields.Selection([
        ('completed', 'Hoàn thành'),
        ('in_progress', 'Đang thực hiện'),
        ('pending', 'Tạm hoãn')
    ], string="Trạng thái dự án")


class HrExternalExperience(models.Model):
    _name = "hr.external.experience"
    _description = "Kinh nghiệm làm việc bên ngoài"
    _order = "date_from desc"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")

    # --- KHÁC BIỆT DUY NHẤT: Thêm tên công ty ---
    company_name = fields.Char(string="Tên công ty/Tổ chức", required=True)

    # --- Các trường dưới đây COPY Y HỆT từ bảng nội bộ ---
    project_name = fields.Char(string="Tên dự án/Công việc", required=True)

    # Dùng chung danh mục với bên nội bộ luôn cho tiện
    project_type = fields.Many2one("hr.experience.project.type", string="Loại dự án")
    position = fields.Many2one("hr.experience.position", string="Vị trí/Chức danh", required=True)

    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")

    status = fields.Selection([
        ('completed', 'Hoàn thành'),
        ('in_progress', 'Đang thực hiện'),
        ('pending', 'Tạm hoãn')
    ], string="Trạng thái")
