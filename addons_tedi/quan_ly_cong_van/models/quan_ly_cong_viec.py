from datetime import timedelta

from pkg_resources import require

from odoo import models, fields, api
from odoo.exceptions import UserError
import odoo

class OfficeTask(models.Model):
    _inherit = 'project.task'

    don_vi = fields.Many2one('hr.department', string='Đơn vị')

    trang_thai = fields.Selection([
        ('draft', 'Nháp'),
        ('da_giao', 'Đã giao')
    ], string='trạng thái', default='draft')

    task_type = fields.Selection([
        ('cong_van_di', 'Công việc của công văn đi'),
        ('quyet_dinh', 'công việc của quyết định'),
        ('cong_van_di_noi_bo', 'công việc của công văn đi nội bộ'),
    ], string='Loại công việc')

    @api.model
    def create(self, vals):
        vals['project_id'] = False
        return super().create(vals)


    def write(self, vals):
        return super().write(vals)

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
                'default_task_id': self.id,
                'default_trich_yeu': self.name,
            },
        }

    def action_create_resolution(self):
        resolution_form_id = self.env.ref('quan_ly_cong_van.office_document_resolution_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo quyết định',
            'res_model': 'office.document',
            'view_mode': 'form',
            'view_id': resolution_form_id,
            'target': 'new',
            'context': {
                'default_document_type': 'resolution',
                'default_task_id': self.id,
                'default_trich_yeu': self.name,
            },
        }

    def action_create_internal_document(self):
        outgoing_form_id = self.env.ref('quan_ly_cong_van.office_document_outgoing_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tạo công văn đi',
            'res_model': 'office.document',
            'view_mode': 'form',
            'view_id': outgoing_form_id,
            'target': 'new',
            'context': {
                'default_document_type': 'outgoing_internal',
                'default_task_id': self.id,
                'default_trich_yeu': self.name,
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

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'task_type' in fields_list and self._context.get('task_type'):
            res['task_type'] = self._context.get('task_type')
        return res