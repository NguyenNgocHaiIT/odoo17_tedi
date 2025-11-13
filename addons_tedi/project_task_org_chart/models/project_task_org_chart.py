from odoo import models, fields, api

class ProjectTask(models.Model):
    _inherit = 'project.task'

    org_chart = fields.Char(compute="_compute_org_chart", readonly=True)
    direct_subtask_count = fields.Integer(compute="_compute_direct_subtask_count", store=False)

    @api.depends('child_ids.state')
    def _compute_direct_subtask_count(self):
        for task in self:
            task.direct_subtask_count = len(task.child_ids.filtered(
                lambda x: x.state not in ('1_done', '1_canceled')
            ))

    def _compute_org_chart(self):
        for task in self:
            task.org_chart = ""

    @api.model
    def get_task_org_chart_data(self, task_id):
        task = self.sudo().browse(task_id)
        if not task.exists():
            return {}

        # Map value -> label của selection type_task
        type_selection_map = dict(self._fields['type_task'].selection)

        def build_node(t):
            users = t.user_ids.sudo()
            main_user = users[:1]
            main_name = main_user.name if main_user else "Chưa phân công"
            main_title = (getattr(main_user, 'function', False) or '') if main_user else ''
            if not main_title and hasattr(t, 'department_id') and t.department_id:
                main_title = t.department_id.name or ''
            avatar_url = (main_user and main_user.image_1920) and f"/web/image/res.users/{main_user.id}/image_1920" or False

            active_children = [c.sudo() for c in t.child_ids if c.state not in ('1_done', '1_canceled')]

            # Lấy code & label của type_task
            type_code = t.type_task or False
            type_label = type_selection_map.get(type_code, '') if type_code else ''

            # Tiến độ: đảm bảo không None
            progress_value = float(t.progress or 0.0)

            return {
                # dùng cho click:
                'task_id': t.id,
                'responsible_id': main_user.id if main_user else False,

                # hiển thị:
                'task_name': t.name or f"Task #{t.id}",
                'stage': t.stage_id.name if t.stage_id else '',
                'deadline': fields.Date.to_string(t.date_deadline) if t.date_deadline else '',
                'responsible_name': main_name,
                'responsible_title': main_title,
                'extra_assignees': [u.name for u in users[1:]],

                # type_task cho front-end
                'type_task': type_code,
                'type_task_label': type_label,

                # progress cho front-end
                'progress': progress_value,

                # giữ lại các field cũ:
                'name': main_name,
                'title': main_title,
                'avatar_url': avatar_url,
                'direct_subtask_count': len(active_children),
                'children': [build_node(c) for c in active_children],
            }

        return build_node(task)

    @api.model
    def action_open_task_form_by_xmlid(self, task_id, view_xmlid):
        """Trả về ir.actions.act_window mở đúng view form theo XMLID."""
        task = self.browse(task_id).exists()
        if not task:
            return False
        view = self.env.ref(view_xmlid, raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': task.id,
            'views': [[(view and view.id) or False, 'form']],
            'view_mode': 'form',
            'target': 'current',
        }
