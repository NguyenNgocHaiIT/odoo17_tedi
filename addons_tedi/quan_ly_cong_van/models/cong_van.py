from datetime import timedelta
from operator import index

from pygments.lexer import default

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import odoo
import re
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PhanPhat(models.TransientModel):
    _name = 'office.document.phan.phat'

    loai_phan_phat = fields.Selection([
        ('don_vi', 'Cho đơn vị'),
        ('ca_nhan', 'Cho cá nhân'),
        ('ca_hai', 'Cho cả đơn vị và cá nhân'),
    ], string='Loại phân phát', default='don_vi', required=True)

    nhan_van_ban = fields.Char('Nhận văn bản')
    don_vi_xu_ly_chinh = fields.Many2one(
        'hr.department',
        string='Đơn vị xử lý chính'
    )
    don_vi_dong_xu_ly = fields.Many2many(
        'hr.department',
        'office_document_dv_dong_xu_ly_rel',
        'phanphat_id', 'department_id',
        string='Đơn vị đồng xử lý'
    )
    pb_dv_nhan = fields.Many2one('hr.department', string='Phòng ban')
    ca_nhan_dv_nhan = fields.Many2one('res.users', string='Cá nhân')
    nhom_nguoi_dung_dv_nhan = fields.Char('Nhóm người dùng')
    noi_nhan_ban_goc_luu_tru = fields.Char('Nơi nhận bản gốc lưu trữ')
    nguoi_xu_ly_chinh = fields.Many2many(
        'hr.employee',
        'office_document_nguoi_xu_ly_chinh_employee_rel',
        'phanphat_id', 'employee_id',
        compute='_compute_nguoi_xu_ly_chinh',
        string='Người xử lý chính')
    nguoi_dong_xu_ly = fields.Many2many(
        'hr.employee',
        'office_document_nguoi_dong_xu_ly_employee_rel',
        'phanphat_id', 'employee_id',
        compute='_compute_nguoi_dong_xu_ly',
        string='Người đồng xử lý'
    )

    ca_nhan_xu_ly_chinh = fields.Many2many(
        'hr.employee',
        'office_document_ca_nhan_xu_ly_chinh_employee_rel',
        'phanphat_id', 'employee_id',
        string='Người xử lý chính')
    ca_nhan_dong_xu_ly = fields.Many2many(
        'hr.employee',
        'office_document_ca_nhan_dong_xu_ly_employee_rel',
        'phanphat_id', 'employee_id',
        string='Người đồng xử lý'
    )

    @api.constrains('don_vi_xu_ly_chinh', 'don_vi_dong_xu_ly')
    def _check_don_vi_trung(self):
        for rec in self:
            if rec.loai_phan_phat in ('don_vi', 'ca_hai') and rec.don_vi_xu_ly_chinh and rec.don_vi_xu_ly_chinh in rec.don_vi_dong_xu_ly:
                raise ValidationError("Đơn vị xử lý chính không được trùng với đơn vị đồng xử lý!")

    @api.constrains('ca_nhan_xu_ly_chinh', 'ca_nhan_dong_xu_ly')
    def _check_ca_nhan_trung(self):
        for rec in self:
            if rec.loai_phan_phat in ('ca_nhan', 'ca_hai'):
                trung_nhau = set(rec.ca_nhan_xu_ly_chinh.ids) & set(rec.ca_nhan_dong_xu_ly.ids)
                if trung_nhau:
                    raise ValidationError("Cá nhân xử lý chính không được trùng với cá nhân đồng xử lý!")

    # ----- COMPUTE FIELD -----
    @api.depends('don_vi_xu_ly_chinh')
    def _compute_nguoi_xu_ly_chinh(self):
        for rec in self:
            if not rec.don_vi_xu_ly_chinh:
                rec.nguoi_xu_ly_chinh = False
                continue

            dept = rec.don_vi_xu_ly_chinh
            employees = dept.manager_id | dept.manager_ids  # union trực tiếp, bỏ qua False
            rec.nguoi_xu_ly_chinh = employees.filtered(bool)  # loại bỏ False nếu có

    @api.depends('don_vi_dong_xu_ly')
    def _compute_nguoi_dong_xu_ly(self):
        for rec in self:
            if not rec.don_vi_dong_xu_ly:
                rec.nguoi_dong_xu_ly = False
                continue

            employees = self.env['hr.employee']
            for dept in rec.don_vi_dong_xu_ly:
                employees |= (dept.manager_id | dept.manager_ids).filtered(bool)
            rec.nguoi_dong_xu_ly = employees or False

    def phan_phat(self):
        doc_id = self.env.context.get('active_id')
        if not doc_id:
            return

        doc = self.env['office.document'].browse(doc_id)
        if not doc.exists():
            return

        nguoi_xu_ly_chinh_ids = []
        nguoi_dong_xu_ly_ids = []

        # Xác định người xử lý dựa vào loại phân phát
        if self.loai_phan_phat in ('don_vi', 'ca_hai'):
            nguoi_xu_ly_chinh_ids += self.nguoi_xu_ly_chinh.ids
            nguoi_dong_xu_ly_ids += self.nguoi_dong_xu_ly.ids
        if self.loai_phan_phat in ('ca_nhan', 'ca_hai'):
            nguoi_xu_ly_chinh_ids += self.ca_nhan_xu_ly_chinh.ids
            nguoi_dong_xu_ly_ids += self.ca_nhan_dong_xu_ly.ids

        nguoi_xu_ly_chinh_ids = list(set(nguoi_xu_ly_chinh_ids))
        nguoi_dong_xu_ly_ids = list(set(nguoi_dong_xu_ly_ids))

        # --- 1. Cập nhật Many2many vào văn bản ---
        update_data = {
            'tt_vb': 'cho_xu_ly',
        }

        if self.loai_phan_phat == 'don_vi':
            update_data.update({
                'dv_xu_ly_chinh': self.don_vi_xu_ly_chinh.id or False,
                'dv_dong_xu_ly': [(6, 0, self.don_vi_dong_xu_ly.ids)],
            })

        update_data.update({
            'nguoi_xu_ly_chinh': [(6, 0, nguoi_xu_ly_chinh_ids)] if nguoi_xu_ly_chinh_ids else [(5,)],
            'nguoi_dong_xu_ly': [(6, 0, nguoi_dong_xu_ly_ids)] if nguoi_dong_xu_ly_ids else [(5,)],
        })

        doc.write(update_data)

        # --- 2. Tạo detail2 cho từng người ---
        lines_to_create = []

        # Tạo danh sách người xử lý
        employees_list = []
        if nguoi_xu_ly_chinh_ids:
            employees_list.extend(
                [(emp, 'Xử lý chính') for emp in self.env['hr.employee'].browse(nguoi_xu_ly_chinh_ids)])
        if nguoi_dong_xu_ly_ids:
            employees_list.extend([(emp, 'Đồng xử lý') for emp in self.env['hr.employee'].browse(nguoi_dong_xu_ly_ids)])

        for emp, role in employees_list:
            if not doc.detail2.filtered(lambda l: l.nguoi_nhap_y_kien == emp):
                lines_to_create.append({
                    'office_document_id': doc.id,
                    'nguoi_nhap_y_kien': emp.id,
                    'nhom_phong_ban': emp.department_id.name or 'Không xác định',
                    'noi_dung_chi_dao': role,
                    'thoi_diem_chi_dao': fields.Datetime.now(),
                })

        if lines_to_create:
            self.env['office.document.detail2'].create(lines_to_create)

        # --- 3. Chuẩn bị thông tin gửi popup, chat, email ---
        odoobot = self.env.ref('base.user_root')
        odoobot_partner = odoobot.partner_id

        # Lấy tất cả nhân viên cần thông báo
        employees_to_notify = self.env['hr.employee'].browse(nguoi_xu_ly_chinh_ids + nguoi_dong_xu_ly_ids)
        users_to_notify = employees_to_notify.mapped('user_id').filtered(lambda u: u.partner_id)

        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        detail_url = f"{web_url}/web#id={doc.id}&model=office.document&view_type=form"

        body_chat = f"""
        <p>📄 Bạn vừa được giao xử lý văn bản: <b>{doc.trich_yeu}</b>.</p>
        <p>
            <a href="{detail_url}" style="background:#875A7B;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                Xem chi tiết
            </a>
        </p>
        """

        # --- 4. Hàm tạo kênh chat 1-1 ---
        def get_or_create_direct_chat(partner1, partner2):
            domain = [
                ('channel_type', '=', 'chat'),
                ('channel_member_ids.partner_id', 'in', [partner1.id, partner2.id])
            ]
            channels = self.env['discuss.channel'].sudo().search(domain)
            for channel in channels:
                members = channel.channel_member_ids.mapped('partner_id')
                if len(members) == 2 and set(members.ids) == {partner1.id, partner2.id}:
                    return channel
            return self.env['discuss.channel'].sudo().create({
                'name': f"Phân phát: {partner2.name}",
                'channel_type': 'chat',
                'channel_member_ids': [
                    (0, 0, {'partner_id': partner1.id}),
                    (0, 0, {'partner_id': partner2.id}),
                ]
            })

        # --- 5. Gửi popup, chat, email ---
        for employee in employees_to_notify:
            user = employee.user_id
            if not user or not user.partner_id:
                continue

            partner = user.partner_id

            # Popup realtime
            self.env['bus.bus']._sendone(
                partner,
                'simple_notification',
                {
                    'title': 'Phân phát văn bản mới',
                    'message': f"Bạn được giao xử lý văn bản: {doc.trich_yeu}",
                    'sticky': False,
                    'type': 'info',
                }
            )

            # Chat Discuss
            try:
                channel = get_or_create_direct_chat(odoobot_partner, partner)
                channel.sudo().message_post(
                    body=body_chat,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    author_id=odoobot_partner.id,
                    body_is_html=True,
                )
            except Exception as e:
                _logger.error(f"Lỗi gửi chat cho {partner.name}: {str(e)}")

            # Email
            try:
                subject = f"[Văn bản mới] {doc.trich_yeu}"
                body_html = f"""
                                <p>Xin chào {employee.name},</p>
                                <p>Bạn vừa được phân công xử lý văn bản: <b>{doc.trich_yeu}</b>.</p>
                                <p>
                                    <a href="{detail_url}" style="background:#875A7B;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                                        Xem chi tiết văn bản
                                    </a>
                                </p>
                                <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
                            """
                email = employee.work_email or user.email
                if not email:
                    continue

                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_to': email,
                    'email_from': self.env.user.email or 'no-reply@company.com',
                    'body_html': body_html,
                }).send()
            except Exception as e:
                _logger.warning(f"Gửi mail thất bại cho {employee.name}: {str(e)}")

        # --- 6. Thông báo thành công ---
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': 'Đã phân phát văn bản và gửi thông báo đến người nhận.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def cancel(self):
        return {'type': 'ir.actions.act_window_close'}


class ButPhe(models.TransientModel):
    _name = 'office.document.but.phe'

    y_kien_xu_ly = fields.Char('Ý kiến xử lý')
    tai_lieu_kem = fields.Binary('Tài liệu kèm')
    quan_trong = fields.Boolean('Quan trọng')
    da_giai_quyet = fields.Boolean('Đã giải quyết')
    thong_bao_cho_van_thu = fields.Boolean('Thông báo cho văn thư', default=True)

    def but_phe(self):
        doc_id = self.env.context.get('active_id')
        if not doc_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi',
                    'message': 'Chưa có văn bản để bút phê.',
                    'type': 'warning',
                    'sticky': False
                }
            }

        doc = self.env['office.document'].browse(doc_id)
        if not doc.exists():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi',
                    'message': 'Văn bản không tồn tại.',
                    'type': 'warning',
                    'sticky': False
                }
            }

        # ===== 1. Cập nhật trạng thái & bút phê =====
        doc.write({
            'but_phe': self.y_kien_xu_ly,
            'tt_vb': 'cho_phan_phat',
        })

        # ===== 2. Xác định nhân viên đang bút phê =====
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.user.id)],
            limit=1
        )

        nhom_phong_ban = employee.department_id.name if employee and employee.department_id else 'Không xác định'

        # ===== 3. Tạo detail1 dưới dạng nhân viên =====
        self.env['office.document.detail1'].create({
            'office_document_id': doc.id,
            'nguoi_nhap_y_kien': employee.id if employee else False,
            'nhom_phong_ban': nhom_phong_ban,
            'noi_dung_chi_dao': self.y_kien_xu_ly or 'Không có ý kiến',
            'thoi_diem_chi_dao': fields.Datetime.now(),
        })
        # ===== 4. GỬI EMAIL CHO VĂN THƯ =====
        if self.thong_bao_cho_van_thu:
            group = self.env.ref('quan_ly_cong_van.group_van_thu', raise_if_not_found=False)
            if group and group.users:
                # Lấy email văn thư
                van_thu_emails = []
                for user in group.users:
                    if user.email:
                        van_thu_emails.append(user.email)

                if van_thu_emails:
                    email_to = ', '.join(van_thu_emails)

                    # Tạo email
                    subject = f"Văn bản đã bút phê: {doc.trich_yeu[:30]}..." if doc.trich_yeu else "Văn bản đã bút phê"

                    body = f"""
                            Văn bản đã được bút phê:

                            Số văn bản: {doc.so_vb or 'Chưa có số'}
                            Trích yếu: {doc.trich_yeu or 'Không có'}
                            Người bút phê: {employee.name if employee else self.env.user.name}
                            Ý kiến: {self.y_kien_xu_ly or 'Không có ý kiến'}
                            Quan trọng: {'Có' if self.quan_trong else 'Không'}
                            Thời gian: {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}

                            Vui lòng xử lý phân phát.
                            """

                    # Gửi email
                    self.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'email_to': email_to,
                        'body_html': body.replace('\n', '<br>'),
                    }).send()

        # ===== 5. Thông báo văn thư (group) =====
        if self.thong_bao_cho_van_thu:
            group = self.env.ref('quan_ly_cong_van.group_van_thu', raise_if_not_found=False)
            if group:
                partners = group.users.mapped('partner_id').ids
                if partners:
                    doc.message_post(
                        body=f"""
                                    <p><b>Văn bản đã được bút phê:</b> {doc.trich_yeu or 'Không có trích yếu'}</p>
                                    <p><b>Người bút phê:</b> {employee.name if employee else self.env.user.name}</p>
                                    <p><b>Ý kiến bút phê:</b> {self.y_kien_xu_ly or 'Không có ý kiến'}</p>
                                    <p><b>Quan trọng:</b> {'Có' if self.quan_trong else 'Không'}</p>
                                    <p><b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                                    """,
                        subject=f"Văn bản đã được bút phê: {doc.trich_yeu[:50]}..." if doc.trich_yeu else "Văn bản đã được bút phê",
                        partner_ids=partners,
                        body_is_html=True,
                    )

        # ===== 6. Lưu tài liệu kèm =====
        if self.tai_lieu_kem:
            self.env['ir.attachment'].create({
                'name': 'Tài liệu bút phê',
                'type': 'binary',
                'datas': self.tai_lieu_kem,
                'res_model': 'office.document',
                'res_id': doc.id,
            })

        return {'type': 'ir.actions.act_window_close'}

    def cancel(self):
        return {'type': 'ir.actions.act_window_close'}


class OfficeDocumentDetail1(models.Model):
    _name = 'office.document.detail1'

    nguoi_nhap_y_kien = fields.Many2one('hr.employee', string='Người nhập ý kiến')
    nhom_phong_ban = fields.Char(
        string='Nhóm phòng ban',
        compute='_compute_nhom_phong_ban',
        store=True  # Nếu muốn lưu giá trị vào DB
    )
    noi_dung_chi_dao = fields.Char('Nội dung chỉ đạo')
    thoi_diem_chi_dao = fields.Datetime('Thời điểm chỉ đạo')
    office_document_id = fields.Many2one('office.document')

    @api.depends('nguoi_nhap_y_kien')
    def _compute_nhom_phong_ban(self):
        for rec in self:
            rec.nhom_phong_ban = 'Không xác định'
            if rec.nguoi_nhap_y_kien and rec.nguoi_nhap_y_kien.department_id:
                rec.nhom_phong_ban = rec.nguoi_nhap_y_kien.department_id.name


class OfficeDocumentDetail2(models.Model):
    _name = 'office.document.detail2'

    nguoi_nhap_y_kien = fields.Many2one('hr.employee', string='Người nhập ý kiến')
    nhom_phong_ban = fields.Char(
        string='Nhóm phòng ban',
        compute='_compute_nhom_phong_ban',
        store=True  # Nếu muốn lưu giá trị vào DB
    )
    noi_dung_chi_dao = fields.Char('Trách nhiệm')
    thoi_diem_chi_dao = fields.Datetime('Thời điểm')
    view_time = fields.Datetime('Thời gian xem', readonly=True)
    office_document_id = fields.Many2one('office.document')

    allow_phan_phat = fields.Boolean(
        string='Có thể phân phát',
        compute='_compute_allow_phan_phat',
        store=False
    )

    @api.depends('nguoi_nhap_y_kien')
    def _compute_allow_phan_phat(self):
        """Tính toán quyền phân phát - cho phép nếu là manager của phòng ban"""
        for rec in self:
            rec.allow_phan_phat = False

            if rec.nguoi_nhap_y_kien and rec.nhom_phong_ban:
                # Kiểm tra xem nhân viên có phải là manager của phòng ban không
                department = self.env['hr.department'].search([
                    ('name', '=', rec.nhom_phong_ban)
                ], limit=1)

                if department:
                    # Kiểm tra nếu nhân viên này là manager của phòng ban
                    is_manager = (
                            rec.nguoi_nhap_y_kien.id == department.manager_id.id or
                            rec.nguoi_nhap_y_kien.id in department.manager_ids.ids
                    )
                    rec.allow_phan_phat = is_manager

    '''chuc_vu = fields.Selection([
        ('quan_ly', 'QUản lý'),
        ('nhan_vien', 'Nhân viên'),
    ], string='Chức vụ')
    nguoi_quan_ly = fields.Many2one('hr.employee', string='Người quản lý')
    cong_viec = fields.Text(string='Nội dung công việc')

    # 2 trường quan trọng nhất
    is_section = fields.Boolean(string="Là Section", compute='_compute_is_section')
    sequence = fields.Integer(string="Thứ tự", default=10)

    def action_open_assign_wizard(self):
        """Mở wizard Giao việc dưới dạng POPUP"""
        self.ensure_one()

        if self.chuc_vu != 'quan_ly':
            raise UserError("Chỉ quản lý mới được giao việc!")

        return {
            'name': 'Giao việc',  # Tiêu đề popup
            'type': 'ir.actions.act_window',
            'res_model': 'assign.task.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_van.view_assign_task_wizard_form').id,
            'target': 'new',  # BẮT BUỘC: mở popup
            'flags': {'modal': True},  # Đảm bảo là modal
            'context': {
                'default_detail_id': self.id,
                'default_office_document_id': self.office_document_id.id,
            },
        }'''

    '''@api.depends('chuc_vu')
    def _compute_is_section(self):
        for rec in self:
            rec.is_section = (rec.chuc_vu == 'quan_ly')'''

    @api.depends('nguoi_nhap_y_kien')
    def _compute_nhom_phong_ban(self):
        for rec in self:
            rec.nhom_phong_ban = 'Không xác định'
            if rec.nguoi_nhap_y_kien and rec.nguoi_nhap_y_kien.department_id:
                rec.nhom_phong_ban = rec.nguoi_nhap_y_kien.department_id.name


    '''allow_assign = fields.Boolean(compute='_compute_allow_assign')

    @api.depends('nguoi_nhap_y_kien')
    def _compute_allow_assign(self):
        # Cho phép giao việc nếu người hiện tại là employee đã nhập ý kiến
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        for rec in self:
            rec.allow_assign = (rec.nguoi_nhap_y_kien.id == current_employee.id if current_employee else False)'''


class OfficeDocumentDetail3(models.Model):
    _name = 'office.document.detail3'

    nguoi_nhap_y_kien = fields.Many2one('hr.employee', string='Người nhập ý kiến')
    nhom_phong_ban = fields.Char(
        string='Nhóm phòng ban',
        compute='_compute_nhom_phong_ban',
        store=True  # Nếu muốn lưu giá trị vào DB
    )
    noi_dung_chi_dao = fields.Char('Nội dung')
    thoi_diem_chi_dao = fields.Datetime('Thời điểm', default=fields.Datetime.now)
    office_document_id = fields.Many2one('office.document')

    @api.depends('nguoi_nhap_y_kien')
    def _compute_nhom_phong_ban(self):
        for rec in self:
            rec.nhom_phong_ban = 'Không xác định'
            if rec.nguoi_nhap_y_kien and rec.nguoi_nhap_y_kien.department_id:
                rec.nhom_phong_ban = rec.nguoi_nhap_y_kien.department_id.name

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Tự động lấy HR Employee của user hiện tại
        user = self.env.user
        hr_employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        if 'nguoi_nhap_y_kien' in fields_list and hr_employee:
            res['nguoi_nhap_y_kien'] = hr_employee.id
        return res


class OfficeDocument(models.Model):
    _name = 'office.document'
    _description = 'Quản lý công văn'
    _rec_name = 'trich_yeu'
    _inherit = ['mail.thread']

    document_type = fields.Selection([
        ('incoming', 'Công văn đến'),
        ('outgoing', 'Công văn đi'),
        ('resolution', 'Quyết định'),
        ('incoming_internal', 'Văn bản nội bộ đến'),
        ('outgoing_internal', 'Văn bản nội bộ đi'),
        ('director', 'Văn bản HĐQT'),
    ], string='Loại công văn', required=True)
    loai_van_ban = fields.Selection([
        ('1', 'Thông báo'),
        ('2', 'Tờ trình'),
        ('3', 'Quy chế')
    ], string='Loại văn bản')
    lanh_dao_xu_ly = fields.Many2many(
        'hr.employee',
        string='Lãnh đạo xử lý')
    lanh_dao_theo_doi = fields.Many2one('hr.employee', string='Lãnh đạo theo dõi')
    ngay_den = fields.Date('Ngày đến', default=fields.Date.context_today)
    phan_loai_van_ban = fields.Many2one('office.document.category', string='Phân loại văn bản')
    so_den_tong_hop = fields.Char('Số đến tổng hợp')
    so_di_tong_hop = fields.Char('Số công văn')
    so_hieu = fields.Char('Số hiệu')
    ngay_ban_hanh = fields.Date('Ngày ban hành')
    noi_gui = fields.Char('Nơi gửi')
    nguoi_ky = fields.Many2one('res.users', string='Người ký')
    do_khan = fields.Selection([
        ('thuong', 'Thường'),
        ('khan', 'Khẩn'),
        ('mat', 'Mật'),
        ('hoa_toc', 'Hỏa tốc')], string='Độ khẩn', default='thuong')
    vb_nhan = fields.Char('Văn bản nhận')
    tt_vb = fields.Selection([
        ('draft', 'Nhập thông tin'),#thường
        ('cho_truong_don_vi_duyet', 'Trình TĐV'),
        ('truong_don_vi_duyet','TĐV duyệt'),
        ('cho_duyet', 'Chờ duyệt'),
        ('da_duyet', 'Đã duyệt'),#vàng
        ('cho_but_phe', 'Chờ bút phê'),#vàng
        ('cho_phan_phat', 'Chờ phân phát'),#vàng
        ('cho_xu_ly', 'Đã phân phát'),#xanh
        ('phat_hanh', 'Đã phát hành'),#xanh
        ('huy', 'Đã hủy'),
    ], string='Trạng thái văn bản', default='draft', tracking=True)
    dv_xu_ly_chinh = fields.Many2one(
        'hr.department',
        string='Đơn vị xử lý chính'
    )
    dv_dong_xu_ly = fields.Many2many(
        'hr.department',
        'office_doc_donvi_rel',
        'document_id',
        'department_id',
        string='Đơn vị đồng xử lý'
    )
    phoi_hop_xu_ly = fields.Char('Phối hợp xử lý')
    pb_dv_nhan = fields.Many2one('hr.department', string='Phòng ban')
    ca_nhan_dv_nhan = fields.Many2one('res.users', string='Cá nhân')
    nhom_nguoi_dung_dv_nhan = fields.Char('Nhóm người dùng')
    nguoi_theo_doi = fields.Many2one('res.users', string='Người theo dõi')
    ngay_bat_dau = fields.Date('Ngày bắt đầu', default=fields.Date.context_today)
    ho_so_cong_viec = fields.Char('Hồ sơ công việc')
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Tài liệu',
        ondelete='cascade'
    )

    attachment_datas = fields.Binary(
        string='Tài liệu',
        compute='_compute_attachment_datas',
        inverse='_inverse_attachment_datas',
        store=False
    )

    attachment_filename = fields.Char(
        string='Tên file',
        compute='_compute_attachment_datas',
        store=False
    )

    @api.depends('attachment_id', 'attachment_id.datas', 'attachment_id.name')
    def _compute_attachment_datas(self):
        """Chiều 1: attachment_id → attachment_datas"""
        for record in self:
            if record.attachment_id:
                record.attachment_datas = record.attachment_id.datas
                record.attachment_filename = record.attachment_id.name
            else:
                record.attachment_datas = False
                record.attachment_filename = False

    def _inverse_attachment_datas(self):
        """Chiều 2: attachment_datas → attachment_id"""
        for record in self:
            if record.attachment_datas:
                if record.attachment_id:
                    # Update attachment hiện có
                    record.attachment_id.write({
                        'datas': record.attachment_datas,
                        'name': record.attachment_filename or record.attachment_id.name,
                    })
                else:
                    # Tạo attachment mới
                    attachment = self.env['ir.attachment'].create({
                        'name': record.attachment_filename or f'document_{record.id or "new"}.pdf',
                        'datas': record.attachment_datas,
                        'res_model': record._name,
                        'res_id': record.id,
                        'mimetype': 'application/pdf',
                    })
                    record.attachment_id = attachment.id
            else:
                # Nếu xóa attachment_datas thì xóa attachment_id
                if record.attachment_id:
                    record.attachment_id.unlink()

    note = fields.Text('Ghi chú')
    don_vi_ban_hanh_ngoai = fields.Many2one('res.partner', string='Đơn vị ban hành')
    don_vi_ban_hanh = fields.Many2one('hr.department', string='Đơn vị ban hành')
    don_vi_soan_thao = fields.Many2one('hr.department', string='Đơn vị soạn thảo')
    don_vi_nhan_ben_ngoai = fields.Char('Đơn vị nhận bên ngoài')
    nguoi_theo_doi_chinh = fields.Many2one('res.users', string='Người theo dõi chính')
    so_den_theo_so = fields.Char('Số đến theo sổ')
    so_di_theo_so = fields.Char('Số đi theo sổ')
    so_vb = fields.Char('Số văn bản')
    ngay_hieu_luc = fields.Date('Ngày hiệu lực', default=fields.Date.context_today)
    ngay_ky = fields.Date('Ngày ký')
    chuc_vu = fields.Char('Chức vụ')
    do_quan_trong = fields.Char('Độ quan trọng')
    nguoi_xu_ly_chinh = fields.Many2many(
        'hr.employee',
        'office_document_detail_nguoi_xu_ly_chinh_employee_rel',
        'document_id',
        'employee_id',
        string='Người xử lý chính')
    nguoi_dong_xu_ly = fields.Many2many(
        'hr.employee',
        'office_document_detail_nguoi_dong_xu_ly_employee_rel',
        'document_id',
        'employee_id',
        string='Người đồng xử lý'
    )
    nguoi_soan_thao = fields.Many2one('res.users', string='Người soạn thảo')
    dv_theo_doi_chinh = fields.Char('Đơn vị theo dõi chính')
    trich_yeu = fields.Text('Trích yếu')
    noi_luu_tru = fields.Char('Nơi lưu trữ')
    han_ket_thuc = fields.Date('Ngày kết thúc')
    so_den_tong_hop_so_den_theo_so = fields.Char('Số công văn')
    so_di_tong_hop_so_den_theo_so = fields.Char('Số công văn')
    but_phe = fields.Char('Bút phê')
    chuyen_ngoai = fields.Boolean('Chuyển ngoài')
    ngay_chuyen_ngoai = fields.Date('Ngày chuyển ngoài')
    dia_diem_chuyen_ngoai = fields.Char('Địa điểm')
    detail1 = fields.One2many('office.document.detail1', 'office_document_id', string='Ý KIẾN CHỈ ĐẠO VÀ XỬ LÝ')
    detail2 = fields.One2many('office.document.detail2', 'office_document_id', string='Ý KIẾN CẤP LÃNH ĐẠO')
    detail3 = fields.One2many('office.document.detail3', 'office_document_id', string='XỬ LÝ VĂN BẢN CỦA BAN/PHÒNG')
    outgoing_internal_id = fields.Many2one(
        'office.document',
        string="Công văn nội bộ đi liên quan",
        domain="[('document_type','in',['outgoing_internal'])]"
    )
    incoming_internal_id = fields.Many2one(
        'office.document',
        string="Công văn nội bộ đến liên quan",
        domain="[('document_type','in',['incoming_internal'])]"
    )
    outgoing_id = fields.Many2one(
        'office.document',
        string="Công văn đi liên quan ",
        domain="[('document_type','in',['outgoing'])]"
    )
    incoming_id = fields.Many2one(
        'office.document',
        string="Công văn đến liên quan ",
        domain="[('document_type','in',['incoming'])]"
    )


    can_duyet = fields.Boolean(string='Văn bản có cần duyệt không ?', default=True)
    co_the_but_phe_cong_van_di = fields.Boolean(
        string='Có thể bút phê',
        compute='_compute_co_the_but_phe_cong_van_di',
        store=False  # Không lưu vào database, tính toán real-time
    )

    co_the_but_phe_cong_van_den = fields.Boolean(
        string='Có thể bút phê',
        compute='_compute_co_the_but_phe_cong_van_den',
        store=False  # Không lưu vào database, tính toán real-time
    )

    ngay_xuat = fields.Date(string='Ngày xuất', default=fields.Date.context_today)

    task_id = fields.Many2one('project.task', string="Công việc liên quan")

    # Thêm trường ngày tạo bổ sung
    ngay_tao_bo_sung = fields.Date(
        string='Ngày tạo bổ sung',
    )

    is_cong_van_bo_sung = fields.Boolean(string="Là công văn bổ sung", default=False)

    ngay_tao = fields.Date(
        string="Ngày tạo",
        compute="_compute_ngay_tao",
        store=True,
        index=True,
    )

    # Thêm vào class OfficeDocument
    truong_don_vi_duyet = fields.Many2one(
        'hr.employee',
        string='Trưởng đơn vị duyệt',
        compute='_compute_truong_don_vi_duyet',
        store=True,
    )


    # Thêm kiểm tra quyền cho trưởng đơn vị
    is_truong_don_vi = fields.Boolean(
        compute='_compute_is_truong_don_vi',
        store=False
    )
    don_vi_ban_hanh_tedi = fields.Char(string="Đơn vị ban hành")

    def _compute_is_truong_don_vi(self):
        """Tính toán xem người dùng hiện tại có phải là trưởng đơn vị duyệt không"""
        user = self.env.user

        for rec in self:
            rec.is_truong_don_vi = False

            if not rec.truong_don_vi_duyet:
                continue

            # Tìm employee của người dùng hiện tại
            current_employee = self.env['hr.employee'].search(
                [('user_id', '=', user.id)],
                limit=1
            )

            if current_employee:
                # So sánh với trưởng đơn vị duyệt
                rec.is_truong_don_vi = (current_employee.id == rec.truong_don_vi_duyet.id)

                # DEBUG: In thông tin
                _logger.debug(
                    f"Document {rec.id}: "
                    f"Creator: {rec.create_uid.name if rec.create_uid else 'None'}, "
                    f"Current user: {user.name}, "
                    f"Current employee: {current_employee.name if current_employee else 'None'}, "
                    f"Trưởng đơn vị: {rec.truong_don_vi_duyet.name if rec.truong_don_vi_duyet else 'None'}, "
                    f"Is trưởng đơn vị: {rec.is_truong_don_vi}"
                )

    def name_get(self):
        result = []
        for record in self:
            # Ưu tiên hiển thị số công văn
            display_value = ""

            if record.document_type in ['incoming', 'incoming_internal']:
                if record.so_den_tong_hop:
                    display_value = f"{record.so_den_tong_hop}"
            elif record.document_type in ['outgoing', 'outgoing_internal']:
                if record.so_di_tong_hop:
                    display_value = f"{record.so_di_tong_hop}"
            # Nếu không có số, mới dùng trích yếu
            if not display_value:
                display_value = record.trich_yeu or ''

            result.append((record.id, display_value))
        return result

    # Thêm phương thức search để tìm kiếm theo số công văn
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = []

        if name:
            # Tìm kiếm theo số công văn (so_den_tong_hop, so_di_tong_hop, so_hieu)
            domain = ['|', '|',
                      ('so_den_tong_hop', operator, name),
                      ('so_di_tong_hop', operator, name),
                      ('trich_yeu', operator, name)]

        # Kết hợp domain tìm kiếm với các điều kiện khác
        combined_domain = args + domain if args else domain
        records = self.search(combined_domain, limit=limit)

        return records.name_get()

    @api.depends('create_uid')
    def _compute_truong_don_vi_duyet(self):
        """Tính toán trưởng đơn vị duyệt dựa trên phòng ban của người tạo"""
        for rec in self:
            current_user = self.env.user

            # Nếu đang ở chế độ tạo mới (chưa có ID)
            if not rec.id:
                # Sử dụng người dùng hiện tại
                employee = self.env['hr.employee'].search(
                    [('user_id', '=', current_user.id)],
                    limit=1
                )
            else:
                # Nếu đã tạo, sử dụng create_uid
                if rec.create_uid:
                    employee = self.env['hr.employee'].search(
                        [('user_id', '=', rec.create_uid.id)],
                        limit=1
                    )
                else:
                    employee = False

            # Tìm manager của phòng ban nhân viên
            if employee and employee.department_id and employee.department_id.manager_id:
                rec.truong_don_vi_duyet = employee.department_id.manager_id
            else:
                rec.truong_don_vi_duyet = False


    @api.depends('ngay_tao_bo_sung', 'create_date')
    def _compute_ngay_tao(self):
        for rec in self:
            if rec.ngay_tao_bo_sung:
                rec.ngay_tao = rec.ngay_tao_bo_sung
            else:
                rec.ngay_tao = (
                    rec.create_date.date()
                    if rec.create_date
                    else fields.Date.today()
                )

    def phan_phat(self):
        return {
            'name': 'Phân phát',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_van.phan_phat_form').id,
            'res_model': 'office.document.phan.phat',
            'target': 'new',
            'context': {
                'footer': False
            }
        }

    def but_phe_action(self):
        return {
            'name': 'Bút phê',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_van.but_phe_form').id,
            'res_model': 'office.document.but.phe',
            'target': 'new'
        }
    def trinh_lanh_dao_cong_van_di_but_phe(self):
        self.ensure_one()
        if not self.lanh_dao_theo_doi:
            raise UserError("Vui lòng chọn lãnh đạo xử lý trước khi trình.")

        self.tt_vb = 'cho_but_phe'

        doc_url = self.get_form_url()
        employees_to_notify = [self.lanh_dao_theo_doi]

        for emp in employees_to_notify:
            # 1. Gửi email
            try:
                email = emp.user_id.email or emp.work_email
                if email:
                    body_html = f"""
                        <p>Xin chào {emp.name},</p>
                        <p>Văn bản <b>{self.trich_yeu}</b> cần xử lý.</p>
                        <p>
                            <a href="{doc_url}" style="background:#875A7B;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                                Xem chi tiết văn bản
                            </a>
                        </p>
                        <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
                    """
                    self.env['mail.mail'].sudo().create({
                        'subject': f"[Văn bản mới] {self.trich_yeu}",
                        'email_to': email,
                        'email_from': self.env.user.email or 'no-reply@company.com',
                        'body_html': body_html,
                    }).send()
            except Exception as e:
                _logger.warning(f"Gửi mail thất bại cho {emp.name}: {str(e)}")

            # 2. Gửi popup/notification nếu có user liên kết
            if emp.user_id:
                try:
                    partner = emp.user_id.partner_id
                    self.env['bus.bus']._sendone(
                        partner,
                        'simple_notification',
                        {
                            'title': 'Phân công xử lý văn bản',
                            'message': f"Bạn vừa được giao xử lý văn bản: {self.trich_yeu}",
                            'sticky': False,
                            'type': 'info',
                        }
                    )
                except Exception as e:
                    _logger.warning(f"Gửi notification thất bại cho {emp.name}: {str(e)}")


    def trinh_lanh_dao_cong_van_den(self):
        self.ensure_one()

        if not self.lanh_dao_xu_ly or not self.lanh_dao_xu_ly.ids:
            raise UserError("Vui lòng chọn lãnh đạo xử lý trước khi trình.")

        self.tt_vb = 'cho_but_phe'

        doc_url = self.get_form_url()
        employees_to_notify = self.lanh_dao_xu_ly

        for emp in employees_to_notify:
            # 1. Gửi email
            try:
                email = emp.user_id.email or emp.work_email
                if email:
                    body_html = f"""
                        <p>Xin chào {emp.name},</p>
                        <p>Văn bản <b>{self.trich_yeu}</b> cần xử lý.</p>
                        <p>
                            <a href="{doc_url}"
                               style="background:#E57373;color:white;padding:6px 12px;
                                      text-decoration:none;border-radius:4px;font-size:12px;">
                                Xem chi tiết văn bản
                            </a>
                        </p>
                        <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
                    """
                    self.env['mail.mail'].sudo().create({
                        'subject': f"[Văn bản mới] {self.trich_yeu}",
                        'email_to': email,
                        'email_from': self.env.user.email or 'no-reply@company.com',
                        'body_html': body_html,
                    }).send()
            except Exception as e:
                _logger.warning(f"Gửi mail thất bại cho {emp.name}: {str(e)}")

            # 2. Gửi popup/notification
            if emp.user_id:
                try:
                    partner = emp.user_id.partner_id
                    self.env['bus.bus']._sendone(
                        partner,
                        'simple_notification',
                        {
                            'title': 'Phân công xử lý văn bản',
                            'message': f"Bạn vừa được giao xử lý văn bản: {self.trich_yeu}",
                            'sticky': False,
                            'type': 'info',
                        }
                    )
                except Exception as e:
                    _logger.warning(f"Gửi notification thất bại cho {emp.name}: {str(e)}")


    def approve(self):
        self.ensure_one()
        self.tt_vb = 'da_duyet'

        if self.document_type in ['outgoing', 'outgoing_internal', 'resolution']:
            # Công văn đi, quyết định: gửi thông báo cho văn thư
            self._send_approval_notification_to_van_thu()
        elif self.document_type in ['incoming', 'incoming_internal']:
            # Công văn đến: gửi thông báo cho người tạo
            self._send_approval_notification_to_creator()
        return True

    def approve_don_vi(self):
        self.ensure_one()
        self.tt_vb = 'truong_don_vi_duyet'

        self._send_approval_notification_to_creator()
        return True

    def _send_approval_notification_to_creator(self):
        """Gửi thông báo cho người tạo khi công văn đến/incoming được duyệt"""
        self.ensure_one()

        try:
            # Lấy thông tin người tạo văn bản
            creator = self.create_uid
            if not creator or not creator.email:
                _logger.warning("Không có thông tin người tạo văn bản.")
                return

            # Lấy thông tin người duyệt
            approver = self.env.user

            # Chuẩn bị nội dung email
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model=office.document&view_type=form"

            # Xác định loại văn bản
            doc_type_display = dict(self._fields['document_type'].selection).get(self.document_type, 'Văn bản')

            subject = f"[{doc_type_display} đã duyệt] {self.trich_yeu[:50]}..."
            body_html = f"""
            <p>Xin chào {creator.name},</p>

            <p><b>{doc_type_display}</b> <b>"{self.trich_yeu}"</b> đã được duyệt bởi <b>{approver.name}</b>.</p>

            <div style="background:#f5f5f5; padding:10px; margin:10px 0; border-left:4px solid #4CAF50;">
                <p><b>Thông tin văn bản đã duyệt:</b></p>
                <ul>
                    <li>Số đến: {self.so_den_tong_hop or self.so_di_tong_hop or 'Chưa có'}</li>
                    <li>Số hiệu: {self.so_hieu or 'Chưa có'}</li>
                    <li>Ngày đến: {self.ngay_den.strftime('%d/%m/%Y') if self.ngay_den else 'Chưa có'}</li>
                    <li>Loại văn bản: {doc_type_display}</li>
                </ul>
                <p><b>Trạng thái hiện tại:</b> Đã duyệt</p>
            </div>

            <p>
                <a href="{detail_url}" style="background:#4CAF50;color:white;padding:8px 16px;text-decoration:none;border-radius:4px;font-size:14px;">
                    Xem chi tiết văn bản
                </a>
            </p>

            <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
            """

            # Gửi email đến người tạo
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': creator.email,
                'email_from': approver.email or 'no-reply@company.com',
                'body_html': body_html,
            }).send()

            _logger.info(f"Đã gửi email thông báo duyệt đến người tạo: {creator.name}")

            # Gửi thông báo popup cho người tạo (nếu online)
            if creator.partner_id:
                try:
                    self.env['bus.bus']._sendone(
                        creator.partner_id,
                        'simple_notification',
                        {
                            'title': f'{doc_type_display} đã duyệt',
                            'message': f'{doc_type_display} "{self.trich_yeu[:50]}..." đã được duyệt.',
                            'sticky': False,
                            'type': 'success',
                        }
                    )
                except Exception as e:
                    _logger.error(f"Lỗi gửi thông báo cho người tạo {creator.name}: {str(e)}")

        except Exception as e:
            _logger.error(f"Lỗi khi gửi thông báo duyệt cho người tạo: {str(e)}")

    def _send_approval_notification_to_van_thu(self):
        """Gửi email thông báo đơn giản cho văn thư khi văn bản đã được duyệt"""
        self.ensure_one()

        try:
            # Lấy nhóm văn thư
            group_van_thu = self.env.ref('quan_ly_cong_van.group_van_thu', raise_if_not_found=False)

            if not group_van_thu:
                _logger.warning("Không tìm thấy nhóm văn thư.")
                return

            # Lấy tất cả người dùng trong nhóm văn thư
            van_thu_users = group_van_thu.users

            # Lấy danh sách email của văn thư
            van_thu_emails = []
            for user in van_thu_users:
                if user.email:
                    van_thu_emails.append(user.email)

            if not van_thu_emails:
                _logger.warning("Không có email nào trong nhóm văn thư.")
                return

            # Chuẩn bị nội dung email đơn giản
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model=office.document&view_type=form"

            # Lấy thông tin người duyệt
            current_user = self.env.user.name

            # Xác định hành động tiếp theo
            next_action = "xử lý tiếp"  # Mặc định

            subject = f"[Văn bản đã duyệt] {self.trich_yeu[:50]}..."
            body_html = f"""
            <p>Kính gửi Anh/Chị Văn thư,</p>

            <p>Văn bản <b>"{self.trich_yeu}"</b> đã được duyệt bởi <b>{current_user}</b>.</p>

            <div style="background:#f5f5f5; padding:10px; margin:10px 0; border-left:4px solid #3498db;">
                <p><b>Lưu ý:</b> Vui lòng kiểm tra lại văn bản trước khi trình để bút phê.</p>
            </div>

            <p>
                <a href="{detail_url}" style="background:#3498db;color:white;padding:8px 16px;text-decoration:none;border-radius:4px;font-size:14px;">
                    Xem chi tiết văn bản
                </a>
            </p>

            <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
            """

            # Gửi email đến tất cả văn thư
            for email in van_thu_emails:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_to': email,
                    'email_from': self.env.user.email or 'no-reply@company.com',
                    'body_html': body_html,
                }).send()

            _logger.info(f"Đã gửi email thông báo duyệt đến {len(van_thu_emails)} văn thư")

            # Gửi thông báo popup đơn giản
            for user in van_thu_users:
                if user.partner_id and user != self.env.user:
                    try:
                        # Gửi popup thông báo đơn giản
                        self.env['bus.bus']._sendone(
                            user.partner_id,
                            'simple_notification',
                            {
                                'title': 'Văn bản đã duyệt',
                                'message': f"Văn bản đã được duyệt. Vui lòng kiểm tra!",
                                'sticky': False,
                                'type': 'info',
                            }
                        )

                    except Exception as e:
                        _logger.error(f"Lỗi gửi thông báo cho văn thư {user.name}: {str(e)}")

        except Exception as e:
            _logger.error(f"Lỗi khi gửi email thông báo cho văn thư: {str(e)}")

    def read(self, field_list=None, load='_classic_read'):
        res = super().read(field_list, load)
        if 'detail2' in (field_list or []):
            for doc in self:
                details = doc.detail2.filtered(lambda d: d.nguoi_nhap_y_kien.user_id.id == self.env.user.id)
                for detail in details:
                    if not detail.view_time:
                        detail.sudo().write({'view_time': fields.Datetime.now()})
        return res

    def unlink(self):
        self.mapped('detail1').unlink()
        self.mapped('detail2').unlink()
        self.mapped('detail3').unlink()
        return super().unlink()

    @api.model
    def create(self, vals):

        self.env.cr.execute("""
                    SELECT setval(
                        pg_get_serial_sequence('office_document', 'id'),
                        (SELECT COALESCE(MAX(id), 0) FROM office_document) + 1,
                        false
                    )
                """)

        # Xử lý han_ket_thuc
        if 'ngay_bat_dau' in vals and not vals.get('han_ket_thuc'):
            vals['han_ket_thuc'] = fields.Date.from_string(vals['ngay_bat_dau']) + timedelta(days=7)

        user = self.env.user
        if user.has_group('quan_ly_cong_van.group_van_thu'):
            vals['can_duyet'] = False

        can_duyet_val = vals.get('can_duyet', self._fields['can_duyet'].default(self))
        document_type_val = vals.get('document_type')
        user = self.env.user
        # Nếu chưa set tt_vb từ form, thì set lại khi lưu
        if (
                user.has_group('quan_ly_cong_van.group_van_thu')
                and document_type_val in ('incoming', 'incoming_internal')
        ):
            vals['tt_vb'] = 'da_duyet'
        elif (
                can_duyet_val is True
                and document_type_val in ('outgoing', 'outgoing_internal','resolution')
        ):
            vals['tt_vb'] = 'draft'
        elif (
                can_duyet_val is False
                and document_type_val in ('outgoing', 'outgoing_internal','resolution')
        ):
            vals['tt_vb'] = 'da_duyet'

        elif (
                user.has_group('quan_ly_cong_van.group_don_vi_xu_ly')
                and document_type_val in ('incoming', 'incoming_internal')
        ):
            vals['tt_vb'] = 'draft'
        else:
            vals['tt_vb'] = 'draft'


        # Xử lý so_den_tong_hop và so_di_tong_hop khi có phan_loai_van_ban
        vals = self._update_document_numbers(vals)

        record = super(OfficeDocument, self).create(vals)

        if record.document_type == 'resolution' and not record.phan_loai_van_ban:
            # Tìm hoặc tạo phân loại "Quyết định"
            category = self.env['office.document.category'].search([
                ('code', '=', 'QĐ')
            ], limit=1)

            if not category:
                # Tạo mới phân loại
                category = self.env['office.document.category'].create({
                    'code': 'QĐ',
                    'name': 'Quyết định',
                })

            # Cập nhật phân loại cho quyết định
            record.phan_loai_van_ban = category.id

        # 🔥 Nếu có task_id, tự chuyển trạng thái task thành "Đã giao"
        if record.task_id:
            record.task_id.da_tao_cong_van = True

        record._sync_related_documents(vals)

        return record

    def write(self, vals):
        # 1. Trường hợp đổi phân loại → cập nhật số
        if 'phan_loai_van_ban' in vals:
            for record in self:
                new_vals = vals.copy()
                new_vals = record._update_document_numbers(new_vals, is_write=True)
                super(OfficeDocument, record).write(new_vals)

            # Sau khi write xong → sync
            for record in self:
                record._sync_related_documents(vals)

            return True

        # 2. Các trường hợp khác → write bình thường
        res = super(OfficeDocument, self).write(vals)

        # 3. Sync liên kết 2 chiều
        for record in self:
            record._sync_related_documents(vals)

        return res

    def _update_document_numbers(self, vals, is_write=False):
        """
        Cập nhật so_den_tong_hop và so_di_tong_hop:
        - Công văn đến: <YYMMDD>.<STT>/<Mã đơn vị>-<Mã loại>
        - Công văn đi:
            + Loại Công văn (CV): <YYMMDD>.<STT>/TEDI-<Mã đơn vị>
            + Loại khác: <YYMMDD>.<STT>/<Mã đơn vị>-<Mã loại>
        - STT: 2 chữ số, reset mỗi ngày
        """
        import re

        def _get_abbreviation_from_name(name, max_length=10):
            """Lấy viết tắt từ tên đơn vị - Bỏ dấu trước khi xử lý"""
            if not name:
                return ''

            import unicodedata

            # Hàm bỏ dấu tiếng Việt
            def remove_diacritics(text):
                if not text:
                    return text
                # Tách ký tự và dấu
                text = unicodedata.normalize('NFD', text)
                # Loại bỏ dấu
                text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
                # Xử lý đ/Đ
                text = text.replace('đ', 'd').replace('Đ', 'D')
                return text

            # Bỏ dấu toàn bộ tên
            name_no_diacritic = remove_diacritics(name)

            # Tách thành các từ (dùng regex đơn giản)
            words = re.findall(r'[A-Za-z0-9]+', name_no_diacritic)

            result_parts = []

            # Xử lý từng từ
            for word in words:
                if not word:
                    continue

                # Nếu từ toàn bộ là VIẾT HOA hoặc chứa số/ký tự đặc biệt
                if word.isupper() or any(c.isdigit() or c in '-_/' for c in word):
                    result_parts.append(word)
                else:
                    # Lấy chữ cái đầu và viết hoa
                    result_parts.append(word[0].upper())

            # Ghép kết quả
            result = ''.join(result_parts)

            # Giới hạn độ dài
            if len(result) > max_length:
                return result[:max_length]

            # Nếu không có kết quả
            if not result:
                clean_name = re.sub(r'\s+', '', name_no_diacritic)
                return clean_name[:max_length].upper()

            return result

        phan_loai_id = vals.get('phan_loai_van_ban')
        document_type = vals.get('document_type') or self._context.get('default_document_type') or (
            self.document_type if self else None)

        # Bỏ qua Quyết định
        if document_type == 'resolution':
            return vals

        # Xác định ngày để tạo số - ƯU TIÊN ngay_tao_bo_sung
        ngay_tao_bo_sung = vals.get('ngay_tao_bo_sung')
        if ngay_tao_bo_sung:
            # Sử dụng ngày tạo bổ sung nếu có
            current_date = fields.Date.from_string(ngay_tao_bo_sung)
        else:
            # Sử dụng ngày hiện tại
            current_date = fields.Date.today()
        current_date_str = current_date.strftime('%y%m%d')  # YYMMDD

        def get_next_number(is_incoming=False):
            """
            Tạo số theo định dạng mới với STT 2 chữ số reset mỗi ngày
            """

            if is_incoming:
                # Số đến: tìm trong các văn bản đến cùng loại
                domain = [
                    ('document_type', 'in', ['incoming', 'incoming_internal']),
                    ('ngay_tao', '=', current_date),
                ]
                number_field = 'so_den_tong_hop'
            else:
                # Số đi: tìm trong các văn bản đi cùng loại
                domain = [
                    ('document_type', 'in', ['outgoing', 'outgoing_internal']),
                    ('ngay_tao', '=', current_date),
                ]
                number_field = 'so_di_tong_hop'

            if phan_loai_id:
                domain.append(('phan_loai_van_ban', '=', phan_loai_id))

            # Tìm tất cả văn bản cùng loại tạo hôm nay
            existing_docs = self.env['office.document'].search(domain)

            # Lấy số STT lớn nhất
            max_seq = 0
            for doc in existing_docs:
                number = getattr(doc, number_field, '')
                if number and '.' in number:
                    try:
                        # Tách phần STT: YYMMDD.STT/...
                        seq_part = number.split('.')[1].split('/')[0]
                        seq_num = int(seq_part)
                        max_seq = max(max_seq, seq_num)
                    except (ValueError, IndexError):
                        continue

            # STT mới
            next_seq = max_seq + 1

            # Lấy MÃ ĐƠN VỊ từ res.partner hoặc hr.department
            ma_don_vi = ''

            if document_type in ('incoming'):
                # Lấy từ res.partner (đơn vị bên ngoài)
                partner_id = vals.get('don_vi_ban_hanh_ngoai') or ''
                if partner_id and isinstance(partner_id, int):
                    partner = self.env['res.partner'].browse(partner_id)
                    if partner and partner.ma_don_vi:
                        ma_don_vi = partner.ma_don_vi.strip()
                    elif partner:
                        # Nếu partner không có mã, lấy tên rút gọn
                        ma_don_vi = _get_abbreviation_from_name(partner.name)
            else:  # internal - lấy TRỰC TIẾP từ hr.department
                dept_id = vals.get('don_vi_ban_hanh') or ''
                if dept_id and isinstance(dept_id, int):
                    dept = self.env['hr.department'].browse(dept_id)
                    if dept:
                        source_info = f"Department ID: {dept_id}, Name: {dept.name}"

                        # TRƯỜNG HỢP 1: Kiểm tra xem department có field ma_don_vi không
                        if hasattr(dept, 'ma_don_vi') and dept.ma_don_vi:
                            ma_don_vi = dept.ma_don_vi.strip()

                        # TRƯỜNG HỢP 2: Kiểm tra field code (mã phòng ban)
                        elif hasattr(dept, 'code') and dept.code:
                            ma_don_vi = dept.code.strip()

                        # TRƯỜNG HỢP 3: Lấy từ field abbreviation nếu có
                        elif hasattr(dept, 'abbreviation') and dept.abbreviation:
                            ma_don_vi = dept.abbreviation.strip()

                        # TRƯỜNG HỢP 4: Lấy viết tắt từ tên
                        else:
                            ma_don_vi = _get_abbreviation_from_name(dept.name)

            # Xử lý nếu không có mã
            if not ma_don_vi:
                ma_don_vi = 'TEDI'  # Mã mặc định

            # Lấy mã loại
            ma_loai = ''
            if phan_loai_id:
                phan_loai = self.env['office.document.category'].browse(phan_loai_id)
                if phan_loai.exists() and phan_loai.code:
                    ma_loai = phan_loai.code
            if not ma_loai:
                ma_loai = 'CV'  # Mã mặc định

            # Tạo số theo định dạng
            if is_incoming:
                # Công văn đến: <YYMMDD>.<STT>/<Mã đơn vị>-<Mã loại>
                return f"{current_date_str}.{next_seq:02d}/{ma_don_vi}-{ma_loai}"
            else:
                # Công văn đi
                if ma_loai == 'CV':
                    # Loại Công văn: <YYMMDD>.<STT>/TEDI-<Mã đơn vị>
                    return f"{current_date_str}.{next_seq:02d}/TEDI-{ma_don_vi}"
                else:
                    # Loại khác: <YYMMDD>.<STT>/<Mã đơn vị>-<Mã loại>
                    return f"{current_date_str}.{next_seq:02d}/{ma_don_vi}-{ma_loai}"

        # ========== SỐ ĐẾN (Công văn đến) ==========
        if document_type in ('incoming', 'incoming_internal') and phan_loai_id:
            if not vals.get('so_den_tong_hop'):
                vals['so_den_tong_hop'] = get_next_number(is_incoming=True)

        # ========== SỐ ĐI (Công văn đi) ==========
        if document_type in ('outgoing', 'outgoing_internal') and phan_loai_id:
            if not vals.get('so_di_tong_hop'):
                vals['so_di_tong_hop'] = get_next_number(is_incoming=False)

        return vals

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        start_date = res.get('ngay_bat_dau', fields.Date.context_today(self))

        res['han_ket_thuc'] = start_date + timedelta(days=7)
        document_type = self._context.get('default_document_type')

        if document_type  == 'resolution':
            # Tìm hoặc tạo phân loại "Quyết định"
            category = self.env['office.document.category'].search([
                ('code', '=', 'QĐ')
            ], limit=1)

            if not category:
                category = self.env['office.document.category'].create({
                    'code': 'QĐ',
                    'name': 'Quyết định',
                })

            res['phan_loai_van_ban'] = category.id

        elif document_type in ('incoming', 'outgoing'):
            category = self.env['office.document.category'].search([
                ('code', '=', 'CV')
            ], limit=1)

            if not category:
                category = self.env['office.document.category'].create({
                    'code': 'CV',
                    'name': 'Công văn',
                })

            res['phan_loai_van_ban'] = category.id
        return res



    @api.constrains('ngay_bat_dau', 'han_ket_thuc')
    def _check_dates(self):
        for rec in self:
            if rec.han_ket_thuc and rec.ngay_bat_dau:
                if rec.han_ket_thuc < rec.ngay_bat_dau:
                    raise ValidationError("Ngày kết thúc không được sớm hơn ngày bắt đầu!")

    def trinh_lanh_dao_cong_van_di(self):
        self.ensure_one()

        if not self.lanh_dao_theo_doi:
            raise UserError("Vui lòng chọn lãnh đạo xử lý trước khi trình.")

        # Cập nhật trạng thái
        self.tt_vb = 'cho_duyet'

        doc_url = self.get_form_url()
        employees_to_notify = [self.lanh_dao_theo_doi]

        for emp in employees_to_notify:
            # 1. Gửi email
            try:
                email = emp.user_id.email or emp.work_email
                if email:
                    body_html = f"""
                        <p>Xin chào {emp.name},</p>
                        <p>Văn bản <b>{self.trich_yeu}</b> đã được trình lãnh đạo bạn để duyệt.</p>
                        <p>
                            <a href="{doc_url}" style="background:#875A7B;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                                Xem chi tiết văn bản
                            </a>
                        </p>
                        <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
                    """
                    self.env['mail.mail'].sudo().create({
                        'subject': f"[Văn bản cần duyệt] {self.trich_yeu}",
                        'email_to': email,
                        'email_from': self.env.user.email or 'no-reply@company.com',
                        'body_html': body_html,
                    }).send()
            except Exception as e:
                _logger.warning(f"Gửi mail thất bại cho {emp.name}: {str(e)}")

            # 2. Gửi popup/notification nếu có user liên kết
            if emp.user_id:
                try:
                    partner = emp.user_id.partner_id
                    self.env['bus.bus']._sendone(
                        partner,
                        'simple_notification',
                        {
                            'title': 'Văn bản cần duyệt',
                            'message': f"Văn bản '{self.trich_yeu}' đã được trình để duyệt.",
                            'sticky': False,
                            'type': 'info',
                        }
                    )
                except Exception as e:
                    _logger.warning(f"Gửi notification thất bại cho {emp.name}: {str(e)}")

        return True

    def get_form_url(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web#id={self.id}&model=office.document&view_type=form"

    def phat_hanh(self):
        self.ensure_one()
        self.tt_vb = 'phat_hanh'
        return True

    def huy(self):
        self.ensure_one()
        self.tt_vb = 'huy'
        return True

    @api.depends('lanh_dao_theo_doi')
    def _compute_co_the_but_phe_cong_van_di(self):
        """Tính toán xem người dùng hiện tại có phải là lãnh đạo xử lý không"""
        current_user = self.env.user
        current_employee = self.env['hr.employee'].search(
            [('user_id', '=', current_user.id)], limit=1
        )

        for record in self:
            # Nếu có lãnh đạo xử lý và người dùng hiện tại là lãnh đạo đó
            if record.lanh_dao_theo_doi and current_employee:
                record.co_the_but_phe_cong_van_di = (record.lanh_dao_theo_doi.id == current_employee.id)
            else:
                record.co_the_but_phe_cong_van_di = False

    @api.depends('lanh_dao_xu_ly')
    def _compute_co_the_but_phe_cong_van_den(self):
        current_employee = self.env.user.employee_id
        for record in self:
            if not current_employee:
                record.co_the_but_phe_cong_van_den = False
            else:
                record.co_the_but_phe_cong_van_den = current_employee in record.lanh_dao_xu_ly

    def xac_nhan(self):
        self.ensure_one()

        # Kiểm tra người dùng hiện tại có phải là văn thư không
        user = self.env.user
        is_van_thu = user.has_group('quan_ly_cong_van.group_van_thu')
        if is_van_thu:
            # Nếu là văn thư: chuyển trạng thái thành "Đã duyệt"
            self.tt_vb = 'da_duyet'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Thành công',
                    'message': 'Văn bản đã được xác nhận và chuyển sang trạng thái Đã duyệt.',
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'reload',  # Thêm dòng này để reload trang
                    },
                }
            }
        else:
            # Nếu là người khác: chuyển trạng thái thành "Chờ duyệt"
            self.tt_vb = 'cho_duyet'

            # Gửi email thông báo cho văn thư
            self._send_email_to_van_thu()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Thành công',
                    'message': 'Văn bản đã được xác nhận và gửi thông báo cho văn thư.',
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'reload',  # Thêm dòng này để reload trang
                    },
                }
            }

    def _send_email_to_van_thu(self):
        """Gửi email thông báo cho nhóm văn thư khi có văn bản cần duyệt"""
        self.ensure_one()

        try:
            # Lấy nhóm văn thư
            group_van_thu = self.env.ref('quan_ly_cong_van.group_van_thu', raise_if_not_found=False)

            if not group_van_thu:
                _logger.warning("Không tìm thấy nhóm văn thư.")
                return

            # Lấy tất cả người dùng trong nhóm văn thư
            van_thu_users = group_van_thu.users

            # Lấy danh sách email của văn thư
            van_thu_emails = []
            for user in van_thu_users:
                if user.email:
                    van_thu_emails.append(user.email)

            if not van_thu_emails:
                _logger.warning("Không có email nào trong nhóm văn thư.")
                return

            # Chuẩn bị nội dung email
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.id}&model=office.document&view_type=form"

            current_user = self.env.user.name

            subject = f"[Văn bản cần duyệt] {self.trich_yeu}"
            body_html = f"""
            <p>Kính gửi</p>
            <p>Người dùng <b>{current_user}</b> vừa xác nhận văn bản sau và cần được duyệt:</p>

            <div style="background:#f5f5f5; padding:10px; margin:10px 0; border-left:4px solid #4CAF50;">
                <p><b>Trích yếu:</b> {self.trich_yeu or 'Không có'}</p>
                <p><b>Loại văn bản:</b> {dict(self._fields['document_type'].selection).get(self.document_type, 'Không xác định')}</p>
                <p><b>Số hiệu:</b> {self.so_hieu or 'Chưa có'}</p>
                <p><b>Ngày đến:</b> {self.ngay_den.strftime('%d/%m/%Y') if self.ngay_den else 'Chưa có'}</p>
                <p><b>Nơi gửi:</b> {self.noi_gui or 'Không có'}</p>
            </div>

            <p>
                <a href="{detail_url}" style="background:#4CAF50;color:white;padding:8px 16px;text-decoration:none;border-radius:4px;font-size:14px;font-weight:bold;">
                    Xem chi tiết và duyệt văn bản
                </a>
            </p>

            <p>Vui lòng kiểm tra và duyệt văn bản trong thời gian sớm nhất.</p>
            <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
            """

            # Gửi email đến tất cả văn thư
            for email in van_thu_emails:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_to': email,
                    'email_from': self.env.user.email or 'no-reply@company.com',
                    'body_html': body_html,
                }).send()

            _logger.info(f"Đã gửi email thông báo đến {len(van_thu_emails)} văn thư cho văn bản {self.id}")

            # Gửi thông báo popup cho văn thư (nếu có user online)
            odoobot = self.env.ref('base.user_root')
            odoobot_partner = odoobot.partner_id

            for user in van_thu_users:
                if user.partner_id and user != self.env.user:
                    try:
                        # Gửi popup thông báo
                        self.env['bus.bus']._sendone(
                            user.partner_id,
                            'simple_notification',
                            {
                                'title': 'Văn bản cần duyệt',
                                'message': f"Có văn bản mới cần duyệt: {self.trich_yeu[:50]}...",
                                'sticky': False,
                                'type': 'warning',
                            }
                        )

                        # Gửi tin nhắn chat qua Discuss
                        domain = [
                            ('channel_type', '=', 'chat'),
                            ('channel_member_ids.partner_id', 'in', [user.partner_id.id, odoobot_partner.id])
                        ]
                        channels = self.env['discuss.channel'].sudo().search(domain)

                        channel = channels.filtered(
                            lambda c: set(c.channel_member_ids.mapped('partner_id').ids) == {user.partner_id.id,
                                                                                             odoobot_partner.id}
                        )

                        if not channel:
                            channel = self.env['discuss.channel'].sudo().create({
                                'name': f"Văn bản cần duyệt: {self.trich_yeu[:30]}...",
                                'channel_type': 'chat',
                                'channel_member_ids': [
                                    (0, 0, {'partner_id': user.partner_id.id}),
                                    (0, 0, {'partner_id': odoobot_partner.id})
                                ]
                            })

                        body_chat = f"""
                        <p>📋 <b>Văn bản cần duyệt</b></p>
                        <p><b>Trích yếu:</b> {self.trich_yeu}</p>
                        <p><b>Người gửi:</b> {current_user}</p>
                        <p>
                            <a href="{detail_url}" style="background:#4CAF50;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                                Xem và duyệt
                            </a>
                        </p>
                        """

                        channel.sudo().message_post(
                            body=body_chat,
                            message_type='comment',
                            subtype_xmlid='mail.mt_comment',
                            author_id=odoobot_partner.id,
                            body_is_html=True,
                        )

                    except Exception as e:
                        _logger.error(f"Lỗi gửi thông báo cho văn thư {user.name}: {str(e)}")

        except Exception as e:
            _logger.error(f"Lỗi khi gửi email thông báo cho văn thư: {str(e)}")

    # Thêm field rejection_ids
    rejection_ids = fields.One2many(
        'office.document.rejection',
        'office_document_id',
        string='Lịch sử từ chối'
    )

    def action_open_rejection_history(self):
        """Mở popup hiển thị lịch sử từ chối"""
        self.ensure_one()

        return {
            'name': 'Lịch sử từ chối',
            'type': 'ir.actions.act_window',
            'res_model': 'office.document.rejection',
            'view_mode': 'tree,form',
            'domain': [('office_document_id', '=', self.id)],
            'context': {
                'default_office_document_id': self.id,
                'create': False,
            },
            'target': 'new',
        }

    def khong_dat(self):
        """Mở wizard từ chối"""
        self.ensure_one()

        return {
            'name': 'Từ chối văn bản',
            'type': 'ir.actions.act_window',
            'res_model': 'office.document.reject.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_van.view_reject_document_wizard_form').id,
            'target': 'new',
            'context': {
                'default_office_document_id': self.id,
            }
        }

    def _send_simple_rejection_notification(self):
        """Gửi thông báo đơn giản cho người tạo"""
        self.ensure_one()

        try:
            creator = self.create_uid
            if not creator or not creator.email:
                return

            subject = f"Văn bản không đạt: {self.trich_yeu[:50]}..."

            body_html = f"""
            <p>Văn bản của bạn <b>"{self.trich_yeu}"</b> đã bị từ chối.</p>
            <p>Vui lòng kiểm tra và chỉnh sửa lại.</p>
            """

            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': creator.email,
                'email_from': self.env.user.email or 'no-reply@company.com',
                'body_html': body_html,
            }).send()

        except Exception as e:
            _logger.warning(f"Không gửi được email từ chối: {str(e)}")

    is_van_thu = fields.Boolean(
        compute='_compute_edit_permission',
        store=False
    )
    not_is_van_thu = fields.Boolean(
        compute='_compute_edit_permission',
        store=False
    )

    @api.depends('tt_vb')
    def _compute_edit_permission(self):
        """Tính toán quyền chỉnh sửa - cập nhật để thêm trưởng đơn vị"""
        user = self.env.user
        is_van_thu_user = user.has_group('quan_ly_cong_van.group_van_thu')
        for rec in self:
            # Văn thư: draft hoặc chờ duyệt thì sửa được
            rec.is_van_thu = (
                    is_van_thu_user and
                    rec.tt_vb in ('draft', 'cho_duyet', 'da_duyet')
            )

            # Không phải văn thư: chỉ draft mới sửa được
            rec.not_is_van_thu = (
                    not is_van_thu_user and
                    rec.tt_vb == 'draft'
            )

    show_skip_button = fields.Boolean(
        compute='_compute_show_skip_button',
        store=False
    )

    def skip(self):
        self.ensure_one()
        # Cập nhật trạng thái
        self.tt_vb = 'cho_phan_phat'


    @api.depends('tt_vb', 'co_the_but_phe_cong_van_di')
    def _compute_show_skip_button(self):
        user = self.env.user
        is_van_thu = user.has_group('quan_ly_cong_van.group_van_thu')

        for record in self:
            if record.tt_vb == 'da_duyet':
                if is_van_thu:
                    record.show_skip_button = True
                else:
                    record.show_skip_button = record.co_the_but_phe_cong_van_di
            else:
                record.show_skip_button = False

    @api.constrains('document_type', 'so_hieu', 'don_vi_ban_hanh', 'don_vi_ban_hanh_ngoai')
    def _check_unique_document(self):
        for rec in self:
            if not rec.so_hieu:
                continue

            # Kiểm tra trùng cho công văn nội bộ
            if rec.document_type in ['incoming_internal', 'outgoing_internal', 'resolution', 'outgoing'] and rec.don_vi_ban_hanh:
                domain = [
                    ('id', '!=', rec.id),
                    ('document_type', '=', rec.document_type),
                    ('so_hieu', '=', rec.so_hieu),
                    ('don_vi_ban_hanh', '=', rec.don_vi_ban_hanh.id)
                ]
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        f"Đã tồn tại {duplicate.display_name} với cùng:\n"
                        f"- Loại: {dict(rec._fields['document_type'].selection).get(rec.document_type)}\n"
                        f"- Số hiệu: {rec.so_hieu}\n"
                        f"- Đơn vị ban hành: {rec.don_vi_ban_hanh.name}"
                    )

            # Kiểm tra trùng cho công văn bên ngoài
            elif rec.document_type in ['incoming'] and rec.don_vi_ban_hanh_ngoai:
                domain = [
                    ('id', '!=', rec.id),
                    ('document_type', '=', rec.document_type),
                    ('so_hieu', '=', rec.so_hieu),
                    ('don_vi_ban_hanh_ngoai', '=', rec.don_vi_ban_hanh_ngoai.id)
                ]
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        f"Đã tồn tại {duplicate.display_name} với cùng:\n"
                        f"- Loại: {dict(rec._fields['document_type'].selection).get(rec.document_type)}\n"
                        f"- Số hiệu: {rec.so_hieu}\n"
                        f"- Đơn vị ban hành: {rec.don_vi_ban_hanh_ngoai.name}"
                    )

    can_create_don_vi = fields.Boolean(
        string="Có thể tạo đơn vị mới",
        compute='_compute_can_create_don_vi',
        store=False
    )

    def _compute_can_create_don_vi(self):
        user = self.env.user
        for rec in self:
            rec.can_create_don_vi = user.has_group('quan_ly_cong_van.group_van_thu') or user.has_group(
                'base.group_system')

    def co_cong_van_dieu_chinh(self):
        """Xử lý khi có công văn điều chỉnh"""
        self.ensure_one()

        # Đặt lại trạng thái về draft để chỉnh sửa
        self.tt_vb = 'da_duyet'

        # Thông báo cho người dùng
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thông báo',
                'message': 'Văn bản đã được chuyển về trạng thái chỉnh sửa. Vui lòng cập nhật thông tin điều chỉnh.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_chuyen_lanh_dao(self):
        """Mở wizard chuyển lãnh đạo"""
        self.ensure_one()

        # Kiểm tra quyền
        current_user = self.env.user
        current_employee = self.env['hr.employee'].search(
            [('user_id', '=', current_user.id)], limit=1
        )

        if not current_employee or current_employee not in self.lanh_dao_xu_ly:
            raise UserError("Bạn không có quyền chuyển lãnh đạo cho văn bản này!")

        return {
            'name': 'Chuyển lãnh đạo',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_van.view_chuyen_lanh_dao_wizard_form').id,
            'res_model': 'office.document.chuyen.lanh.dao',
            'target': 'new',
            'context': {
                'default_office_document_id': self.id,
                'default_lanh_dao_hien_tai_id': current_employee.id,
            }
        }

    def unlink_detail2(self):
        # Kiểm tra quyền trước khi xóa
        user = self.env.user
        if not user.has_group('quan_ly_cong_van.group_van_thu'):
            raise UserError("Chỉ văn thư mới có quyền xóa bản ghi này!")

        return super().unlink()

    def _sync_related_documents(self, vals):
        if self.env.context.get('skip_link_sync'):
            return

        ctx = dict(self.env.context, skip_link_sync=True)

        for rec in self:
            try:
                # Công văn đến → công văn đi
                if 'outgoing_id' in vals:
                    if rec.outgoing_id:
                        # Kiểm tra xem công văn đi đã có incoming_id chưa
                        if rec.outgoing_id.incoming_id and rec.outgoing_id.incoming_id.id != rec.id:
                            raise ValidationError(
                                f"Công văn '{rec.outgoing_id.trich_yeu}' "
                                f"đã được kết nối với công văn đến khác: '{rec.outgoing_id.incoming_id.trich_yeu}'. "
                                f"Vui lòng chọn công văn đi khác."
                            )
                        rec.outgoing_id.with_context(ctx).write({
                            'incoming_id': rec.id
                        })
                    elif vals['outgoing_id'] is False:
                        # Xóa kết nối ngược
                        old_outgoing = self.browse(rec.id).outgoing_id
                        if old_outgoing and old_outgoing.incoming_id.id == rec.id:
                            old_outgoing.with_context(ctx).write({
                                'incoming_id': False
                            })

                # Công văn đi → công văn đến
                if 'incoming_id' in vals:
                    if rec.incoming_id:
                        if rec.incoming_id.outgoing_id and rec.incoming_id.outgoing_id.id != rec.id:
                            raise ValidationError(
                                f"Công văn '{rec.incoming_id.trich_yeu}' "
                                f"đã được kết nối với công văn đi khác: '{rec.incoming_id.outgoing_id.trich_yeu}'. "
                                f"Vui lòng chọn công văn đến khác."
                            )
                        rec.incoming_id.with_context(ctx).write({
                            'outgoing_id': rec.id
                        })
                    elif vals['incoming_id'] is False:
                        old_incoming = self.browse(rec.id).incoming_id
                        if old_incoming and old_incoming.outgoing_id.id == rec.id:
                            old_incoming.with_context(ctx).write({
                                'outgoing_id': False
                            })

                # Tương tự cho internal documents...
                if 'outgoing_internal_id' in vals:
                    if rec.outgoing_internal_id:
                        if rec.outgoing_internal_id.incoming_internal_id and rec.outgoing_internal_id.incoming_internal_id.id != rec.id:
                            raise ValidationError(
                                f"Công văn '{rec.outgoing_internal_id.trich_yeu}' "
                                f"đã được kết nối với công văn nội bộ đến khác. "
                                f"Vui lòng chọn công văn nội bộ đi khác."
                            )
                        rec.outgoing_internal_id.with_context(ctx).write({
                            'incoming_internal_id': rec.id
                        })
                    elif vals['outgoing_internal_id'] is False:
                        old_outgoing_internal = self.browse(rec.id).outgoing_internal_id
                        if old_outgoing_internal and old_outgoing_internal.incoming_internal_id.id == rec.id:
                            old_outgoing_internal.with_context(ctx).write({
                                'incoming_internal_id': False
                            })

                if 'incoming_internal_id' in vals:
                    if rec.incoming_internal_id:
                        if rec.incoming_internal_id.outgoing_internal_id and rec.incoming_internal_id.outgoing_internal_id.id != rec.id:
                            raise ValidationError(
                                f"Công văn '{rec.incoming_internal_id.trich_yeu}' "
                                f"đã được kết nối với công văn nội bộ đi khác. "
                                f"Vui lòng chọn công văn nội bộ đến khác."
                            )
                        rec.incoming_internal_id.with_context(ctx).write({
                            'outgoing_internal_id': rec.id
                        })
                    elif vals['incoming_internal_id'] is False:
                        old_incoming_internal = self.browse(rec.id).incoming_internal_id
                        if old_incoming_internal and old_incoming_internal.outgoing_internal_id.id == rec.id:
                            old_incoming_internal.with_context(ctx).write({
                                'outgoing_internal_id': False
                            })

            except Exception as e:
                _logger.error(f"Error in _sync_related_documents: {str(e)}")
                raise

    # Thêm các trường để kiểm tra
    is_linked_as_incoming = fields.Boolean(
        string="Đã được kết nối như công văn đến",
        compute='_compute_linked_status',
        store=False
    )
    is_linked_as_outgoing = fields.Boolean(
        string="Đã được kết nối như công văn đi",
        compute='_compute_linked_status',
        store=False
    )
    is_linked_as_incoming_internal = fields.Boolean(
        string="Đã được kết nối như công văn nội bộ đến",
        compute='_compute_linked_status',
        store=False
    )
    is_linked_as_outgoing_internal = fields.Boolean(
        string="Đã được kết nối như công văn nội bộ đi",
        compute='_compute_linked_status',
        store=False
    )

    @api.depends('outgoing_id', 'incoming_id', 'outgoing_internal_id', 'incoming_internal_id')
    def _compute_linked_status(self):
        """Tính toán trạng thái kết nối"""
        for rec in self:
            rec.is_linked_as_incoming = bool(rec.incoming_id)
            rec.is_linked_as_outgoing = bool(rec.outgoing_id)
            rec.is_linked_as_incoming_internal = bool(rec.incoming_internal_id)
            rec.is_linked_as_outgoing_internal = bool(rec.outgoing_internal_id)

    @api.constrains(
        'outgoing_internal_id', 'incoming_internal_id',
        'outgoing_id', 'incoming_id'
    )
    def _check_single_connection(self):
        """Kiểm tra mỗi công văn chỉ được kết nối với một công văn khác"""
        if self.env.context.get('skip_link_sync'):
            return

        for rec in self:
            # Đếm số lượng kết nối
            connections = []
            if rec.outgoing_internal_id:
                connections.append(('outgoing_internal_id', rec.outgoing_internal_id.display_name))
            if rec.incoming_internal_id:
                connections.append(('incoming_internal_id', rec.incoming_internal_id.display_name))
            if rec.outgoing_id:
                connections.append(('outgoing_id', rec.outgoing_id.display_name))
            if rec.incoming_id:
                connections.append(('incoming_id', rec.incoming_id.display_name))

            # Kiểm tra nếu có nhiều hơn 1 kết nối
            if len(connections) > 1:
                connection_names = ", ".join([f"{field}: {name}" for field, name in connections])
                raise ValidationError(
                    f"Mỗi công văn chỉ được kết nối với một công văn khác. "
                    f"Hiện tại có {len(connections)} kết nối: {connection_names}"
                )

    @api.constrains('outgoing_internal_id')
    def _check_outgoing_internal_unique(self):
        if self.env.context.get('skip_link_sync'):
            return
        """Kiểm tra outgoing_internal_id không được trùng"""
        for rec in self:
            if rec.outgoing_internal_id:
                # Kiểm tra xem công văn đã được kết nối chưa
                existing = self.search([
                    ('outgoing_internal_id', '=', rec.outgoing_internal_id.id),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        f"Công văn '{rec.outgoing_internal_id.trich_yeu}' "
                        f"đã được kết nối với công văn '{existing.trich_yeu}'. "
                        f"Mỗi công văn chỉ được kết nối một lần."
                    )

    @api.constrains('incoming_internal_id')
    def _check_incoming_internal_unique(self):
        if self.env.context.get('skip_link_sync'):
            return
        """Kiểm tra incoming_internal_id không được trùng"""
        for rec in self:
            if rec.incoming_internal_id:
                existing = self.search([
                    ('incoming_internal_id', '=', rec.incoming_internal_id.id),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        f"Công văn '{rec.incoming_internal_id.trich_yeu}' "
                        f"đã được kết nối với công văn '{existing.trich_yeu}'. "
                        f"Mỗi công văn chỉ được kết nối một lần."
                    )

    @api.constrains('outgoing_id')
    def _check_outgoing_unique(self):
        if self.env.context.get('skip_link_sync'):
            return
        """Kiểm tra outgoing_id không được trùng"""
        for rec in self:
            if rec.outgoing_id:
                existing = self.search([
                    ('outgoing_id', '=', rec.outgoing_id.id),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        f"Công văn '{rec.outgoing_id.trich_yeu}' "
                        f"đã được kết nối với công văn '{existing.trich_yeu}'. "
                        f"Mỗi công văn chỉ được kết nối một lần."
                    )

    @api.constrains('incoming_id')
    def _check_incoming_unique(self):
        if self.env.context.get('skip_link_sync'):
            return
        """Kiểm tra incoming_id không được trùng"""
        for rec in self:
            if rec.incoming_id:
                existing = self.search([
                    ('incoming_id', '=', rec.incoming_id.id),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        f"Công văn '{rec.incoming_id.trich_yeu}' "
                        f"đã được kết nối với công văn '{existing.trich_yeu}'. "
                        f"Mỗi công văn chỉ được kết nối một lần."
                    )

    def trinh_truong_don_vi(self):
        """Trình văn bản lên trưởng đơn vị duyệt"""
        self.ensure_one()

        # Cập nhật trạng thái
        self.tt_vb = 'cho_truong_don_vi_duyet'

        # Gửi thông báo cho trưởng đơn vị
        self._send_notification_to_truong_don_vi()

        return True

    def _send_notification_to_truong_don_vi(self):
        """Gửi thông báo cho trưởng đơn vị"""
        truong_don_vi = self.truong_don_vi_duyet
        if not truong_don_vi or not truong_don_vi.user_id:
            return

        doc_url = self.get_form_url()
        partner = truong_don_vi.user_id.partner_id

        # 1. Gửi email
        try:
            email = truong_don_vi.work_email or truong_don_vi.user_id.email
            if email:
                body_html = f"""
                    <p>Xin chào {truong_don_vi.name},</p>
                    <p>Văn bản <b>{self.trich_yeu}</b> cần được bạn duyệt.</p>
                    <p>
                        <a href="{doc_url}" style="background:#4CAF50;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                            Xem chi tiết văn bản
                        </a>
                    </p>
                    <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
                """
                self.env['mail.mail'].sudo().create({
                    'subject': f"[Văn bản cần duyệt] {self.trich_yeu}",
                    'email_to': email,
                    'email_from': self.env.user.email or 'no-reply@company.com',
                    'body_html': body_html,
                }).send()
        except Exception as e:
            _logger.warning(f"Gửi mail thất bại cho {truong_don_vi.name}: {str(e)}")

        # 2. Gửi popup/notification
        try:
            self.env['bus.bus']._sendone(
                partner,
                'simple_notification',
                {
                    'title': 'Văn bản cần duyệt',
                    'message': f"Văn bản '{self.trich_yeu}' cần được bạn duyệt.",
                    'sticky': False,
                    'type': 'info',
                }
            )
        except Exception as e:
            _logger.warning(f"Gửi notification thất bại cho {truong_don_vi.name}: {str(e)}")

    show_phan_phat_button = fields.Boolean(
        compute='_compute_show_phan_phat_button',
        store=False
    )

    def _compute_show_phan_phat_button(self):
        """Tính toán khi nào hiển thị nút phân phát"""
        user = self.env.user
        is_van_thu = user.has_group('quan_ly_cong_van.group_van_thu')

        for rec in self:
            # Mặc định: văn thư có thể phân phát
            if is_van_thu:
                rec.show_phan_phat_button = True
                continue

            # Kiểm tra nếu người dùng là manager trong detail2
            current_employee = self.env['hr.employee'].search([
                ('user_id', '=', user.id)
            ], limit=1)

            if not current_employee:
                rec.show_phan_phat_button = False
                continue

            # Tìm detail2 record của người dùng hiện tại
            user_detail = rec.detail2.filtered(
                lambda d: d.nguoi_nhap_y_kien.id == current_employee.id
            )

            # Nếu có record và có quyền phân phát
            rec.show_phan_phat_button = any(
                detail.allow_phan_phat for detail in user_detail
            )


'''class AssignTaskWizard(models.TransientModel):
    _name = 'assign.task.wizard'
    _description = 'Giao việc - Danh sách từng người'

    detail_id = fields.Many2one('office.document.detail2', required=True, readonly=True)
    office_document_id = fields.Many2one('office.document', readonly=True)

    # Dòng giao việc (tree view)
    line_ids = fields.One2many(
        'assign.task.wizard.line',
        'wizard_id',
        string='Danh sách giao việc',
    )

    def action_assign(self):
        self.ensure_one()
        manager = self.detail_id
        current_user = self.env.user.employee_ids[:1]  # employee đang bấm nút
        vals_list = []

        for line in self.line_ids.filtered('cong_viec'):
            vals = {
                'office_document_id': self.office_document_id.id,
                'nguoi_nhap_y_kien': line.nguoi_nhap_y_kien.id,
                'nhom_phong_ban': manager.nhom_phong_ban,
                'noi_dung_chi_dao': manager.noi_dung_chi_dao,
                'cong_viec': line.cong_viec,
                'thoi_diem_chi_dao': fields.Datetime.now(),
                'chuc_vu': 'nhan_vien',
                'nguoi_quan_ly': current_user.id if current_user else False,
                'sequence': manager.sequence + 1,
            }
            vals_list.append(vals)

        if vals_list:
            created_lines = self.env['office.document.detail2'].create(vals_list)

            # --- Gửi email trực tiếp ---
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.office_document_id.id}&model=office.document&view_type=form"

            for line in created_lines:
                emp = line.nguoi_nhap_y_kien
                email = emp.work_email or (emp.user_id.email if emp.user_id else False)
                if email:
                    try:
                        subject = f"[Văn bản mới] {self.office_document_id.trich_yeu}"
                        body_html = f"""
                            <p>Xin chào {emp.name},</p>
                            <p>Bạn vừa được giao xử lý văn bản: <b>{self.office_document_id.trich_yeu}</b>.</p>
                            <p>
                                <a href="{detail_url}" style="background:#875A7B;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                                    Xem chi tiết văn bản
                                </a>
                            </p>
                            <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
                        """
                        self.env['mail.mail'].sudo().create({
                            'subject': subject,
                            'email_to': email,
                            'email_from': self.env.user.email or 'odoobot@example.com',
                            'body_html': body_html,
                        }).send()
                    except Exception as e:
                        _logger.error(f"Lỗi gửi email cho {emp.name}: {str(e)}")

            # --- Gửi thông báo popup + chat ---
            odoobot = self.env.ref('base.user_root')
            odoobot_partner = odoobot.partner_id
            partners = created_lines.mapped('nguoi_nhap_y_kien.user_id.partner_id')

            body_chat = f"""
            <p>📄 Bạn vừa được giao xử lý văn bản: <b>{self.office_document_id.trich_yeu}</b>.</p>
            <p>
                <a href="{detail_url}" style="background:#875A7B;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                    Xem chi tiết
                </a>
            </p>
            """

            for partner in partners:
                # popup real-time
                self.env['bus.bus']._sendone(
                    partner,
                    'simple_notification',
                    {
                        'title': 'Văn bản mới được giao',
                        'message': f"Bạn vừa được giao xử lý văn bản: {self.office_document_id.trich_yeu}",
                        'sticky': False,
                        'type': 'info',
                    }
                )

                # chat qua Discuss
                try:
                    domain = [
                        ('channel_type', '=', 'chat'),
                        ('channel_member_ids.partner_id', 'in', [partner.id, odoobot_partner.id])
                    ]
                    channels = self.env['discuss.channel'].sudo().search(domain)
                    channel = channels.filtered(
                        lambda c: set(c.channel_member_ids.mapped('partner_id').ids) == {partner.id, odoobot_partner.id})
                    if not channel:
                        channel = self.env['discuss.channel'].sudo().create({
                            'name': f"Giao việc: {partner.name}",
                            'channel_type': 'chat',
                            'channel_member_ids': [(0, 0, {'partner_id': partner.id}),
                                                   (0, 0, {'partner_id': odoobot_partner.id})]
                        })
                    channel.sudo().message_post(
                        body=body_chat,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=odoobot_partner.id,
                        body_is_html=True,
                    )
                except Exception as e:
                    _logger.error(f"Lỗi gửi chat cho {partner.name}: {str(e)}")

        return {'type': 'ir.actions.act_window_close'}


class AssignTaskWizardLine(models.TransientModel):
    _name = 'assign.task.wizard.line'
    _description = 'Dòng giao việc'

    wizard_id = fields.Many2one('assign.task.wizard', required=True, ondelete='cascade')
    employee_id = fields.Many2one('office.document.detail2')
    cong_viec = fields.Text(string="Công việc", required=False)

    nguoi_nhap_y_kien = fields.Many2one(
        'hr.employee',
        string="Nhân viên",
    )

    @api.onchange('wizard_id')
    def _onchange_wizard_id(self):
        """Set domain cho field 'nguoi_nhap_y_kien' theo phòng ban của document"""
        if not self.wizard_id or not self.wizard_id.detail_id or not self.wizard_id.detail_id.nhom_phong_ban:
            return {'domain': {'nguoi_nhap_y_kien': [('id', '=', False)]}}

        department_name = self.wizard_id.detail_id.nhom_phong_ban

        # Lấy nhân viên theo phòng ban
        employees = self.env['hr.employee'].search([
            ('department_id.name', '=', department_name)
        ])
        return {'domain': {'nguoi_nhap_y_kien': [('id', 'in', employees.ids)] if employees else [('id', '=', False)]}}
'''

class ChuyenLanhDaoWizard(models.TransientModel):
    _name = 'office.document.chuyen.lanh.dao'
    _description = 'Chuyển lãnh đạo xử lý'

    office_document_id = fields.Many2one(
        'office.document',
        string='Văn bản',
        required=True,
        readonly=True
    )

    lanh_dao_hien_tai_id = fields.Many2one(
        'hr.employee',
        string='Lãnh đạo hiện tại',
        required=True,
        readonly=True
    )

    lanh_dao_moi_id = fields.Many2one(
        'hr.employee',
        string='Lãnh đạo mới',
        required=True,
        domain="[('id', '!=', lanh_dao_hien_tai_id)]"
    )

    @api.constrains('lanh_dao_moi_id')
    def _check_lanh_dao_moi(self):
        for rec in self:
            if rec.lanh_dao_moi_id == rec.lanh_dao_hien_tai_id:
                raise ValidationError("Lãnh đạo mới không được trùng với lãnh đạo hiện tại!")

    def action_chuyen(self):
        """Thực hiện chuyển lãnh đạo"""
        self.ensure_one()

        doc = self.office_document_id
        lanh_dao_cu = self.lanh_dao_hien_tai_id
        lanh_dao_moi = self.lanh_dao_moi_id

        # 1. Cập nhật danh sách lãnh đạo xử lý
        current_leaders = doc.lanh_dao_xu_ly
        new_leaders = current_leaders - lanh_dao_cu + lanh_dao_moi

        doc.write({
            'lanh_dao_xu_ly': [(6, 0, new_leaders.ids)]
        })

        # 3. Gửi thông báo cho lãnh đạo mới
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        detail_url = f"{web_url}/web#id={doc.id}&model=office.document&view_type=form"

        # Thông báo popup
        if lanh_dao_moi.user_id:
            try:
                partner = lanh_dao_moi.user_id.partner_id
                self.env['bus.bus']._sendone(
                    partner,
                    'simple_notification',
                    {
                        'title': 'Được chuyển xử lý văn bản',
                        'message': f"Bạn vừa được chuyển xử lý văn bản: {doc.trich_yeu}",
                        'sticky': False,
                        'type': 'info',
                    }
                )
            except Exception as e:
                _logger.warning(f"Gửi notification thất bại: {str(e)}")

        # Gửi email
        try:
            email = lanh_dao_moi.work_email or (lanh_dao_moi.user_id.email if lanh_dao_moi.user_id else None)
            if email:
                subject = f"[Chuyển xử lý] {doc.trich_yeu}"
                body_html = f"""
                <p>Xin chào {lanh_dao_moi.name},</p>
                <p>Bạn vừa được chuyển xử lý văn bản: <b>{doc.trich_yeu}</b>.</p>
                <p><b>Chuyển từ:</b> {lanh_dao_cu.name}</p>
                <p>
                    <a href="{detail_url}" style="background:#875A7B;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                        Xem chi tiết văn bản
                    </a>
                </p>
                <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
                """
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_to': email,
                    'email_from': self.env.user.email or 'no-reply@company.com',
                    'body_html': body_html,
                }).send()
        except Exception as e:
            _logger.warning(f"Gửi mail thất bại: {str(e)}")

        return {
            'type': 'ir.actions.client',
            'tag': 'history_back',  # Tag phải khớp với tên đăng ký trong JS
        }

    def cancel(self):
        return {'type': 'ir.actions.act_window_close'}

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        # Chỉ áp dụng cho wizard phân phát
        if self.env.context.get('phan_phat_full_label'):
            args = args or []
            domain = args + ['|', '|',
                ('name', operator, name),
                ('department_id.name', operator, name),
                ('position_id.name', operator, name),
            ]
            employees = self.search(domain, limit=limit)
            return [
                (
                    emp.id,
                    f"{emp.name} - {emp.department_id.name or ''} - {emp.position_id.name or ''}".strip(' -')
                )
                for emp in employees
            ]

        # Mặc định: giữ nguyên hành vi gốc
        return super().name_search(name, args, operator, limit)


class OfficeDocumentRejection(models.Model):
    """Lịch sử từ chối văn bản"""
    _name = 'office.document.rejection'
    _description = 'Lịch sử từ chối văn bản'
    _order = 'rejection_date desc'

    office_document_id = fields.Many2one(
        'office.document',
        string='Văn bản',
        required=True,
        ondelete='cascade'
    )

    rejection_reason = fields.Text(
        string='Lý do từ chối',
        required=True
    )

    rejected_by = fields.Many2one(
        'res.users',
        string='Người từ chối',
        required=True,
        default=lambda self: self.env.user
    )

    rejection_date = fields.Datetime(
        string='Thời gian từ chối',
        required=True,
        default=fields.Datetime.now
    )



# ========== 2. THÊM WIZARD TỪ CHỐI ==========

class RejectDocumentWizard(models.TransientModel):
    """Wizard nhập lý do từ chối"""
    _name = 'office.document.reject.wizard'
    _description = 'Nhập lý do từ chối văn bản'

    office_document_id = fields.Many2one(
        'office.document',
        string='Văn bản',
        required=True,
        readonly=True
    )

    rejection_reason = fields.Text(
        string='Lý do từ chối',
        required=True,
        placeholder='Vui lòng nhập lý do từ chối văn bản...'
    )


    def action_confirm_reject(self):
        """Xác nhận từ chối"""
        self.ensure_one()

        # 1. Tạo bản ghi lịch sử từ chối
        self.env['office.document.rejection'].create({
            'office_document_id': self.office_document_id.id,
            'rejection_reason': self.rejection_reason,
            'rejected_by': self.env.user.id,
            'rejection_date': fields.Datetime.now(),
        })

        # 2. Cập nhật trạng thái văn bản
        self.office_document_id.tt_vb = 'draft'

        # 3. Gửi thông báo cho người tạo
        self._send_rejection_notification()

        return {
            'type': 'ir.actions.client',
            'tag': 'history_back',  # Tag phải khớp với tên đăng ký trong JS
        }

    def _send_rejection_notification(self):
        """Gửi thông báo từ chối cho người tạo"""
        self.ensure_one()
        doc = self.office_document_id
        creator = doc.create_uid

        if not creator or not creator.email:
            return

        try:
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={doc.id}&model=office.document&view_type=form"

            subject = f"[Văn bản bị từ chối] {doc.trich_yeu[:50]}..."
            body_html = f"""
            <p>Xin chào {creator.name},</p>

            <p>Văn bản <b>"{doc.trich_yeu}"</b> của bạn đã bị từ chối.</p>

            <div style="background:#ffebee; padding:10px; margin:10px 0; border-left:4px solid #f44336;">
                <p><b>Người từ chối:</b> {self.env.user.name}</p>
                <p><b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                <p><b>Lý do từ chối:</b></p>
                <p style="white-space: pre-wrap;">{self.rejection_reason}</p>
            </div>

            <p>Vui lòng kiểm tra và chỉnh sửa lại văn bản.</p>

            <p>
                <a href="{detail_url}" style="background:#f44336;color:white;padding:8px 16px;text-decoration:none;border-radius:4px;font-size:14px;">
                    Xem chi tiết văn bản
                </a>
            </p>

            <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
            """

            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_to': creator.email,
                'email_from': self.env.user.email or 'no-reply@company.com',
                'body_html': body_html,
            }).send()

            # Gửi popup notification
            if creator.partner_id:
                self.env['bus.bus']._sendone(
                    creator.partner_id,
                    'simple_notification',
                    {
                        'title': 'Văn bản bị từ chối',
                        'message': f'Văn bản "{doc.trich_yeu[:50]}..." đã bị từ chối.',
                        'sticky': False,
                        'type': 'warning',
                    }
                )

        except Exception as e:
            _logger.error(f"Lỗi gửi thông báo từ chối: {str(e)}")

    def action_cancel(self):
        """Hủy từ chối"""
        return {'type': 'ir.actions.act_window_close'}
