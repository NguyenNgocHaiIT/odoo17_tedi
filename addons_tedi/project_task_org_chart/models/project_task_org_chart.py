from odoo import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'


    # Đếm số công việc con trực tiếp còn active (không tính done/canceled)
    direct_subtask_count = fields.Integer(
        compute="_compute_direct_subtask_count",
        store=False,
        string="Số công việc con"
    )

    @api.depends('child_ids.state')
    def _compute_direct_subtask_count(self):
        """Đếm số child_ids không ở trạng thái done/canceled."""
        for task in self:
            task.direct_subtask_count = len(task.child_ids.filtered(
                lambda x: x.state not in ('1_done', '1_canceled')
            ))

    # ==================== DATA CHO ORG CHART ==================== #

    @api.model
    def get_task_org_chart_data(self, task_id):
        """Trả về cây task cho widget org chart (dạng dict lồng nhau)."""
        task = self.sudo().browse(task_id)
        if not task.exists():
            return {}

        # Map value -> label của selection type_task (nếu có)
        type_selection_map = {}
        field_type_task = self._fields.get('type_task')
        if field_type_task and getattr(field_type_task, "selection", None):
            type_selection_map = dict(field_type_task.selection)

        def build_node(t):
            t = t.sudo()

            # Người phụ trách chính
            users = t.user_ids
            main_user = users[:1]
            main_name = main_user.name if main_user else "Chưa phân công"

            main_title = ""
            if main_user and getattr(main_user, "function", False):
                main_title = main_user.function or ""
            elif getattr(t, "department_id", False) and t.department_id:
                main_title = t.department_id.name or ""

            avatar_url = False
            if main_user and main_user.image_1920:
                avatar_url = f"/web/image/res.users/{main_user.id}/image_1920"

            # Children còn active
            active_children = t.child_ids.filtered(
                lambda c: c.state not in ('1_done', '1_canceled')
            ).sudo()

            # type_task cho front-end
            type_code = getattr(t, "type_task", False) or False
            type_label = type_selection_map.get(type_code, '') if type_code else ''

            # Tiến độ: đảm bảo là float
            progress_value = float(t.progress or 0.0)

            return {
                # dùng cho click / mở form
                'task_id': t.id,
                'responsible_id': main_user.id if main_user else False,

                # thông tin hiển thị cơ bản
                'task_name': t.name or f"Task #{t.id}",
                'stage': t.stage_id.name if t.stage_id else '',
                'deadline': fields.Date.to_string(t.date_deadline) if t.date_deadline else '',
                'responsible_name': main_name,
                'responsible_title': main_title,
                'extra_assignees': [u.name for u in users[1:]],

                # type_task cho front-end
                'type_task': type_code,
                'type_task_label': type_label,

                # tiến độ
                'progress': progress_value,

                # giữ lại các field cũ (nếu JS đang dùng)
                'name': main_name,
                'title': main_title,
                'avatar_url': avatar_url,

                # số lượng công việc con trực tiếp còn active
                'direct_subtask_count': len(active_children),

                # children (đệ quy)
                'children': [build_node(c) for c in active_children],
            }

        return build_node(task)

    # ==================== ACTION MỞ FORM CUSTOM ==================== #

    @api.model
    def action_open_task_form_by_xmlid(self, task_id, view_xmlid):
        """
        Trả về ir.actions.act_window mở đúng form view theo XMLID truyền vào.
        Dùng cho JS gọi để mở form riêng (không dùng form mặc định).
        """
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
