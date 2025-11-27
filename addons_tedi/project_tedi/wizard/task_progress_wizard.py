from odoo import models, fields, api


class TaskProgressWizard(models.TransientModel):
    _name = 'task.progress.wizard'
    _description = 'Wizard cập nhật tiến độ Task'

    task_id = fields.Many2one('project.task', string='Task', required=True)
    progress = fields.Float(string='Tiến độ (%)', required=True)
    review = fields.Text(string='Review/Nhận xét')

    def action_save_progress(self):
        # Cập nhật tiến độ task
        self.task_id.progress = self.progress

        # Lưu vào lịch sử review
        self.env['project.task.progress'].create({
            'task_id': self.task_id.id,
            'progress': self.progress,
            'review': self.review,
        })
