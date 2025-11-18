from odoo import models, fields, api


class ProjectState(models.Model):
    _name = 'project.state'
    _description = 'Bước thực hiện'

    name = fields.Char('Tên bước thực hiện')


class Project(models.Model):
    _inherit = 'project.project'

    code = fields.Char('Mã dự án')
    user_id = fields.Many2one('res.users', string="Giám đốc điều hành dự án")
    employee_user_id = fields.Many2one('hr.employee', string="Giám đốc điều hành dự án")

    @api.onchange('user_id')
    def onchange_user_id(self):
        if self.user_id:
            employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', self.user_id.id)], limit=1)
            self.employee_user_id = employee_id.id
    phan_loai_goi_thau = fields.Selection([('1', 'Khảo sát thiết kế'),
                                           ('2', 'Tư vấn giám sát'),
                                           ('3', 'Kiểm định')], string='Phân loại gói thầu')
    phan_loai_cong_trinh = fields.Selection([('1', 'Đường bộ'),
                                             ('2', 'Đường sắt'),
                                             ('3', 'Hàng không'),
                                             ('4', 'Cảng, đường thủy'),
                                             ('5', 'Cầu đặc biệt'),
                                             ('6', 'Hầm đặc biệt')], string="Phân loại công trình")
    contract_id = fields.Char('Hợp đồng')
    giai_doan_du_an = fields.Char("Giai đoạn thực hiện")
    project_member_ids = fields.One2many('project.member', 'project_id')
    dia_diem = fields.Text('Địa điểm')
    giao_nhiem_vu = fields.One2many('project.giao.nhiem.vu', 'project_id', 'Phân công giao nhiệm vụ')
    giao_nhiem_vu_attachment_id = fields.Many2many('ir.attachment', string='Thông báo giao nhiệm vụ')


class ProjectMember(models.Model):
    _name = 'project.member'

    sequence = fields.Integer(string="Sequence", default=10)
    display_type = fields.Selection(
        [
            ("line_section", "Section"),
            ("line_note", "Note"),
        ], string="Display Type", help="If set, the line will be displayed as a section or note.", default=False)
    project_id = fields.Many2one('project.project')
    employee_id = fields.Many2one('hr.employee', string='Họ và tên')
    job_id = fields.Many2one('hr.job', string='Vị trí/Chức vụ', related='employee_id.job_id')
    department_id = fields.Many2one('hr.department', string='Đơn vị/Phòng ban', related='employee_id.department_id')
    name = fields.Char(string='Mã nhân viên')
    job_tile = fields.Text(string='Chức danh tổng thể')

    @api.onchange('employee_id')
    def onchange_employee(self):
        self.name = False
        if self.employee_id:
            self.name = self.employee_id.name


class ProjectGiaoNhiemVu(models.Model):
    _name = 'project.giao.nhiem.vu'

    sequence = fields.Integer(string="Sequence", default=10)
    project_id = fields.Many2one('project.project')
    department_id = fields.Many2one('hr.department', string='Phòng ban/Đơn vị')
    nhiem_vu = fields.Text(string='Nhiệm vụ')