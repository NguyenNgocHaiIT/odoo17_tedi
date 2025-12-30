from odoo import api, models, fields
from odoo.exceptions import ValidationError
from datetime import timedelta

class CalendarOutside(models.Model):
    _name = 'calendar.outside'

    name = fields.Char(string='Chủ đề cuộc họp')
    location = fields.Many2one('calendar.location', string='Địa điểm')
    start = fields.Datetime(string='Thời gian bắt đầu')
    stop = fields.Datetime(string='Thời gian kết thúc')
    user_id = fields.Many2one('hr.employee', string='Người chủ trì')
    partner_ids = fields.Many2many('hr.employee', string='Thành phần tham gia')
    lanh_dao = fields.Many2one('hr.employee', string='Lãnh đạo')
    color = fields.Integer(string='Màu', default=lambda self: 0)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('approved', 'Đã duyệt'),
        ('canceled', 'Đã hủy')
    ], string='Trạng thái', default='draft', tracking=True)

    can_approve_meeting = fields.Boolean(compute="_compute_permissions")

    is_current_user_creator = fields.Boolean(
        compute='_compute_is_current_user_creator',
        string='Is Current User Creator',
        store=False
    )

    @api.depends_context('uid')
    def _compute_is_current_user_creator(self):
        current_user = self.env.user
        for rec in self:
            rec.is_current_user_creator = rec.create_uid.id == current_user.id

    @api.depends_context('uid')
    @api.depends('create_uid', 'state')
    def _compute_permissions(self):
        current_user = self.env.user

        # ID của Group
        group_dept_manager = 'Quan_ly_lich_hop.group_calendar_department_manager'
        group_room_manager = 'Quan_ly_lich_hop.group_meeting_room_manager'

        is_admin = current_user.has_group('base.group_system')
        is_dept_manager = current_user.has_group(group_dept_manager)
        is_room_manager = current_user.has_group(group_room_manager)

        # Lấy phòng ban hiện tại của user đang login
        current_employee = self.env['hr.employee'].search([('user_id', '=', current_user.id)], limit=1)
        current_dept = current_employee.department_id if current_employee else False

        for rec in self:
            # --- A. DUYỆT LỊCH HỌP ---
            can_meeting = False

            # Tìm phòng ban người tạo phiếu
            creator_employee = self.env['hr.employee'].search([('user_id', '=', rec.create_uid.id)], limit=1)
            creator_dept = creator_employee.department_id if creator_employee else False

            # SỬA: Thêm "or is_room_manager" vào điều kiện cao nhất
            # Nếu là Admin HOẶC Quản lý phòng họp -> Duyệt tất cả
            if is_admin or is_room_manager:
                can_meeting = True

            # Nếu không phải cấp cao, mới xét đến cấp Quản lý đơn vị (check cùng phòng ban)
            elif is_dept_manager:
                if current_dept and creator_dept and current_dept.id == creator_dept.id:
                    can_meeting = True

            rec.can_approve_meeting = can_meeting

    @api.constrains('start', 'stop')
    def _check_start_stop(self):
        for rec in self:
            if rec.start and rec.stop and rec.start > rec.stop:
                raise ValidationError("Thời gian bắt đầu không được lớn hơn thời gian kết thúc.")

    def approve(self):
        for event in self:
            # Ví dụ: đánh dấu trạng thái đã duyệt
            event.write({'state': 'approved'})
        return True

    @api.model
    def create(self, vals):
        record = super().create(vals)
        record.color = record.id % 12
        return record


class CalendarLocation(models.Model):
    _name = 'calendar.location'

    name = fields.Char(string='Tên địa điểm')