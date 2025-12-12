# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from markupsafe import Markup
from werkzeug.urls import url_encode
from odoo.exceptions import UserError
import base64
import logging
_logger = logging.getLogger(__name__)


class HrEmployeePrivate(models.Model):
    _inherit = "hr.employee"

    # ==== Field custom mở rộng ====
    citizen_id = fields.Char(string="Số CMND")
    citizen_issue_date = fields.Date(string="Cấp ngày")
    citizen_issuer = fields.Char(string="Cấp tại")
    phone_personal = fields.Char(string="Điện thoại")
    bank_account = fields.Char(string="Tài khoản số")
    bank_name = fields.Char(string="Ngân hàng")
    email_personal = fields.Char(string="Email")
    household_address = fields.Char(string="Địa chỉ thường trú")
    occupation = fields.Char(string="Nghề nghiệp")
    ethnicity = fields.Char(string="Dân tộc")

    # ==== One2many ====
    education_ids = fields.One2many("hr.employee.education", "employee_id", string="Trình độ chuyên môn")
    certificate_ids = fields.One2many("hr.employee.certificate", "employee_id", string="Chứng chỉ hành nghề")
    trip_ids = fields.One2many("hr.employee.trip", "employee_id", string="Xuất/Nhập cảnh")
    work_process_tedi_ids = fields.One2many("hr.employee.work.process.tedi", "employee_id", string="Quá trình công tác tại TEDI")
    work_process_old_ids  = fields.One2many("hr.employee.work.process.old",  "employee_id", string="Quá trình công tác tại đơn vị cũ")
    experience_ids        = fields.One2many("hr.employee.experience",       "employee_id", string="Kinh nghiệm công việc liên quan")
    reward_discipline_ids = fields.One2many("hr.employee.reward.discipline","employee_id", string="Khen thưởng - Kỷ luật")
    training_ids = fields.One2many("hr.employee.training", "employee_id", string="Quá trình đào tạo")

    tedi_training_history_ids = fields.One2many(
        "hr.employee.training.tedi",
        "employee_id",
        string="Quá trình đào tạo tại TEDI"
    )

    # Onchange để đánh số lại STT khi giao diện thay đổi (giống logic bạn gửi trước đó)
    @api.onchange('tedi_training_history_ids')
    def _onchange_tedi_training_seq(self):
        for rec in self:
            for idx, line in enumerate(rec.tedi_training_history_ids, start=1):
                line.stt = idx

    # ==== Đảng – Đoàn thể (liên kết với hr.party.cell / hr.party.title) ====
    party_member = fields.Boolean(string="Là Đảng viên?")
    party_join_date = fields.Date(string="Ngày kết nạp Đảng")
    party_official_date = fields.Date(string="Ngày chuyển chính thức")
    party_title_id = fields.Many2one("hr.party.title", string="Chức danh Đảng")
    party_cell_id = fields.Many2one("hr.party.cell", string="Chi bộ đang sinh hoạt")
    party_profile_no = fields.Char(string="Số lý lịch Đảng viên")
    party_card_no = fields.Char(string="Số thẻ Đảng viên")
    party_medal_no = fields.Char(string="Số Huy hiệu Đảng")

    union_member = fields.Boolean(string="Công đoàn?")
    union_join_date = fields.Date(string="Ngày vào Công đoàn")
    union_profile_no = fields.Char(string="Số lý lịch Công đoàn")
    union_card_no = fields.Char(string="Số thẻ Công đoàn")

    youth_member = fields.Boolean(string="Đoàn thanh niên?")
    youth_join_date = fields.Date(string="Ngày vào Đoàn")
    youth_card_no = fields.Char(string="Số thẻ Đoàn")

    # ==== Mã nhân viên ====
    employee_code = fields.Char(string="Employee Code", readonly=False, copy=False)



    @api.onchange('name')
    def _onchange_name_generate_code(self):
        if not self.id and not self.employee_code:
            last_employee = self.env['hr.employee'].search(
                [('employee_code', '=like', 'NV%')],
                order='employee_code desc',
                limit=1
            )
            max_number = 0
            if last_employee and last_employee.employee_code:
                try:
                    max_number = int(last_employee.employee_code[2:])
                except ValueError:
                    pass
            self.employee_code = f"NV{max_number + 1:03d}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('employee_code'):
                last_employee = self.search([('employee_code', '=like', 'NV%')], order='employee_code desc', limit=1)
                max_number = 0
                if last_employee and last_employee.employee_code:
                    try:
                        max_number = int(last_employee.employee_code[2:])
                    except ValueError:
                        pass
                vals['employee_code'] = f"NV{max_number + 1:03d}"

        # giữ nguyên đoạn đồng bộ user_id của bạn
        for vals in vals_list:
            if vals.get('user_id'):
                user = self.env['res.users'].browse(vals['user_id'])
                vals.update(self._sync_user(user, bool(vals.get('image_1920'))))
                vals['name'] = vals.get('name', user.name)
                self._remove_work_contact_id(user, vals.get('company_id'))

        employees = super().create(vals_list)

        employees.filtered(lambda e: not e.work_contact_id).sudo()._create_work_contacts()
        for employee_sudo in employees.sudo():
            if not employee_sudo.image_1920 and self.env['ir.ui.view'].sudo(False).check_access_rights('write', raise_exception=False):
                employee_sudo.image_1920 = employee_sudo._avatar_generate_svg()
                employee_sudo.work_contact_id.image_1920 = employee_sudo.image_1920

        if self.env.context.get('salary_simulation'):
            return employees

        employee_departments = employees.department_id
        if employee_departments:
            self.env['discuss.channel'].sudo().search([
                ('subscription_department_ids', 'in', employee_departments.ids)
            ])._subscribe_users_automatically()

        onboarding_notes_bodies = {}
        hr_root_menu = self.env.ref('hr.menu_hr_root')
        for employee in employees:
            url = '/web#%s' % url_encode({
                'action': 'hr.plan_wizard_action',
                'active_id': employee.id,
                'active_model': 'hr.employee',
                'menu_id': hr_root_menu.id,
            })
            onboarding_notes_bodies[employee.id] = Markup(_(
                '<b>Congratulations!</b> May I recommend you to setup an <a href="%s">onboarding plan?</a>',
            )) % url
        employees._message_log_batch(onboarding_notes_bodies)
        return employees

    # ==== Onchange: đánh số sequence + STT cho o2m (hiển thị đúng ngay khi Add a line) ====
    @api.onchange('education_ids')
    def _onchange_edu_seq(self):
        for rec in self:
            for idx, line in enumerate(rec.education_ids, start=1):
                if hasattr(line, 'sequence'):
                    line.sequence = idx
                if hasattr(line, 'stt'):
                    line.stt = idx

    @api.onchange('certificate_ids')
    def _onchange_cert_seq(self):
        for rec in self:
            for idx, line in enumerate(rec.certificate_ids, start=1):
                if hasattr(line, 'sequence'):
                    line.sequence = idx
                if hasattr(line, 'stt'):
                    line.stt = idx

    @api.onchange('trip_ids')
    def _onchange_trip_seq(self):
        for rec in self:
            for idx, line in enumerate(rec.trip_ids, start=1):
                if hasattr(line, 'sequence'):
                    line.sequence = idx
                if hasattr(line, 'stt'):
                    line.stt = idx

    def action_open_create_user(self):
        self.ensure_one()

        # --- Lấy view res.users ưu tiên ---
        view = None
        try:
            view = self.env.ref('hr.res_users_view_form')
        except Exception:
            try:
                view = self.env.ref('base.view_users_form')
            except Exception:
                view = self.env['ir.ui.view'].search([
                    ('model', '=', 'res.users'),
                    ('type', '=', 'form'),
                    ('mode', '=', 'primary'),
                ], limit=1)

        _logger.info(f"Opening res.users form view ID: {view.id}")

        # --- Chuẩn bị image base64 ---
        default_image = False
        if self.image_1920:
            # Nếu image là bytes, chuyển sang base64 string
            if isinstance(self.image_1920, bytes):
                default_image = base64.b64encode(self.image_1920).decode('utf-8')
            else:
                default_image = self.image_1920

        # --- Trả về action ---
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo người dùng cho %s') % self.name,
            'res_model': 'res.users',
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'current',  # mở full page, không popup
            'context': {
                'default_name': self.name,
                'default_login': self.work_email,
                'default_email': self.work_email,
                'default_image_1920': default_image,
                'default_employee_ids': [(4, self.id)],
                'defaylt_password': 1,
                'form_view_initial_mode': 'edit',
                # Đảm bảo avatar hiển thị ngay
                'show_hr_icon_display': True,
            },
        }


