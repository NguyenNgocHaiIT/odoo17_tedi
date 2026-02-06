# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import  logging
from datetime import date
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
    _description = "Báo cáo tổng hợp KPI"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Tên báo cáo", required=True, tracking=True)
    create_date = fields.Date(string="Ngày tạo", default=fields.Date.context_today)

    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban',
        required=True,
        default=lambda self: self.env.user.employee_id.department_id
    )

    quarter = fields.Selection([
        ('1', 'Quý 1'), ('2', 'Quý 2'), ('3', 'Quý 3'), ('4', 'Quý 4')
    ], string='Chọn Quý', required=True, default='1')

    year = fields.Integer(
        string='Năm',
        required=True,
        default=lambda self: fields.Date.today().year
    )

    period = fields.Char(string="Chu kỳ", compute="_compute_period", store=True)

    # --- BỎ TRẠNG THÁI IN_PROGRESS ---
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('to_approve', 'Chờ duyệt'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Đã hủy')
    ], string="Trạng thái", default='draft', required=True, tracking=True)

    evaluate_kpi_ids = fields.One2many(
        'evaluation.kpi',
        'evaluate_kpi_id',
        string="Danh sách phiếu đánh giá"
    )

    @api.depends('quarter', 'year')
    def _compute_period(self):
        for rec in self:
            rec.period = f"Quý {rec.quarter}/ {rec.year}" if rec.quarter and rec.year else ""

    # --- TỰ ĐỘNG GÁN PHIẾU KHI TẠO/LƯU ---
    @api.model
    def create(self, vals):
        res = super(EvaluationReport, self).create(vals)
        # Tự động quét phiếu ngay khi tạo
        res._assign_related_kpis()
        return res

    def write(self, vals):
        res = super(EvaluationReport, self).write(vals)
        # Nếu sửa thông tin lọc thì quét lại phiếu
        if any(f in vals for f in ['department_id', 'quarter', 'year']):
            self._assign_related_kpis()
        return res

    def _assign_related_kpis(self):
        """Hàm quét phiếu KPI và gán vào báo cáo"""
        for rec in self:
            kpis = self.env['evaluation.kpi'].search([
                ('department_id', '=', rec.department_id.id),
                ('quarter', '=', rec.quarter),
                ('year', '=', rec.year),
                ('evaluate_kpi_id', 'in', [False, rec.id])
            ])
            if kpis:
                # Cập nhật danh sách phiếu (ghi đè)
                rec.evaluate_kpi_ids = [(6, 0, kpis.ids)]

    @api.onchange('department_id', 'quarter', 'year')
    def _onchange_fetch_kpis(self):
        """Hiển thị trước danh sách phiếu trên giao diện khi đang chọn"""
        if self.department_id and self.quarter and self.year:
            kpis = self.env['evaluation.kpi'].search([
                ('department_id', '=', self.department_id.id),
                ('quarter', '=', self.quarter),
                ('year', '=', self.year),
                ('evaluate_kpi_id', 'in', [False, self._origin.id])
            ])
            self.evaluate_kpi_ids = kpis

    # --- LUỒNG XỬ LÝ ---
    def action_submit_for_approval(self):
        """Từ Nháp -> Chờ duyệt"""
        self.ensure_one()
        if not self.evaluate_kpi_ids:
            raise UserError(_("Không có phiếu KPI nào để trình duyệt."))

        # Kiểm tra xem các phiếu con đã xong chưa
        unfinished = self.evaluate_kpi_ids.filtered(lambda x: x.state != 'done')
        if unfinished:
            raise UserError(_("Vẫn còn %s phiếu chưa hoàn thành. Vui lòng đốc thúc nhân viên.") % len(unfinished))

        self.write({'state': 'to_approve'})

    def action_approve_report(self):
        """TGĐ Duyệt -> Hoàn thành"""
        self.ensure_one()
        self.write({'state': 'done'})

    def action_refuse_report(self):
        """TGĐ Từ chối -> Quay về Nháp để sửa"""
        self.ensure_one()
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


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

    @api.model
    def cron_auto_generate_quarterly_kpi(self):
        """
        Cron chạy định kỳ đầu tháng.
        Tự động tạo phiếu cho Quý trước vào ngày đầu Quý sau.
        """
        today = date.today()
        # Chỉ chạy vào ngày 1 của các tháng 1, 4, 7, 10
        if today.day != 1 or today.month not in [1, 4, 7, 10]:
            return

        # Tính toán kỳ đánh giá (Quý vừa trôi qua)
        curr_month = today.month
        eval_year = today.year
        if curr_month == 1:
            eval_quarter = '4'
            eval_year -= 1
        elif curr_month == 4:
            eval_quarter = '1'
        elif curr_month == 7:
            eval_quarter = '2'
        else:
            eval_quarter = '3'

        employees = self.env['hr.employee'].search([('active', '=', True)])
        count = 0
        for emp in employees:
            # Tránh tạo trùng
            exists = self.search_count([
                ('employee_id', '=', emp.id),
                ('quarter', '=', eval_quarter),
                ('year', '=', eval_year)
            ])
            if exists: continue

            kpi = self.create({
                'employee_id': emp.id,
                'quarter': eval_quarter,
                'year': eval_year,
                'state': 'draft'
            })
            # Gửi mail cho nhân viên
            kpi._send_workflow_email(emp, "MỜI TỰ ĐÁNH GIÁ KPI")
            count += 1
        return count

    def action_send(self):
        """Nhân viên gửi -> Cấp quản lý kế tiếp"""
        self.ensure_one()
        if self.is_manager_review_required and self.employee_id.parent_id:
            self.write({'state': 'wait_manager'})
            self._send_workflow_email(self.employee_id.parent_id, "CẦN PHÊ DUYỆT KPI (CẤP QUẢN LÝ)")
        else:
            self.action_manager_evaluation()  # Nhảy bước nếu không cần

    def action_manager_evaluation(self):
        """Quản lý gửi -> Hội đồng/Trưởng đơn vị"""
        self.ensure_one()
        if self.is_council_review_required and self.department_id.manager_id:
            self.write({'state': 'wait_council'})
            self._send_workflow_email(self.department_id.manager_id, "CẦN PHÊ DUYỆT KPI (CẤP TRƯỞNG ĐƠN VỊ)")
        else:
            self.action_council_evaluation()

    def action_council_evaluation(self):
        """Hội đồng gửi -> Tổng giám đốc"""
        self.ensure_one()
        if self.is_director_review_required:
            self.write({'state': 'wait_director'})
            # Lấy user có quyền TGĐ
            director_group = self.env.ref('om_hr_payroll.group_kpi_director_new')
            director = director_group.users[:1].employee_id
            if director:
                self._send_workflow_email(director, "CẦN PHÊ DUYỆT KPI (CẤP TỔNG GIÁM ĐỐC)")
        else:
            self._finish_and_display_result()

    def _send_workflow_email(self, receiver_emp, subject_title):
        if not receiver_emp or not receiver_emp.work_email: return

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        action_url = f"{base_url}/web#id={self.id}&model=evaluation.kpi&view_type=form"

        body = f"""
                <div style="font-family: Arial, sans-serif;">
                    <p>Kính gửi <b>{receiver_emp.name}</b>,</p>
                    <p>Hệ thống thông báo phiếu KPI của <b>{self.employee_id.name}</b> đang chờ bạn xử lý.</p>
                    <p><b>Kỳ đánh giá:</b> {self.period}</p>
                    <div style="margin: 20px 0;">
                        <a href="{action_url}" style="background-color: #875A7B; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">TRUY CẬP PHIẾU</a>
                    </div>
                </div>
            """
        self.env['mail.mail'].sudo().create({
            'subject': f"[{subject_title}] - {self.employee_id.name}",
            'email_to': receiver_emp.work_email,
            'body_html': body,
        }).send()

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