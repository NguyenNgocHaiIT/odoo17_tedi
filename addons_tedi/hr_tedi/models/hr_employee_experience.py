
from odoo import models, fields

class HREmployeeExperience(models.Model):
    _name = "hr.employee.experience"
    _description = "Kinh nghiệm công việc liên quan"
    _order = "date_from desc, id desc"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")

    project_name = fields.Char(string="Tên dự án")
    project_type = fields.Char(string="Loại dự án")
    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")
    position = fields.Char(string="Vị trí/Chức danh")
    status = fields.Selection([
        ('completed', 'Hoàn thành'),
        ('in_progress', 'Đang thực hiện'),
        ('pending', 'Tạm hoãn')
    ], string="Trạng thái dự án")
