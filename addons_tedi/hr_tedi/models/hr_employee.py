# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from markupsafe import Markup
from werkzeug.urls import url_encode
from odoo.exceptions import UserError
import base64
import logging
_logger = logging.getLogger(__name__)

class ResEthnic(models.Model):
    _name = 'res.ethnic'
    _description = 'Danh mục Dân tộc'
    _order = 'name'

    name = fields.Char(string="Tên dân tộc", required=True)
    code = fields.Char(string="Mã", help="Ví dụ: KINH, TAY, THAI...")
    active = fields.Boolean(string="Đang sử dụng", default=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tên dân tộc đã tồn tại!'),
        ('code_uniq', 'unique (code)', 'Mã dân tộc phải là duy nhất!')
    ]

class HrPosition(models.Model):
    _name = 'hr.position'
    _description = 'Danh mục Chức vụ'
    _order = 'name'

    name = fields.Char(string="Tên chức vụ", required=True)
    code = fields.Char(string="Mã chức vụ")
    description = fields.Text(string="Mô tả")
    active = fields.Boolean(string="Đang sử dụng", default=True)

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'Mã chức vụ phải là duy nhất!')
    ]

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
    folk_id = fields.Many2one(
        'res.ethnic',
        string="Dân tộc",
        help="Chọn dân tộc từ danh mục"
    )

    # ==== One2many ====
    education_ids = fields.One2many("hr.employee.education", "employee_id", string="Trình độ chuyên môn")
    certificate_ids = fields.One2many("hr.employee.certificate", "employee_id", string="Chứng chỉ hành nghề")
    trip_ids = fields.One2many("hr.employee.trip", "employee_id", string="Xuất/Nhập cảnh")
    work_process_tedi_ids = fields.One2many("hr.employee.work.process.tedi", "employee_id", string="Quá trình công tác tại TEDI")
    work_process_old_ids  = fields.One2many("hr.employee.work.process.old",  "employee_id", string="Quá trình công tác tại đơn vị cũ")
    experience_ids        = fields.One2many("hr.employee.experience",       "employee_id", string="Kinh nghiệm công việc liên quan")
    reward_discipline_ids = fields.One2many("hr.employee.reward.discipline","employee_id", string="Khen thưởng - Kỷ luật")
    training_ids = fields.One2many("hr.employee.training", "employee_id", string="Quá trình đào tạo")
    external_experience_ids = fields.One2many(
        "hr.external.experience", "employee_id", string="Kinh nghiệm Bên ngoài"
    )
    tedi_training_history_ids = fields.One2many(
        "hr.employee.training.tedi",
        "employee_id",
        string="Quá trình đào tạo tại TEDI"
    )
    position_id = fields.Many2one(
        'hr.position',
        string="Chức vụ",
        help="Chọn chức vụ từ danh mục (VD: Giám đốc, Trưởng phòng, Chuyên viên...)"
    )

    personal_tax_code = fields.Char(string="Mã số thuế")

    @api.onchange('citizen_id')
    def _onchange_citizen_id_update_tax_code(self):
        """
        Khi nhập số CCCD/CMND:
        - Nếu Mã số thuế đang trống -> Tự động điền bằng số CCCD.
        - Nếu Mã số thuế đã có dữ liệu -> Giữ nguyên (để người dùng có thể nhập khác nếu muốn).
        """
        for rec in self:
            if rec.citizen_id and not rec.personal_tax_code:
                rec.personal_tax_code = rec.citizen_id

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
    union_title_id = fields.Many2one("hr.union.title", string="Chức danh Công đoàn")

    youth_member = fields.Boolean(string="Đoàn thanh niên?")
    youth_join_date = fields.Date(string="Ngày vào Đoàn")
    youth_card_no = fields.Char(string="Số thẻ Đoàn")
    youth_title_id = fields.Many2one("hr.youth.union.title", string="Chức danh Đoàn")

    # ==== Quân ngũ ====
    is_military = fields.Boolean(string="Đã tham gia quân ngũ?")
    military_start_date = fields.Date(string="Ngày nhập ngũ")
    military_end_date = fields.Date(string="Ngày xuất ngũ")
    military_rank_id = fields.Many2one(
        'hr.military.rank',
        string="Chức danh/Cấp bậc"
    )

    # ==== Thuong binh ====
    is_policy_beneficiary = fields.Boolean(string="Thuộc diện chính sách?")
    policy_type = fields.Selection([
        ('wounded', 'Thương binh'),  # Là thương binh
        ('sick', 'Bệnh binh'),  # Là bệnh binh
        ('martyr_family', 'Thân nhân Liệt sĩ')  # Quan hệ với liệt sĩ
    ], string="Loại đối tượng")

    policy_rank = fields.Char(string="Hạng (Thương/Bệnh binh)", help="Ví dụ: 1/4, 2/4...")
    # Dành cho thân nhân liệt sĩ
    policy_martyr_relation = fields.Char(string="Quan hệ với Liệt sĩ", help="Ví dụ: Con đẻ, Vợ/Chồng...")
    # Thông tin chung về giấy tờ
    policy_card_no = fields.Char(string="Số thẻ Thương/Bệnh binh/Liệt sĩ")
    policy_issue_date = fields.Date(string="Ngày cấp thẻ")
    policy_issue_place = fields.Char(string="Nơi cấp")

    # ==== Mã nhân viên ====
    employee_code = fields.Char(string="Employee Code", readonly=False, copy=False)



    attachment_ids = fields.Many2many(
        'ir.attachment',
        string="Tài liệu đính kèm"
    )
    province_id = fields.Many2one(
        'res.country.state',
        string="Tỉnh/Thành phố",
        domain="[('country_id.code', '=', 'VN')]"  # Mặc định lọc Việt Nam
    )
    supervisor_ids = fields.Many2many('hr.employee', 'hr_employee_supervisor_rel', 'emp_id', 'sup_id',
                                      string="Đồng quản lý")

    # --- HÀM TỰ ĐỘNG LẤY DANH SÁCH SẾP TỪ PHÒNG BAN ---
    @api.onchange('department_id')
    def _onchange_department_get_multi_managers(self):
        # Giữ lại logic cũ: Lấy sếp chính (để vẽ sơ đồ tổ chức)
        # Lưu ý: department_id.manager_id là field gốc (Many2one) hoặc field logic bạn đã map
        if self.department_id.manager_id:
            self.parent_id = self.department_id.manager_id

        # LOGIC MỚI: Lấy danh sách ban quản lý (Many2many) từ phòng ban
        # Lưu ý: department_id.manager_ids là field custom bên model hr.department bạn đã tạo
        if self.department_id and hasattr(self.department_id, 'manager_ids'):
            # Lọc bỏ chính nhân viên đang sửa (để tránh lỗi tự mình quản lý mình)
            managers = self.department_id.manager_ids.filtered(lambda m: m.id != self._origin.id)
            self.supervisor_ids = managers
        else:
            self.supervisor_ids = False

    # 2. Quận/Huyện
    district_id = fields.Many2one(
        'res.district',
        string="Quận/Huyện",
        domain="[('state_id', '=', province_id)]"  # Chỉ hiện huyện thuộc tỉnh đã chọn
    )

    # 3. Xã/Phường
    ward_id = fields.Many2one(
        'res.ward',
        string="Xã/Phường",
        domain="[('state_id', '=', province_id)]"  # Lọc Xã theo Tỉnh
    )

    street_detail = fields.Char(string="Số nhà/Đường")

    # --- Khi đổi Tỉnh -> Reset Xã ---
    @api.onchange('province_id')
    def _onchange_province(self):
        self.ward_id = False

    # --- Tự động gộp địa chỉ hiển thị (Bỏ District) ---
    @api.onchange('street_detail', 'ward_id', 'province_id')
    def _onchange_full_address(self):
        parts = [
            self.street_detail,
            self.ward_id.name,
            # Bỏ self.district_id.name
            self.province_id.name
        ]
        self.household_address = ", ".join([p for p in parts if p])


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

    def action_terminate_contract(self):
        self.ensure_one()
        # Gọi Wizard Thôi việc chuẩn của Odoo (hr.departure.wizard)
        return {
            'name': _('Thủ tục Thôi việc / Chấm dứt hợp đồng'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.departure.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'default_employee_id': self.id,
            },
        }

    def write(self, vals):
        if 'active' in vals:
            _logger.info(f"DEBUG: Đang ghi field 'active' của nhân viên {self.ids} thành: {vals['active']}")
        return super(HrEmployeePrivate, self).write(vals)




# class HrDepartureWizard(models.TransientModel):
#     _inherit = 'hr.departure.wizard'
#
#     archive_private_address = fields.Boolean(default=True)
#
#     def action_register_departure(self):
#         # 1. Gọi hàm gốc để xử lý các logic khác (Contract, Activities...)
#         res = super(HrDepartureWizard, self).action_register_departure()
#
#         # 2. [QUAN TRỌNG] Ép buộc Archive thủ công
#         # Vì log cho thấy hàm gốc không làm việc này, ta tự làm.
#         if self.employee_id.active:
#             _logger.info(f"DEBUG: Đang ép buộc Archive nhân viên {self.employee_id.name}...")
#             self.employee_id.write({'active': False})
#
#         # 3. Log kiểm tra lại lần cuối
#         _logger.info(f"--> KẾT QUẢ CUỐI CÙNG: Active = {self.employee_id.active}")
#
#         # 4. Reload lại giao diện để XML nhận diện active=False (ẩn nút, hiện ribbon)
#         return {
#             'type': 'ir.actions.client',
#             'tag': 'reload',
#         }



class ResWard(models.Model):
    _name = 'res.ward'
    _description = 'Xã/Phường'
    _order = 'name'

    name = fields.Char(string="Tên Xã/Phường", required=True)
    state_id = fields.Many2one('res.country.state', string="Tỉnh/Thành phố", required=True)

    _sql_constraints = [
        ('name_state_uniq', 'unique(name, state_id)', 'Xã/Phường này đã tồn tại trong Tỉnh/TP này!')
    ]

# 2. KẾ THỪA MODEL TỈNH/THÀNH PHỐ (Thêm mới đoạn này)
class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    # Tạo quan hệ ngược: Một Tỉnh có nhiều Xã
    ward_ids = fields.One2many('res.ward', 'state_id', string="Danh sách Xã/Phường")




class ResPartner(models.Model):
    _inherit = 'res.partner'

    def init(self):
        super(ResPartner, self).init()
        try:
            # Lấy sequence name chuẩn của bảng res_partner
            self.env.cr.execute("SELECT setval('res_partner_id_seq', (SELECT MAX(id) FROM res_partner));")
            _logger.info("Đã reset sequence res_partner_id_seq thành công.")
        except Exception as e:
            _logger.warning(f"Không thể reset sequence: {e}")


class ResourceResource(models.Model):
    _inherit = 'resource.resource'

    def init(self):
        super(ResourceResource, self).init()
        # Thêm dòng log này để biết chắc chắn hàm đã chạy
        _logger.info(">>>>>>>> TEDI FIX: Đang reset sequence cho resource_resource...")

        sql = """
            SELECT setval('resource_resource_id_seq', COALESCE((SELECT MAX(id) FROM resource_resource), 0) + 1);
        """
        self.env.cr.execute(sql)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def init(self):
        super(HrEmployee, self).init()
        # Fix lỗi sequence cho bảng Nhân viên
        sql = """
            SELECT setval('hr_employee_id_seq', COALESCE((SELECT MAX(id) FROM hr_employee), 0) + 1);
        """
        self.env.cr.execute(sql)