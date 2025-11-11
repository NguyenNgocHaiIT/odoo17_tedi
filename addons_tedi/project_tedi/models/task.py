from odoo import models, fields, api


class ProjectDeliverableType(models.Model):
    _name = "project.deliverable.type"
    _description = "Loại hồ sơ"

    name = fields.Char('Tên')


class ProjectTaskProgress(models.Model):
    _name = 'project.task.progress'
    _description = 'Tiến độ và Review Task'

    task_id = fields.Many2one('project.task', string='Task', required=True)
    progress = fields.Float(string='Tiến độ (%)', required=True)
    review = fields.Text(string='Review/Nhận xét')
    user_id = fields.Many2one('res.users', string='Người cập nhật', default=lambda self: self.env.user)
    date = fields.Datetime(string='Ngày cập nhật', default=fields.Datetime.now)


class ProjectTaskDeliverable(models.Model):
    _name = "project.task.deliverable"
    _description = "Hồ sơ trong công việc"

    name = fields.Char('Tên')
    task_id = fields.Many2one('project.task', string='Công việc')
    version = fields.Integer('Phiên bản')
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu', required=True)
    state = fields.Selection([('draft', 'Đang thực hiện'),
                              ('wait_approve', 'Chờ phê duyệt'),
                              ('approve', 'Đã phê duyệt'),
                              ('reject', 'Từ chối'),
                              ('done', 'Hoàn thành')], string='Trạng thái', default='draft')
    review_by = fields.Many2one('res.users', 'Người review')
    review_date = fields.Datetime('Thời gian review')
    review_note = fields.Text('Nội dung review')

    def action_waiting_deliverable(self):
        if self.state == 'draft':
            # self.state = 'wait_approve'
            self.state = 'done'

    def action_draft(self):
        if self.state == 'wait_approve':
            self.state = 'draft'

    def action_approve(self):
        if self.state == 'wait_approve':
            self.state = 'approve'

    def action_reject(self):
        if self.state == 'wait_approve':
            self.state = 'reject'



class ProjectTask(models.Model):
    _inherit = "project.task"

    type_task = fields.Selection([('1', 'Công tác khảo sát'),
                                  ('2', 'Công tác thiết kế'),
                                  ('3', 'Công tác tư vấn giám sát'),
                                  ('4', 'Công việc chung')], string='Phân loại')
    department_id = fields.Many2one('hr.department', 'Đơn vị phụ trách')
    department_ids = fields.Many2many('hr.department', 'project_task_hr_department_rel', string='Đơn vị đồng phụ trách')
    is_deliverable = fields.Boolean('Đây là công việc làm hồ sơ')
    deliverable_type_id = fields.Many2one('project.deliverable.type', string='Loại hồ sơ')
    deliverable_count = fields.Integer('Số tài liệu được chấp nhận')
    child_deliverable_ids = fields.One2many('project.task.deliverable', 'task_id', string='Danh sách tài liệu')
    progress = fields.Float(string="Tiến độ (%)", default=0.0)
    task_progress_ids = fields.One2many('project.task.progress', 'task_id', string='Tiến độ chi tiết')
    project_code = fields.Char('Mã dự án', related="project_id.code", store=True)
    dia_diem = fields.Text('Địa điểm', related="project_id.dia_diem", store=True)
    partner_id = fields.Many2one('res.partner', related="project_id.partner_id", store=True)

    def action_open_progress_wizard(self):
        return {
            'name': 'Cập nhật tiến độ',
            'type': 'ir.actions.act_window',
            'res_model': 'task.progress.wizard',
            'view_mode': 'form',
            'target': 'new',  # Mở popup
            'context': {'default_task_id': self.id, 'default_progress': self.progress},
        }
