# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # ... [GIỮ NGUYÊN PHẦN 1, 2, 3: KHAI BÁO FIELD & GIỜ] ...

    # 1. KHAI BÁO DANH SÁCH GIỜ (Giữ nguyên)
    _HOUR_SELECTION = [
        ('0', '12:00 AM'), ('0.5', '12:30 AM'),
        ('1', '1:00 AM'), ('1.5', '1:30 AM'),
        ('2', '2:00 AM'), ('2.5', '2:30 AM'),
        ('3', '3:00 AM'), ('3.5', '3:30 AM'),
        ('4', '4:00 AM'), ('4.5', '4:30 AM'),
        ('5', '5:00 AM'), ('5.5', '5:30 AM'),
        ('6', '6:00 AM'), ('6.5', '6:30 AM'),
        ('7', '7:00 AM'), ('7.5', '7:30 AM'),
        ('8', '8:00 AM'), ('8.5', '8:30 AM'),
        ('9', '9:00 AM'), ('9.5', '9:30 AM'),
        ('10', '10:00 AM'), ('10.5', '10:30 AM'),
        ('11', '11:00 AM'), ('11.5', '11:30 AM'),
        ('12', '12:00 PM'), ('12.5', '12:30 PM'),
        ('13', '1:00 PM'), ('13.5', '1:30 PM'),
        ('14', '2:00 PM'), ('14.5', '2:30 PM'),
        ('15', '3:00 PM'), ('15.5', '3:30 PM'),
        ('16', '4:00 PM'), ('16.5', '4:30 PM'),
        ('17', '5:00 PM'), ('17.5', '5:30 PM'),
        ('18', '6:00 PM'), ('18.5', '6:30 PM'),
        ('19', '7:00 PM'), ('19.5', '7:30 PM'),
        ('20', '8:00 PM'), ('20.5', '8:30 PM'),
        ('21', '9:00 PM'), ('21.5', '9:30 PM'),
        ('22', '10:00 PM'), ('22.5', '10:30 PM'),
        ('23', '11:00 PM'), ('23.5', '11:30 PM')
    ]

    request_unit_hours = fields.Boolean(string='Custom Hours', store=True, default=True)
    request_unit_half = fields.Boolean(string='Half Day', store=True, default=False)
    request_hour_from = fields.Selection(selection=_HOUR_SELECTION, string='Giờ bắt đầu', store=True, default='7.5')
    request_hour_to = fields.Selection(selection=_HOUR_SELECTION, string='Giờ kết thúc', store=True, default='17')

    @api.onchange('request_unit_hours')
    def _onchange_request_unit_hours(self):
        if self.request_unit_hours:
            if not self.request_hour_from: self.request_hour_from = '7.5'
            if not self.request_hour_to: self.request_hour_to = '17'

    @api.constrains('request_hour_from', 'request_hour_to')
    def _check_custom_hours(self):
        for holiday in self:
            if holiday.request_unit_hours and not (holiday.date_from and holiday.date_to):
                if not holiday.request_hour_from or not holiday.request_hour_to:
                    pass

    @api.depends('request_date_from_period', 'request_hour_from', 'request_hour_to',
                 'request_date_from', 'request_date_to',
                 'request_unit_half', 'request_unit_hours', 'employee_id')
    def _compute_date_from_to(self):
        for holiday in self:
            if holiday.date_from and holiday.date_to:
                holiday.date_from = holiday.date_from
                holiday.date_to = holiday.date_to
                continue
            super(HrLeave, holiday)._compute_date_from_to()

    # ... [GIỮ NGUYÊN CÁC FIELD CUSTOM KHÁC: leaves_taken_count, manager_id...] ...

    leaves_taken_count = fields.Float(string='Số ngày phép đã nghỉ', compute='_compute_leave_stats')
    remaining_leaves_count = fields.Float(string='Số ngày phép còn lại', compute='_compute_leave_stats')
    my_history_ids = fields.Many2many('hr.leave', string='Các đơn báo của tôi', compute='_compute_my_history')

    request_date = fields.Date(string='Ngày làm đơn', default=fields.Date.context_today, readonly=True)
    report_title = fields.Char(string='Tiêu đề')
    employee_code = fields.Char(related='employee_id.employee_code', string='Mã NV', store=True)
    is_imported = fields.Boolean(string="Tạo tự động (Import)", default=False, readonly=True)

    manager_id = fields.Many2one('hr.employee', string='Người phê duyệt', compute='_compute_manager_id_by_group',
                                 store=True, readonly=False)

    # ... [GIỮ NGUYÊN Logic _get_manager_of_department, _compute_manager_id_by_group...] ...
    def _get_manager_of_department(self, department):
        if not department: return False
        group_xml_id = 'hr_attendance_tedi.group_time_off_unit_manager'
        try:
            group_id = self.env.ref(group_xml_id).id
        except ValueError:
            return False
        return self.env['hr.employee'].search([
            ('department_id', '=', department.id),
            ('user_id.groups_id', 'in', [group_id]),
            ('user_id', '!=', False)
        ], limit=1)

    @api.depends('employee_id', 'employee_id.parent_id', 'employee_id.department_id')
    def _compute_manager_id_by_group(self):
        for rec in self:
            if rec.state not in ['draft', 'confirm', 'cancel']: continue
            employee = rec.employee_id
            if not employee:
                rec.manager_id = False
                continue
            approver = False
            if employee.parent_id and employee.parent_id.id != employee.id:
                approver = employee.parent_id
            if not approver and employee.department_id:
                current_dept = employee.department_id
                approver = self._get_manager_of_department(current_dept)
                if approver and approver.id == employee.id:
                    parent_dept = current_dept.parent_id
                    if parent_dept:
                        approver = self._get_manager_of_department(parent_dept)
                    else:
                        approver = False
            rec.manager_id = approver

    # ... [GIỮ NGUYÊN Logic Phân Quyền compute...] ...
    can_approve_by_unit_manager = fields.Boolean(string='Có quyền duyệt (Unit Manager)',
                                                 compute='_compute_can_approve_by_unit_manager')
    is_officer = fields.Boolean(string="Is Officer", compute='_compute_is_officer')

    @api.depends_context('uid')
    def _compute_is_officer(self):
        for rec in self:
            rec.is_officer = self.env.user.has_group('hr_holidays.group_hr_holidays_user')

    @api.depends('state', 'employee_id')
    def _compute_can_approve_by_unit_manager(self):
        current_user = self.env.user
        current_employee = current_user.employee_id
        is_superuser = current_user.has_group('hr_holidays.group_hr_holidays_manager') or current_user._is_superuser()
        is_unit_manager = current_user.has_group('hr_attendance_tedi.group_time_off_unit_manager')

        for rec in self:
            rec.can_approve_by_unit_manager = False
            if is_superuser:
                rec.can_approve_by_unit_manager = True
                continue
            if current_employee and rec.employee_id and current_employee.id == rec.employee_id.id:
                rec.can_approve_by_unit_manager = False
                continue
            if rec.employee_id.parent_id and rec.employee_id.parent_id.id == current_employee.id:
                rec.can_approve_by_unit_manager = True
                continue
            if not is_unit_manager: continue
            if current_employee.department_id and rec.employee_id.department_id:
                manager_dept = current_employee.department_id
                employee_dept = rec.employee_id.department_id
                is_sub_department = self.env['hr.department'].search_count([
                    ('id', '=', employee_dept.id),
                    ('id', 'child_of', manager_dept.id)
                ])
                if is_sub_department > 0:
                    rec.can_approve_by_unit_manager = True
                    continue

    # =========================================================================
    # TOOL: GỬI MAIL
    # =========================================================================
    def _send_custom_leave_notification(self, template_xml_id):
        for leave in self:
            try:
                template = self.env.ref(template_xml_id, raise_if_not_found=False)
                if template:
                    template.sudo().send_mail(leave.id, force_send=True)
            except Exception as e:
                _logger.error("Lỗi gửi mail %s: %s", template_xml_id, str(e))

    # =========================================================================
    # CREATE / WRITE
    # =========================================================================
    @api.model
    def create(self, vals):
        if vals.get('date_from'):
            vals['request_date_from'] = fields.Datetime.to_datetime(vals['date_from']).date()
        if vals.get('date_to'):
            vals['request_date_to'] = fields.Datetime.to_datetime(vals['date_to']).date()
        vals['request_unit_hours'] = True
        vals['request_unit_half'] = False

        leave = super(HrLeave, self).create(vals)
        if not leave.is_imported:
            leave._send_custom_leave_notification('hr_attendance_tedi.email_template_leave_create_notification')
        return leave

    def write(self, vals):
        if len(self) == 1 and ('date_from' in vals or 'date_to' in vals):
            # ... (Giữ nguyên logic fix date của bạn) ...
            pass
        return super(HrLeave, self).write(vals)

    # =========================================================================
    # OVERRIDE CÁC HÀM DUYỆT (QUAN TRỌNG NHẤT)
    # =========================================================================

    def _check_approval_update(self, state):
        # Bypass check quyền nếu có cờ bypass trong context
        if self._context.get('bypass_manager_check'):
            return
        super(HrLeave, self)._check_approval_update(state)

    def _check_double_validation_rules(self, employees, state):
        if self._context.get('bypass_manager_check'):
            return
        super(HrLeave, self)._check_double_validation_rules(employees, state)

    def action_approve(self, check_state=True):
        # Nếu là Unit Manager, chúng ta dùng sudo() để gọi hàm cha.
        # Điều này giúp bypass các check quyền của Odoo nhưng vẫn chạy logic chuẩn.
        if self.can_approve_by_unit_manager:
            current_employee = self.env.user.employee_id
            if current_employee:
                self.sudo().write({'manager_id': current_employee.id})

            # Sử dụng sudo() + context bypass để Odoo không chặn quyền
            # nhưng VẪN CHẠY logic state chuyển đổi của Odoo
            return super(HrLeave, self.sudo().with_context(bypass_manager_check=True)).action_approve(
                check_state=check_state)

        return super(HrLeave, self).action_approve(check_state=check_state)

    def action_validate(self):
        current_employee = self.env.user.employee_id
        if current_employee:
            self.sudo().write({'manager_id': current_employee.id})

        if self.can_approve_by_unit_manager:
            # === FIX CHÍNH: KHÔNG TỰ VIẾT LẠI LOGIC VALIDATE ===
            # Thay vì write state thủ công, hãy gọi hàm action_validate gốc bằng quyền sudo.
            # Hàm gốc sẽ tự động gọi _validate_leave_request, _create_resource_leave (để trừ phép), v.v.

            # 1. Gọi super().action_validate() với sudo()
            # Context 'leave_skip_state_check' có thể cần thiết nếu Odoo chặn chuyển trạng thái
            res = super(HrLeave, self.sudo().with_context(bypass_manager_check=True)).action_validate()

            # 2. Gửi mail
            self._send_custom_leave_notification('hr_attendance_tedi.email_template_leave_approve_notification')
            return res

        # Luồng thường
        res = super(HrLeave, self).action_validate()
        self._send_custom_leave_notification('hr_attendance_tedi.email_template_leave_approve_notification')
        return res

    def action_refuse(self):
        current_employee = self.env.user.employee_id
        if current_employee:
            self.sudo().write({'manager_id': current_employee.id})

        if self.can_approve_by_unit_manager:
            res = super(HrLeave, self.sudo().with_context(bypass_manager_check=True)).action_refuse()
        else:
            res = super(HrLeave, self).action_refuse()

        self._send_custom_leave_notification('hr_attendance_tedi.email_template_leave_refuse_notification')
        return res

    # =========================================================================
    # FIX WORK ENTRY & COMPUTE STATS
    # =========================================================================

    def _validate_leave_request(self):
        # PHẢI GỌI SUPER ĐẦU TIÊN
        # Hàm super này (trong code base) chứa logic:
        # 1. holidays._create_resource_leave() -> Tạo bản ghi nghỉ để trừ ngày phép
        # 2. Tạo meeting lịch
        res = super(HrLeave, self)._validate_leave_request()

        # Logic fix work entry chồng lấn của bạn
        sudo_we = self.env['hr.work.entry'].sudo()
        for leave in self:
            if leave.employee_id and leave.date_from and leave.date_to:
                d_from_date = leave.date_from.date()
                d_to_date = leave.date_to.date()

                to_remove = sudo_we.search([
                    ('employee_id', '=', leave.employee_id.id),
                    ('date_stop', '>', leave.date_from),
                    ('date_start', '<', leave.date_to),
                    ('state', '!=', 'validated')
                ])
                if to_remove:
                    to_remove.unlink()

                # Tái tạo work entries (nếu cần thiết)
                # Lưu ý: Hàm _create_resource_leave ở super() đã đánh dấu lịch nghỉ,
                # nên generate_work_entries sẽ tạo ra entry loại nghỉ phép.
                leave.employee_id.sudo().generate_work_entries(d_from_date, d_to_date, True)

                generated_entries = sudo_we.search([
                    ('employee_id', '=', leave.employee_id.id),
                    ('date_stop', '>', leave.date_from),
                    ('date_start', '<', leave.date_to),
                    ('state', '!=', 'validated')
                ])
                if generated_entries:
                    vals = {'state': 'validated', 'leave_id': leave.id}
                    if leave.holiday_status_id.work_entry_type_id:
                        vals['work_entry_type_id'] = leave.holiday_status_id.work_entry_type_id.id
                    generated_entries.write(vals)
        return res

    # THÊM 'state' VÀO DEPENDS ĐỂ SỐ LIỆU CẬP NHẬT NGAY KHI DUYỆT
    @api.depends('employee_id', 'holiday_status_id', 'date_from', 'state')
    def _compute_leave_stats(self):
        for rec in self:
            rec.leaves_taken_count = 0.0
            rec.remaining_leaves_count = 0.0

            # Chỉ chạy khi đã chọn Nhân viên và Loại nghỉ
            if rec.employee_id and rec.holiday_status_id:
                try:
                    # 1. Xác định ngày để kiểm tra số dư (Ngày bắt đầu nghỉ hoặc Hôm nay)
                    check_date = rec.date_from.date() if rec.date_from else fields.Date.context_today(rec)

                    # 2. Tạo một bản ghi Loại nghỉ "ảo" với Context của nhân viên đó
                    # Đây là cách Odoo tính số liệu cho Header "còn X trong tổng số Y"
                    leave_type_with_ctx = rec.holiday_status_id.sudo().with_context(
                        employee_id=rec.employee_id.id,
                        date=check_date
                    )

                    # 3. Lấy giá trị trực tiếp từ trường compute của Odoo
                    # virtual_remaining_leaves: Số ngày/giờ còn lại (đã trừ các đơn chờ duyệt)
                    # leaves_taken: Số ngày/giờ đã nghỉ
                    remaining = leave_type_with_ctx.virtual_remaining_leaves
                    taken = leave_type_with_ctx.leaves_taken

                    # 4. Gán giá trị
                    rec.remaining_leaves_count = remaining
                    rec.leaves_taken_count = taken

                    # --- DEBUG LOG (Kiểm tra trong Log Server nếu vẫn sai) ---
                    # _logger.info(f"User: {rec.employee_id.name} | Type: {rec.holiday_status_id.name} | Remaining: {remaining}")

                except Exception as e:
                    _logger.error("Lỗi tính số dư phép (ID %s): %s", rec.id, str(e))
                    rec.remaining_leaves_count = 0.0

    @api.depends('employee_id')
    def _compute_my_history(self):
        for rec in self:
            if rec.employee_id:
                domain = [('employee_id', '=', rec.employee_id.id), ('id', '!=', rec.id if rec.id else False)]
                rec.my_history_ids = self.env['hr.leave'].search(domain, order='create_date desc', limit=10)
            else:
                rec.my_history_ids = False