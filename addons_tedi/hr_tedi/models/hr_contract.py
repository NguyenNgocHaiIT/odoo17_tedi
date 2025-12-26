from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

class HrContract(models.Model):
    _inherit = 'hr.contract'

    # 1. Phân loại lớn
    contract_category = fields.Selection([
        ('probation', 'Hợp đồng Thử việc'),
        ('official', 'Hợp đồng Chính thức')
    ], string='Phân loại hợp đồng', default='official', required=True)

    # 2. Phân loại con (Chính thức)
    official_contract_type = fields.Selection([
        ('fixed_term', 'Có thời hạn'),
        ('indefinite_term', 'Vô thời hạn')
    ], string='Hình thức (Chính thức)')

    # --- SỬA: Dùng Integer để nhập số tháng ---
    duration_months = fields.Integer(string="Thời hạn (Tháng)", help="Nhập số tháng của hợp đồng")

    # --- LOGIC TÍNH NGÀY KẾT THÚC ---
    @api.onchange('date_start', 'duration_months', 'official_contract_type')
    def _onchange_calculate_end_date(self):
        # 1. Nếu là vô thời hạn -> Xóa ngày kết thúc và số tháng
        if self.official_contract_type == 'indefinite_term':
            self.date_end = False
            self.duration_months = 0
            return

        # 2. Nếu là Có thời hạn + Có ngày bắt đầu + Có nhập số tháng > 0
        if self.official_contract_type == 'fixed_term' and self.date_start and self.duration_months > 0:
            # Công thức: Ngày bắt đầu + Số tháng - 1 ngày
            self.date_end = self.date_start + relativedelta(months=self.duration_months) - relativedelta(days=1)

    # Logic cũ: Reset khi đổi loại hợp đồng lớn (Thử việc/Chính thức)
    @api.onchange('contract_category')
    def _onchange_contract_category(self):
        if self.contract_category == 'probation':
            self.official_contract_type = False
            self.duration_months = 0 # Reset tháng