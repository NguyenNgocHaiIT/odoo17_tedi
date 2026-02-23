# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta


# --- PHẦN 1: TÙY CHỈNH KẾ HOẠCH TÍCH LŨY (ACCRUAL PLAN) ---
class HrLeaveAccrualPlan(models.Model):
    _inherit = 'hr.leave.accrual.plan'

    is_default = fields.Boolean(string="Mặc định cho Hợp đồng", default=False,
                                help="Nếu chọn, kế hoạch này sẽ tự động được áp dụng khi Hợp đồng bắt đầu.")

    @api.constrains('is_default')
    def _check_single_default(self):
        """Đảm bảo chỉ có một kế hoạch được chọn là mặc định"""
        for plan in self:
            if plan.is_default:
                # Tìm các plan khác cũng là default
                domain = [('id', '!=', plan.id), ('is_default', '=', True)]
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        _("Chỉ được phép có một Kế hoạch tích lũy mặc định! Vui lòng bỏ chọn ở kế hoạch khác trước."))


# --- PHẦN 2: TÙY CHỈNH HỢP ĐỒNG (CONTRACT) ---
class HrContract(models.Model):
    _inherit = 'hr.contract'

    # --- CODE CŨ CỦA BẠN (GIỮ NGUYÊN) ---
    contract_category = fields.Selection([
        ('probation', 'Hợp đồng Thử việc'),
        ('official', 'Hợp đồng Chính thức')
    ], string='Phân loại hợp đồng', default='official', required=True)

    official_contract_type = fields.Selection([
        ('fixed_term', 'Có thời hạn'),
        ('indefinite_term', 'Vô thời hạn')
    ], string='Hình thức (Chính thức)')

    duration_months = fields.Integer(string="Thời hạn (Tháng)", help="Nhập số tháng của hợp đồng")

    @api.onchange('date_start', 'duration_months', 'official_contract_type')
    def _onchange_calculate_end_date(self):
        if self.official_contract_type == 'indefinite_term':
            self.date_end = False
            self.duration_months = 0
            return
        if self.official_contract_type == 'fixed_term' and self.date_start and self.duration_months > 0:
            self.date_end = self.date_start + relativedelta(months=self.duration_months) - relativedelta(days=1)

    @api.onchange('contract_category')
    def _onchange_contract_category(self):
        if self.contract_category == 'probation':
            self.official_contract_type = False
            self.duration_months = 0

    # --- CODE MỚI: NÚT BẮT ĐẦU VÀ TẠO PHÂN BỔ ---

    def action_start_contract_running(self):
        """Nút Bắt đầu: Chuyển trạng thái sang Running và tạo phân bổ"""
        self.ensure_one()

        # 1. Chuyển trạng thái hợp đồng sang Đang chạy (open)
        self.write({'state': 'open'})

        # 2. Tự động tạo phân bổ ngày nghỉ (Accrual Allocation)
        self._create_auto_leave_allocation()

        return True

    def _create_auto_leave_allocation(self):
        """Hàm logic tạo đơn phân bổ tích lũy"""
        self.ensure_one()

        # Tìm kế hoạch tích lũy mặc định
        default_plan = self.env['hr.leave.accrual.plan'].sudo().search([('is_default', '=', True)], limit=1)

        if not default_plan:
            # Nếu không cấu hình default thì thôi, không báo lỗi để tránh chặn luồng, hoặc có thể raise UserError nếu bắt buộc
            return

            # Tìm Loại nghỉ (Time Off Type) phù hợp để gắn phân bổ
        # Lưu ý: Cần tìm loại nghỉ cho phép dùng Accrual Plan (requires_allocation='yes')
        # Ở đây mình lấy loại nghỉ có tên 'Paid Time Off' hoặc loại đầu tiên tìm thấy.
        # Tốt nhất bạn nên tạo 1 field setting để chọn Loại nghỉ mặc định, nhưng ở đây mình sẽ search.
        leave_type = self.env['hr.leave.type'].sudo().search([
            ('active', '=', True),
            ('requires_allocation', '=', 'yes')  # Loại nghỉ yêu cầu phân bổ
        ], limit=1)

        if not leave_type:
            raise UserError(_("Không tìm thấy Loại nghỉ (Time Off Type) nào yêu cầu phân bổ để tạo tự động."))

        # Kiểm tra xem nhân viên đã có phân bổ nào chạy cùng Plan và cùng thời gian chưa để tránh trùng lặp
        existing_allocation = self.env['hr.leave.allocation'].sudo().search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['confirm', 'validate']),
            ('accrual_plan_id', '=', default_plan.id),
            ('date_from', '=', self.date_start)
        ], limit=1)

        if existing_allocation:
            return  # Đã có rồi thì không tạo nữa

        # Tạo đơn phân bổ
        allocation_vals = {
            'name': _('Phân bổ tự động từ Hợp đồng: %s') % self.name,
            'employee_id': self.employee_id.id,
            'holiday_status_id': leave_type.id,
            'allocation_type': 'accrual',  # Loại: Tích lũy
            'accrual_plan_id': default_plan.id,  # Plan mặc định
            'date_from': self.date_start,  # Ngày bắt đầu tính từ ngày bắt đầu HĐ
            'number_of_days': 0,  # Số ngày ban đầu = 0, sẽ tự cộng theo cron
            'state': 'confirm',  # Tạo ở trạng thái Confirm
        }

        allocation = self.env['hr.leave.allocation'].create(allocation_vals)

        # Tự động duyệt đơn phân bổ luôn (nếu muốn)
        allocation.action_validate()