from odoo import models, fields, api


class ProjectTaskTemplate(models.Model):
    _name = 'project.task.template'
    _description = 'Template nhiệm vụ theo phân loại công trình'

    name = fields.Char('Tên phân loại công trình', required=True)  # name = phân loại
    nhiem_vu_ids = fields.One2many(
        'project.task.template.line',
        'template_id',
        string='Danh sách nhiệm vụ'
    )

class ProjectTaskTemplateLine(models.Model):
    _name = 'project.task.template.line'
    _description = 'Dòng nhiệm vụ template'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'project.task.template',
        string='Template',
        ondelete='cascade'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban/Đơn vị'
    )

    nhiem_vu = fields.Text(string='Nhiệm vụ')

    sequence = fields.Integer(string='Thứ tự',)

    @api.onchange('template_id', 'template_id.nhiem_vu_ids')
    def _onchange_template_lines(self):
        """
        Cập nhật sequence 1,2,3... ngay khi thêm, xóa, reorder dòng
        ngay cả khi chưa bấm Lưu.
        """
        if self.template_id:
            for idx, line in enumerate(self.template_id.nhiem_vu_ids):
                line.sequence = idx + 1

    # Giữ lại override create/unlink để đảm bảo DB luôn sạch
    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.template_id:
            for idx, line in enumerate(record.template_id.nhiem_vu_ids):
                line.sequence = idx + 1
        return record

    def unlink(self):
        template_ids = self.mapped('template_id')
        result = super().unlink()
        for template in template_ids:
            for idx, line in enumerate(template.nhiem_vu_ids):
                line.sequence = idx + 1
        return result