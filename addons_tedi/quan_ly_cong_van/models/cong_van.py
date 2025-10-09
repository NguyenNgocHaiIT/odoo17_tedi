from datetime import timedelta

from odoo import models, fields, api


class PhanPhat(models.TransientModel):
    _name = 'office.document.phan.phat'

    nhan_van_ban = fields.Char('Nhận văn bản')
    don_vi_xu_ly_chinh = fields.Char('Đơn vị xử lý chính')
    don_vi_dong_xu_ly = fields.Char('Đơn vị đồng xử lý')
    pb_dv_nhan = fields.Char('Phòng ban')
    ca_nhan_dv_nhan = fields.Char('Cá nhân')
    nhom_nguoi_dung_dv_nhan = fields.Char('Nhóm người dùng')
    noi_nhan_ban_goc_luu_tru = fields.Char('Nơi nhận bản gốc lưu trữ')
    nguoi_xu_ly_chinh = fields.Char('Người xử lý chính')
    nguoi_dong_xu_ly = fields.Char('Người đồng xử lý')

    def phan_phat(self):
        return True


class ButPhe(models.TransientModel):
    _name = 'office.document.but.phe'

    y_kien_xu_ly = fields.Char('Ý kiến xử lý')
    tai_lieu_kem = fields.Binary('Tài liệu kèm')
    quan_trong = fields.Boolean('Quan trọng')
    da_giai_quyet = fields.Boolean('Đã giải quyết')
    thong_bao_cho_van_thu = fields.Boolean('Thông báo cho văn thư')

    def phan_phat(self):
        return True


class OfficeDocumentDetail1(models.Model):
    _name = 'office.document.detail1'

    nguoi_nhap_y_kien = fields.Char('Người nhập ý kiến')
    nhom_phong_ban = fields.Char('Nhóm phòng ban')
    noi_dung_chi_dao = fields.Char('Nội dung chỉ đạo')
    thoi_diem_chi_dao = fields.Datetime('Thời điểm chỉ đạo')
    office_document_id = fields.Many2one('office.document')


class OfficeDocumentDetail2(models.Model):
    _name = 'office.document.detail2'

    nguoi_nhap_y_kien = fields.Char('Người nhập ý kiến')
    nhom_phong_ban = fields.Char('Nhóm phòng ban')
    noi_dung_chi_dao = fields.Char('Nội dung')
    thoi_diem_chi_dao = fields.Datetime('Thời điểm')
    office_document_id = fields.Many2one('office.document')


class OfficeDocumentDetail3(models.Model):
    _name = 'office.document.detail3'

    nguoi_nhap_y_kien = fields.Char('Người nhập ý kiến')
    nhom_phong_ban = fields.Char('Nhóm phòng ban')
    noi_dung_chi_dao = fields.Char('Nội dung')
    thoi_diem_chi_dao = fields.Datetime('Thời điểm')
    office_document_id = fields.Many2one('office.document')


class OfficeDocument(models.Model):
    _name = 'office.document'
    _description = 'Quản lý công văn'
    _rec_name = 'trich_yeu'

    document_type = fields.Selection([
        ('incoming', 'Công văn đến'),
        ('outgoing', 'Công văn đi'),
        ('resolution', 'Quyết định')
    ], string='Loại công văn', required=True)
    loai_van_ban = fields.Selection([
        ('1', 'Thông báo'),
        ('2', 'Tờ trình'),
        ('3', 'Quy chế')
    ], string='Phân loại văn bản')
    lanh_dao_xu_ly = fields.Char('Lãnh đạo xử lý')
    lanh_dao_theo_doi = fields.Char('Lãnh đạo theo dõi')
    ngay_den = fields.Date('Ngày đến')
    phan_loai_van_ban = fields.Char('Phân loại văn bản')
    so_den_tong_hop = fields.Char('Số đến tổng hợp')
    so_di_tong_hop = fields.Char('Số công văn')
    so_hieu = fields.Char('Số hiệu')
    ngay_ban_hanh = fields.Date('Ngày ban hành')
    noi_gui = fields.Char('Nơi gửi')
    nguoi_ky = fields.Char('Người ký')
    do_khan = fields.Char('Độ khẩn')
    vb_nhan = fields.Char('Văn bản nhận')
    tt_vb = fields.Char('Trạng thái văn bản')
    dv_xu_ly_chinh = fields.Char('Đơn vị xử lý chính')
    dv_dong_xu_ly = fields.Char('Đơn vị đồng xử lý')
    phoi_hop_xu_ly = fields.Char('Phối hợp xử lý')
    pb_dv_nhan = fields.Char('Phòng ban')
    ca_nhan_dv_nhan = fields.Char('Cá nhân')
    nhom_nguoi_dung_dv_nhan = fields.Char('Nhóm người dùng')
    nguoi_theo_doi = fields.Char('Người theo dõi')
    ngay_bat_dau = fields.Date('Ngày bắt đầu')
    ho_so_cong_viec = fields.Char('Hồ sơ công việc')
    attachment = fields.Binary('Tài liệu')
    note = fields.Text('Ghi chú')
    don_vi_ban_hanh = fields.Char('Đơn vị ban hành')
    don_vi_soan_thao = fields.Char('Đơn vị soạn thảo')
    don_vi_nhan_ben_ngoai = fields.Char('Đơn vị nhận bên ngoài')
    nguoi_theo_doi_chinh = fields.Char('Người theo dõi chính')
    so_den_theo_so = fields.Char('Số đến theo sổ')
    so_di_theo_so = fields.Char('Số đi theo sổ')
    so_vb = fields.Char('Số văn bản')
    ngay_hieu_luc = fields.Date('Ngày hiệu lực')
    ngay_ky = fields.Date('Ngày ký')
    chuc_vu = fields.Char('Chức vụ')
    do_quan_trong = fields.Char('Độ quan trọng')
    nguoi_xu_ly_chinh = fields.Char('Người xử lý chính')
    nguoi_soan_thao = fields.Char('Người soạn thảo')
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
        return True

