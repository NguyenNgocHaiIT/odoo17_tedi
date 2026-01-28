# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import  logging

_logger = logging.getLogger(__name__)


# --- 1. CÁC MODEL CẤU HÌNH (GROUP, CRITERIA) ---
class EvaluationGroup(models.Model):
    _name = 'evaluation.group'
    _description = 'Nhóm đánh giá'
    _rec_name = 'code'

    name = fields.Many2many("hr.job", "group_rel", "group_id", "job_id", string="Chức danh áp dụng")
    code = fields.Char(string="Mã nhóm", required=True)


class EvaluationCriteria(models.Model):
    _name = 'evaluation.criteria'
    _description = 'Tiêu chí đánh giá (Mục lớn)'
    _rec_name = 'name'

    name = fields.Char(string="Tên tiêu chí", required=True)
    code = fields.Char(string="Mã tiêu chí")
    evaluation_group_id = fields.Many2one("evaluation.group", string="Nhóm ĐG")
    line_ids = fields.One2many('evaluation.criteria.line', 'evaluation_criteria_id', string="Chi tiết")


class EvaluationCriteriaLine(models.Model):
    _name = 'evaluation.criteria.line'
    _description = 'Chi tiết tiêu chí (Mục nhỏ)'

    name = fields.Char(string="Tên hạng mục")
    content = fields.Char(string="Mục tiêu nhiệm vụ/công việc")
    percent = fields.Float(string="Tỷ trọng (%)")
    evaluation_criteria_id = fields.Many2one("evaluation.criteria", string="Tiêu chí cha")


# --- HÀM HELPER CHUYỂN SỐ LA MÃ ---
def to_roman(n):
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_num = ''
    i = 0
    while n > 0:
        for _ in range(n // val[i]):
            roman_num += syb[i]
            n -= val[i]
        i += 1
    return roman_num


class EvaluationReport(models.Model):
    _name = "evaluation.report"
    _description = "EvaluationReport"

    name = fields.Char(string="Tên báo cáo", required=True)
    create_date = fields.Date(string="Ngày tạo", default=fields.Date.context_today)
    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban',
        required=True,
        # Lấy phòng ban của nhân viên gắn với user hiện tại
        default=lambda self: self.env.user.employee_id.department_id
    )
    evaluate_kpi = fields.One2many('evaluation.kpi', 'evaluate_kpi_id', string="Danh sách phiếu đánh giá",
                                   readonly=True)

    # 1. Trường Tháng đánh giá (Dùng để tính toán)
    quarter = fields.Selection([
        ('1', 'Quý 1'),
        ('2', 'Quý 2'),
        ('3', 'Quý 3'),
        ('4', 'Quý 4')
    ], string='Chọn Quý', required=True, default='1')

    execution_date = fields.Date(string="Tháng đánh giá")

    year = fields.Integer(
        string='Năm',
        required=True,
        default=lambda self: fields.Date.today().year
    )

    period = fields.Char(string="Chu kỳ", compute="_compute_period", store=True)

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('in_progress', 'Đang đánh giá'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Đã hủy')
    ], string="Trạng thái", default='draft', required=True, tracking=True)

    # --- 2. QUẢN LÝ DANH SÁCH ---
    # Danh sách dự kiến (Hiện khi Nháp)
    report_line_ids = fields.One2many('evaluation.report.line', 'report_id', string="Danh sách nhân viên dự kiến")

    # Danh sách chính thức (Hiện khi Đang đánh giá / Hoàn thành)
    # Lưu ý: readonly=True để không add trực tiếp ở đây mà phải qua quy trình


    @api.depends('quarter', 'year')
    def _compute_period(self):
        for rec in self:
            if rec.quarter and rec.year:
                rec.period = f"Quý {rec.quarter}/ {rec.year}"
            else:
                rec.period = ""

    # 2. Trường Chu kỳ (Tự động tính nhưng cho phép sửa)
    # period = fields.Char(string="Chu kỳ", required=True)

    def action_open_generate_wizard(self):
        self.ensure_one()
        if not self.department_id:
            raise UserError(_("Vui lòng chọn phòng ban trước khi tạo phiếu!"))

        return {
            'name': 'Tạo phiếu đánh giá KPI',
            'type': 'ir.actions.act_window',
            'res_model': 'evaluation.kpi.generate.wizard',
            'view_mode': 'form',
            'target': 'new',  # Mở dạng popup (modal)
            'context': {
                'default_report_id': self.id,
                'default_department_id': self.department_id.id
            }
        }

    def action_start_evaluation(self):
        """Chuyển sang trạng thái Đang đánh giá, sinh phiếu KPI và gửi email thông báo"""
        self.ensure_one()
        if not self.report_line_ids:
            raise UserError(_("Vui lòng chọn danh sách nhân viên trước khi bắt đầu!"))

        KPIModel = self.env['evaluation.kpi']

        # 1. Lấy URL gốc của hệ thống (Ví dụ: https://my-odoo.com)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        for line in self.report_line_ids:
            # Kiểm tra xem phiếu đã tồn tại chưa
            current_kpi = KPIModel.search([
                ('evaluate_kpi_id', '=', self.id),
                ('employee_id', '=', line.employee_id.id)
            ], limit=1)

            if not current_kpi:
                # Tạo phiếu KPI mới nếu chưa có
                current_kpi = KPIModel.create({
                    'name': 'New',
                    'evaluate_kpi_id': self.id,
                    'employee_id': line.employee_id.id,
                    'quarter': self.quarter,
                    'year': self.year,
                    'state': 'draft',
                })
                # Trigger lấy tiêu chí
                current_kpi._onchange_employee_id()

            # --- LOGIC GỬI EMAIL ---
            if current_kpi and line.employee_id.work_email:
                # 2. Tạo đường dẫn trực tiếp đến phiếu KPI này
                # Format: /web#id={ID}&model={MODEL}&view_type=form
                action_url = f"{base_url}/web#id={current_kpi.id}&model=evaluation.kpi&view_type=form"

                # 3. Soạn nội dung Email (HTML)
                subject = f"THÔNG BÁO ĐÁNH GIÁ KPI - {self.period}"
                body_html = f"""
                <div style="font-family: Arial, sans-serif; font-size: 14px;">
                    <p>Chào <b>{line.employee_id.name}</b>,</p>
                    <p>Kỳ đánh giá <b>{self.period}</b> đã chính thức bắt đầu.</p>
                    <p>Hệ thống đã tạo phiếu đánh giá KPI cho bạn. Vui lòng truy cập đường dẫn bên dưới để thực hiện phần tự đánh giá:</p>

                    <div style="margin: 20px 0;">
                        <a href="{action_url}" 
                           style="background-color: #875A7B; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                           TRUY CẬP PHIẾU ĐÁNH GIÁ
                        </a>
                    </div>

                    <p>Vui lòng hoàn thành trước thời hạn quy định.</p>
                    <p>Trân trọng,<br/>Phòng Nhân Sự</p>
                </div>
                """

                # 4. Tạo và gửi Email
                mail_values = {
                    'subject': subject,
                    'email_from': self.env.user.company_id.email or self.env.user.email_formatted,
                    'email_to': line.employee_id.work_email,
                    'body_html': body_html,
                    'state': 'outgoing',  # outgoing: chờ cron gửi, sent: đã gửi (nếu dùng hàm send)
                }
                # Tạo record mail và gửi ngay lập tức
                mail = self.env['mail.mail'].create(mail_values)
                mail.send()  # Gửi ngay lập tức (có thể bỏ dòng này nếu muốn để Cron job tự quét gửi sau)

        self.write({'state': 'in_progress'})

    def action_done_evaluation(self):
        """Kết thúc đợt đánh giá"""
        self.ensure_one()
        # Có thể thêm logic kiểm tra xem tất cả KPI con đã xong chưa
        # un-comment nếu muốn bắt buộc xong hết mới được close
        # if any(kpi.state != 'done' for kpi in self.evaluate_kpi):
        #     raise UserError(_("Tất cả phiếu đánh giá phải hoàn thành trước khi đóng báo cáo!"))

        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        """Quay về nháp - Cẩn thận: Có thể cần xóa KPI cũ hoặc giữ lại tùy nghiệp vụ"""
        self.ensure_one()
        if self.evaluate_kpi:
            raise UserError(_("Đã có phiếu đánh giá được tạo. Không thể quay về nháp. Hãy Hủy thay thế."))
        self.write({'state': 'draft'})

    def action_generate_kpis(self):
        """
        Hàm tạo tự động phiếu KPI cho tất cả nhân viên trong phòng ban được chọn
        """
        self.ensure_one()
        if not self.department_id:
            raise UserError(_("Vui lòng chọn phòng ban trước khi tạo phiếu!"))

        employees = self.env['hr.employee'].sudo().search([
            ('department_id', '=', self.department_id.id),
            ('active', '=', True)
        ])

        if not employees:
            raise UserError(_("Không tìm thấy nhân viên nào trong phòng ban này."))

        KPIModel = self.env['evaluation.kpi']
        count = 0

        for emp in employees:
            # 2. Kiểm tra trùng dựa trên QUÝ và NĂM
            existing_kpi = KPIModel.search([
                ('evaluate_kpi_id', '=', self.id),
                ('employee_id', '=', emp.id),
                ('quarter', '=', self.quarter), # Check trùng quý
                ('year', '=', self.year)        # Check trùng năm
            ], limit=1)

            if existing_kpi:
                continue

            # 3. Tạo phiếu KPI (Truyền Quarter và Year xuống)
            new_kpi = KPIModel.sudo().create({
                'name': 'New',
                'evaluate_kpi_id': self.id,
                'employee_id': emp.id,
                'quarter': self.quarter,  # <--- Mới
                'year': self.year,        # <--- Mới
                'state': 'draft',
            })

            new_kpi.sudo()._onchange_employee_id()
            count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'effect': {
                'fadeout': 'slow',
                'message': _(f'Đã tạo thành công {count} phiếu đánh giá cho {self.period}!'),
                'type': 'rainbow_man',
            }
        }

class EvaluationReportLine(models.Model):
    _name = 'evaluation.report.line'
    _description = 'Chi tiết dòng báo cáo (Dự kiến)'
    _rec_name = 'employee_id'

    report_id = fields.Many2one('evaluation.report', string="Báo cáo", ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string="Nhân viên", required=True)
    job_id = fields.Many2one('hr.job', related='employee_id.job_id', string="Chức danh", readonly=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', string="Phòng ban", readonly=True)


# --- 2. MODEL PHIẾU ĐÁNH GIÁ (MAIN) ---
class EvaluationKPI(models.Model):
    _name = 'evaluation.kpi'
    _description = 'Phiếu đánh giá KPI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'create_date desc'

    # --- 8. MÃ PHIẾU (Autocode) ---
    name = fields.Char(string="Phiếu", default="New", readonly=True, copy=False)

    # --- 6, 9, 10, 11. THÔNG TIN NHÂN VIÊN ---
    employee_id = fields.Many2one('hr.employee', string="Người lao động", required=True,
                                  )
    job_id = fields.Many2one('hr.job', string="Chức danh", related='employee_id.job_id', store=True, readonly=True)
    department_id = fields.Many2one('hr.department', string="Đơn vị", related='employee_id.department_id', store=True,
                                    readonly=True)

    evaluate_kpi_id = fields.Many2one('evaluation.report', string="Thuộc báo cáo")

    report_state = fields.Selection(related='evaluate_kpi_id.state', string="Trạng thái báo cáo", store=False)

    @api.constrains('self_score', 'manager_score', 'line_ids')
    def _check_report_state_on_write(self):
        for rec in self:
            # Nếu có báo cáo cha, và báo cáo cha KHÔNG PHẢI là in_progress
            # Thì không cho sửa đổi dữ liệu quan trọng
            if rec.evaluate_kpi_id and rec.evaluate_kpi_id.state != 'in_progress':
                # Bỏ qua nếu là admin hoặc logic hệ thống (tùy nhu cầu)
                # Ở đây chặn chung:
                pass
                # Lưu ý: Khi code hàm action_start_evaluation gọi create(), state report vẫn đang là draft
                # nên cần cẩn thận. Tốt nhất dùng readonly ở XML View là đủ cho UX.
                # Nếu muốn chặn chặt chẽ (Server side), cần logic phức tạp hơn chút để bypass lúc tạo.

    # Giả sử wage_level lấy từ job_title hoặc contract (tùy thực tế database của bạn)
    wage_level = fields.Char(string="Nhóm, bậc lương", compute="_compute_wage_level", store=True)

    # 2. Hàm mở Form view của chính record này
    def action_open_kpi_detail(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Chi tiết phiếu đánh giá',
            'res_model': 'evaluation.kpi',
            'res_id': self.id,  # Mở đúng ID của dòng hiện tại
            'view_mode': 'form',
            'target': 'current',  # 'current' để nhảy trang, 'new' để mở popup
        }

    @api.depends('employee_id')
    def _compute_wage_level(self):
        for rec in self:
            if not rec.employee_id:
                rec.wage_level = False
                continue

            # Tìm hợp đồng đang chạy (state='open') của nhân viên này
            # Lưu ý: Cần đảm bảo quyền truy cập contract hoặc dùng sudo() nếu user thường không thấy hợp đồng
            contract = self.env['hr.contract'].sudo().search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'open')  # Chỉ lấy hợp đồng Đang chạy
            ], limit=1)

            if contract and contract.salary_grade_id:
                # Lấy tên của bậc lương (ví dụ: Chuyên viên bậc 3...)
                rec.wage_level = contract.salary_grade_id.name
            else:
                rec.wage_level = "Chưa có bậc lương/HĐ"

    quarter = fields.Selection([
        ('1', 'Quý 1'),
        ('2', 'Quý 2'),
        ('3', 'Quý 3'),
        ('4', 'Quý 4')
    ], string='Quý', required=True, default=lambda self: self._get_default_quarter())

    year = fields.Integer(
        string='Năm',
        required=True,
        default=lambda self: fields.Date.today().year
    )

    # Trường period (Computed) để hiển thị trên view tree/form cũ mà không bị lỗi
    period = fields.Char(string="Chu kỳ", compute="_compute_period_display", store=True)

    @api.model
    def _get_default_quarter(self):
        """Lấy quý hiện tại mặc định"""
        month = fields.Date.today().month
        return str((month - 1) // 3 + 1)

    @api.depends('quarter', 'year')
    def _compute_period_display(self):
        for rec in self:
            if rec.quarter and rec.year:
                rec.period = f"Quý {rec.quarter}/ {rec.year}"
            else:
                rec.period = "N/A"

    # --- CẤU HÌNH QUY TRÌNH (Lấy từ Employee) ---

    is_manager_review_required = fields.Boolean(
        string="Cần QLTT duyệt",
        related='job_id.kpi_manager_review',  # <--- Đổi từ employee_id sang job_id
        store=True,
        readonly=True
    )

    is_council_review_required = fields.Boolean(
        string="Cần TĐV duyệt",
        related='job_id.kpi_council_review',  # <--- Đổi từ employee_id sang job_id
        store=True,
        readonly=True
    )

    is_director_review_required = fields.Boolean(
        string="Cần TGĐ duyệt",
        related='job_id.kpi_director_review',  # <--- Đổi từ employee_id sang job_id
        store=True,
        readonly=True
    )

    total_score = fields.Float(string="Tổng điểm (1-5)", compute="_compute_results", store=True, digits=(16, 2),
                               tracking=True)
    # Trường này chỉ dùng để hiển thị widget progressbar (Quy đổi ra thang 100)
    total_score_percent = fields.Float(string="Tiến độ hoàn thành", compute="_compute_results", store=True)

    # --- TRẠNG THÁI ---
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('wait_manager', 'Chờ QLTT đánh giá'),
        ('wait_council', 'Chờ TĐV đánh giá'),
        ('wait_director', 'Chờ TGĐ đánh giá'),
        ('done', 'Hoàn thành')
    ], string="Trạng thái", default='draft', tracking=True, copy=False)

    line_ids = fields.One2many('evaluation.kpi.line', 'kpi_id', string="Chi tiết đánh giá")

    # --- 18, 19, 20. KẾT QUẢ ---
    is_result_computed = fields.Boolean(string="Đã tính kết quả", default=False, copy=False)

    k_coefficient = fields.Float(string="Hệ số K", compute="_compute_results", store=True, digits=(16, 2),
                                 tracking=True)
    final_result = fields.Char(string="Kết quả thực hiện", compute="_compute_results", store=True, tracking=True)

    is_department_manager = fields.Boolean(compute='_compute_is_department_manager')
    is_direct_manager = fields.Boolean(compute='_compute_is_direct_manager')
    is_director_manager = fields.Boolean(compute='_compute_is_director_manager')

    @api.depends('department_id')
    def _compute_is_department_manager(self):
        current_user = self.env.user

        # --- LOG 1: Kiểm tra User hiện tại ---
        # _logger.info("=" * 30)
        # _logger.info(
        #     f"DEBUG KPI: Bắt đầu tính quyền Trưởng Đơn Vị cho User: {current_user.name} (ID: {current_user.id})")

        # 1. Kiểm tra nhóm quyền
        is_in_group = current_user.has_group('om_hr_payroll.group_kpi_dept_manager_new')
        # _logger.info(f"DEBUG KPI: User có nhóm 'Trưởng đơn vị' (group_kpi_dept_manager_new)? -> {is_in_group}")

        # 2. Kiểm tra phòng ban của User
        current_user_dept = current_user.employee_id.department_id
        # _logger.info(f"DEBUG KPI: Phòng ban của User: {current_user_dept.name if current_user_dept else 'Không có'}")

        is_admin = current_user.has_group('base.group_system')
        # _logger.info(f"DEBUG KPI: User là Admin? -> {is_admin}")

        for rec in self:
            # _logger.info(f"--- Đang check Phiếu: {rec.name} (ID: {rec.id}) ---")

            # Admin luôn đúng
            if is_admin:
                # _logger.info("DEBUG KPI: -> TRUE (Do là Admin)")
                rec.is_department_manager = True
                continue

            # Kiểm tra phòng ban phiếu
            rec_dept = rec.department_id
            # _logger.info(f"DEBUG KPI: Phòng ban của Phiếu: {rec_dept.name if rec_dept else 'Không có'}")

            # LOGIC SO SÁNH
            if is_in_group and current_user_dept and rec_dept:
                if current_user_dept.id == rec_dept.id:
                    # _logger.info("DEBUG KPI: -> TRUE (Cùng phòng ban + Có quyền)")
                    rec.is_department_manager = True
                else:
                    # _logger.info(
                    #     f"DEBUG KPI: -> FALSE (Khác phòng ban: User Dept {current_user_dept.id} != KPI Dept {rec_dept.id})")
                    rec.is_department_manager = False
            else:
                # _logger.info("DEBUG KPI: -> FALSE (Thiếu điều kiện: Không có nhóm, hoặc User/Phiếu không có phòng ban)")
                rec.is_department_manager = False

            # _logger.info("=" * 30)

    @api.depends('employee_id')
    def _compute_is_direct_manager(self):
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system')

        for rec in self:
            if is_admin:
                rec.is_direct_manager = True
                continue

            is_manager = False
            if rec.employee_id.parent_id and rec.employee_id.parent_id.user_id == current_user:
                is_manager = True

            rec.is_direct_manager = is_manager

    def _compute_is_director_manager(self):
        current_user = self.env.user
        # Lấy ID của nhóm quyền TGĐ (bạn thay ID thực tế nếu khác)
        # Dựa trên XML bạn gửi thì ID là: om_hr_payroll.group_kpi_director_new
        is_director = current_user.has_group('om_hr_payroll.group_kpi_director_new')
        is_admin = current_user.has_group('base.group_system')

        for rec in self:
            # Nếu là Admin hoặc thuộc nhóm TGĐ -> True
            if is_admin or is_director:
                rec.is_director_manager = True
            else:
                rec.is_director_manager = False

    @api.depends('line_ids.final_score', 'line_ids.weight', 'line_ids.display_type')
    def _compute_results(self):
        for rec in self:
            weighted_score_sum = 0.0
            total_weight = 0.0

            for line in rec.line_ids:
                # Chỉ tính các dòng là tiêu chí (không phải Section hay Note)
                if not line.display_type:
                    # x: Tổng (Điểm * Tỷ trọng)
                    weighted_score_sum += (line.final_score * line.weight)
                    total_weight += line.weight

            # Tính x (total_score):
            # Giả sử x được tính là điểm trung bình có trọng số:
            x = (weighted_score_sum / total_weight) if total_weight > 0 else 0.0

            # Làm tròn điểm tổng (tùy chọn, ở đây làm tròn 2 số lẻ)
            rec.total_score = round(x, 2)

            # Gán % hiển thị
            rec.total_score_percent = (rec.total_score / 5.0) * 100

            # -----------------------------------------------------------
            # TÌM XẾP LOẠI VÀ TÍNH HỆ SỐ K (NỘI SUY)
            # -----------------------------------------------------------
            rule = self.env['evaluation.kpi.classification'].search([
                ('min_score', '<=', rec.total_score),
                ('max_score', '>=', rec.total_score)
            ], limit=1, order='min_score desc')

            if rule:
                rec.final_result = rule.classification

                # Các biến theo công thức của bạn
                k_min = rule.k_coefficient_min
                k_max = rule.k_coefficient_max
                s_min = rule.min_score
                s_max = rule.max_score

                # Kiểm tra tránh lỗi chia cho 0 (nếu min_score == max_score)
                if s_max - s_min == 0:
                    rec.k_coefficient = k_max
                else:
                    # y = (k_max - k_min) / (max_score - min_score)
                    y = (k_max - k_min) / (s_max - s_min)

                    # k = k_min + (x - min_score) * y
                    rec.k_coefficient = k_min + (rec.total_score - s_min) * y
            else:
                rec.k_coefficient = 0.0
                rec.final_result = "Chưa xếp loại"

    # --- HÀM HELPER LẤY CHU KỲ ---
    def _get_default_period(self):
        today = fields.Date.today()
        month = today.month
        quarter = (month - 1) // 3 + 1
        return f"Quý {quarter}/{today.year}"

    # --- SINH MÃ TỰ ĐỘNG ---
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            # 1. Lấy thông tin sequence (chỉ lấy số, ví dụ: 00001)
            seq_number = self.env['ir.sequence'].next_by_code('evaluation.kpi') or '00000'

            # 2. Xử lý Tên nhân viên (Viết hoa, bỏ khoảng trắng)
            # Ví dụ: "Nguyễn Văn A" -> "NGUYENVANA"
            emp_code = "UNK"
            if vals.get('employee_id'):
                employee = self.env['hr.employee'].browse(vals.get('employee_id'))
                if employee.name:
                    # Bỏ khoảng trắng thừa và nối lại
                    clean_name = "".join(employee.name.split())
                    emp_code = clean_name.upper()

            # 3. Lấy Năm và Quý
            # Nếu trong vals không có (do default), ta lấy thời gian hiện tại làm fallback
            current_year = vals.get('year') or fields.Date.today().year
            current_quarter = vals.get('quarter') or self._get_default_quarter()

            # 4. Ghép chuỗi: TEN/NAM/QUY/SO
            # Kết quả: NGUYENVANA/2024/Q1/00001
            vals['name'] = f"{emp_code}/{current_year}/Q{current_quarter}/{seq_number}"

        res = super(EvaluationKPI, self).create(vals)

        # Trigger tạo các dòng chi tiết KPI nếu chưa có (logic cũ của bạn)
        # Lưu ý: Logic _onchange_employee_id thường không tự chạy khi gọi create từ code
        # nên ta cần gọi thủ công hoặc đảm bảo vals['line_ids'] đã có dữ liệu.
        if not res.line_ids:
            res._onchange_employee_id()

        return res

    def _finish_and_display_result(self):
        """
        Hàm này được gọi khi người đánh giá cuối cùng xác nhận.
        Tác dụng: Chuyển sang Done và Bắt buộc hiện kết quả.
        """
        # Trigger tính toán lại lần cuối để đảm bảo điểm số chính xác
        self._compute_results()

        self.write({
            'state': 'done',
            'is_result_computed': True  # <--- Tự động hiện kết quả
        })


    # --- DATA FETCHING ---
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if not self.employee_id or not self.employee_id.job_id: return

        # Xóa dòng cũ nếu có
        self.line_ids = [(5, 0, 0)]

        groups = self.env['evaluation.group'].search([('name', 'in', self.employee_id.job_id.id)])
        if not groups: return

        new_lines = []
        criterias = self.env['evaluation.criteria'].search([('evaluation_group_id', 'in', groups.ids)])
        section_idx = 1

        for criteria in criterias:
            # Dòng Section
            new_lines.append((0, 0, {
                'display_type': 'line_section',
                'stt': to_roman(section_idx),
                'name': criteria.name,
                'weight': 0.0,  # Section không có trọng số
                'sequence': section_idx * 100,
            }))
            line_idx = 1
            # Dòng Chi tiết
            for line in criteria.line_ids:
                new_lines.append((0, 0, {
                    'display_type': False,
                    'stt': str(line_idx),
                    'name': line.content,
                    'weight': line.percent,  # Lấy giá trị percent gán thẳng vào weight
                    'sequence': section_idx * 100 + line_idx,
                }))
                line_idx += 1
            section_idx += 1

        self.line_ids = new_lines

    # --- TÍNH TOÁN KẾT QUẢ TỰ ĐỘNG ---
    total_score

    # --- WORKFLOW & NÚT BẤM ---
    def action_send(self):
        self.ensure_one()
        # Logic nhảy bước
        if self.is_manager_review_required:
            self.write({'state': 'wait_manager'})
        elif self.is_council_review_required:
            self.write({'state': 'wait_council'})
        elif self.is_director_review_required:
            self.write({'state': 'wait_director'})
        else:
            # Trường hợp đặc biệt: Không ai đánh giá ngoài nhân viên -> Done luôn
            # Nhân viên là người cuối cùng
            self._finish_and_display_result()

    def action_manager_evaluation(self):
        """QLTT đánh giá xong"""
        self.ensure_one()
        if self.is_council_review_required:
            # Vẫn còn bước TĐV -> Chỉ chuyển trạng thái, chưa hiện kết quả tự động
            self.write({'state': 'wait_council'})
        elif self.is_director_review_required:
            # Vẫn còn bước TGĐ -> Chỉ chuyển trạng thái
            self.write({'state': 'wait_director'})
        else:
            # Không còn ai sau QLTT -> QLTT là người cuối cùng -> Done & Hiện kết quả
            self._finish_and_display_result()

    def action_council_evaluation(self):
        """TĐV đánh giá xong"""
        self.ensure_one()
        if self.is_director_review_required:
            # Vẫn còn bước TGĐ -> Chỉ chuyển trạng thái
            self.write({'state': 'wait_director'})
        else:
            # Không còn ai sau TĐV -> TĐV là người cuối cùng -> Done & Hiện kết quả
            self._finish_and_display_result()

    def action_director_evaluation(self):
        """TGĐ đánh giá xong"""
        self.ensure_one()
        # TGĐ luôn là cấp cao nhất trong luồng này -> Done & Hiện kết quả
        self._finish_and_display_result()


    def action_compute_result_manual(self):
        """Nút tính toán thủ công để reload view và HIỆN KẾT QUẢ"""
        # 1. Tính toán lại số liệu (gọi hàm compute để đảm bảo số mới nhất)
        self._compute_results()

        # 2. Bật cờ hiển thị group kết quả
        self.write({'is_result_computed': True})

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_reset_draft(self):
        self.write({'state': 'draft', 'is_result_computed': False})

    # --- HỆ THỐNG TỰ ĐỘNG (CRON) ---
    @api.model
    def cron_generate_kpi_slips(self):
        """Tự động sinh phiếu và gửi email"""
        employees = self.env['hr.employee'].search([('active', '=', True)])
        current_period = self._get_default_period()

        for emp in employees:
            # Check trùng
            exist = self.search_count([('employee_id', '=', emp.id), ('period', '=', current_period)])
            if exist > 0: continue

            # Tạo phiếu
            kpi = self.create({
                'employee_id': emp.id,
                'period': current_period,
            })
            kpi._onchange_employee_id()  # Điền tiêu chí

            # Gửi email (Giả sử có template)
            # template = self.env.ref('om_hr_payroll.email_template_kpi_notify_employee', raise_if_not_found=False)
            # if template:
            #     template.send_mail(kpi.id, force_send=True)


# --- 3. MODEL CHI TIẾT DÒNG ---
class EvaluationKPILine(models.Model):
    _name = 'evaluation.kpi.line'
    _description = 'Chi tiết phiếu KPI'

    kpi_id = fields.Many2one('evaluation.kpi', string="Phiếu KPI", ondelete='cascade')

    report_state = fields.Selection(related='kpi_id.evaluate_kpi_id.state', string="Trạng thái báo cáo", store=False)

    display_type = fields.Selection([('line_section', "Section"), ('line_note', "Note")], default=False)
    sequence = fields.Integer(string="Sequence", default=10)

    stt = fields.Char(string="STT", readonly=True)  # Số La Mã / Thường
    name = fields.Char(string="Mục tiêu nhiệm vụ/ công việc", required=True)
    weight = fields.Float(string="Tỷ trọng (%)", digits=(16, 1), default=0.0)

    # Các cột điểm (14, 15, 16, 17)
    self_score = fields.Float(string="CBNV tự ĐG (1-5)", digits=(16, 1))
    manager_score = fields.Float(string="QLTT ĐG (1-5)", digits=(16, 1))
    council_score = fields.Float(string="TĐV ĐG (1-5)", digits=(16, 1))
    director_score = fields.Float(string="TGĐ ĐG (1-5)", digits=(16, 1))

    # Điểm chốt để tính toán (Lấy cấp cao nhất)
    final_score = fields.Float(string="Điểm chốt", compute="_compute_final_score", store=True)

    @api.depends('self_score', 'manager_score', 'council_score', 'director_score',
                 'kpi_id.is_manager_review_required',
                 'kpi_id.is_council_review_required',
                 'kpi_id.is_director_review_required')
    def _compute_final_score(self):
        for line in self:
            # 1. Mặc định khởi đầu bằng điểm Nhân viên tự đánh giá
            # (Nếu nhân viên chưa đánh giá thì = 0)
            current_score = line.self_score

            # 2. Kiểm tra cấp Quản lý trực tiếp (Manager)
            # Điều kiện: Phải CÓ cấu hình yêu cầu Manager VÀ Manager ĐÃ nhập điểm (> 0)
            if line.kpi_id.is_manager_review_required and line.manager_score > 0:
                current_score = line.manager_score

            # 3. Kiểm tra cấp Trưởng đơn vị/Hội đồng (Council)
            # Logic: Nếu ông này đã chấm, lấy điểm ông này đè lên điểm ông Manager
            if line.kpi_id.is_council_review_required and line.council_score > 0:
                current_score = line.council_score

            # 4. Kiểm tra cấp Giám đốc (Director)
            # Logic: Đây là cấp cao nhất, nếu đã chấm thì lấy điểm này là chốt
            if line.kpi_id.is_director_review_required and line.director_score > 0:
                current_score = line.director_score

            # Gán kết quả cuối cùng
            line.final_score = current_score

    _sql_constraints = [
        ('check_self_score', 'CHECK(self_score >= 0 AND self_score <= 5)', 'Điểm tự đánh giá phải từ 0 đến 5!'),
        ('check_manager_score', 'CHECK(manager_score >= 0 AND manager_score <= 5)',
         'Điểm quản lý đánh giá phải từ 0 đến 5!'),
        ('check_council_score', 'CHECK(council_score >= 0 AND council_score <= 5)',
         'Điểm TĐV đánh giá phải từ 0 đến 5!'),
        ('check_director_score', 'CHECK(director_score >= 0 AND director_score <= 5)',
         'Điểm TGĐ đánh giá phải từ 0 đến 5!'),
    ]




class EvaluationKPIClassification(models.Model):
    _name = 'evaluation.kpi.classification'
    _description = 'Xếp loại kết quả thực hiện KPI'
    _order = 'min_score asc'
    _rec_name = 'classification'

    name = fields.Char(string="Mô tả ngắn", compute="_compute_name")

    # Range of Score (e.g., 4.5 <= Score <= 5)
    min_score = fields.Float(string="Điểm từ", required=True, digits=(16, 2))
    max_score = fields.Float(string="Điểm đến", required=True, digits=(16, 2))

    # Resulting Values
    k_coefficient_min = fields.Float(string="Hệ số K (Min)", digits=(16, 2))
    k_coefficient_max = fields.Float(string="Hệ số K (Max)", digits=(16, 2))

    # Or just a single K if fixed
    k_coefficient = fields.Float(string="Hệ số K chuẩn", digits=(16, 2), help="Giá trị K mặc định trả về")

    classification = fields.Char(string="Xếp loại", required=True, translate=True)
    description = fields.Text(string="Mô tả chi tiết")

    @api.depends('min_score', 'max_score', 'classification')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.min_score} - {rec.max_score}: {rec.classification}"