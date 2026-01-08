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
    project_state_ids = fields.Many2many('project.state', 'project_project_state', string='Bước thực hiện')

    @api.onchange('user_id')
    def onchange_user_id(self):
        if self.user_id:
            employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', self.user_id.id)], limit=1)
            self.employee_user_id = employee_id.id
    phan_loai_goi_thau = fields.Selection([('1', 'Khảo sát thiết kế'),
                                           ('2', 'Tư vấn giám sát'),
                                           ('3', 'Kiểm định')], string='Phân loại gói thầu')
    phan_loai_cong_trinh_id = fields.Many2one(
        'project.task.template',
        string='Phân loại công trình'
    )

    contract_id = fields.Char('Hợp đồng')
    giai_doan_du_an = fields.Char("Giai đoạn thực hiện")
    project_member_ids = fields.One2many('project.member', 'project_id')
    dia_diem = fields.Text('Địa điểm')
    giao_nhiem_vu = fields.One2many('project.task', 'project_id', 'Phân công giao nhiệm vụ')
    giao_nhiem_vu_attachment_id = fields.Many2many('ir.attachment', string='Thông báo giao nhiệm vụ')

    @api.onchange('phan_loai_cong_trinh_id')
    def _onchange_template(self):
        """Xử lý khi thay đổi phân loại công trình"""
        if self.phan_loai_cong_trinh_id:
            # Xóa tất cả nhiệm vụ cũ và tạo mới
            self._regenerate_all_tasks()

    @api.onchange('project_state_ids')
    def _onchange_project_states(self):
        """Xử lý khi thay đổi bước thực hiện"""
        if self.phan_loai_cong_trinh_id:
            # Chỉ tạo lại nếu đã có template
            self._regenerate_all_tasks()

    def _regenerate_all_tasks(self):
        """Tạo lại tất cả nhiệm vụ dựa trên template và bước thực hiện hiện tại"""
        if not self.phan_loai_cong_trinh_id:
            return

        # Xóa tất cả nhiệm vụ hiện tại
        self.giao_nhiem_vu = [(5, 0, 0)]

        project_states = self.project_state_ids
        has_states = bool(project_states)
        all_tasks = []

        # Duyệt qua từng nhiệm vụ trong template
        for line in self.phan_loai_cong_trinh_id.nhiem_vu_ids:
            if has_states:
                # Nếu có bước thực hiện, tạo nhiệm vụ cho từng bước
                for state in project_states:
                    task_name = f"{line.nhiem_vu} ({state.name})"
                    all_tasks.append((0, 0, {
                        'department_id': line.department_id.id,
                        'name': task_name,
                        'sequence': line.sequence,
                        'task_categorize': line.task_categorize.id,
                        'is_deliverable': line.is_deliverable,
                        'deliverable_type_id': line.deliverable_type_id.id,
                        'project_id': self.id,
                    }))
            else:
                # Nếu không có bước thực hiện, tạo nhiệm vụ bình thường
                all_tasks.append((0, 0, {
                    'department_id': line.department_id.id,
                    'name': line.nhiem_vu,
                    'sequence': line.sequence,
                    'task_categorize': line.task_categorize.id,
                    'is_deliverable': line.is_deliverable,
                    'deliverable_type_id': line.deliverable_type_id.id,
                    'project_id': self.id,
                }))

        # Gán tất cả nhiệm vụ mới
        if all_tasks:
            self.giao_nhiem_vu = all_tasks


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

