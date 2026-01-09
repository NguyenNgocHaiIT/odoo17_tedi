from odoo import api, fields, models

class HrJob(models.Model):
    _inherit = 'hr.job'

    # Chuyển các field cấu hình sang đây
    kpi_manager_review = fields.Boolean(string="Yêu cầu QLTT đánh giá?", default=True,
                                        help="Nếu tích, quy trình sẽ có bước Quản lý trực tiếp đánh giá")
    kpi_council_review = fields.Boolean(string="Yêu cầu TĐV đánh giá?", default=True,
                                        help="Nếu tích, quy trình sẽ có bước Trưởng đơn vị đánh giá")
    kpi_director_review = fields.Boolean(string="Yêu cầu TGĐ đánh giá?", default=True,
                                         help="Nếu tích, quy trình sẽ có bước Tổng Giám Đốc đánh giá")