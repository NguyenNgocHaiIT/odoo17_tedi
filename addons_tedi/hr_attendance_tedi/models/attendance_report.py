# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # =========================================================================
    # 1. KHAI BÁO DANH SÁCH GIỜ
    # =========================================================================
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

    # =========================================================================
    # 2. CORE FIX: ỔN ĐỊNH LOGIC TÍNH GIỜ
    # =========================================================================

    request_unit_hours = fields.Boolean(
        string='Custom Hours',
        store=True,
        default=True
    )

    request_unit_half = fields.Boolean(
        string='Half Day',
        store=True,
        default=False
    )

    request_hour_from = fields.Selection(
        selection=_HOUR_SELECTION,
        string='Giờ bắt đầu',
        store=True,
        readonly=False,
        default='7.5'  # Set mặc định là 7:30 sáng (hoặc giờ bắt đầu làm việc của cty)
    )
    request_hour_to = fields.Selection(
        selection=_HOUR_SELECTION,
        string='Giờ kết thúc',
        store=True,
        readonly=False,
        default='17'  # Set mặc định là 5:00 chiều
    )

    # THÊM HÀM NÀY ĐỂ FIX LỖI KHI BẤM DUYỆT/TỪ CHỐI
    @api.onchange('request_unit_hours')
    def _onchange_request_unit_hours(self):
        if self.request_unit_hours:
            if not self.request_hour_from:
                self.request_hour_from = '7.5'  # Giá trị mặc định an toàn
            if not self.request_hour_to:
                self.request_hour_to = '17'  # Giá trị mặc định an toàn

    @api.constrains('request_hour_from', 'request_hour_to')
    def _check_custom_hours(self):
        for holiday in self:
            if holiday.request_unit_hours:
                # Nếu có date_from/date_to rồi thì coi như hợp lệ, không bắt bẻ field giờ nữa
                if holiday.date_from and holiday.date_to:
                    continue

                # Nếu chưa có thì mới check
                if not holiday.request_hour_from or not holiday.request_hour_to:
                    pass  # Bỏ qua luôn, không raise ValidationError

    @api.depends('request_date_from_period', 'request_hour_from', 'request_hour_to',
                 'request_date_from', 'request_date_to',
                 'request_unit_half', 'request_unit_hours', 'employee_id')
    def _compute_date_from_to(self):
        for holiday in self:
            # FIX QUAN TRỌNG:
            # Nếu bản ghi đã có ngày giờ cụ thể (do user chọn), giữ nguyên, không để Odoo tính lại.
            if holiday.date_from and holiday.date_to:
                holiday.date_from = holiday.date_from
                holiday.date_to = holiday.date_to
                continue

            # Chỉ gọi super khi đang tạo mới chưa có dữ liệu hoặc thay đổi chế độ
            super(HrLeave, holiday)._compute_date_from_to()

    # =========================================================================
    # 3. FIELD CUSTOM
    # =========================================================================
    leaves_taken_count = fields.Float(string='Số ngày phép đã nghỉ', compute='_compute_leave_stats')
    remaining_leaves_count = fields.Float(string='Số ngày phép còn lại', compute='_compute_leave_stats')
    my_history_ids = fields.Many2many('hr.leave', string='Các đơn báo của tôi', compute='_compute_my_history')

    request_date = fields.Date(string='Ngày làm đơn', default=fields.Date.context_today, readonly=True)
    report_title = fields.Char(string='Tiêu đề')
    employee_code = fields.Char(related='employee_id.employee_code', string='Mã NV', store=True)

    is_imported = fields.Boolean(
        string="Tạo tự động (Import)",
        default=False,
        readonly=True,
        help="Đánh dấu đơn này được tạo tự động từ file Excel chấm công"
    )

    manager_id = fields.Many2one(
        'hr.employee',
        string='Người phê duyệt',
        compute='_compute_manager_id_by_group',
        store=True,
        readonly=False,
        help="Người trong phòng ban nắm giữ quyền Unit Manager."
    )

    def _get_manager_of_department(self, department):
        """
        Hàm phụ: Tìm nhân viên trong 1 phòng ban cụ thể
        mà User của họ có nhóm quyền 'group_time_off_unit_manager'.
        """
        if not department:
            return False

        # 1. Lấy ID của nhóm quyền Unit Manager
        # Lưu ý: Thay 'ten_module_cua_ban' bằng tên thư mục module thực tế của bạn
        # Ví dụ: 'hr_attendance_tedi' hoặc 'quan_ly_nghi_phep'
        group_xml_id = 'hr_attendance_tedi.group_time_off_unit_manager'

        try:
            group_id = self.env.ref(group_xml_id).id
        except ValueError:
            # Phòng trường hợp gõ sai tên module
            return False

        # 2. Tìm Employee thuộc phòng ban này VÀ User của họ có Group đó
        manager = self.env['hr.employee'].search([
            ('department_id', '=', department.id),
            ('user_id.groups_id', 'in', [group_id]),
            ('user_id', '!=', False)  # Phải có user mới check được quyền
        ], limit=1)  # Lấy người đầu tiên tìm thấy

        return manager

    @api.depends('employee_id', 'employee_id.department_id')
    def _compute_manager_id_by_group(self):
        for rec in self:
            # Chỉ chạy khi đơn mới
            if rec.state not in ['draft', 'confirm', 'cancel']:
                continue

            employee = rec.employee_id
            if not employee or not employee.department_id:
                rec.manager_id = False
                continue

            # BƯỚC 1: Tìm người nắm quyền Unit Manager trong phòng của nhân viên
            current_dept = employee.department_id
            approver = self._get_manager_of_department(current_dept)

            # BƯỚC 2: Kiểm tra nếu người làm đơn CHÍNH LÀ người vừa tìm thấy
            # (Tức là Trưởng phòng đang làm đơn)
            if approver and approver.id == employee.id:
                # -> Tìm người nắm quyền ở phòng ban cha
                parent_dept = current_dept.parent_id
                if parent_dept:
                    approver = self._get_manager_of_department(parent_dept)
                else:
                    # Hết cấp cha -> Không ai duyệt
                    approver = False

            rec.manager_id = approver
    # =========================================================================
    # 4. FIELD COMPUTE PHÂN QUYỀN
    # =========================================================================
    can_approve_by_unit_manager = fields.Boolean(
        string='Có quyền duyệt (Unit Manager)',
        compute='_compute_can_approve_by_unit_manager'
    )

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
            if not is_unit_manager:
                continue
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
    # 5. LOGIC XỬ LÝ (CREATE/WRITE) - ĐÃ LOẠI BỎ CODE GÂY LỖI
    # =========================================================================

    @api.model
    def create(self, vals):
        if vals.get('date_from'):
            vals['request_date_from'] = fields.Datetime.to_datetime(vals['date_from']).date()
        if vals.get('date_to'):
            vals['request_date_to'] = fields.Datetime.to_datetime(vals['date_to']).date()

        # Đảm bảo logic tính giờ được bật, nhưng KHÔNG ép về '0'
        vals['request_unit_hours'] = True
        vals['request_unit_half'] = False

        return super(HrLeave, self).create(vals)

    def write(self, vals):
        if len(self) == 1 and ('date_from' in vals or 'date_to' in vals):
            new_date_from_dt = vals.get('date_from') and fields.Datetime.to_datetime(
                vals['date_from']) or self.date_from
            new_date_to_dt = vals.get('date_to') and fields.Datetime.to_datetime(vals['date_to']) or self.date_to

            if new_date_from_dt and new_date_to_dt and new_date_from_dt > new_date_to_dt:
                if 'date_from' in vals:
                    new_date_to_dt = new_date_from_dt
                    vals['date_to'] = vals['date_from']
                elif 'date_to' in vals:
                    new_date_from_dt = new_date_to_dt
                    vals['date_from'] = vals['date_to']

            if new_date_from_dt:
                vals['request_date_from'] = new_date_from_dt.date()
            if new_date_to_dt:
                vals['request_date_to'] = new_date_to_dt.date()

        return super(HrLeave, self).write(vals)

    # =========================================================================
    # 6. OVERRIDE CÁC HÀM DUYỆT
    # =========================================================================

    def _check_approval_update(self, state):
        if self._context.get('bypass_manager_check'):
            return
        super(HrLeave, self)._check_approval_update(state)

    def _check_double_validation_rules(self, employees, state):
        if self._context.get('bypass_manager_check'):
            return
        super(HrLeave, self)._check_double_validation_rules(employees, state)

    def _send_refusal_email(self):
        # _logger.info("========== BAT DAU GOI HAM GUI MAIL ==========")
        try:
            template = self.env.ref('hr_attendance_tedi.email_template_leave_refuse_notification',
                                    raise_if_not_found=False)
            if not template:
                _logger.error("!!! KHONG TIM THAY XML ID: hr_attendance_tedi.email_template_leave_refuse_notification")
                return

            for leave in self:
                _logger.info("Dang gui mail cho don ID: %s - Email NV: %s", leave.id, leave.employee_id.work_email)
                if leave.employee_id.work_email:
                    template.sudo().send_mail(leave.id, force_send=True)
                    _logger.info("--- GUI MAIL THANH CONG ---")
                else:
                    _logger.warning("--- NV KHONG CO EMAIL ---")
        except Exception as e:
            _logger.error("!!! LOI KHI GUI MAIL: %s", str(e))

    def action_refuse(self):
        # _logger.info("========== CLICK NUT TU CHOI ==========")
        current_employee = self.env.user.employee_id

        # In ra de check quyen Unit Manager
        # _logger.info("User: %s - can_approve_by_unit_manager: %s", self.env.user.name, self.can_approve_by_unit_manager)

        if current_employee:
            self.sudo().write({'manager_id': current_employee.id})

        if self.can_approve_by_unit_manager:
            # _logger.info("Duyet theo luong Unit Manager")
            self.sudo().with_context(bypass_manager_check=True).write({'state': 'refuse'})
            res = True
        else:
            # _logger.info("Duyet theo luong chuan Odoo")
            res = super(HrLeave, self).action_refuse()

        # Goi gui mail
        self._send_refusal_email()
        return res


    def action_approve(self):
        if self.can_approve_by_unit_manager:
            current_employee = self.env.user.employee_id
            if current_employee:
                self.sudo().write({'manager_id': current_employee.id})
            for leave in self:
                validation_type = leave.holiday_status_id.leave_validation_type
                if validation_type == 'both':
                    leave.sudo().with_context(bypass_manager_check=True).write({
                        'state': 'validate1',
                        'first_approver_id': current_employee.id,
                    })
                    leave.activity_update()
                else:
                    leave.action_validate()
            return True
        return super(HrLeave, self).action_approve()

    def action_validate(self):
        current_employee = self.env.user.employee_id
        if current_employee:
            self.sudo().write({'manager_id': current_employee.id})
        if self.can_approve_by_unit_manager:
            self.sudo().with_context(bypass_manager_check=True).write({'state': 'validate'})
            self.sudo()._validate_leave_request()
            self.activity_update()
            return True
        return super(HrLeave, self).action_validate()



    # =========================================================================
    # 7. FIX WORK ENTRY CHỒNG LẤN
    # =========================================================================

    def _validate_leave_request(self):
        res = super(HrLeave, self)._validate_leave_request()
        sudo_we = self.env['hr.work.entry'].sudo()
        for leave in self:
            if leave.employee_id and leave.date_from and leave.date_to:
                d_from_date = leave.date_from.date()
                d_to_date = leave.date_to.date()

                # Xóa entry cũ
                to_remove = sudo_we.search([
                    ('employee_id', '=', leave.employee_id.id),
                    ('date_stop', '>', leave.date_from),
                    ('date_start', '<', leave.date_to),
                    ('state', '!=', 'validated')
                ])
                if to_remove:
                    to_remove.unlink()

                # Tái tạo
                leave.employee_id.sudo().generate_work_entries(d_from_date, d_to_date, True)

                # Cập nhật
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

    # =========================================================================
    # 8. CÁC HÀM COMPUTE KHÁC
    # =========================================================================
    @api.depends('employee_id', 'holiday_status_id', 'date_from')
    def _compute_leave_stats(self):
        for rec in self:
            rec.leaves_taken_count = 0.0
            rec.remaining_leaves_count = 0.0
            if rec.employee_id and rec.holiday_status_id:
                leave_type = rec.holiday_status_id.with_context(
                    employee_id=rec.employee_id.id,
                    date=rec.date_from or fields.Date.today()
                )
                rec.remaining_leaves_count = leave_type.virtual_remaining_leaves
                rec.leaves_taken_count = leave_type.leaves_taken

    @api.depends('employee_id')
    def _compute_my_history(self):
        for rec in self:
            if rec.employee_id:
                domain = [
                    ('employee_id', '=', rec.employee_id.id),
                    ('id', '!=', rec.id if rec.id else False)
                ]
                rec.my_history_ids = self.env['hr.leave'].search(domain, order='create_date desc', limit=10)
            else:
                rec.my_history_ids = False