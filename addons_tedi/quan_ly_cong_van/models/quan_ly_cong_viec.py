from datetime import timedelta

from pkg_resources import require

from odoo import models, fields, api
from odoo.exceptions import UserError
import odoo

class OfficeTask(models.Model):
    _inherit = 'project.task'

    don_vi = fields.Many2one('hr.department', string='Đơn vị')
    thoi_han = fields.Date(string='Thời hạn')
    noi_dung = fields.Text(string='Nội dung công việc')
    trang_thai = fields.Selection([
        ('draft', 'Nháp'),
        ('da_giao', 'Đã giao')
    ], string='trạng thái', default='draft')

    @api.model
    def create(self, vals):
        if vals.get('noi_dung') and not vals.get('name'):
            vals['name'] = vals['noi_dung']
        return super().create(vals)

    def write(self, vals):
        if 'noi_dung' in vals:
            vals['name'] = vals['noi_dung']
        return super().write(vals)

    @api.onchange('noi_dung')
    def _onchange_noi_dung_set_name(self):
        if self.noi_dung:
            self.name = self.noi_dung

    def action_create_document(self):
        outgoing_form_id = self.env.ref('quan_ly_cong_van.office_document_outgoing_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo công văn đi',
            'res_model': 'office.document',
            'view_mode': 'form',
            'view_id': outgoing_form_id,
            'target': 'new',
            'context': {
                'default_document_type': 'outgoing',
                'default_phan_loai_van_ban': 'outside',
                'default_task_id': self.id,
            },
        }

    def action_confirm_task(self):
        self.ensure_one()
        if not self.don_vi:
            raise UserError("Vui lòng chọn đơn vị xử lý để giao việc")
        self.trang_thai = 'da_giao'
        return True

    def action_delete_task(self):
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Công việc',
            'res_model': 'project.task',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref('quan_ly_cong_van.view_office_task_tree').id, 'tree'),
                (self.env.ref('quan_ly_cong_van.view_office_task_form').id, 'form'),
            ],
            'target': 'main',
        }
