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

# =====================================================================
# EMAIL CONSTANTS
# =====================================================================
CC_EMAIL_DIEP = 'lediephx@gmail.com'


def _build_email_html(title, greeting, body_lines, detail_url, btn_label='XEM CHI TIẾT VĂN BẢN',
                      btn_color='#875A7B', company_name=''):
    """
    Template email chuẩn dùng chung cho toàn hệ thống.
    - title: tiêu đề khối header (VD: 'PHÂN PHÁT VĂN BẢN')
    - greeting: câu chào (VD: 'Kính gửi: <b>Nguyễn Văn A</b>,')
    - body_lines: list các chuỗi HTML hiển thị trong khối nội dung
    - detail_url: đường dẫn truy cập văn bản
    - btn_label: nhãn nút
    - btn_color: màu nút (mặc định tím Odoo)
    - company_name: tên công ty
    """
    body_html_lines = '\n'.join(f'<p>{line}</p>' for line in body_lines)
    return f"""
<div style="font-family: Arial, sans-serif; max-width: 620px; margin: 0 auto; border:1px solid #e0e0e0; border-radius:6px; overflow:hidden;">
  <div style="background:{btn_color}; padding:18px 24px;">
    <h3 style="color:#ffffff; margin:0; font-size:16px;">📄 {title}</h3>
  </div>
  <div style="padding:24px;">
    <p>{greeting}</p>
    <div style="background:#f7f7f7; padding:16px; border-left:4px solid {btn_color}; margin:16px 0; border-radius:0 4px 4px 0;">
      {body_html_lines}
    </div>
    <div style="text-align:center; margin:28px 0;">
      <a href="{detail_url}"
         style="background:{btn_color}; color:#ffffff; padding:12px 28px;
                text-decoration:none; border-radius:5px; font-size:15px;
                font-weight:bold; display:inline-block;">
        📌 {btn_label}
      </a>
    </div>
    <p style="color:#888; font-size:12px; margin-top:24px;">
      <em>Đây là email tự động từ Hệ thống quản lý công văn. Vui lòng không trả lời email này.</em>
    </p>
  </div>
  <div style="background:#f0f0f0; padding:14px 24px; border-top:1px solid #e0e0e0;">
    <p style="margin:0; color:#666; font-size:12px;">
      Trân trọng,<br/>
      <b>Hệ thống quản lý công văn</b><br/>
      {company_name}
    </p>
  </div>
</div>
"""


def _send_mail(env, subject, email_to_list, body_html, email_from=None, reply_to=None):
    """
    Hàm gửi email dùng chung.
    - email_to_list: list email của người nhận (chỉ employee)
    - Tự động CC cho Diệp
    """
    if not email_to_list:
        return

    company = env.company
    from_addr = email_from or f'TEDI ERP <{company.email or "noreply@tedierp.com"}>'
    reply = reply_to or env.user.email or company.email

    # Lọc email hợp lệ
    valid_emails = [e.strip() for e in email_to_list if e and '@' in e and '.' in e]
    if not valid_emails:
        return

    mail_vals = {
        'subject': subject,
        'email_to': ', '.join(valid_emails),
        'email_from': from_addr,
        'body_html': body_html,
        'reply_to': reply,
        'email_cc': CC_EMAIL_DIEP,
    }

    try:
        mail = env['mail.mail'].sudo().create(mail_vals)
        mail.send()
        _logger.info(f"✅ Email gửi đến: {', '.join(valid_emails)} | CC: {CC_EMAIL_DIEP}")
    except Exception as e:
        _logger.error(f"❌ Gửi email thất bại: {str(e)}")


def _get_employee_emails(employees):
    """Chỉ lấy email của employee (work_email), không lấy từ user."""
    emails = []
    for emp in employees:
        if emp.work_email and '@' in emp.work_email:
            emails.append(emp.work_email.strip())
        else:
            _logger.warning(f"✗ Không có work_email cho nhân viên: {emp.name} (ID: {emp.id})")
    return emails


# =====================================================================


class PhanPhat(models.TransientModel):
    _name = 'office.document.phan.phat'

    loai_phan_phat = fields.Selection([
        ('don_vi', 'Cho đơn vị'),
        ('ca_nhan', 'Cho cá nhân'),
        ('ca_hai', 'Cho cả đơn vị và cá nhân'),
    ], string='Loại phân phát', default='don_vi', required=True)

    nhan_van_ban = fields.Char('Nhận văn bản')

    # ----- Đơn vị -----
    don_vi_xu_ly_chinh = fields.Many2one(
        'hr.department',
        string='Đơn vị xử lý chính',
        domain=lambda self: self._get_department_domain()
    )
    don_vi_dong_xu_ly = fields.Many2many(
        'hr.department',
        'office_document_dv_dong_xu_ly_rel',
        'phanphat_id', 'department_id',
        string='Đơn vị đồng xử lý',
        domain=lambda self: self._get_department_domain()
    )

    # ----- Cá nhân và đơn vị nhận -----
    pb_dv_nhan = fields.Many2one('hr.department', string='Phòng ban')
    ca_nhan_dv_nhan = fields.Many2one(
        'res.users',
        string='Cá nhân',
        domain=lambda self: self._get_user_domain()
    )
    nhom_nguoi_dung_dv_nhan = fields.Char('Nhóm người dùng')
    noi_nhan_ban_goc_luu_tru = fields.Char('Nơi nhận bản gốc lưu trữ')

    # ----- Người xử lý từ đơn vị -----
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

    # ----- Cá nhân xử lý -----
    ca_nhan_xu_ly_chinh = fields.Many2many(
        'hr.employee',
        'office_document_ca_nhan_xu_ly_chinh_employee_rel',
        'phanphat_id', 'employee_id',
        string='Người xử lý chính',
        domain=lambda self: self._get_employee_domain()
    )
    ca_nhan_dong_xu_ly = fields.Many2many(
        'hr.employee',
        'office_document_ca_nhan_dong_xu_ly_employee_rel',
        'phanphat_id', 'employee_id',
        string='Người đồng xử lý',
        domain=lambda self: self._get_employee_domain()
    )

    # ----- KIỂM TRA QUYỀN VĂN THƯ -----
    def _is_van_thu(self):
        van_thu_group = self.env.ref('quan_ly_cong_van.group_van_thu', raise_if_not_found=False)
        if van_thu_group and self.env.user.has_group('quan_ly_cong_van.group_van_thu'):
            return True
        return False

    def _is_truong_don_vi(self):
        """Kiểm tra user hiện tại có phải là trưởng đơn vị (manager) không"""
        employee = self.env.user.employee_id
        if not employee:
            return False
        departments_managed = self.env['hr.department'].search([
            ('manager_id', '=', employee.id),
        ])
        return bool(departments_managed)

    def _can_phan_phat(self):
        """Có quyền phân phát nếu là văn thư hoặc trưởng đơn vị"""
        return self._is_van_thu() or self._is_truong_don_vi()

    def _get_child_departments(self, department):
        childs = self.env['hr.department'].search([('parent_id', '=', department.id)])
        all_childs = childs
        for child in childs:
            all_childs |= self._get_child_departments(child)
        return all_childs

    # ----- DOMAIN CHO DEPARTMENT - SỬA LẠI CHO VĂN THƯ -----
    def _get_department_domain(self):
        """Nếu là văn thư thì xem tất cả, nếu không thì chỉ xem đơn vị của mình và cấp dưới"""
        if self._is_van_thu():
            return []  # Văn thư xem tất cả phòng ban
        employee = self.env.user.employee_id
        if not employee or not employee.department_id:
            return [('id', '=', False)]
        current_dept = employee.department_id
        child_depts = self._get_child_departments(current_dept)
        dept_ids = [current_dept.id] + child_depts.ids
        return [('id', 'in', dept_ids)]

    # ----- DOMAIN CHO EMPLOYEE - SỬA LẠI CHO VĂN THƯ -----
    def _get_employee_domain(self):
        """Nếu là văn thư thì xem tất cả nhân viên, nếu không thì chỉ xem nhân viên trong đơn vị của mình và cấp dưới"""
        if self._is_van_thu():
            return []  # Văn thư xem tất cả nhân viên
        employee = self.env.user.employee_id
        if not employee or not employee.department_id:
            return [('id', '=', False)]
        current_dept = employee.department_id
        child_depts = self._get_child_departments(current_dept)
        dept_ids = [current_dept.id] + child_depts.ids
        return [('department_id', 'in', dept_ids)]

    # ----- DOMAIN CHO USER - SỬA LẠI CHO VĂN THƯ -----
    def _get_user_domain(self):
        """Nếu là văn thư thì xem tất cả users, nếu không thì chỉ xem users trong đơn vị của mình và cấp dưới"""
        if self._is_van_thu():
            return []  # Văn thư xem tất cả users
        employee = self.env.user.employee_id
        if not employee or not employee.department_id:
            return [('id', '=', False)]
        current_dept = employee.department_id
        child_depts = self._get_child_departments(current_dept)
        dept_ids = [current_dept.id] + child_depts.ids
        employees = self.env['hr.employee'].search([('department_id', 'in', dept_ids)])
        return [('employee_ids', 'in', employees.ids)] if employees else [('id', '=', False)]

    # ----- CONSTRAINTS -----
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

    @api.constrains('don_vi_xu_ly_chinh')
    def _check_don_vi_permission(self):
        for rec in self:
            if not rec.don_vi_xu_ly_chinh:
                continue
            if not rec._is_van_thu():
                employee = self.env.user.employee_id
                if employee and employee.department_id:
                    current_dept = employee.department_id
                    child_depts = rec._get_child_departments(current_dept)
                    allowed_dept_ids = [current_dept.id] + child_depts.ids
                    if rec.don_vi_xu_ly_chinh.id not in allowed_dept_ids:
                        raise ValidationError("Bạn chỉ được phép chọn đơn vị của mình hoặc đơn vị cấp dưới!")

    @api.constrains('ca_nhan_xu_ly_chinh', 'ca_nhan_dong_xu_ly')
    def _check_ca_nhan_permission(self):
        for rec in self:
            if not rec._is_van_thu():
                employee = self.env.user.employee_id
                if employee and employee.department_id:
                    current_dept = employee.department_id
                    child_depts = rec._get_child_departments(current_dept)
                    allowed_dept_ids = [current_dept.id] + child_depts.ids
                    allowed_employees = self.env['hr.employee'].search([('department_id', 'in', allowed_dept_ids)])
                    for emp in rec.ca_nhan_xu_ly_chinh:
                        if emp not in allowed_employees:
                            raise ValidationError(
                                f"Bạn không có quyền chọn nhân viên {emp.name} vì không cùng phòng ban hoặc phòng ban cấp dưới!")
                    for emp in rec.ca_nhan_dong_xu_ly:
                        if emp not in allowed_employees:
                            raise ValidationError(
                                f"Bạn không có quyền chọn nhân viên {emp.name} vì không cùng phòng ban hoặc phòng ban cấp dưới!")

    # ----- COMPUTE FIELD -----
    @api.depends('don_vi_xu_ly_chinh')
    def _compute_nguoi_xu_ly_chinh(self):
        for rec in self:
            if not rec.don_vi_xu_ly_chinh:
                rec.nguoi_xu_ly_chinh = False
                continue
            dept = rec.don_vi_xu_ly_chinh
            employees = dept.manager_id | dept.manager_ids
            rec.nguoi_xu_ly_chinh = employees.filtered(bool)

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

    # ----- PHƯƠNG THỨC CHÍNH -----
    def phan_phat(self):
        doc_id = self.env.context.get('active_id')
        if not doc_id:
            return

        doc = self.env['office.document'].browse(doc_id)
        if not doc.exists():
            return

        nguoi_xu_ly_chinh_ids = []
        nguoi_dong_xu_ly_ids = []

        if self.loai_phan_phat in ('don_vi', 'ca_hai'):
            nguoi_xu_ly_chinh_ids += self.nguoi_xu_ly_chinh.ids
            nguoi_dong_xu_ly_ids += self.nguoi_dong_xu_ly.ids
        if self.loai_phan_phat in ('ca_nhan', 'ca_hai'):
            nguoi_xu_ly_chinh_ids += self.ca_nhan_xu_ly_chinh.ids
            nguoi_dong_xu_ly_ids += self.ca_nhan_dong_xu_ly.ids

        nguoi_xu_ly_chinh_ids = list(set(nguoi_xu_ly_chinh_ids))
        nguoi_dong_xu_ly_ids = list(set(nguoi_dong_xu_ly_ids))

        update_data = {'tt_vb': 'cho_xu_ly'}
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

        # Tạo detail2 CHỈ cho người CHƯA có
        lines_to_create = []
        employees_list = []
        if nguoi_xu_ly_chinh_ids:
            employees_list.extend(
                [(emp, 'Xử lý chính') for emp in self.env['hr.employee'].browse(nguoi_xu_ly_chinh_ids)])
        if nguoi_dong_xu_ly_ids:
            employees_list.extend(
                [(emp, 'Đồng xử lý') for emp in self.env['hr.employee'].browse(nguoi_dong_xu_ly_ids)])

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

        # Gửi email – chỉ dùng work_email của employee
        all_employees = self.env['hr.employee'].browse(nguoi_xu_ly_chinh_ids + nguoi_dong_xu_ly_ids)
        email_list = _get_employee_emails(all_employees)
        name_list = [emp.name for emp in all_employees if emp.work_email and '@' in emp.work_email]

        if email_list:
            detail_url = doc.get_form_url()
            names_str = ', '.join(name_list)
            subject = f"Phân phát văn bản: {doc.trich_yeu[:50]}..." if doc.trich_yeu else "Phân phát văn bản"
            body_lines = [
                f"<b>Trích yếu:</b> {doc.trich_yeu or 'Không có'}",
                f"<b>Mã văn bản:</b> {doc.so_vb or 'Không có mã'}",
                f"<b>Ngày phân phát:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ]
            body_html = _build_email_html(
                title='PHÂN PHÁT VĂN BẢN',
                greeting=f"Kính gửi: <b>{names_str}</b>,<br/>Bạn vừa được phân công xử lý văn bản.",
                body_lines=body_lines,
                detail_url=detail_url,
                company_name=self.env.company.name or '',
            )
            _send_mail(self.env, subject, email_list, body_html)

        # Gửi popup notification
        for employee in all_employees:
            user = employee.user_id
            if not user or not user.partner_id:
                continue
            try:
                self.env['bus.bus']._sendone(
                    user.partner_id,
                    'simple_notification',
                    {
                        'title': 'Phân phát văn bản mới',
                        'message': f"Bạn được giao xử lý văn bản: {doc.trich_yeu}",
                        'sticky': False,
                        'type': 'info',
                    }
                )
            except Exception as e:
                _logger.warning(f"Lỗi gửi notification: {str(e)}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': f'Đã phân phát văn bản và gửi email đến {len(email_list)} người.',
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
                'params': {'title': 'Lỗi', 'message': 'Chưa có văn bản để bút phê.', 'type': 'warning', 'sticky': False}
            }

        doc = self.env['office.document'].browse(doc_id)
        if not doc.exists():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': 'Lỗi', 'message': 'Văn bản không tồn tại.', 'type': 'warning', 'sticky': False}
            }

        doc.write({'but_phe': self.y_kien_xu_ly, 'tt_vb': 'cho_phan_phat'})

        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        nhom_phong_ban = employee.department_id.name if employee and employee.department_id else 'Không xác định'

        self.env['office.document.detail1'].create({
            'office_document_id': doc.id,
            'nguoi_nhap_y_kien': employee.id if employee else False,
            'nhom_phong_ban': nhom_phong_ban,
            'noi_dung_chi_dao': self.y_kien_xu_ly or 'Không có ý kiến',
            'thoi_diem_chi_dao': fields.Datetime.now(),
        })

        # Gửi email cho VĂN THƯ – chỉ dùng work_email
        group = self.env.ref('quan_ly_cong_van.group_van_thu', raise_if_not_found=False)
        if group and group.users:
            van_thu_employees = self.env['hr.employee'].search([
                ('user_id', 'in', group.users.ids)
            ])
            email_list = _get_employee_emails(van_thu_employees)
            if email_list:
                detail_url = doc.get_form_url()
                subject = f"Văn bản đã bút phê: {doc.trich_yeu[:50]}..." if doc.trich_yeu else "Văn bản đã bút phê"
                body_lines = [
                    f"<b>Số văn bản:</b> {doc.so_vb or 'Chưa có số'}",
                    f"<b>Trích yếu:</b> {doc.trich_yeu or 'Không có'}",
                    f"<b>Người bút phê:</b> {employee.name if employee else self.env.user.name}",
                    f"<b>Ý kiến:</b> {self.y_kien_xu_ly or 'Không có ý kiến'}",
                    f"<b>Quan trọng:</b> {'Có' if self.quan_trong else 'Không'}",
                    f"<b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}",
                ]
                body_html = _build_email_html(
                    title='VĂN BẢN ĐÃ ĐƯỢC BÚT PHÊ',  # Đồng bộ format với các chức năng khác
                    greeting='Kính gửi Anh/Chị Văn thư,<br/>Văn bản sau đã được bút phê, vui lòng xử lý phân phát.',
                    body_lines=body_lines,
                    detail_url=detail_url,
                    btn_label='XEM CHI TIẾT VĂN BẢN',  # Đồng bộ với các chức năng khác
                    btn_color='#875A7B',
                    company_name=self.env.company.name or '',
                )
                _send_mail(self.env, subject, email_list, body_html)

                # CHỈ gửi thông báo popup, KHÔNG gửi email qua message_post
                partners = group.users.mapped('partner_id').ids
                if partners:
                    for partner_id in partners:
                        try:
                            self.env['bus.bus']._sendone(
                                partner_id,
                                'simple_notification',
                                {
                                    'title': 'Văn bản đã bút phê',
                                    'message': f"Văn bản '{doc.trich_yeu[:50]}...' đã được bút phê, cần phân phát.",
                                    'sticky': True,
                                    'type': 'info',
                                }
                            )
                        except Exception as e:
                            _logger.warning(f"Gửi notification thất bại: {str(e)}")

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
    nhom_phong_ban = fields.Char(string='Nhóm phòng ban', compute='_compute_nhom_phong_ban', store=True)
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
    nhom_phong_ban = fields.Char(string='Nhóm phòng ban', compute='_compute_nhom_phong_ban', store=True)
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
        for rec in self:
            rec.allow_phan_phat = False
            if rec.nguoi_nhap_y_kien and rec.nhom_phong_ban:
                department = self.env['hr.department'].search([('name', '=', rec.nhom_phong_ban)], limit=1)
                if department:
                    is_manager = (
                        rec.nguoi_nhap_y_kien.id == department.manager_id.id or
                        rec.nguoi_nhap_y_kien.id in department.manager_ids.ids
                    )
                    rec.allow_phan_phat = is_manager

    @api.depends('nguoi_nhap_y_kien')
    def _compute_nhom_phong_ban(self):
        for rec in self:
            rec.nhom_phong_ban = 'Không xác định'
            if rec.nguoi_nhap_y_kien and rec.nguoi_nhap_y_kien.department_id:
                rec.nhom_phong_ban = rec.nguoi_nhap_y_kien.department_id.name


class OfficeDocumentDetail3(models.Model):
    _name = 'office.document.detail3'

    nguoi_nhap_y_kien = fields.Many2one('hr.employee', string='Người nhập ý kiến')
    nhom_phong_ban = fields.Char(string='Nhóm phòng ban', compute='_compute_nhom_phong_ban', store=True)
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
    lanh_dao_xu_ly = fields.Many2many('hr.employee', string='Lãnh đạo xử lý')
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
        ('draft', 'Nháp'),
        ('cho_truong_don_vi_duyet', 'Chờ TĐV duyệt'),
        ('truong_don_vi_duyet', 'TĐV duyệt'),
        ('cho_duyet', 'Chờ duyệt'),
        ('da_duyet', 'Đã duyệt'),
        ('cho_but_phe', 'Chờ bút phê'),
        ('cho_phan_phat', 'Chờ phân phát'),
        ('cho_xu_ly', 'Đã phân phát'),
        ('phat_hanh', 'Đã phát hành'),
        ('huy', 'Đã hủy'),
    ], string='Trạng thái văn bản', default='draft', tracking=True)
    dv_xu_ly_chinh = fields.Many2one('hr.department', string='Đơn vị xử lý chính')
    dv_dong_xu_ly = fields.Many2many(
        'hr.department', 'office_doc_donvi_rel', 'document_id', 'department_id',
        string='Đơn vị đồng xử lý'
    )
    phoi_hop_xu_ly = fields.Char('Phối hợp xử lý')
    pb_dv_nhan = fields.Many2one('hr.department', string='Phòng ban')
    ca_nhan_dv_nhan = fields.Many2one('res.users', string='Cá nhân')
    nhom_nguoi_dung_dv_nhan = fields.Char('Nhóm người dùng')
    nguoi_theo_doi = fields.Many2one('res.users', string='Người theo dõi')
    ngay_bat_dau = fields.Date('Ngày bắt đầu', default=fields.Date.context_today)
    ho_so_cong_viec = fields.Char('Hồ sơ công việc')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'office_document_attachment_rel', 'document_id', 'attachment_id',
        compute='_compute_attachment_ids', inverse='_inverse_attachment_ids',
        string='Tài liệu đính kèm'
    )

    def _inverse_attachment_ids(self):
        Attachment = self.env['ir.attachment'].sudo()
        for doc in self:
            attachments = Attachment.search([('res_model', '=', doc._name), ('res_id', '=', doc.id)])
            new_attachments = doc.attachment_ids - attachments
            removed_attachments = attachments - doc.attachment_ids
            if new_attachments:
                new_attachments.write({'res_model': doc._name, 'res_id': doc.id})
                pdf_files = new_attachments.filtered(lambda x: x.mimetype == 'application/pdf')
                if pdf_files:
                    latest_pdf = pdf_files.sorted(key=lambda x: x.create_date, reverse=True)[0]
                    if (not doc.attachment_id or
                            latest_pdf.create_date > (doc.attachment_id.create_date or fields.Datetime.now())):
                        doc.attachment_id = latest_pdf
            if removed_attachments:
                if doc.attachment_id in removed_attachments:
                    doc.attachment_id = False
                for attachment in removed_attachments:
                    attachment.write({'res_model': False, 'res_id': False})
                    other_refs = Attachment.search_count([
                        ('id', '=', attachment.id), ('res_model', '!=', False), ('res_id', '!=', False)
                    ])
                    if other_refs == 0:
                        attachment.unlink()

    def _compute_attachment_ids(self):
        Attachment = self.env['ir.attachment'].sudo()
        for doc in self:
            doc.attachment_ids = Attachment.search([('res_model', '=', 'office.document'), ('res_id', '=', doc.id)])

    attachment_id = fields.Many2one(
        'ir.attachment', string='Tài liệu',
        domain="[('id', 'in', attachment_ids), ('mimetype', '=', 'application/pdf')]",
    )

    @api.onchange('attachment_ids')
    def _onchange_attachment_ids(self):
        for doc in self:
            if doc.attachment_ids:
                if not doc.attachment_id or doc.attachment_id not in doc.attachment_ids:
                    doc.attachment_id = doc.attachment_ids[-1]

    attachment_datas = fields.Binary(
        string='Tài liệu',
        compute='_compute_attachment_datas',
        inverse='_inverse_attachment_datas',
        store=False,
        attachment = False,
        prefetch = False
    )
    attachment_filename = fields.Char(string='Tên file', compute='_compute_attachment_datas', store=False)

    @api.depends('attachment_id', 'attachment_id.datas', 'attachment_id.name', 'attachment_id.write_date')
    def _compute_attachment_datas(self):
        for record in self:
            if record.attachment_id:
                record.attachment_datas = record.attachment_id.datas
                record.attachment_filename = record.attachment_id.name
            else:
                record.attachment_datas = False
                record.attachment_filename = False

    def _inverse_attachment_datas(self):
        for record in self:
            if record.attachment_datas:
                if record.attachment_id:
                    record.attachment_id.write({
                        'datas': record.attachment_datas,
                        'name': record.attachment_filename or record.attachment_id.name,
                    })
                    record._compute_pdf_viewer_key()
                else:
                    attachment = self.env['ir.attachment'].create({
                        'name': record.attachment_filename or f'document_{record.id or "new"}.pdf',
                        'datas': record.attachment_datas,
                        'res_model': record._name,
                        'res_id': record.id,
                        'mimetype': 'application/pdf',
                    })
                    record.attachment_id = attachment.id
                    record._compute_pdf_viewer_key()
            else:
                if record.attachment_id:
                    record.attachment_id.unlink()

    pdf_viewer_key = fields.Char(compute='_compute_pdf_viewer_key', store=False)

    @api.depends('attachment_id', 'attachment_id.datas', 'attachment_id.write_date')
    def _compute_pdf_viewer_key(self):
        for r in self:
            if r.attachment_id:
                r.pdf_viewer_key = f"{r.attachment_id.id}_{r.attachment_id.write_date or ''}"
            else:
                r.pdf_viewer_key = 'empty'

    note = fields.Text('Ghi chú')
    don_vi_ban_hanh_ngoai = fields.Many2one('res.partner', string='Đơn vị ban hành')
    don_vi_ban_hanh = fields.Many2one('hr.department', string='Đơn vị ban hành')
    don_vi_soan_thao = fields.Many2one('hr.department', string='Đơn vị soạn thảo')
    don_vi_nhan_ben_ngoai = fields.Char('Đơn vị nhận bên ngoài')
    nguoi_theo_doi_chinh = fields.Many2one('res.users', string='Người theo dõi chính')
    so_den_tong_hop_so_den_theo_so = fields.Char('Số công văn')
    so_di_tong_hop_so_den_theo_so = fields.Char('Số công văn')
    so_den_theo_so = fields.Char('Số đến theo sổ')
    so_di_theo_so = fields.Char('Số đi theo sổ')
    so_vb = fields.Char('Số văn bản', compute='_compute_so_vb')

    @api.depends('document_type', 'so_den_tong_hop', 'so_di_tong_hop')
    def _compute_so_vb(self):
        for record in self:
            if record.document_type in ['incoming', 'incoming_internal']:
                record.so_vb = record.so_den_tong_hop
            elif record.document_type:
                record.so_vb = record.so_di_tong_hop
            else:
                record.so_vb = False

    ngay_hieu_luc = fields.Date('Ngày hiệu lực', default=fields.Date.context_today)
    ngay_ky = fields.Date('Ngày ký')
    chuc_vu = fields.Char('Chức vụ')
    do_quan_trong = fields.Char('Độ quan trọng')
    nguoi_xu_ly_chinh = fields.Many2many(
        'hr.employee', 'office_document_detail_nguoi_xu_ly_chinh_employee_rel', 'document_id', 'employee_id',
        string='Người xử lý chính')
    nguoi_dong_xu_ly = fields.Many2many(
        'hr.employee', 'office_document_detail_nguoi_dong_xu_ly_employee_rel', 'document_id', 'employee_id',
        string='Người đồng xử lý'
    )
    nguoi_soan_thao = fields.Many2one('res.users', string='Người soạn thảo')
    dv_theo_doi_chinh = fields.Char('Đơn vị theo dõi chính')
    trich_yeu = fields.Text('Trích yếu')
    noi_luu_tru = fields.Char('Nơi lưu trữ')
    han_ket_thuc = fields.Date('Ngày kết thúc')
    but_phe = fields.Char('Bút phê')
    chuyen_ngoai = fields.Boolean('Chuyển ngoài')
    ngay_chuyen_ngoai = fields.Date('Ngày chuyển ngoài')
    dia_diem_chuyen_ngoai = fields.Char('Địa điểm')
    detail1 = fields.One2many('office.document.detail1', 'office_document_id', string='Ý KIẾN CHỈ ĐẠO VÀ XỬ LÝ')
    detail2 = fields.One2many('office.document.detail2', 'office_document_id', string='Ý KIẾN CẤP LÃNH ĐẠO')
    detail3 = fields.One2many('office.document.detail3', 'office_document_id', string='XỬ LÝ VĂN BẢN CỦA BAN/PHÒNG')

    outgoing_internal_id = fields.Many2one(
        'office.document', string="Công văn nội bộ đi liên quan",
        domain="[('document_type','=','outgoing_internal'), ('id', '!=', id)]"
    )
    incoming_internal_id = fields.Many2one(
        'office.document', string="Công văn nội bộ đến liên quan",
        domain="[('document_type','=','incoming_internal'), ('id', '!=', id)]"
    )
    outgoing_id = fields.Many2one(
        'office.document', string="Công văn đi liên quan",
        domain="[('document_type','=','outgoing'), ('id', '!=', id)]"
    )
    incoming_id = fields.Many2one(
        'office.document', string="Công văn đến liên quan",
        domain="[('document_type','=','incoming'), ('id', '!=', id)]"
    )

    can_duyet = fields.Boolean(string='Văn bản có cần duyệt không ?', default=True)
    co_the_but_phe_cong_van_di = fields.Boolean(
        string='Có thể bút phê', compute='_compute_co_the_but_phe_cong_van_di', store=False
    )
    co_the_but_phe_cong_van_den = fields.Boolean(
        string='Có thể bút phê', compute='_compute_co_the_but_phe_cong_van_den', store=False
    )
    ngay_xuat = fields.Date(string='Ngày xuất', default=fields.Date.context_today)
    task_id = fields.Many2one('project.task', string="Công việc liên quan")
    ngay_tao_bo_sung = fields.Date(string='Ngày tạo bổ sung')
    is_cong_van_bo_sung = fields.Boolean(string="Là công văn bổ sung", default=False)
    ngay_tao = fields.Date(string="Ngày tạo", compute="_compute_ngay_tao", store=True, index=True)

    truong_don_vi_duyet = fields.Many2one(
        'hr.employee', string='Trưởng đơn vị duyệt',
        compute='_compute_truong_don_vi_duyet', store=True,
    )
    is_truong_don_vi = fields.Boolean(compute='_compute_is_truong_don_vi', store=False)
    don_vi_ban_hanh_tedi = fields.Char(string="Đơn vị ban hành")

    # =====================================================================
    # TRƯỞNG PHÒNG BAN CHA LỚN NHẤT (duyệt công văn đi)
    # =====================================================================
    lanh_dao_duyet_cao_nhat = fields.Many2one(
        'hr.employee', string='Lãnh đạo duyệt (cấp cao nhất)',
        compute='_compute_lanh_dao_duyet_cao_nhat', store=True,
        help='Trưởng phòng ban cha lớn nhất (root department) của người tạo. '
             'Đây là người có quyền duyệt công văn đi.'
    )

    @api.depends('create_uid')
    def _compute_lanh_dao_duyet_cao_nhat(self):
        """
        Tìm trưởng phòng ban cha lớn nhất (root department) của người tạo.
        Ví dụ: Nhân viên → Phòng KT → Ban TCKT → Công ty
        → root là Ban TCKT (hoặc tuỳ cấu trúc cây phòng ban của bạn).
        """
        for rec in self:
            rec.lanh_dao_duyet_cao_nhat = False
            user = rec.create_uid or self.env.user
            employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
            if not employee or not employee.department_id:
                continue

            # Leo lên cây phòng ban để tìm root
            dept = employee.department_id
            while dept.parent_id:
                dept = dept.parent_id

            # dept giờ là phòng ban gốc (root)
            if dept.manager_id:
                rec.lanh_dao_duyet_cao_nhat = dept.manager_id

    def _compute_is_truong_don_vi(self):
        user = self.env.user
        for rec in self:
            rec.is_truong_don_vi = False
            if not rec.truong_don_vi_duyet:
                continue
            current_employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
            if current_employee:
                rec.is_truong_don_vi = (current_employee.id == rec.truong_don_vi_duyet.id)

    def name_get(self):
        result = []
        for record in self:
            display_value = ""
            if record.document_type in ['incoming', 'incoming_internal']:
                if record.so_den_tong_hop:
                    display_value = f"{record.so_den_tong_hop}"
            elif record.document_type in ['outgoing', 'outgoing_internal']:
                if record.so_di_tong_hop:
                    display_value = f"{record.so_di_tong_hop}"
            if not display_value:
                display_value = record.trich_yeu or ''
            result.append((record.id, display_value))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|',
                      ('so_den_tong_hop', operator, name),
                      ('so_di_tong_hop', operator, name),
                      ('trich_yeu', operator, name)]
        combined_domain = args + domain if args else domain
        records = self.search(combined_domain, limit=limit)
        return records.name_get()

    @api.depends('create_uid')
    def _compute_truong_don_vi_duyet(self):
        for rec in self:
            current_user = self.env.user
            if not rec.id:
                employee = self.env['hr.employee'].search([('user_id', '=', current_user.id)], limit=1)
            else:
                if rec.create_uid:
                    employee = self.env['hr.employee'].search([('user_id', '=', rec.create_uid.id)], limit=1)
                else:
                    employee = False

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
                rec.ngay_tao = rec.create_date.date() if rec.create_date else fields.Date.today()

    def phan_phat(self):
        """Mở wizard phân phát - kiểm tra quyền trước khi mở"""
        self.ensure_one()

        # Kiểm tra quyền trước khi mở wizard
        user = self.env.user
        is_van_thu = user.has_group('quan_ly_cong_van.group_van_thu')

        if not is_van_thu:
            # Nếu không phải văn thư, kiểm tra quyền trưởng đơn vị
            current_employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
            if not current_employee:
                raise UserError("Bạn không có quyền phân phát văn bản này!")

            departments_as_manager = self.env['hr.department'].search([
                '|',
                ('manager_id', '=', current_employee.id),
                ('manager_ids', 'in', current_employee.id),
            ])

            if not departments_as_manager:
                user_detail = self.detail2.filtered(lambda d: d.nguoi_nhap_y_kien.id == current_employee.id)
                if not any(detail.allow_phan_phat for detail in user_detail):
                    raise UserError("Bạn không có quyền phân phát văn bản này!")

        # Mở wizard phân phát
        return {
            'name': 'Phân phát văn bản',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_van.phan_phat_form').id,
            'res_model': 'office.document.phan.phat',
            'target': 'new',
            'context': {
                'default_loai_phan_phat': 'don_vi',
                'active_id': self.id,
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

    # =====================================================================
    # TRÌNH LÃNH ĐẠO / BÚT PHÊ
    # =====================================================================

    def trinh_lanh_dao_cong_van_di_but_phe(self):
        self.ensure_one()
        if not self.lanh_dao_theo_doi:
            raise UserError("Vui lòng chọn lãnh đạo xử lý trước khi trình.")

        self.tt_vb = 'cho_but_phe'
        self._auto_phan_phat_to_leaders_or_manager()

        detail_url = self.get_form_url()
        employees_to_notify = [self.lanh_dao_theo_doi]
        email_list = _get_employee_emails(self.env['hr.employee'].browse([e.id for e in employees_to_notify]))

        if email_list:
            subject = f"Văn bản cần xử lý/bút phê: {self.trich_yeu[:50]}..." if self.trich_yeu else "Văn bản cần xử lý/bút phê"
            body_lines = [
                f"<b>Trích yếu:</b> {self.trich_yeu}",
                f"<b>Số văn bản:</b> {self.so_vb or 'N/A'}",
                f"<b>Người trình:</b> {self.env.user.name}",
            ]
            body_html = _build_email_html(
                title='VĂN BẢN CẦN XỬ LÝ / BÚT PHÊ',
                greeting='Kính gửi Quý lãnh đạo,<br/>Văn bản sau đã được trình lên để xử lý/bút phê.',
                body_lines=body_lines,
                detail_url=detail_url,
                btn_label='XEM CHI TIẾT VĂN BẢN',
                company_name=self.env.company.name or '',
            )
            _send_mail(self.env, subject, email_list, body_html)

        # Popup notification
        for emp in employees_to_notify:
            if emp.user_id and emp.user_id.partner_id:
                try:
                    self.env['bus.bus']._sendone(
                        emp.user_id.partner_id,
                        'simple_notification',
                        {
                            'title': 'Văn bản cần xử lý',
                            'message': f"Văn bản '{self.trich_yeu[:30]}...' cần bạn xử lý",
                            'sticky': True,
                            'type': 'warning',
                        }
                    )
                except Exception as e:
                    _logger.warning(f"Gửi notification thất bại: {str(e)}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': f"Đã trình văn bản cho {len(email_list)} người",
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def trinh_lanh_dao_cong_van_den(self):
        self.ensure_one()
        if not self.lanh_dao_xu_ly:
            raise UserError("Vui lòng chọn lãnh đạo xử lý trước khi trình.")

        self.tt_vb = 'cho_but_phe'
        detail_url = self.get_form_url()
        self._auto_phan_phat_to_leaders_or_manager()

        email_list = _get_employee_emails(self.lanh_dao_xu_ly)
        if email_list:
            subject = f"Văn bản cần xử lý: {self.trich_yeu[:50]}..." if self.trich_yeu else "Văn bản cần xử lý"
            body_lines = [
                f"<b>Trích yếu:</b> {self.trich_yeu}",
                f"<b>Số văn bản:</b> {self.so_vb or 'N/A'}",
                f"<b>Người trình:</b> {self.env.user.name}",
            ]
            body_html = _build_email_html(
                title='VĂN BẢN CẦN XỬ LÝ',
                greeting='Kính gửi Quý lãnh đạo,<br/>Văn bản sau cần được xử lý.',
                body_lines=body_lines,
                detail_url=detail_url,
                btn_label='XEM CHI TIẾT VĂN BẢN',
                btn_color='#E57373',
                company_name=self.env.company.name or '',
            )
            _send_mail(self.env, subject, email_list, body_html)

        for emp in self.lanh_dao_xu_ly:
            if emp.user_id and emp.user_id.partner_id:
                self.env['bus.bus']._sendone(
                    emp.user_id.partner_id,
                    'simple_notification',
                    {'title': 'Văn bản cần xử lý', 'message': f"Văn bản '{self.trich_yeu[:30]}...' cần bạn xử lý", 'type': 'info'}
                )
        return True

    # =====================================================================
    # DUYỆT VĂN BẢN
    # =====================================================================

    def approve(self):
        self.ensure_one()
        self.tt_vb = 'da_duyet'
        if self.document_type in ['outgoing', 'outgoing_internal', 'resolution']:
            self._send_approval_notification_to_all()
        elif self.document_type in ['incoming', 'incoming_internal']:
            self._send_approval_notification_to_creator()
        return True

    def approve_don_vi(self):
        self.ensure_one()
        self.tt_vb = 'truong_don_vi_duyet'
        self._send_approval_notification_to_creator()
        return True

    def _send_approval_notification_to_all(self):
        """Gửi thông báo duy nhất cho tất cả đối tượng khi văn bản được duyệt"""
        self.ensure_one()
        detail_url = self.get_form_url()
        creator = self.create_uid

        try:
            # Thu thập employee nhận email
            recipient_employees = self.env['hr.employee']

            # Người tạo
            if creator:
                emp = self.env['hr.employee'].search([('user_id', '=', creator.id)], limit=1)
                if emp:
                    recipient_employees |= emp

            # Trưởng đơn vị của người tạo
            if creator and creator.employee_ids:
                creator_emp = creator.employee_ids[0]
                dept = creator_emp.department_id
                if dept and dept.manager_id:
                    recipient_employees |= dept.manager_id

            # Văn thư
            group_van_thu = self.env.ref('quan_ly_cong_van.group_van_thu', raise_if_not_found=False)
            if group_van_thu:
                van_thu_employees = self.env['hr.employee'].search([('user_id', 'in', group_van_thu.users.ids)])
                recipient_employees |= van_thu_employees

            email_list = _get_employee_emails(recipient_employees)
            if not email_list:
                return

            subject = f"Văn bản đã được duyệt: {self.trich_yeu[:50]}" if self.trich_yeu else "Văn bản đã được duyệt"
            body_lines = [
                f"<b>Số văn bản:</b> {self.so_vb or self.so_den_tong_hop or 'Chưa có số'}",
                f"<b>Trích yếu:</b> {self.trich_yeu or 'Không có'}",
                f"<b>Người tạo:</b> {creator.name if creator else 'Không xác định'}",
                f"<b>Người duyệt:</b> {self.env.user.name}",
                f"<b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ]
            body_html = _build_email_html(
                title='VĂN BẢN ĐÃ ĐƯỢC DUYỆT',
                greeting='Kính gửi,<br/>Văn bản sau đã được duyệt thành công.',
                body_lines=body_lines,
                detail_url=detail_url,
                btn_label='XEM CHI TIẾT VĂN BẢN',
                btn_color='#4CAF50',
                company_name=self.env.company.name or '',
            )
            _send_mail(self.env, subject, email_list, body_html)

        except Exception as e:
            _logger.error(f"Lỗi khi gửi thông báo duyệt: {str(e)}")

    def _send_approval_notification_to_creator(self):
        """Gửi thông báo cho người tạo khi văn bản được duyệt"""
        self.ensure_one()
        creator = self.create_uid
        if not creator:
            return

        creator_emp = self.env['hr.employee'].search([('user_id', '=', creator.id)], limit=1)
        email_list = _get_employee_emails(creator_emp) if creator_emp else []
        if not email_list:
            return

        detail_url = self.get_form_url()
        doc_type_display = dict(self._fields['document_type'].selection).get(self.document_type, 'Văn bản')
        subject = f"{doc_type_display} đã được duyệt: {self.trich_yeu[:50]}..." if self.trich_yeu else f"{doc_type_display} đã được duyệt"
        body_lines = [
            f"<b>Loại văn bản:</b> {doc_type_display}",
            f"<b>Số đến:</b> {self.so_den_tong_hop or self.so_di_tong_hop or 'Chưa có'}",
            f"<b>Số hiệu:</b> {self.so_hieu or 'Chưa có'}",
            f"<b>Ngày đến:</b> {self.ngay_den.strftime('%d/%m/%Y') if self.ngay_den else 'Chưa có'}",
            f"<b>Người duyệt:</b> {self.env.user.name}",
            f"<b>Trạng thái:</b> Đã duyệt",
        ]
        body_html = _build_email_html(
            title=f'{doc_type_display.upper()} ĐÃ ĐƯỢC DUYỆT',
            greeting=f'Xin chào {creator.name},<br/>{doc_type_display} <b>"{self.trich_yeu}"</b> đã được duyệt.',
            body_lines=body_lines,
            detail_url=detail_url,
            btn_label='XEM CHI TIẾT VĂN BẢN',
            btn_color='#4CAF50',
            company_name=self.env.company.name or '',
        )
        _send_mail(self.env, subject, email_list, body_html)

        # Popup
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
                _logger.error(f"Lỗi gửi thông báo popup: {str(e)}")

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
        if 'ngay_bat_dau' in vals and not vals.get('han_ket_thuc'):
            vals['han_ket_thuc'] = fields.Date.from_string(vals['ngay_bat_dau']) + timedelta(days=7)

        user = self.env.user
        if user.has_group('quan_ly_cong_van.group_van_thu'):
            vals['can_duyet'] = False

        can_duyet_val = vals.get('can_duyet', self._fields['can_duyet'].default(self))
        document_type_val = vals.get('document_type')

        if (user.has_group('quan_ly_cong_van.group_van_thu')
                and document_type_val in ('incoming', 'incoming_internal')):
            vals['tt_vb'] = 'da_duyet'
        elif (can_duyet_val is True and document_type_val in ('outgoing', 'outgoing_internal', 'resolution')):
            vals['tt_vb'] = 'draft'
        elif (can_duyet_val is False and document_type_val in ('outgoing', 'outgoing_internal', 'resolution')):
            vals['tt_vb'] = 'da_duyet'
        elif (user.has_group('quan_ly_cong_van.group_don_vi_xu_ly')
              and document_type_val in ('incoming', 'incoming_internal')):
            vals['tt_vb'] = 'draft'
        else:
            vals['tt_vb'] = 'draft'

        vals = self._update_document_numbers(vals)
        record = super(OfficeDocument, self).create(vals)

        if record.document_type == 'resolution' and not record.phan_loai_van_ban:
            category = self.env['office.document.category'].search([('code', '=', 'QĐ')], limit=1)
            if not category:
                category = self.env['office.document.category'].create({'code': 'QĐ', 'name': 'Quyết định'})
            record.phan_loai_van_ban = category.id

        if record.task_id:
            record.task_id.da_tao_cong_van = True

        record._sync_related_documents(vals)
        return record

    def write(self, vals):
        if 'phan_loai_van_ban' in vals:
            for record in self:
                new_vals = vals.copy()
                new_vals = record._update_document_numbers(new_vals, is_write=True)
                super(OfficeDocument, record).write(new_vals)
            for record in self:
                record._sync_related_documents(vals)
            return True

        res = super(OfficeDocument, self).write(vals)
        for record in self:
            record._sync_related_documents(vals)
        return res

    def _update_document_numbers(self, vals, is_write=False):
        import re

        def _get_abbreviation_from_name(name, max_length=10):
            if not name:
                return ''
            import unicodedata

            def remove_diacritics(text):
                if not text:
                    return text
                text = unicodedata.normalize('NFD', text)
                text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
                text = text.replace('đ', 'd').replace('Đ', 'D')
                return text

            name_no_diacritic = remove_diacritics(name)
            words = re.findall(r'[A-Za-z0-9]+', name_no_diacritic)
            result_parts = []
            for word in words:
                if not word:
                    continue
                if word.isupper() or any(c.isdigit() or c in '-_/' for c in word):
                    result_parts.append(word)
                else:
                    result_parts.append(word[0].upper())
            result = ''.join(result_parts)
            if len(result) > max_length:
                return result[:max_length]
            if not result:
                clean_name = re.sub(r'\s+', '', name_no_diacritic)
                return clean_name[:max_length].upper()
            return result

        phan_loai_id = vals.get('phan_loai_van_ban')
        document_type = vals.get('document_type') or self._context.get('default_document_type') or (
            self.document_type if self else None)

        if document_type == 'resolution':
            return vals

        ngay_tao_bo_sung = vals.get('ngay_tao_bo_sung')
        if ngay_tao_bo_sung:
            current_date = fields.Date.from_string(ngay_tao_bo_sung)
        else:
            current_date = fields.Date.today()
        current_date_str = current_date.strftime('%y%m%d')

        def get_next_number(is_incoming=False):
            if is_incoming:
                domain = [('document_type', 'in', ['incoming', 'incoming_internal']), ('ngay_tao', '=', current_date)]
                number_field = 'so_den_tong_hop'
            else:
                domain = [('document_type', 'in', ['outgoing', 'outgoing_internal']), ('ngay_tao', '=', current_date)]
                number_field = 'so_di_tong_hop'

            if phan_loai_id:
                domain.append(('phan_loai_van_ban', '=', phan_loai_id))

            existing_docs = self.env['office.document'].search(domain)
            max_seq = 0
            for doc in existing_docs:
                number = getattr(doc, number_field, '')
                if number and '.' in number:
                    try:
                        seq_part = number.split('.')[1].split('/')[0]
                        seq_num = int(seq_part)
                        max_seq = max(max_seq, seq_num)
                    except (ValueError, IndexError):
                        continue

            next_seq = max_seq + 1
            ma_don_vi = ''

            if document_type in ('incoming',):
                partner_id = vals.get('don_vi_ban_hanh_ngoai') or ''
                if partner_id and isinstance(partner_id, int):
                    partner = self.env['res.partner'].browse(partner_id)
                    if partner and partner.ma_don_vi:
                        ma_don_vi = partner.ma_don_vi.strip()
                    elif partner:
                        ma_don_vi = _get_abbreviation_from_name(partner.name)
            else:
                dept_id = vals.get('don_vi_ban_hanh') or ''
                if dept_id and isinstance(dept_id, int):
                    dept = self.env['hr.department'].browse(dept_id)
                    if dept:
                        if hasattr(dept, 'ma_don_vi') and dept.ma_don_vi:
                            ma_don_vi = dept.ma_don_vi.strip()
                        elif hasattr(dept, 'code') and dept.code:
                            ma_don_vi = dept.code.strip()
                        elif hasattr(dept, 'abbreviation') and dept.abbreviation:
                            ma_don_vi = dept.abbreviation.strip()
                        else:
                            ma_don_vi = _get_abbreviation_from_name(dept.name)

            if not ma_don_vi:
                ma_don_vi = 'TEDI'

            ma_loai = ''
            if phan_loai_id:
                phan_loai = self.env['office.document.category'].browse(phan_loai_id)
                if phan_loai.exists() and phan_loai.code:
                    ma_loai = phan_loai.code
            if not ma_loai:
                ma_loai = 'CV'

            if is_incoming:
                return f"{current_date_str}.{next_seq:02d}/{ma_don_vi}-{ma_loai}"
            else:
                if ma_loai == 'CV':
                    return f"{current_date_str}.{next_seq:02d}/TEDI-{ma_don_vi}"
                else:
                    return f"{current_date_str}.{next_seq:02d}/{ma_don_vi}-{ma_loai}"

        if document_type in ('incoming', 'incoming_internal') and phan_loai_id:
            if not vals.get('so_den_tong_hop'):
                vals['so_den_tong_hop'] = get_next_number(is_incoming=True)

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

        if document_type == 'resolution':
            category = self.env['office.document.category'].search([('code', '=', 'QĐ')], limit=1)
            if not category:
                category = self.env['office.document.category'].create({'code': 'QĐ', 'name': 'Quyết định'})
            res['phan_loai_van_ban'] = category.id
        elif document_type in ('incoming', 'outgoing'):
            category = self.env['office.document.category'].search([('code', '=', 'CV')], limit=1)
            if not category:
                category = self.env['office.document.category'].create({'code': 'CV', 'name': 'Công văn'})
            res['phan_loai_van_ban'] = category.id
        return res

    @api.constrains('ngay_bat_dau', 'han_ket_thuc')
    def _check_dates(self):
        for rec in self:
            if rec.han_ket_thuc and rec.ngay_bat_dau:
                if rec.han_ket_thuc < rec.ngay_bat_dau:
                    raise ValidationError("Ngày kết thúc không được sớm hơn ngày bắt đầu!")

    # =====================================================================
    # TRÌNH LÃNH ĐẠO CÔNG VĂN ĐI (CHỜ DUYỆT) – trưởng ban cha lớn nhất
    # =====================================================================

    def trinh_lanh_dao_cong_van_di(self):
        self.ensure_one()

        # Ưu tiên lanh_dao_theo_doi; fallback sang lanh_dao_duyet_cao_nhat
        lanh_dao = self.lanh_dao_theo_doi or self.lanh_dao_duyet_cao_nhat
        if not lanh_dao:
            raise UserError(
                "Vui lòng chọn lãnh đạo xử lý trước khi trình, hoặc đảm bảo phòng ban đã có trưởng đơn vị cấp cao nhất.")

        self.tt_vb = 'cho_duyet'
        detail_url = self.get_form_url()
        self._auto_phan_phat_to_leaders_or_manager()

        email_list = _get_employee_emails(lanh_dao)
        if email_list:
            subject = f"Văn bản cần duyệt: {self.trich_yeu[:50]}..." if self.trich_yeu else "Văn bản cần duyệt"
            body_lines = [
                f"<b>Trích yếu:</b> {self.trich_yeu}",
                f"<b>Số văn bản:</b> {self.so_vb or 'N/A'}",
                f"<b>Người trình:</b> {self.env.user.name}",
            ]
            body_html = _build_email_html(
                title='VĂN BẢN CẦN DUYỆT',
                greeting=f'Xin chào {lanh_dao.name},<br/>Văn bản sau đã được trình lên để duyệt.',
                body_lines=body_lines,
                detail_url=detail_url,
                btn_label='XEM VÀ DUYỆT VĂN BẢN',
                company_name=self.env.company.name or '',
            )
            _send_mail(self.env, subject, email_list, body_html)

        if lanh_dao.user_id and lanh_dao.user_id.partner_id:
            self.env['bus.bus']._sendone(
                lanh_dao.user_id.partner_id,
                'simple_notification',
                {'title': 'Văn bản cần duyệt', 'message': f"Văn bản '{self.trich_yeu[:30]}...' cần bạn duyệt", 'type': 'info'}
            )
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
        current_user = self.env.user
        current_employee = self.env['hr.employee'].search([('user_id', '=', current_user.id)], limit=1)
        for record in self:
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
        user = self.env.user
        is_van_thu = user.has_group('quan_ly_cong_van.group_van_thu')
        if is_van_thu:
            self.tt_vb = 'da_duyet'
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'title': 'Thành công',
                    'message': 'Văn bản đã được xác nhận và chuyển sang trạng thái Đã duyệt.',
                    'type': 'success', 'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }
        else:
            self.tt_vb = 'cho_duyet'
            self._send_email_to_van_thu()
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'title': 'Thành công',
                    'message': 'Văn bản đã được xác nhận và gửi thông báo cho văn thư.',
                    'type': 'success', 'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }

    def _send_email_to_van_thu(self):
        self.ensure_one()
        group_van_thu = self.env.ref('quan_ly_cong_van.group_van_thu', raise_if_not_found=False)
        if not group_van_thu:
            return

        van_thu_employees = self.env['hr.employee'].search([('user_id', 'in', group_van_thu.users.ids)])
        email_list = _get_employee_emails(van_thu_employees)
        if not email_list:
            return

        detail_url = self.get_form_url()
        subject = f"Văn bản cần duyệt: {self.trich_yeu[:50]}..." if self.trich_yeu else "Văn bản cần duyệt"
        body_lines = [
            f"<b>Người xác nhận:</b> {self.env.user.name}",
            f"<b>Trích yếu:</b> {self.trich_yeu}",
        ]
        body_html = _build_email_html(
            title='VĂN BẢN CẦN DUYỆT',
            greeting='Kính gửi nhóm văn thư,<br/>Người dùng vừa xác nhận văn bản cần duyệt.',
            body_lines=body_lines,
            detail_url=detail_url,
            btn_label='XEM CHI TIẾT VĂN BẢN',
            btn_color='#4CAF50',
            company_name=self.env.company.name or '',
        )
        _send_mail(self.env, subject, email_list, body_html)

        van_thu_users = group_van_thu.users
        for user in van_thu_users:
            if user.partner_id and user != self.env.user:
                self.env['bus.bus']._sendone(
                    user.partner_id,
                    'simple_notification',
                    {'title': 'Văn bản cần duyệt', 'message': f"Văn bản '{self.trich_yeu[:30]}...' cần duyệt", 'type': 'warning'}
                )
        return True

    rejection_ids = fields.One2many('office.document.rejection', 'office_document_id', string='Lịch sử từ chối')

    def action_open_rejection_history(self):
        self.ensure_one()
        return {
            'name': 'Lịch sử từ chối', 'type': 'ir.actions.act_window',
            'res_model': 'office.document.rejection', 'view_mode': 'tree,form',
            'domain': [('office_document_id', '=', self.id)],
            'context': {'default_office_document_id': self.id, 'create': False},
            'target': 'new',
        }

    def khong_dat(self):
        self.ensure_one()
        return {
            'name': 'Từ chối văn bản', 'type': 'ir.actions.act_window',
            'res_model': 'office.document.reject.wizard', 'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_van.view_reject_document_wizard_form').id,
            'target': 'new',
            'context': {'default_office_document_id': self.id, 'tag': 'history_back'}
        }

    is_van_thu = fields.Boolean(compute='_compute_edit_permission', store=False)
    not_is_van_thu = fields.Boolean(compute='_compute_edit_permission', store=False)

    @api.depends('tt_vb')
    def _compute_edit_permission(self):
        user = self.env.user
        is_van_thu_user = user.has_group('quan_ly_cong_van.group_van_thu')
        for rec in self:
            rec.is_van_thu = (
                is_van_thu_user and
                rec.tt_vb in ('draft', 'cho_truong_don_vi_duyet', 'truong_don_vi_duyet', 'cho_duyet', 'da_duyet')
            )
            rec.not_is_van_thu = (not is_van_thu_user and rec.tt_vb == 'draft')

    show_skip_button = fields.Boolean(compute='_compute_show_skip_button', store=False)

    def skip(self):
        self.ensure_one()
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
            if rec.document_type in ['incoming_internal', 'outgoing_internal', 'resolution', 'outgoing'] and rec.don_vi_ban_hanh:
                domain = [('id', '!=', rec.id), ('document_type', '=', rec.document_type),
                          ('so_hieu', '=', rec.so_hieu), ('don_vi_ban_hanh', '=', rec.don_vi_ban_hanh.id)]
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        f"Đã tồn tại {duplicate.display_name} với cùng:\n"
                        f"- Loại: {dict(rec._fields['document_type'].selection).get(rec.document_type)}\n"
                        f"- Số hiệu: {rec.so_hieu}\n"
                        f"- Đơn vị ban hành: {rec.don_vi_ban_hanh.name}"
                    )
            elif rec.document_type in ['incoming'] and rec.don_vi_ban_hanh_ngoai:
                domain = [('id', '!=', rec.id), ('document_type', '=', rec.document_type),
                          ('so_hieu', '=', rec.so_hieu), ('don_vi_ban_hanh_ngoai', '=', rec.don_vi_ban_hanh_ngoai.id)]
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        f"Đã tồn tại {duplicate.display_name} với cùng:\n"
                        f"- Loại: {dict(rec._fields['document_type'].selection).get(rec.document_type)}\n"
                        f"- Số hiệu: {rec.so_hieu}\n"
                        f"- Đơn vị ban hành: {rec.don_vi_ban_hanh_ngoai.name}"
                    )

    can_create_don_vi = fields.Boolean(compute='_compute_can_create_don_vi', store=False)

    def _compute_can_create_don_vi(self):
        user = self.env.user
        for rec in self:
            rec.can_create_don_vi = user.has_group('quan_ly_cong_van.group_van_thu') or user.has_group('base.group_system')

    def co_cong_van_dieu_chinh(self):
        self.ensure_one()
        self.tt_vb = 'da_duyet'
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': 'Thông báo',
                'message': 'Văn bản đã được chuyển về trạng thái chỉnh sửa.',
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_chuyen_lanh_dao(self):
        self.ensure_one()
        current_user = self.env.user
        current_employee = self.env['hr.employee'].search([('user_id', '=', current_user.id)], limit=1)
        if not current_employee or current_employee not in self.lanh_dao_xu_ly:
            raise UserError("Bạn không có quyền chuyển lãnh đạo cho văn bản này!")
        return {
            'name': 'Chuyển lãnh đạo', 'type': 'ir.actions.act_window', 'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_van.view_chuyen_lanh_dao_wizard_form').id,
            'res_model': 'office.document.chuyen.lanh.dao', 'target': 'new',
            'context': {
                'default_office_document_id': self.id,
                'default_lanh_dao_hien_tai_id': current_employee.id,
            }
        }

    def unlink_detail2(self):
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
                if 'outgoing_id' in vals:
                    if rec.outgoing_id:
                        if rec.outgoing_id.incoming_id and rec.outgoing_id.incoming_id.id != rec.id:
                            raise ValidationError(
                                f"Công văn '{rec.outgoing_id.trich_yeu}' đã được kết nối với công văn đến khác.")
                        rec.outgoing_id.with_context(ctx).write({'incoming_id': rec.id})
                    elif vals['outgoing_id'] is False:
                        old_outgoing = self.browse(rec.id).outgoing_id
                        if old_outgoing and old_outgoing.incoming_id.id == rec.id:
                            old_outgoing.with_context(ctx).write({'incoming_id': False})

                if 'incoming_id' in vals:
                    if rec.incoming_id:
                        if rec.incoming_id.outgoing_id and rec.incoming_id.outgoing_id.id != rec.id:
                            raise ValidationError(
                                f"Công văn '{rec.incoming_id.trich_yeu}' đã được kết nối với công văn đi khác.")
                        rec.incoming_id.with_context(ctx).write({'outgoing_id': rec.id})
                    elif vals['incoming_id'] is False:
                        old_incoming = self.browse(rec.id).incoming_id
                        if old_incoming and old_incoming.outgoing_id.id == rec.id:
                            old_incoming.with_context(ctx).write({'outgoing_id': False})

                if 'outgoing_internal_id' in vals:
                    if rec.outgoing_internal_id:
                        if rec.outgoing_internal_id.incoming_internal_id and rec.outgoing_internal_id.incoming_internal_id.id != rec.id:
                            raise ValidationError(
                                f"Công văn '{rec.outgoing_internal_id.trich_yeu}' đã kết nối với công văn nội bộ đến khác.")
                        rec.outgoing_internal_id.with_context(ctx).write({'incoming_internal_id': rec.id})
                    elif vals['outgoing_internal_id'] is False:
                        old = self.browse(rec.id).outgoing_internal_id
                        if old and old.incoming_internal_id.id == rec.id:
                            old.with_context(ctx).write({'incoming_internal_id': False})

                if 'incoming_internal_id' in vals:
                    if rec.incoming_internal_id:
                        if rec.incoming_internal_id.outgoing_internal_id and rec.incoming_internal_id.outgoing_internal_id.id != rec.id:
                            raise ValidationError(
                                f"Công văn '{rec.incoming_internal_id.trich_yeu}' đã kết nối với công văn nội bộ đi khác.")
                        rec.incoming_internal_id.with_context(ctx).write({'outgoing_internal_id': rec.id})
                    elif vals['incoming_internal_id'] is False:
                        old = self.browse(rec.id).incoming_internal_id
                        if old and old.outgoing_internal_id.id == rec.id:
                            old.with_context(ctx).write({'outgoing_internal_id': False})
            except Exception as e:
                _logger.error(f"Error in _sync_related_documents: {str(e)}")
                raise

    is_linked_as_incoming = fields.Boolean(compute='_compute_linked_status', store=False)
    is_linked_as_outgoing = fields.Boolean(compute='_compute_linked_status', store=False)
    is_linked_as_incoming_internal = fields.Boolean(compute='_compute_linked_status', store=False)
    is_linked_as_outgoing_internal = fields.Boolean(compute='_compute_linked_status', store=False)

    @api.depends('outgoing_id', 'incoming_id', 'outgoing_internal_id', 'incoming_internal_id')
    def _compute_linked_status(self):
        for rec in self:
            rec.is_linked_as_incoming = bool(rec.incoming_id)
            rec.is_linked_as_outgoing = bool(rec.outgoing_id)
            rec.is_linked_as_incoming_internal = bool(rec.incoming_internal_id)
            rec.is_linked_as_outgoing_internal = bool(rec.outgoing_internal_id)

    @api.constrains('outgoing_internal_id', 'incoming_internal_id', 'outgoing_id', 'incoming_id')
    def _check_single_connection(self):
        if self.env.context.get('skip_link_sync'):
            return
        for rec in self:
            connections = []
            if rec.outgoing_internal_id:
                connections.append(('outgoing_internal_id', rec.outgoing_internal_id.display_name))
            if rec.incoming_internal_id:
                connections.append(('incoming_internal_id', rec.incoming_internal_id.display_name))
            if rec.outgoing_id:
                connections.append(('outgoing_id', rec.outgoing_id.display_name))
            if rec.incoming_id:
                connections.append(('incoming_id', rec.incoming_id.display_name))
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
        for rec in self:
            if rec.outgoing_internal_id:
                existing = self.search([('outgoing_internal_id', '=', rec.outgoing_internal_id.id), ('id', '!=', rec.id)], limit=1)
                if existing:
                    raise ValidationError(f"Công văn '{rec.outgoing_internal_id.trich_yeu}' đã được kết nối với công văn '{existing.trich_yeu}'.")

    @api.constrains('incoming_internal_id')
    def _check_incoming_internal_unique(self):
        if self.env.context.get('skip_link_sync'):
            return
        for rec in self:
            if rec.incoming_internal_id:
                existing = self.search([('incoming_internal_id', '=', rec.incoming_internal_id.id), ('id', '!=', rec.id)], limit=1)
                if existing:
                    raise ValidationError(f"Công văn '{rec.incoming_internal_id.trich_yeu}' đã được kết nối với công văn '{existing.trich_yeu}'.")

    @api.constrains('outgoing_id')
    def _check_outgoing_unique(self):
        if self.env.context.get('skip_link_sync'):
            return
        for rec in self:
            if rec.outgoing_id:
                existing = self.search([('outgoing_id', '=', rec.outgoing_id.id), ('id', '!=', rec.id)], limit=1)
                if existing:
                    raise ValidationError(f"Công văn '{rec.outgoing_id.trich_yeu}' đã được kết nối với công văn '{existing.trich_yeu}'.")

    @api.constrains('incoming_id')
    def _check_incoming_unique(self):
        if self.env.context.get('skip_link_sync'):
            return
        for rec in self:
            if rec.incoming_id:
                existing = self.search([('incoming_id', '=', rec.incoming_id.id), ('id', '!=', rec.id)], limit=1)
                if existing:
                    raise ValidationError(f"Công văn '{rec.incoming_id.trich_yeu}' đã được kết nối với công văn '{existing.trich_yeu}'.")

    def trinh_truong_don_vi(self):
        self.ensure_one()
        self.tt_vb = 'cho_truong_don_vi_duyet'
        self._send_notification_to_truong_don_vi()
        self._auto_phan_phat_to_leaders_or_manager()
        return True

    def _send_notification_to_truong_don_vi(self):
        truong_don_vi = self.truong_don_vi_duyet
        if not truong_don_vi:
            return

        email_list = _get_employee_emails(truong_don_vi)
        detail_url = self.get_form_url()

        if email_list:
            subject = f"Văn bản cần duyệt: {self.trich_yeu}" if self.trich_yeu else "Văn bản cần duyệt"
            body_lines = [
                f"<b>Trích yếu:</b> {self.trich_yeu}",
                f"<b>Số văn bản:</b> {self.so_vb or 'N/A'}",
                f"<b>Người trình:</b> {self.create_uid.name if self.create_uid else ''}",
            ]
            body_html = _build_email_html(
                title='VĂN BẢN CẦN DUYỆT (TRƯỞNG ĐƠN VỊ)',
                greeting=f'Xin chào {truong_don_vi.name},<br/>Văn bản sau cần được bạn duyệt.',
                body_lines=body_lines,
                detail_url=detail_url,
                btn_label='XEM VÀ DUYỆT VĂN BẢN',
                btn_color='#4CAF50',
                company_name=self.env.company.name or '',
            )
            _send_mail(self.env, subject, email_list, body_html)

        if truong_don_vi.user_id and truong_don_vi.user_id.partner_id:
            try:
                self.env['bus.bus']._sendone(
                    truong_don_vi.user_id.partner_id,
                    'simple_notification',
                    {'title': 'Văn bản cần duyệt', 'message': f"Văn bản '{self.trich_yeu}' cần được bạn duyệt.", 'sticky': False, 'type': 'info'}
                )
            except Exception as e:
                _logger.warning(f"Gửi notification thất bại: {str(e)}")

    # =====================================================================
    # PHÂN PHÁT – QUYỀN TRƯỞNG ĐƠN VỊ
    # =====================================================================

    show_phan_phat_button = fields.Boolean(compute='_compute_show_phan_phat_button', store=False)

    def _compute_show_phan_phat_button(self):
        user = self.env.user
        is_van_thu = user.has_group('quan_ly_cong_van.group_van_thu')

        for rec in self:
            if is_van_thu:
                rec.show_phan_phat_button = True
                continue

            current_employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
            if not current_employee:
                rec.show_phan_phat_button = False
                continue

            # Kiểm tra có phải trưởng đơn vị không (manager của bất kỳ phòng ban nào)
            departments_as_manager = self.env['hr.department'].search([
                ('manager_id', '=', current_employee.id),
            ])

            if departments_as_manager:
                rec.show_phan_phat_button = True
            else:
                user_detail = rec.detail2.filtered(lambda d: d.nguoi_nhap_y_kien.id == current_employee.id)
                rec.show_phan_phat_button = any(detail.allow_phan_phat for detail in user_detail)

    def _auto_phan_phat_to_leaders_or_manager(self):
        self.ensure_one()
        employees_to_assign = self.env['hr.employee']
        is_for_leaders = False
        is_for_manager = False

        if self.tt_vb == 'cho_but_phe':
            if self.document_type in ['outgoing', 'outgoing_internal', 'resolution']:
                if self.lanh_dao_theo_doi:
                    employees_to_assign |= self.lanh_dao_theo_doi
                    is_for_leaders = True
            elif self.document_type in ['incoming', 'incoming_internal']:
                if self.lanh_dao_xu_ly:
                    employees_to_assign |= self.lanh_dao_xu_ly
                    is_for_leaders = True
        elif self.tt_vb == 'cho_truong_don_vi_duyet':
            if self.truong_don_vi_duyet:
                employees_to_assign |= self.truong_don_vi_duyet
                is_for_manager = True
        elif self.tt_vb == 'cho_duyet':
            if self.document_type in ['outgoing', 'outgoing_internal', 'resolution']:
                lanh_dao = self.lanh_dao_theo_doi or self.lanh_dao_duyet_cao_nhat
                if lanh_dao:
                    employees_to_assign |= lanh_dao
                    is_for_leaders = True

        if not employees_to_assign:
            return

        nguoi_xu_ly_chinh_ids = employees_to_assign.ids
        update_data = {
            'nguoi_xu_ly_chinh': [(6, 0, nguoi_xu_ly_chinh_ids)],
            'nguoi_dong_xu_ly': [(5,)],
        }
        if is_for_manager and self.truong_don_vi_duyet.department_id:
            update_data['dv_xu_ly_chinh'] = self.truong_don_vi_duyet.department_id.id

        self.write(update_data)

        lines_to_create = []
        now = fields.Datetime.now()
        for emp in employees_to_assign:
            if not self.detail2.filtered(lambda l: l.nguoi_nhap_y_kien == emp):
                role = 'Lãnh đạo xử lý' if is_for_leaders else 'Trưởng đơn vị duyệt'
                lines_to_create.append({
                    'office_document_id': self.id,
                    'nguoi_nhap_y_kien': emp.id,
                    'nhom_phong_ban': emp.department_id.name or 'Không xác định',
                    'noi_dung_chi_dao': role,
                    'thoi_diem_chi_dao': now,
                })
        if lines_to_create:
            self.env['office.document.detail2'].create(lines_to_create)

    def tu_choi_cua_lanh_dao(self):
        self.ensure_one()
        return {
            'name': 'Từ chối văn bản (Lãnh đạo)', 'type': 'ir.actions.act_window', 'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_van.view_lanh_dao_reject_document_wizard_form').id,
            'res_model': 'office.document.lanh.dao.reject.wizard', 'target': 'new',
            'context': {'default_office_document_id': self.id, 'default_current_user_id': self.env.user.id}
        }


class ChuyenLanhDaoWizard(models.TransientModel):
    _name = 'office.document.chuyen.lanh.dao'
    _description = 'Chuyển lãnh đạo xử lý'

    office_document_id = fields.Many2one('office.document', string='Văn bản', required=True, readonly=True)
    lanh_dao_hien_tai_id = fields.Many2one('hr.employee', string='Lãnh đạo hiện tại', required=True, readonly=True)
    lanh_dao_moi_id = fields.Many2one(
        'hr.employee', string='Lãnh đạo mới', required=True,
        domain="[('id', '!=', lanh_dao_hien_tai_id)]"
    )

    @api.constrains('lanh_dao_moi_id')
    def _check_lanh_dao_moi(self):
        for rec in self:
            if rec.lanh_dao_moi_id == rec.lanh_dao_hien_tai_id:
                raise ValidationError("Lãnh đạo mới không được trùng với lãnh đạo hiện tại!")

    def action_chuyen(self):
        self.ensure_one()
        doc = self.office_document_id
        lanh_dao_cu = self.lanh_dao_hien_tai_id
        lanh_dao_moi = self.lanh_dao_moi_id

        current_leaders = doc.lanh_dao_xu_ly
        new_leaders = current_leaders - lanh_dao_cu + lanh_dao_moi
        doc.write({'lanh_dao_xu_ly': [(6, 0, new_leaders.ids)]})

        email_list = _get_employee_emails(lanh_dao_moi)
        detail_url = doc.get_form_url()

        if email_list:
            subject = f"Chuyển xử lý văn bản: {doc.trich_yeu}" if doc.trich_yeu else "Chuyển xử lý văn bản"
            body_lines = [
                f"<b>Trích yếu:</b> {doc.trich_yeu}",
                f"<b>Chuyển từ:</b> {lanh_dao_cu.name}",
            ]
            body_html = _build_email_html(
                title='ĐƯỢC CHUYỂN XỬ LÝ VĂN BẢN',
                greeting=f'Xin chào {lanh_dao_moi.name},<br/>Bạn vừa được chuyển xử lý văn bản.',
                body_lines=body_lines,
                detail_url=detail_url,
                btn_label='XEM CHI TIẾT VĂN BẢN',
                company_name=self.env.company.name or '',
            )
            _send_mail(self.env, subject, email_list, body_html)

        if lanh_dao_moi.user_id and lanh_dao_moi.user_id.partner_id:
            try:
                self.env['bus.bus']._sendone(
                    lanh_dao_moi.user_id.partner_id,
                    'simple_notification',
                    {'title': 'Được chuyển xử lý văn bản', 'message': f"Bạn vừa được chuyển xử lý văn bản: {doc.trich_yeu}", 'sticky': False, 'type': 'info'}
                )
            except Exception as e:
                _logger.warning(f"Gửi notification thất bại: {str(e)}")

        return {'type': 'ir.actions.act_window_close'}

    def cancel(self):
        return {'type': 'ir.actions.act_window_close'}


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self.env.context.get('phan_phat_full_label'):
            args = args or []
            domain = args + ['|', '|',
                ('name', operator, name),
                ('department_id.name', operator, name),
                ('position_id.name', operator, name),
            ]
            employees = self.search(domain, limit=limit)
            return [
                (emp.id, f"{emp.name} - {emp.department_id.name or ''} - {emp.position_id.name or ''}".strip(' -'))
                for emp in employees
            ]
        return super().name_search(name, args, operator, limit)


class OfficeDocumentRejection(models.Model):
    _name = 'office.document.rejection'
    _description = 'Lịch sử từ chối văn bản'
    _order = 'rejection_date desc'

    office_document_id = fields.Many2one('office.document', string='Văn bản', required=True, ondelete='cascade')
    rejection_reason = fields.Text(string='Lý do từ chối', required=True)
    rejected_by = fields.Many2one('res.users', string='Người từ chối', required=True, default=lambda self: self.env.user)
    rejection_date = fields.Datetime(string='Thời gian từ chối', required=True, default=fields.Datetime.now)


class RejectDocumentWizard(models.TransientModel):
    _name = 'office.document.reject.wizard'
    _description = 'Nhập lý do từ chối văn bản'

    office_document_id = fields.Many2one('office.document', string='Văn bản', required=True, readonly=True)
    rejection_reason = fields.Text(
        string='Lý do từ chối', required=True,
        placeholder='Vui lòng nhập lý do từ chối văn bản...'
    )

    def action_confirm_reject(self):
        self.ensure_one()
        self.env['office.document.rejection'].create({
            'office_document_id': self.office_document_id.id,
            'rejection_reason': self.rejection_reason,
            'rejected_by': self.env.user.id,
            'rejection_date': fields.Datetime.now(),
        })
        self.office_document_id.tt_vb = 'draft'
        self._send_rejection_notification()
        self.env.cr.commit()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        tree_url = f"{base_url}/web#action=&model=office.document&view_type=list"
        return {'type': 'ir.actions.act_url', 'url': tree_url, 'target': 'self'}

    def _send_rejection_notification(self):
        self.ensure_one()
        doc = self.office_document_id
        creator = doc.create_uid
        if not creator:
            return

        creator_emp = self.env['hr.employee'].search([('user_id', '=', creator.id)], limit=1)
        email_list = _get_employee_emails(creator_emp) if creator_emp else []
        if not email_list:
            return

        detail_url = doc.get_form_url()
        subject = f"Văn bản bị từ chối: {doc.trich_yeu[:50]}..." if doc.trich_yeu else "Văn bản bị từ chối"
        body_lines = [
            f"<b>Người từ chối:</b> {self.env.user.name}",
            f"<b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}",
            f"<b>Lý do từ chối:</b><br/>{self.rejection_reason}",
        ]
        body_html = _build_email_html(
            title='VĂN BẢN BỊ TỪ CHỐI',
            greeting=f'Xin chào {creator.name},<br/>Văn bản <b>"{doc.trich_yeu}"</b> của bạn đã bị từ chối.',
            body_lines=body_lines,
            detail_url=detail_url,
            btn_label='XEM VÀ CHỈNH SỬA VĂN BẢN',
            btn_color='#f44336',
            company_name=self.env.company.name or '',
        )
        _send_mail(self.env, subject, email_list, body_html)

        if creator.partner_id:
            try:
                self.env['bus.bus']._sendone(
                    creator.partner_id,
                    'simple_notification',
                    {'title': 'Văn bản bị từ chối', 'message': f'Văn bản "{doc.trich_yeu[:50]}..." đã bị từ chối.', 'sticky': False, 'type': 'warning'}
                )
            except Exception as e:
                _logger.error(f"Lỗi gửi thông báo từ chối: {str(e)}")

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}


class OfficeDocumentLanhDaoRejectWizard(models.TransientModel):
    _name = 'office.document.lanh.dao.reject.wizard'
    _description = 'Lãnh đạo từ chối văn bản'

    office_document_id = fields.Many2one('office.document', string='Văn bản', required=True, readonly=True)
    current_user_id = fields.Many2one('res.users', string='Người từ chối', default=lambda self: self.env.user, readonly=True)
    rejection_reason = fields.Text(
        string='Lý do từ chối', required=True,
        placeholder='Vui lòng nhập lý do từ chối văn bản...'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get('default_office_document_id'):
            doc = self.env['office.document'].browse(self._context['default_office_document_id'])
            if doc.exists():
                res['office_document_id'] = doc.id
        return res

    def action_confirm_reject(self):
        self.ensure_one()
        doc = self.office_document_id

        self.env['office.document.rejection'].create({
            'office_document_id': doc.id,
            'rejection_reason': self.rejection_reason,
            'rejected_by': self.current_user_id.id,
            'rejection_date': fields.Datetime.now(),
        })
        doc.tt_vb = 'cho_truong_don_vi_duyet'
        self._send_rejection_notifications()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        tree_url = f"{base_url}/web#action=&model=office.document&view_type=list"
        return {'type': 'ir.actions.act_url', 'url': tree_url, 'target': 'self'}

    def _send_rejection_notifications(self):
        doc = self.office_document_id
        creator = doc.create_uid
        truong_don_vi = doc.truong_don_vi_duyet
        detail_url = doc.get_form_url()

        # Gửi cho người tạo
        if creator:
            creator_emp = self.env['hr.employee'].search([('user_id', '=', creator.id)], limit=1)
            email_list = _get_employee_emails(creator_emp) if creator_emp else []
            if email_list:
                subject = f"Văn bản bị lãnh đạo từ chối: {doc.trich_yeu[:50]}..."
                body_lines = [
                    f"<b>Người từ chối:</b> {self.current_user_id.name} (Lãnh đạo xử lý)",
                    f"<b>Thời gian:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    f"<b>Lý do:</b><br/>{self.rejection_reason}",
                    f"<b>Trạng thái mới:</b> Chờ trưởng đơn vị duyệt",
                    f"<b>Trưởng đơn vị:</b> {truong_don_vi.name if truong_don_vi else 'Chưa xác định'}",
                ]
                body_html = _build_email_html(
                    title='VĂN BẢN BỊ LÃNH ĐẠO TỪ CHỐI',
                    greeting=f'Xin chào {creator.name},<br/>Văn bản <b>"{doc.trich_yeu}"</b> bị lãnh đạo từ chối và chuyển về chờ trưởng đơn vị duyệt.',
                    body_lines=body_lines,
                    detail_url=detail_url,
                    btn_label='XEM LẠI VĂN BẢN',
                    btn_color='#ffc107',
                    company_name=self.env.company.name or '',
                )
                _send_mail(self.env, subject, email_list, body_html)

                if creator.partner_id:
                    try:
                        self.env['bus.bus']._sendone(
                            creator.partner_id,
                            'simple_notification',
                            {'title': 'Văn bản bị lãnh đạo từ chối', 'message': f'Văn bản "{doc.trich_yeu[:50]}..." bị lãnh đạo từ chối.', 'sticky': False, 'type': 'warning'}
                        )
                    except Exception as e:
                        _logger.error(f"Lỗi gửi thông báo: {str(e)}")

        # Gửi cho trưởng đơn vị
        if truong_don_vi:
            email_list_tdv = _get_employee_emails(truong_don_vi)
            if email_list_tdv:
                subject_tdv = f"Văn bản cần xem lại: {doc.trich_yeu[:50]}..."
                body_lines_tdv = [
                    f"<b>Số văn bản:</b> {doc.so_vb or 'Chưa có'}",
                    f"<b>Người tạo:</b> {creator.name if creator else 'Không xác định'}",
                    f"<b>Lãnh đạo từ chối:</b> {self.current_user_id.name}",
                    f"<b>Thời gian từ chối:</b> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    f"<b>Lý do từ chối:</b><br/>{self.rejection_reason}",
                    f"<b>Yêu cầu:</b> Vui lòng xem xét và xử lý văn bản.",
                ]
                body_html_tdv = _build_email_html(
                    title='VĂN BẢN CẦN DUYỆT LẠI',
                    greeting=f'Xin chào {truong_don_vi.name},<br/>Văn bản <b>"{doc.trich_yeu}"</b> bị lãnh đạo từ chối, cần bạn xem xét lại.',
                    body_lines=body_lines_tdv,
                    detail_url=detail_url,
                    btn_label='XEM VÀ XỬ LÝ VĂN BẢN',
                    btn_color='#0dcaf0',
                    company_name=self.env.company.name or '',
                )
                _send_mail(self.env, subject_tdv, email_list_tdv, body_html_tdv)

                if truong_don_vi.user_id and truong_don_vi.user_id.partner_id:
                    try:
                        self.env['bus.bus']._sendone(
                            truong_don_vi.user_id.partner_id,
                            'simple_notification',
                            {'title': 'Văn bản cần duyệt lại', 'message': f'Văn bản "{doc.trich_yeu[:50]}..." cần bạn duyệt lại.', 'sticky': True, 'type': 'warning'}
                        )
                    except Exception as e:
                        _logger.error(f"Lỗi gửi thông báo: {str(e)}")

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}