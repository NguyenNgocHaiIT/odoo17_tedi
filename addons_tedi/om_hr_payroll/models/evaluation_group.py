# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


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
                                  states={'draft': [('readonly', False)]})
    job_id = fields.Many2one('hr.job', string="Chức danh", related='employee_id.job_id', store=True, readonly=True)
    department_id = fields.Many2one('hr.department', string="Đơn vị", related='employee_id.department_id', store=True,
                                    readonly=True)

    # Giả sử wage_level lấy từ job_title hoặc contract (tùy thực tế database của bạn)
    wage_level = fields.Char(string="Nhóm, bậc lương", related='employee_id.job_title', readonly=True)

    # --- 7. CHU KỲ ---
    period = fields.Char(string="Chu kỳ", default=lambda self: self._get_default_period(), required=True)

    # --- CẤU HÌNH QUY TRÌNH (Lấy từ Employee) ---

    is_manager_review_required = fields.Boolean(related='employee_id.kpi_manager_review', store=True, readonly=True)
    is_council_review_required = fields.Boolean(related='employee_id.kpi_council_review', store=True, readonly=True)
    is_director_review_required = fields.Boolean(related='employee_id.kpi_director_review', store=True, readonly=True)

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
    total_score = fields.Float(string="Tổng cộng", compute="_compute_results", store=True, digits=(16, 1),
                               tracking=True)
    k_coefficient = fields.Float(string="Hệ số K", compute="_compute_results", store=True, digits=(16, 2),
                                 tracking=True)
    final_result = fields.Char(string="Kết quả thực hiện", compute="_compute_results", store=True, tracking=True)

    is_department_manager = fields.Boolean(compute='_compute_is_department_manager')
    is_direct_manager = fields.Boolean(compute='_compute_is_direct_manager')

    @api.depends('department_id')
    def _compute_is_department_manager(self):
        current_user = self.env.user

        # 1. Kiểm tra có nằm trong nhóm quyền "Trưởng đơn vị" không
        # Lưu ý: Vì cấu trúc dropdown, TGĐ và Admin cũng sẽ có has_group này = True (Đúng logic)
        is_in_group = current_user.has_group('om_hr_payroll.group_kpi_dept_manager_new')

        # Lấy phòng ban của user hiện tại (thông qua employee)
        current_user_dept = current_user.employee_id.department_id

        is_admin = current_user.has_group('base.group_system')

        for rec in self:
            # Admin luôn đúng
            if is_admin:
                rec.is_department_manager = True
                continue

            # LOGIC MỚI:
            # 1. User phải có quyền Trưởng đơn vị
            # 2. User phải cùng phòng ban với phiếu đánh giá (rec.department_id)
            if is_in_group and current_user_dept and rec.department_id:
                if current_user_dept.id == rec.department_id.id:
                    rec.is_department_manager = True
                else:
                    rec.is_department_manager = False
            else:
                rec.is_department_manager = False

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
            vals['name'] = self.env['ir.sequence'].next_by_code('evaluation.kpi') or 'New'
        return super(EvaluationKPI, self).create(vals)

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
    @api.depends('line_ids.final_score', 'line_ids.weight', 'line_ids.display_type')
    def _compute_results(self):
        for rec in self:
            weighted_score_sum = 0.0
            total_weight = 0.0

            for line in rec.line_ids:
                if not line.display_type:
                    weighted_score_sum += (line.final_score * line.weight)
                    total_weight += line.weight

            raw_score = (weighted_score_sum / total_weight) if total_weight > 0 else 0.0

            # Gán điểm thực
            rec.total_score = round(raw_score, 2)

            # Gán % hiển thị (Ví dụ: 4.0 điểm / 5.0 * 100 = 80%)
            rec.total_score_percent = (rec.total_score / 5.0) * 100

            # Xếp loại (Logic cũ giữ nguyên)
            rule = self.env['evaluation.kpi.classification'].search([
                ('min_score', '<=', rec.total_score),
                ('max_score', '>=', rec.total_score)
            ], limit=1, order='min_score desc')

            if rule:
                rec.k_coefficient = rule.k_coefficient
                rec.final_result = rule.classification
            else:
                rec.k_coefficient = 0.0
                rec.final_result = "Chưa xếp loại"

            rec.is_result_computed = True

    # --- WORKFLOW & NÚT BẤM ---
    def action_send(self):
        self.ensure_one()
        # Logic nhảy bước dựa trên cấu hình Boolean
        if self.is_manager_review_required:
            self.write({'state': 'wait_manager'})
        elif self.is_council_review_required:
            self.write({'state': 'wait_council'})
        elif self.is_director_review_required:
            self.write({'state': 'wait_director'})
        else:
            # Trường hợp đặc biệt: Không ai đánh giá ngoài nhân viên -> Done luôn
            self.action_director_evaluation()  # Hoặc hàm finish tương ứng

    def action_manager_evaluation(self):
        """QLTT xong -> Check xem có cần TĐV không"""
        if self.is_council_review_required:
            self.write({'state': 'wait_council'})
        elif self.is_director_review_required:
            self.write({'state': 'wait_director'})
        else:
            self.write({'state': 'done'})

    def action_council_evaluation(self):
        """TĐV xong -> Check xem có cần TGĐ không"""
        if self.is_director_review_required:
            self.write({'state': 'wait_director'})
        else:
            self.write({'state': 'done'})

    def action_director_evaluation(self):
        self.write({'state': 'done'})

    def action_compute_result_manual(self):
        """Nút tính toán thủ công để reload view"""
        self._compute_results()
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
            # Logic: Lấy điểm của người "Cao nhất" được yêu cầu (Checked).
            # Không quan tâm họ đã nhập hay chưa (nếu chưa nhập thì chấp nhận là 0 để ép nhập).

            if line.kpi_id.is_director_review_required:
                line.final_score = line.director_score
            elif line.kpi_id.is_council_review_required:
                line.final_score = line.council_score
            elif line.kpi_id.is_manager_review_required:
                line.final_score = line.manager_score
            else:
                # Nếu không ai cần đánh giá, lấy điểm tự đánh giá
                line.final_score = line.self_score

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