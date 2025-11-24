from datetime import timedelta
from operator import index

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import odoo
import logging

_logger = logging.getLogger(__name__)


class PhanPhat(models.TransientModel):
    _name = 'office.document.phan.phat'

    nhan_van_ban = fields.Char('Nhận văn bản')
    don_vi_xu_ly_chinh = fields.Many2many(
        'hr.department',
        'office_document_dv_xu_ly_chinh_rel',
        'phanphat_id', 'department_id',
        string='Đơn vị xử lý chính')
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
        'res.users',
        'office_document_nguoi_xu_ly_chinh_rel',
        'phanphat_id', 'user_id',
        compute='_compute_nguoi_xu_ly_chinh',
        string='Người xử lý chính')
    nguoi_dong_xu_ly = fields.Many2many(
        'res.users',
        'office_document_nguoi_dong_xu_ly_rel',
        'phanphat_id', 'user_id',
        compute='_compute_nguoi_dong_xu_ly',
        string='Người đồng xử lý'
    )

    @api.constrains('don_vi_xu_ly_chinh', 'don_vi_dong_xu_ly')
    def _check_don_vi_trung(self):
        for rec in self:
            common = set(rec.don_vi_xu_ly_chinh.ids) & set(rec.don_vi_dong_xu_ly.ids)
            if common:
                raise ValidationError("Đơn vị xử lý chính và đồng xử lý không được trùng nhau!")

    # ----- COMPUTE FIELD -----
    @api.depends('don_vi_xu_ly_chinh')
    def _compute_nguoi_xu_ly_chinh(self):
        for rec in self:
            if rec.don_vi_xu_ly_chinh:
                # Lấy manager_id của các phòng ban
                managers = rec.don_vi_xu_ly_chinh.mapped('manager_id.user_id')
                rec.nguoi_xu_ly_chinh = managers if managers else False
            else:
                rec.nguoi_xu_ly_chinh = False

    @api.depends('don_vi_dong_xu_ly')
    def _compute_nguoi_dong_xu_ly(self):
        for rec in self:
            if rec.don_vi_dong_xu_ly:
                managers = rec.don_vi_dong_xu_ly.mapped('manager_id.user_id')
                rec.nguoi_dong_xu_ly = managers if managers else False
            else:
                rec.nguoi_dong_xu_ly = False

    def phan_phat(self):
        doc_id = self.env.context.get('active_id')
        if not doc_id:
            return

        doc = self.env['office.document'].browse(doc_id)
        if not doc.exists():
            return

        # --- 1. Cập nhật Many2many vào văn bản ---
        doc.write({
            'dv_xu_ly_chinh': [(6, 0, self.don_vi_xu_ly_chinh.ids)],
            'dv_dong_xu_ly': [(6, 0, self.don_vi_dong_xu_ly.ids)],
            'nguoi_xu_ly_chinh': [(6, 0, self.nguoi_xu_ly_chinh.ids)],
            'nguoi_dong_xu_ly': [(6, 0, self.nguoi_dong_xu_ly.ids)],
            'tt_vb': 'cho_xu_ly',
        })

        # --- 2. Tạo detail2 cho từng người ---
        lines_to_create = []
        for user, role in [(u, 'Xử lý chính') for u in self.nguoi_xu_ly_chinh] + \
                          [(u, 'Đồng xử lý') for u in self.nguoi_dong_xu_ly]:
            if not doc.detail2.filtered(lambda l: l.nguoi_nhap_y_kien == user):
                lines_to_create.append({
                    'office_document_id': doc.id,
                    'nguoi_nhap_y_kien': user.id,
                    'nhom_phong_ban': user.employee_ids[
                                      :1].department_id.name if user.employee_ids else 'Không xác định',
                    'noi_dung_chi_dao': role,
                    'thoi_diem_chi_dao': fields.Datetime.now(),
                    'chuc_vu': 'quan_ly',
                })
        if lines_to_create:
            self.env['office.document.detail2'].create(lines_to_create)

        # --- 3. Chuẩn bị thông tin gửi popup, chat, email ---
        odoobot = self.env.ref('base.user_root')
        odoobot_partner = odoobot.partner_id

        users_to_notify = (self.nguoi_xu_ly_chinh + self.nguoi_dong_xu_ly).filtered(lambda u: u.partner_id)
        partners = users_to_notify.mapped('partner_id')

        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        detail_url = f"{web_url}/web#id={doc.id}&model=office.document&view_type=form"

        body_chat = f"""
        <p>📄 Bạn vừa được giao xử lý văn bản: <b>{doc.trich_yeu}</b>.</p>
        <p>
            <a href="{detail_url}" style="background:#875A7B;color:blue;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
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
        for user in users_to_notify:
            partner = user.partner_id

            # Popup real-time
            self.env['bus.bus']._sendone(
                partner,
                'simple_notification',
                {
                    'title': 'Phân phát văn bản mới',
                    'message': f"Bạn vừa được phân công xử lý văn bản: {doc.trich_yeu}",
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
                    <p>Xin chào {user.name},</p>
                    <p>Bạn vừa được phân công xử lý văn bản: <b>{doc.trich_yeu}</b>.</p>
                    <p>
                        <a href="{detail_url}" style="background:#875A7B;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                            Xem chi tiết văn bản
                        </a>
                    </p>
                    <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
                """
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_to': user.email,
                    'email_from': self.env.user.email or 'odoobot@example.com',
                    'body_html': body_html,
                }).send()
            except Exception as e:
                _logger.warning(f"Gửi mail thất bại cho {user.email}: {str(e)}")

        # --- 6. Thông báo thành công ---
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': 'Đã phân phát văn bản và gửi email đến người nhận.',
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
    thong_bao_cho_van_thu = fields.Boolean('Thông báo cho văn thư')

    def but_phe(self):
        doc_id = self.env.context.get('active_id')
        if not doc_id:
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': 'Lỗi', 'message': 'Chưa có văn bản để bút phê.',
                               'type': 'warning', 'sticky': False}}

        doc = self.env['office.document'].browse(doc_id)
        if not doc.exists():
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': 'Lỗi', 'message': 'Văn bản không tồn tại.', 'type': 'warning', 'sticky': False}}

        # Update văn bản
        doc.write({
            'but_phe': self.y_kien_xu_ly,
            'tt_vb': 'cho_phan_phat',
        })

        # Tạo detail1
        nhom_phong_ban = self.env.user.employee_ids[
                         :1].department_id.name if self.env.user.employee_ids else 'Không xác định'
        self.env['office.document.detail1'].create({
            'office_document_id': doc.id,
            'nguoi_nhap_y_kien': self.env.user.id,
            'nhom_phong_ban': nhom_phong_ban,
            'noi_dung_chi_dao': self.y_kien_xu_ly or 'Không có ý kiến',
            'thoi_diem_chi_dao': fields.Datetime.now(),
        })

        # Gửi thông báo lãnh đạo
        partner_ids = doc.lanh_dao_xu_ly.partner_id.ids if doc.lanh_dao_xu_ly and doc.lanh_dao_xu_ly.partner_id else []
        doc.message_post(
            body=f"Bút phê: {self.y_kien_xu_ly or 'Không có ý kiến'}, Quan trọng: {self.quan_trong}",
            partner_ids=partner_ids
        )

        # Thông báo văn thư
        if self.thong_bao_cho_van_thu:
            group = self.env.ref('quan_ly_cong_van.group_van_thu', raise_if_not_found=False)
            if group:
                doc.message_post(
                    body="Thông báo văn thư: Văn bản đã có bút phê.",
                    partner_ids=group.users.mapped('partner_id').ids
                )

        # Lưu tài liệu kèm
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

    nguoi_nhap_y_kien = fields.Many2one('res.users', string='Người nhập ý kiến')
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
            rec.nhom_phong_ban = False
            try:
                if rec.nguoi_nhap_y_kien and rec.nguoi_nhap_y_kien.employee_ids:
                    employee = rec.nguoi_nhap_y_kien.employee_ids[:1]
                    if employee and employee[0].department_id:
                        rec.nhom_phong_ban = employee[0].department_id.name
            except Exception:
                rec.nhom_phong_ban = 'Không xác định'


class OfficeDocumentDetail2(models.Model):
    _name = 'office.document.detail2'

    nguoi_nhap_y_kien = fields.Many2one('res.users', string='Người nhập ý kiến')
    nhom_phong_ban = fields.Char(
        string='Nhóm phòng ban',
        compute='_compute_nhom_phong_ban',
        store=True  # Nếu muốn lưu giá trị vào DB
    )
    noi_dung_chi_dao = fields.Char('Trách nhiệm')
    thoi_diem_chi_dao = fields.Datetime('Thời điểm')
    view_time = fields.Datetime('Thời gian xem', readonly=True)
    office_document_id = fields.Many2one('office.document')

    chuc_vu = fields.Selection([
        ('quan_ly', 'QUản lý'),
        ('nhan_vien', 'Nhân viên'),
    ], string='Chức vụ')
    nguoi_quan_ly = fields.Many2one('res.users', string='Người quản lý')
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
        }

    @api.depends('chuc_vu')
    def _compute_is_section(self):
        for rec in self:
            rec.is_section = (rec.chuc_vu == 'quan_ly')

    def action_open_document(self):
        self.ensure_one()
        user = self.env.user
        details = self.detail2.filtered(lambda d: d.nguoi_nhap_y_kien.id == user.id)
        for detail in details:
            if not detail.view_time:
                detail.write({'view_time': fields.Datetime.now()})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'office.document',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    @api.depends('nguoi_nhap_y_kien')
    def _compute_nhom_phong_ban(self):
        for rec in self:
            rec.nhom_phong_ban = False
            try:
                if rec.nguoi_nhap_y_kien and rec.nguoi_nhap_y_kien.employee_ids:
                    employee = rec.nguoi_nhap_y_kien.employee_ids[:1]
                    if employee and employee[0].department_id:
                        rec.nhom_phong_ban = employee[0].department_id.name
            except Exception:
                rec.nhom_phong_ban = 'Không xác định'

    allow_assign = fields.Boolean(compute='_compute_allow_assign')

    @api.depends('nguoi_nhap_y_kien')
    def _compute_allow_assign(self):
        for rec in self:
            rec.allow_assign = (rec.nguoi_nhap_y_kien.id == self.env.user.id)


class OfficeDocumentDetail3(models.Model):
    _name = 'office.document.detail3'

    nguoi_nhap_y_kien = fields.Many2one('res.users', string='Người nhập ý kiến')
    nhom_phong_ban = fields.Char(
        string='Nhóm phòng ban',
        compute='_compute_nhom_phong_ban',
        store=True  # Nếu muốn lưu giá trị vào DB
    )
    noi_dung_chi_dao = fields.Char('Nội dung')
    thoi_diem_chi_dao = fields.Datetime('Thời điểm')
    office_document_id = fields.Many2one('office.document')

    @api.depends('nguoi_nhap_y_kien')
    def _compute_nhom_phong_ban(self):
        for rec in self:
            rec.nhom_phong_ban = False
            try:
                if rec.nguoi_nhap_y_kien and rec.nguoi_nhap_y_kien.employee_ids:
                    employee = rec.nguoi_nhap_y_kien.employee_ids[:1]
                    if employee and employee[0].department_id:
                        rec.nhom_phong_ban = employee[0].department_id.name
            except Exception:
                rec.nhom_phong_ban = 'Không xác định'


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
    ], string='Loại công văn', required=True)
    loai_van_ban = fields.Selection([
        ('1', 'Thông báo'),
        ('2', 'Tờ trình'),
        ('3', 'Quy chế')
    ], string='Loại văn bản')
    lanh_dao_xu_ly = fields.Many2one('res.users', string='Lãnh đạo xử lý')
    lanh_dao_theo_doi = fields.Many2one('res.users', string='Lãnh đạo theo dõi')
    ngay_den = fields.Date('Ngày đến')
    phan_loai_van_ban = fields.Many2one('office.document.category', string='Phân loại văn bản')
    so_den_tong_hop = fields.Char('Số đến tổng hợp')
    so_di_tong_hop = fields.Char('Số công văn')
    so_hieu = fields.Char('Số hiệu')
    ngay_ban_hanh = fields.Date('Ngày ban hành')
    noi_gui = fields.Char('Nơi gửi')
    nguoi_ky = fields.Many2one('res.users', string='Người ký')
    do_khan = fields.Selection([
        ('khan', 'Khẩn'),
        ('mat', 'Mật'),
        ('hoa_toc', 'Hỏa tốc')], string='Độ khẩn', default='khan')
    vb_nhan = fields.Char('Văn bản nhận')
    tt_vb = fields.Selection([
        ('draft', 'Nhập thông tin'),
        ('cho_duyet', 'Chờ duyệt'),
        ('da_duyet', 'Đã duyệt'),
        ('cho_but_phe', 'Chờ bút phê'),
        ('cho_phan_phat', 'Chờ phân phát'),
        ('cho_xu_ly', 'Chờ xử lý'),
        ('da_xu_ly', 'Đã xử lý')
    ], string='Trạng thái văn bản', default='draft', tracking=True)
    dv_xu_ly_chinh = fields.Many2many(
        'hr.department',
        'dv_xu_ly_chinh_rel',
        'document_id',
        'department_id',
        string='Đơn vị xử lý chính')
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
    attachment = fields.Many2many('ir.attachment', string='Tài liệu')
    note = fields.Text('Ghi chú')
    don_vi_ban_hanh_ngoai = fields.Many2one('res.partner', string='Đơn vị ban hành')
    don_vi_ban_hanh = fields.Many2one('hr.department', string='Đơn vị ban hành')
    don_vi_soan_thao = fields.Many2one('hr.department', string='Đơn vị soạn thảo')
    don_vi_nhan_ben_ngoai = fields.Char('Đơn vị nhận bên ngoài')
    nguoi_theo_doi_chinh = fields.Many2one('res.users', string='Người theo dõi chính')
    so_den_theo_so = fields.Char('Số đến theo sổ')
    so_di_theo_so = fields.Char('Số đi theo sổ')
    so_vb = fields.Char('Số văn bản')
    ngay_hieu_luc = fields.Date('Ngày hiệu lực')
    ngay_ky = fields.Date('Ngày ký')
    chuc_vu = fields.Char('Chức vụ')
    do_quan_trong = fields.Char('Độ quan trọng')
    nguoi_xu_ly_chinh = fields.Many2many(
        'res.users',
        'nguoi_xu_ly_chinh_rel',
        'document_id',
        'user_id',
        string='Người xử lý chính')
    nguoi_dong_xu_ly = fields.Many2many(
        'res.users',
        'office_doc_user_rel',
        'document_id',
        'user_id',
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
    can_duyet = fields.Boolean(string='Văn bản có cần duyệt không ?')

    @api.model
    def log(self):
        import pprint
        vals = {
            'dv_xu_ly_chinh': self.dv_xu_ly_chinh.id if self.dv_xu_ly_chinh else False,
            'dv_dong_xu_ly': self.dv_dong_xu_ly.id if self.dv_dong_xu_ly else False,
            'nguoi_xu_ly_chinh': self.nguoi_xu_ly_chinh.id if self.nguoi_xu_ly_chinh else False,
            'nguoi_dong_xu_ly': self.nguoi_dong_xu_ly.id if self.nguoi_dong_xu_ly else False,
        }

        # In ra console log Odoo server
        _logger = self.env['ir.logging']
        print("=== DEBUG vals trước write ===")
        pprint.pprint(vals)

    def create(self, vals):
        if 'ngay_bat_dau' in vals and not vals.get('han_ket_thuc'):
            vals['han_ket_thuc'] = fields.Date.from_string(vals['ngay_bat_dau']) + timedelta(days=7)
        user = self.env.user
        # Nếu chưa set tt_vb từ form, thì set lại khi lưu
        if user.has_group('quan_ly_cong_van.group_van_thu'):
            vals['tt_vb'] = 'da_duyet'
        elif user.has_group('quan_ly_cong_van.group_don_vi_xu_ly'):
            vals['tt_vb'] = 'cho_duyet'

        return super().create(vals)

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

    def trinh_lanh_dao_cong_van_den(self):
        self.ensure_one()
        if not self.lanh_dao_xu_ly:
            raise UserError("Vui lòng chọn lãnh đạo xử lý trước khi trình.")

        # Cập nhật trạng thái
        self.tt_vb = 'cho_but_phe'

        # Lấy partner của lãnh đạo
        partner = self.lanh_dao_xu_ly.partner_id
        if not partner or not partner.email:
            raise UserError("Lãnh đạo xử lý chưa có địa chỉ email.")

        # Nội dung thông báo
        subject = f"Văn bản '{self.trich_yeu}' cần xử lý"
        body = f"Văn bản '{self.trich_yeu}' đã được trình lãnh đạo {self.lanh_dao_xu_ly.name}."

        # Gửi email
        self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': body,
            'email_to': partner.email,
            'auto_delete': True,  # Xóa mail sau khi gửi
        }).send()

        return True

    def approve(self):
        self.ensure_one()
        self.tt_vb = 'da_duyet'
        return True

    def read(self, fields=None, load='_classic_read'):
        res = super().read(fields, load)
        if 'detail2' in (fields or []):
            for doc in self:
                details = doc.detail2.filtered(lambda d: d.nguoi_nhap_y_kien.id == self.env.user.id)
                for detail in details:
                    if not detail.view_time:
                        detail.sudo().write({'view_time': odoo.fields.Datetime.now()})
        return res

    def unlink(self):
        self.mapped('detail1').unlink()
        self.mapped('detail2').unlink()
        self.mapped('detail3').unlink()
        return super().unlink()

    @api.model
    def create(self, vals):
        # Xử lý han_ket_thuc
        if 'ngay_bat_dau' in vals and not vals.get('han_ket_thuc'):
            vals['han_ket_thuc'] = fields.Date.from_string(vals['ngay_bat_dau']) + timedelta(days=7)

        can_duyet_val = vals.get('can_duyet')
        user = self.env.user
        # Nếu chưa set tt_vb từ form, thì set lại khi lưu
        if user.has_group('quan_ly_cong_van.group_van_thu'):
            vals['tt_vb'] = 'da_duyet'
        elif can_duyet_val is True:
            vals['tt_vb'] = 'draft'
        elif user.has_group('quan_ly_cong_van.group_don_vi_xu_ly'):
            vals['tt_vb'] = 'cho_duyet'
        else:
            vals['tt_vb'] = 'cho_duyet'

        # Xử lý so_den_tong_hop và so_di_tong_hop khi có phan_loai_van_ban
        vals = self._update_document_numbers(vals)

        return super(OfficeDocument, self).create(vals)

    def write(self, vals):
        # 1. Kiểm tra trạng thái draft
        for doc in self:
            if doc.tt_vb != 'draft':
                raise UserError("Chỉ có thể chỉnh sửa khi trạng thái là nhập văn bản!")

        # 2. Nếu thay đổi phan_loai_van_ban thì cập nhật số tổng hợp
        if 'phan_loai_van_ban' in vals:
            new_vals_list = []
            for record in self:
                new_vals = vals.copy()
                new_vals = record._update_document_numbers(new_vals, is_write=True)
                new_vals_list.append((record.id, new_vals))

            # Gọi super.write cho từng record (không còn gọi lại write cho toàn bộ recordset)
            for record_id, new_vals in new_vals_list:
                super(OfficeDocument, self.browse(record_id)).write(new_vals)
            return True
        else:
            # Nếu không thay đổi phân loại → write bình thường
            return super(OfficeDocument, self).write(vals)

    def _update_document_numbers(self, vals, is_write=False):
        """
        Cập nhật so_den_tong_hop và so_di_tong_hop:
        - Loại bình thường: <YYMMDD>-<Mã loại>-<STT> (STT 4 chữ số)
        - Quyết định: <YYMMDD>-QĐ-<STT> (STT 4 chữ số)
        """
        phan_loai_id = vals.get('phan_loai_van_ban')
        document_type = vals.get('document_type') or self._context.get('default_document_type') or (
            self.document_type if self else None)

        current_date_str = fields.Date.today().strftime('%y%m%d')  # YYMMDD

        def get_or_create_sequence(code, name, prefix):
            seq = self.env['ir.sequence'].sudo().search([('code', '=', code)], limit=1)
            if not seq:
                seq = self.env['ir.sequence'].sudo().create({
                    'name': name,
                    'code': code,
                    'prefix': prefix,
                    'padding': 4,
                    'company_id': False,
                })
            return seq

        # ========== SỐ ĐẾN ==========
        if phan_loai_id:
            phan_loai = self.env['office.document.category'].browse(phan_loai_id)
            if not phan_loai.exists() or not phan_loai.code:
                raise UserError("Phân loại văn bản chưa có mã (code)!")
            code = phan_loai.code
            seq_code_den = f'den.{code}'
            seq_den = get_or_create_sequence(
                seq_code_den,
                f'Số đến - {code}',
                f'{current_date_str}-{code}-'
            )
            if not vals.get('so_den_tong_hop'):
                vals['so_den_tong_hop'] = self.env['ir.sequence'].next_by_code(seq_code_den)

        # ========== SỐ ĐI ==========
        if document_type == 'resolution':
            seq_code_qd = 'di.resolution'
            seq_qd = get_or_create_sequence(
                seq_code_qd,
                'Số đi - Quyết định',
                f'{current_date_str}-QĐ-'
            )
            if not vals.get('so_di_tong_hop'):
                vals['so_di_tong_hop'] = self.env['ir.sequence'].next_by_code(seq_code_qd)
        else:
            if phan_loai_id:
                code = self.env['office.document.category'].browse(phan_loai_id).code
                seq_code_di = f'di.{code}'
                seq_di = get_or_create_sequence(
                    seq_code_di,
                    f'Số đi - {code}',
                    f'{current_date_str}-{code}-'
                )
                if not vals.get('so_di_tong_hop'):
                    vals['so_di_tong_hop'] = self.env['ir.sequence'].next_by_code(seq_code_di)

        return vals

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        start_date = res.get('ngay_bat_dau', fields.Date.context_today(self))
        res['han_ket_thuc'] = start_date + timedelta(days=7)
        return res

    @api.constrains('ngay_bat_dau', 'han_ket_thuc')
    def _check_dates(self):
        for rec in self:
            if rec.han_ket_thuc and rec.ngay_bat_dau:
                if rec.han_ket_thuc < rec.ngay_bat_dau:
                    raise ValidationError("Ngày kết thúc không được sớm hơn ngày bắt đầu!")

    def trinh_lanh_dao_cong_van_di(self):
        self.ensure_one()

        if not self.lanh_dao_xu_ly:
            raise UserError("Vui lòng chọn lãnh đạo xử lý trước khi trình.")

        # Cập nhật trạng thái
        self.tt_vb = 'cho_duyet'

        # Lấy partner của lãnh đạo
        partner = self.lanh_dao_xu_ly.partner_id
        if not partner or not partner.email:
            raise UserError("Lãnh đạo xử lý chưa có địa chỉ email.")

        # Nội dung mail
        subject = f"Văn bản '{self.trich_yeu}' cần duyệt"
        body = f"Văn bản '{self.trich_yeu}' đã được trình lãnh đạo {self.lanh_dao_xu_ly.name} để duyệt."

        # Gửi email
        self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': body,
            'email_to': partner.email,
            'auto_delete': True,  # Xóa mail sau khi gửi
        }).send()

        return True

    def get_form_url(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web#id={self.id}&model=office.document&view_type=form"

    def phat_hanh(self):
        self.ensure_one()
        self.tt_vb = 'da_xu_ly'
        return True

class AssignTaskWizard(models.TransientModel):
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
        current_user = self.env.user  # người đang bấm nút
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
                'nguoi_quan_ly': current_user.id,
                'sequence': manager.sequence + 1,
            }
            vals_list.append(vals)

        if vals_list:
            created_lines = self.env['office.document.detail2'].create(vals_list)

            # --- Gửi email trực tiếp ---
            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.office_document_id.id}&model=office.document&view_type=form"

            for line in created_lines:
                user = line.nguoi_nhap_y_kien
                if user.email:
                    try:
                        subject = f"[Văn bản mới] {self.office_document_id.trich_yeu}"
                        body_html = f"""
                                    <p>Xin chào {user.name},</p>
                                    <p>Bạn vừa được giao xử lý văn bản: <b>{self.office_document_id.trich_yeu}</b>.</p>
                                    <p>
                                        <a href="{detail_url}" style="background:#875A7B;color:white;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
                                            Xem chi tiết văn bản
                                        </a>
                                    </p>
                                    <p>Trân trọng,<br/>Hệ thống quản lý công văn</p>
                                """
                        mail_values = {
                            'subject': subject,
                            'email_to': user.email,
                            'email_from': self.env.user.email or 'odoobot@example.com',
                            'body_html': body_html,
                        }
                        self.env['mail.mail'].sudo().create(mail_values).send()
                    except Exception as e:
                        _logger.error(f"Lỗi gửi email cho {user.name}: {str(e)}")

            # --- Gửi thông báo popup + chat ---
            odoobot = self.env.ref('base.user_root')
            odoobot_partner = odoobot.partner_id
            partners = created_lines.mapped('nguoi_nhap_y_kien.partner_id')

            web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            detail_url = f"{web_url}/web#id={self.office_document_id.id}&model=office.document&view_type=form"

            body_chat = f"""
            <p>📄 Bạn vừa được giao xử lý văn bản: <b>{self.office_document_id.trich_yeu}</b>.</p>
            <p>
                <a href="{detail_url}" style="background:#875A7B;color:blue;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
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
                        lambda c: set(c.channel_member_ids.mapped('partner_id').ids) == {partner.id,
                                                                                         odoobot_partner.id})
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
        'res.users',
        string="Nhân viên",
    )

    @api.onchange('wizard_id')
    def _onchange_wizard_id(self):
        """Set domain cho field 'nguoi_nhap_y_kien' theo phòng ban của document"""
        if not self.wizard_id or not self.wizard_id.detail_id or not self.wizard_id.detail_id.nhom_phong_ban:
            return {'domain': {'nguoi_nhap_y_kien': [('id', '=', False)]}}

        department_name = self.wizard_id.detail_id.nhom_phong_ban

        # Lấy nhân viên theo phòng ban và đã có user_id
        employees = self.env['hr.employee'].search([
            ('department_id.name', '=', department_name),
            ('user_id', '!=', False)
        ])
        user_ids = employees.mapped('user_id').ids

        return {'domain': {'nguoi_nhap_y_kien': [('id', 'in', user_ids)] if user_ids else [('id', '=', False)]}}
