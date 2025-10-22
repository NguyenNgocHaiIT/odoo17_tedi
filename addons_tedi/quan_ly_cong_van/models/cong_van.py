from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError
import odoo

class PhanPhat(models.TransientModel):
    _name = 'office.document.phan.phat'

    nhan_van_ban = fields.Char('Nhận văn bản')
    don_vi_xu_ly_chinh = fields.Many2one('hr.department', string='Đơn vị xử lý chính')
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
    nguoi_xu_ly_chinh = fields.Many2one('res.users', string='Người xử lý chính')
    nguoi_dong_xu_ly = fields.Many2many(
        'res.users',
        'office_document_nguoi_dong_xu_ly_rel',
        'phanphat_id', 'user_id',
        string='Người đồng xử lý'
    )

    def phan_phat(self):
        doc_id = self.env.context.get('active_id')
        if not doc_id:
            return

        doc = self.env['office.document'].browse(doc_id)
        if not doc.exists():
            return

        # Cập nhật văn bản (chỉ người nhận)
        doc.write({
            'nguoi_xu_ly_chinh': self.nguoi_xu_ly_chinh.id if self.nguoi_xu_ly_chinh else False,
            'nguoi_dong_xu_ly': [(6, 0, self.nguoi_dong_xu_ly.ids)],
            'tt_vb': 'da_phan_phat',
        })

        # Tạo detail2 chỉ với người nhận
        lines_to_create = []

        if self.nguoi_xu_ly_chinh:
            if not doc.detail2.filtered(lambda l: l.nguoi_nhap_y_kien == self.nguoi_xu_ly_chinh):
                lines_to_create.append({
                    'office_document_id': doc.id,
                    'nguoi_nhap_y_kien': self.nguoi_xu_ly_chinh.id,
                    'nhom_phong_ban': self.nguoi_xu_ly_chinh.employee_ids[
                                      :1].department_id.name if self.nguoi_xu_ly_chinh.employee_ids else 'Không xác định',
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

        # Gửi thông báo cho người nhận
        partner_ids = []
        if self.nguoi_xu_ly_chinh and self.nguoi_xu_ly_chinh.partner_id:
            partner_ids.append(self.nguoi_xu_ly_chinh.partner_id.id)
        partner_ids += [u.partner_id.id for u in self.nguoi_dong_xu_ly if u.partner_id]

        doc.message_post(
            body=f"Văn bản '{doc.trich_yeu}' đã được phân phát đến người nhận.",
            partner_ids=partner_ids
        )

        return {'type': 'ir.actions.act_window_close'}

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
            'do_quan_trong': 'Cao' if self.quan_trong else (doc.do_quan_trong or 'Bình thường'),
        })

        # Tạo detail1
        nhom_phong_ban = self.env.user.employee_ids[:1].department_id.name if self.env.user.employee_ids else 'Không xác định'
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
    noi_dung_chi_dao = fields.Char('Nội dung')
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
        ('resolution', 'Quyết định')
    ], string='Loại công văn', required=True)
    loai_van_ban = fields.Selection([
        ('1', 'Thông báo'),
        ('2', 'Tờ trình'),
        ('3', 'Quy chế')
    ], string='Loại văn bản')
    lanh_dao_xu_ly = fields.Many2one('res.users', string='Lãnh đạo xử lý')
    lanh_dao_theo_doi = fields.Many2one('res.users', string='Lãnh đạo theo dõi')
    ngay_den = fields.Date('Ngày đến')
    phan_loai_van_ban = fields.Selection([
        ('outside', 'Công văn'),
        ('inside', 'Văn bản nội bộ')], string='Phân loại văn bản')
    so_den_tong_hop = fields.Char('Số đến tổng hợp')
    so_di_tong_hop = fields.Char('Số công văn')
    so_hieu = fields.Char('Số hiệu')
    ngay_ban_hanh = fields.Date('Ngày ban hành')
    noi_gui = fields.Char('Nơi gửi')
    nguoi_ky = fields.Many2one('res.users', string='Người ký')
    do_khan =  fields.Selection([
        ('thap', 'Thấp'),
        ('thuong', 'Thường'),
        ('trung_binh', 'Trung bình'),
        ('cao', 'Cao')], string='Độ khẩn', default='thuong')
    vb_nhan = fields.Char('Văn bản nhận')
    tt_vb = fields.Selection([
        ('draft', 'Nháp'),
        ('dang_trinh', 'Đang trình lãnh đạo'),
        ('da_duyet', 'Đã duyệt'),
        ('da_phan_phat', 'Đã phân phát')
    ], string='Trạng thái văn bản', default='draft', tracking=True)
    dv_xu_ly_chinh = fields.Many2one('hr.department', string='Đơn vị xử lý chính')
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
    ngay_bat_dau = fields.Date('Ngày bắt đầu')
    ho_so_cong_viec = fields.Char('Hồ sơ công việc')
    attachment = fields.Binary('Tài liệu')
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
    nguoi_xu_ly_chinh = fields.Many2one('res.users', string='Người xử lý chính')
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
            'dv_xu_ly_chinh': self.don_vi_xu_ly_chinh.id if self.don_vi_xu_ly_chinh else False,
            'dv_dong_xu_ly': self.don_vi_dong_xu_ly.id if self.don_vi_dong_xu_ly else False,
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

    def trinh_lanh_dao(self):
        self.ensure_one()
        if not self.lanh_dao_xu_ly:
            raise UserError("Vui lòng chọn lãnh đạo xử lý trước khi trình.")
        self.tt_vb = 'dang_trinh'
        partner_ids = self.lanh_dao_xu_ly.partner_id.ids if self.lanh_dao_xu_ly and self.lanh_dao_xu_ly.partner_id else []
        self.message_post(
            body=f"Văn bản '{self.trich_yeu}' đã được trình lãnh đạo {self.lanh_dao_xu_ly.name if self.lanh_dao_xu_ly else 'Không xác định'}.",
            partner_ids=partner_ids
        )
        return True

    def approve(self):
        self.ensure_one()
        if not self.lanh_dao_xu_ly:
            raise UserError("Vui lòng chọn lãnh đạo xử lý trước khi duyệt.")
        self.tt_vb = 'da_duyet'
        partner_ids = self.lanh_dao_xu_ly.partner_id.ids if self.lanh_dao_xu_ly and self.lanh_dao_xu_ly.partner_id else []
        self.message_post(
            body=f"Văn bản/Quyết định '{self.trich_yeu}' đã được duyệt bởi {self.lanh_dao_xu_ly.name if self.lanh_dao_xu_ly else 'Không xác định'}.",
            partner_ids=partner_ids
        )
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

