from datetime import timedelta
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
                employees = self.env['hr.employee'].search([
                    ('department_id', 'in', rec.don_vi_xu_ly_chinh.ids),
                    ('user_id', '!=', False)
                ])
                rec.nguoi_xu_ly_chinh = employees.mapped('user_id')
            else:
                rec.nguoi_xu_ly_chinh = False

    @api.depends('don_vi_dong_xu_ly')
    def _compute_nguoi_dong_xu_ly(self):
        for rec in self:
            if rec.don_vi_dong_xu_ly:
                employees = self.env['hr.employee'].search([
                    ('department_id', 'in', rec.don_vi_dong_xu_ly.ids),
                    ('user_id', '!=', False)
                ])
                rec.nguoi_dong_xu_ly = employees.mapped('user_id')
            else:
                rec.nguoi_dong_xu_ly = False

    def phan_phat(self):
        doc_id = self.env.context.get('active_id')
        if not doc_id:
            return

        doc = self.env['office.document'].browse(doc_id)
        if not doc.exists():
            return

        # Ghi các Many2many vào văn bản
        doc.write({
            'dv_xu_ly_chinh': [(6, 0, self.don_vi_xu_ly_chinh.ids)],
            'dv_dong_xu_ly': [(6, 0, self.don_vi_dong_xu_ly.ids)],
            'nguoi_xu_ly_chinh': [(6, 0, self.nguoi_xu_ly_chinh.ids)],
            'nguoi_dong_xu_ly': [(6, 0, self.nguoi_dong_xu_ly.ids)],
            'tt_vb': 'cho_xu_ly',
        })

        # Tạo detail2
        lines_to_create = []

        for user in self.nguoi_xu_ly_chinh:
            if not doc.detail2.filtered(lambda l: l.nguoi_nhap_y_kien == user):
                lines_to_create.append({
                    'office_document_id': doc.id,
                    'nguoi_nhap_y_kien': user.id,
                    'nhom_phong_ban': user.employee_ids[
                                      :1].department_id.name if user.employee_ids else 'Không xác định',
                    'noi_dung_chi_dao': 'Xử lý chính',
                    'thoi_diem_chi_dao': fields.Datetime.now(),
                })

        for user in self.nguoi_dong_xu_ly:
            if not doc.detail2.filtered(lambda l: l.nguoi_nhap_y_kien == user):
                lines_to_create.append({
                    'office_document_id': doc.id,
                    'nguoi_nhap_y_kien': user.id,
                    'nhom_phong_ban': user.employee_ids[
                                      :1].department_id.name if user.employee_ids else 'Không xác định',
                    'noi_dung_chi_dao': 'Đồng xử lý',
                    'thoi_diem_chi_dao': fields.Datetime.now(),
                })

        if lines_to_create:
            self.env['office.document.detail2'].create(lines_to_create)

        # --- 3. Gửi thông báo popup + chat ---
        odoobot = self.env.ref('base.user_root')
        odoobot_partner = odoobot.partner_id
        partner_ids = []

        # Lấy tất cả partner người xử lý
        partner_ids += [u.partner_id.id for u in self.nguoi_xu_ly_chinh if u.partner_id]
        partner_ids += [u.partner_id.id for u in self.nguoi_dong_xu_ly if u.partner_id]
        partners = self.env['res.partner'].browse(partner_ids)

        # Link chi tiết công văn
        web_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        detail_url = f"{web_url}/web#id={doc.id}&model=office.document&view_type=form"

        # Nội dung chat HTML với link xem chi tiết
        body_chat = f"""
        <p>📄 Bạn vừa được giao xử lý văn bản: <b>{doc.trich_yeu}</b>.</p>
        <p>
            <a href="{detail_url}"
               style="background:#875A7B;color:blue;padding:6px 12px;text-decoration:none;border-radius:4px;font-size:12px;">
               Xem chi tiết
            </a>
        </p>
        """

        # Gửi thông báo trong chatter của document
        doc.message_post(
            body=f"📄 Văn bản <b>{doc.trich_yeu}</b> đã được phân phát đến người xử lý. <a href='{detail_url}'>Xem chi tiết</a>",
            partner_ids=partner_ids,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )

        # Hàm tạo kênh chat 1-1
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

        # Gửi popup và tin nhắn chat đến từng người
        for partner in partners:
            # Gửi popup real-time
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

            # Gửi tin nhắn chat qua Discuss
            try:
                channel = get_or_create_direct_chat(odoobot_partner, partner)
                if channel:
                    channel.sudo().message_post(
                        body=body_chat,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=odoobot_partner.id,
                        body_is_html=True,
                    )
            except Exception as e:
                _logger.error(f"Lỗi gửi chat cho {partner.name}: {str(e)}")

        # --- 4. Hoàn tất và đóng wizard ---
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': 'Đã phân phát văn bản và gửi thông báo đến người nhận.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},  # Đóng wizard form
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
        self.tt_vb = 'cho_but_phe'
        partner_ids = self.lanh_dao_xu_ly.partner_id.ids if self.lanh_dao_xu_ly and self.lanh_dao_xu_ly.partner_id else []
        self.message_post(
            body=f"Văn bản '{self.trich_yeu}' đã được trình lãnh đạo {self.lanh_dao_xu_ly.name if self.lanh_dao_xu_ly else 'Không xác định'}.",
            partner_ids=partner_ids
        )
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

        user = self.env.user
        # Nếu chưa set tt_vb từ form, thì set lại khi lưu
        if user.has_group('quan_ly_cong_van.group_van_thu'):
            vals['tt_vb'] = 'da_duyet'
        elif user.has_group('quan_ly_cong_van.group_lanh_dao'):
            vals['tt_vb'] = 'da_duyet'
        elif user.has_group('quan_ly_cong_van.group_don_vi_xu_ly'):
            vals['tt_vb'] = 'cho_duyet'
        else:
            vals['tt_vb'] = 'cho_duyet'

        # Xử lý so_den_tong_hop và so_di_tong_hop khi có phan_loai_van_ban
        vals = self._update_document_numbers(vals)

        return super(OfficeDocument, self).create(vals)

    def write(self, vals):
        # Nếu thay đổi phan_loai_van_ban thì cập nhật lại số tổng hợp
        if 'phan_loai_van_ban' in vals:
            for record in self:
                new_vals = vals.copy()
                new_vals = record._update_document_numbers(new_vals, is_write=True)
                super(OfficeDocument, record).write(new_vals)
            return True
        else:
            # Nếu không thay đổi phân loại, nhưng có thay đổi số → giữ nguyên logic cũ
            return super(OfficeDocument, self).write(vals)

    def _update_document_numbers(self, vals, is_write=False):
        """
        Cập nhật so_den_tong_hop và so_di_tong_hop theo format:
        - Mặc định: <Năm hiện tại>-<Mã loại công văn>-<STT>
        - Nếu document_type = 'resolution': QĐ-<STT>
        """
        phan_loai_id = vals.get('phan_loai_van_ban')
        document_type = vals.get('document_type') or self._context.get('default_document_type') or (
            self.document_type if self else None)

        current_year = fields.Date.today().year

        # ========== XỬ LÝ SỐ ĐẾN (vẫn như cũ) ==========
        if phan_loai_id:
            phan_loai = self.env['office.document.category'].browse(phan_loai_id)
            if not phan_loai.exists() or not phan_loai.code:
                raise UserError("Phân loại văn bản chưa có mã (code)!")

            code = phan_loai.code
            seq_prefix_den = f'den.{current_year}.{code}'
            seq_den = self.env['ir.sequence'].sudo().search([('code', '=', seq_prefix_den)], limit=1)
            if not seq_den:
                seq_den = self.env['ir.sequence'].sudo().create({
                    'name': f'Số đến - {current_year} - {code}',
                    'code': seq_prefix_den,
                    'prefix': f'{current_year}-{code}-',
                    'padding': 3,
                    'company_id': False,
                })

            if not vals.get('so_den_tong_hop'):
                vals['so_den_tong_hop'] = self.env['ir.sequence'].next_by_code(seq_prefix_den)

        # ========== XỬ LÝ SỐ ĐI ==========
        # Nếu loại văn bản là 'resolution' → dùng QĐ-<STT>
        if document_type == 'resolution':
            seq_code_qd = 'di.resolution'
            seq_qd = self.env['ir.sequence'].sudo().search([('code', '=', seq_code_qd)], limit=1)
            if not seq_qd:
                seq_qd = self.env['ir.sequence'].sudo().create({
                    'name': 'Số đi - Quyết định',
                    'code': seq_code_qd,
                    'prefix': 'QĐ-',
                    'padding': 3,
                    'company_id': False,
                })
            if not vals.get('so_di_tong_hop'):
                vals['so_di_tong_hop'] = self.env['ir.sequence'].next_by_code(seq_code_qd)

        else:
            # Các loại khác theo phân loại văn bản
            if phan_loai_id:
                code = self.env['office.document.category'].browse(phan_loai_id).code
                seq_prefix_di = f'di.{current_year}.{code}'
                seq_di = self.env['ir.sequence'].sudo().search([('code', '=', seq_prefix_di)], limit=1)
                if not seq_di:
                    seq_di = self.env['ir.sequence'].sudo().create({
                        'name': f'Số đi - {current_year} - {code}',
                        'code': seq_prefix_di,
                        'prefix': f'{current_year}-{code}-',
                        'padding': 3,
                        'company_id': False,
                    })

                if not vals.get('so_di_tong_hop'):
                    vals['so_di_tong_hop'] = self.env['ir.sequence'].next_by_code(seq_prefix_di)

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
        self.tt_vb = 'cho_duyet'
        return True