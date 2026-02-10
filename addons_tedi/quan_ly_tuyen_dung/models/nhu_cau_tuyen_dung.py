# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, AccessError, UserError


class RecruitmentNeeds(models.Model):
    _name = "recruitment.needs"
    _description = "Recruitment Needs"
    _rec_name = "display_code"

    display_code = fields.Char(string="Mã phiếu", compute="_compute_display_code", store=True, default="Mới")

    @api.depends('type', 'department_id', 'create_date', 'name', 'plan_id')
    def _compute_display_code(self):
        for rec in self:
            prefix = "KH-NĂM" if rec.type == 'year' else "KH-TT"
            dept = rec.department_id.name or "N/A"
            date = rec.create_date.strftime('%d/%m') if rec.create_date else ""

            # Tạo tên dạng: KH-NĂM | Phòng IT | 22/12
            rec.display_code = f"{prefix} | {dept} | {date}"
    name = fields.Many2one(
        "recruitment.survey",
        string="Tên đợt khảo sát",
        domain=[('state', '=', 'in_process')],
        # Bỏ required=True ở Python, xử lý ở XML
    )

    # 3. THÊM TRƯỜNG KẾ HOẠCH QUÝ (Cho Nhu cầu Thực tế)
    plan_id = fields.Many2one(
        "recruitment.plan",
        string="Thuộc Kế hoạch Quý",
        # Lấy loại là 'quarter' VÀ trạng thái là 'in_process'
        domain="[('type', '=', 'quarter'), ('recruitment_status', '=', 'draft')]",
    )

    create_date = fields.Date(
        string="Ngày đăng ký",
        readonly=True,
        default=fields.Date.context_today,
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban đăng ký',
        default=lambda self: self.env.user.employee_id.department_id
    )
    type = fields.Selection([
        ('year', 'Nhu cầu Năm'),
        ('actual', 'Nhu cầu Thực tế'),
    ], string="Loại nhu cầu", default='year', required=True)



    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('confirmed', 'Đã xác nhận'),
    ], string="Trạng thái", default='draft')

    line_ids = fields.One2many(
        'recruitment.needs.line',
        'recruitment_needs_id',
        string='Chi tiết nhu cầu',
    )

    def _check_unique_job(self):
        for rec in self:
            jobs = rec.line_ids.mapped('job_id')
            if len(jobs) != len(set(jobs.ids)):
                raise UserError(_("Bạn không được chọn 2 vị trí tuyển dụng giống nhau trong cùng một phiếu."))

    @api.model
    def create(self, vals):

        if vals.get('type') == 'year' and not vals.get('name'):
            raise UserError(_("Với Nhu cầu Năm, bạn phải chọn Đợt khảo sát."))
        if vals.get('type') == 'actual' and not vals.get('plan_id'):
            raise UserError(_("Với Nhu cầu Thực tế, bạn phải chọn Kế hoạch Quý."))
        if not vals.get('department_id'):
            employee = self.env.user.employee_id
            if employee and employee.department_id:
                vals['department_id'] = employee.department_id.id
        res = super().create(vals)
        res._check_unique_job()
        return res

    def write(self, vals):
        res = super().write(vals)
        self._check_unique_job()
        return res

    def action_approve(self):

        for rec in self:

            if rec.type == 'year' and not rec.name:
                raise UserError(_("Vui lòng chọn 'Đợt khảo sát' trước khi Xác nhận."))

                # 2. Bắt buộc phải chọn Kế hoạch quý (nếu là Thực tế)
            if rec.type == 'actual' and not rec.plan_id:
                raise UserError(_("Vui lòng chọn 'Kế hoạch Quý' trước khi Xác nhận."))

                # 3. Kiểm tra dòng chi tiết
            if not rec.line_ids:
                raise UserError(_("Vui lòng nhập ít nhất 1 dòng nhu cầu tuyển dụng."))
            if rec.state != 'draft':
                raise UserError(_("Chỉ được duyệt khi phiếu đang ở trạng thái 'Dự thảo'."))
            if not rec.line_ids:
                raise UserError(_("Bạn phải nhập ít nhất 1 dòng nhu cầu tuyển dụng trước khi xác nhận."))

            # --- LOGIC MỚI: CẬP NHẬT KẾ HOẠCH QUÝ ---
            if rec.type == 'actual' and rec.plan_id:
                rec._update_linked_quarterly_plan()
            # ----------------------------------------

            rec.state = "confirmed"

        # --- HÀM XỬ LÝ CẬP NHẬT PLAN ---

    def _update_linked_quarterly_plan(self):
        self.ensure_one()
        # 1. Dùng sudo() ngay từ đầu để đảm bảo quyền ghi log vào Plan
        plan = self.plan_id.sudo()

        if plan.recruitment_status in ['approved', 'in_process', 'complete']:
            return

        msg_body = f"<b>Cập nhật từ Nhu cầu thực tế ({self.display_name}):</b><ul>"

        # Model Detail cũng cần quyền sudo để search/create/write
        PlanDetailSudo = self.env['recruitment.plan.detail'].sudo()

        for line in self.line_ids:
            domain = [
                ('plan_id', '=', plan.id),
                ('recruitment_job', '=', line.job_id.id),
                ('department_request', '=', self.department_id.id),
                # ('expense_per_head', '=', line.expected_salary),
                ('experient_request_id', '=', line.experience_id.id or False),
                ('professional_qualification', '=', line.professional_qualification or False),
            ]

            # 2. Tìm kiếm với quyền Admin
            existing_detail = PlanDetailSudo.search(domain, limit=1)

            if existing_detail:
                # 3. Ghi (Write) với quyền Admin
                old_qty = existing_detail.requested_quantity
                new_qty = old_qty + line.amount

                # Lưu ý: existing_detail đã được search từ PlanDetailSudo nên nó đã mang quyền sudo
                existing_detail.requested_quantity = new_qty

                msg_body += (
                    f"<li>Vị trí <b>{line.job_id.name}</b> (Trùng tiêu chí): "
                    f"Tăng từ {old_qty} lên {new_qty} (+{line.amount}).</li>"
                )
            else:
                # 4. Tạo mới (Create) với quyền Admin
                vals = {
                    'plan_id': plan.id,
                    'department_request': self.department_id.id,
                    'recruitment_job': line.job_id.id,
                    'requested_quantity': line.amount,
                    'experient_request_id': line.experience_id.id,
                    'professional_qualification': line.professional_qualification,
                    # 'expense_per_head': line.expected_salary,
                    'note': line.note or _("Bổ sung từ nhu cầu thực tế"),
                }
                PlanDetailSudo.create(vals)

                msg_body += (
                    f"<li>Vị trí <b>{line.job_id.name}</b> (Tiêu chí mới): "
                    f"Thêm mới số lượng {line.amount}.</li>"
                )

        msg_body += "</ul>"

        # 5. Ghi log (Message Post) với quyền Admin
        # (Do biến 'plan' ở trên đã .sudo() rồi nên dòng này sẽ không lỗi)
        plan.message_post(body=msg_body)

class RecruitmentNeedsLine(models.Model):
    _name = 'recruitment.needs.line'
    _description = "Recruitment Needs Line"

    job_id = fields.Many2one("hr.job", string="Vị trí tuyển dụng", required=True)
    experience_id = fields.Many2one("experience.request", string="Yêu cầu kinh nghiệm")

    amount = fields.Integer(string="Số lượng cần tuyển", default=1)

    # 1. MỨC LƯƠNG DỰ KIẾN
    expected_salary = fields.Float(string="Mức lương dự kiến", default=0)

    # 2. CÁC TRƯỜNG LƯU TRỮ TIẾN TRÌNH (Ẩn trên view, hiện trên popup)
    qty_q1 = fields.Integer(string="Quý 1", default=0)
    qty_q2 = fields.Integer(string="Quý 2", default=0)
    qty_q3 = fields.Integer(string="Quý 3", default=0)
    qty_q4 = fields.Integer(string="Quý 4", default=0)

    progress_summary = fields.Char(
        string="Tiến độ (Q1-Q2-Q3-Q4)",
        compute='_compute_progress_summary',
        store=False
    )

    action_helper = fields.Char(string="Cấu hình", compute='_compute_action_helper')

    def _compute_action_helper(self):
        for rec in self:
            rec.action_helper = ""  # Hoặc để chữ "Click ->" nếu muốn

    @api.depends('qty_q1', 'qty_q2', 'qty_q3', 'qty_q4')
    def _compute_progress_summary(self):
        for rec in self:
            rec.progress_summary = f"{rec.qty_q1} - {rec.qty_q2} - {rec.qty_q3} - {rec.qty_q4}"

    current_employee_count = fields.Integer(
        string="Nhân sự hiện có",
        compute="_compute_current_employee_count"
    )

    professional_qualification = fields.Selection([
        ("bachelor", "Cử nhân"),
        ("engineer", "Kỹ sư"),
        ("master", "Thạc sĩ"),
        ("PhD", "Tiến sĩ"),
    ], string="Yêu cầu chuyên môn")

    note = fields.Char("Ghi chú")

    recruitment_needs_id = fields.Many2one("recruitment.needs", string="Nhu cầu tuyển dụng")

    # --- SQL CONSTRAINT: CHECK LƯƠNG > 0 ---
    _sql_constraints = [
        ('check_expected_salary_positive',
         'CHECK(expected_salary > 0)',
         'Mức lương dự kiến phải lớn hơn 0.')
    ]

    @api.depends('job_id', 'recruitment_needs_id.department_id')
    def _compute_current_employee_count(self):
        for rec in self:
            department = rec.recruitment_needs_id.department_id
            job = rec.job_id
            if department and job:
                count = self.env['hr.employee'].search_count([
                    ('department_id', '=', department.id),
                    ('job_id', '=', job.id),
                    ('active', '=', True)
                ])
                rec.current_employee_count = count
            else:
                rec.current_employee_count = 0


    # --- ACTION MỞ POPUP ---
    def action_open_progress_wizard(self):
        self.ensure_one()
        # Cơ chế Odoo: Khi ấn nút này trên giao diện editable="bottom",
        # Odoo đã tự động gọi lệnh write/create để lưu dòng này vào DB rồi.

        return {
            'name': _('Cấu hình tiến trình bổ sung'),
            'type': 'ir.actions.act_window',
            'res_model': 'recruitment.progress.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                # Truyền ID để wizard biết đang link với dòng nào
                'default_line_id': self.id,

                # TRUYỀN GIÁ TRỊ TRỰC TIẾP:
                # Wizard sẽ nhận các giá trị này làm mặc định (default_get)
                # giúp hiển thị ngay lập tức số liệu vừa nhập.
                'default_amount_total': self.amount,
                'default_qty_q1': self.qty_q1,
                'default_qty_q2': self.qty_q2,
                'default_qty_q3': self.qty_q3,
                'default_qty_q4': self.qty_q4,
            }
        }



class RecruitmentProgressWizard(models.TransientModel):
    _name = 'recruitment.progress.wizard'
    _description = 'Cấu hình tiến trình tuyển dụng theo quý'
    _rec_name = 'display_name_wizard'  # 1. Thêm Rec Name cho Wizard

    display_name_wizard = fields.Char(string="Tiêu đề", default="Phân bổ tiến độ")

    line_id = fields.Many2one('recruitment.needs.line', string="Dòng nhu cầu", required=True)
    amount_total = fields.Integer(string="Tổng số lượng cần tuyển", readonly=True)

    qty_q1 = fields.Integer(string="Quý 1")
    qty_q2 = fields.Integer(string="Quý 2")
    qty_q3 = fields.Integer(string="Quý 3")
    qty_q4 = fields.Integer(string="Quý 4")

    # --- TỰ ĐỘNG LOAD DỮ LIỆU CŨ ---
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)


        # Logic cũ của bạn vẫn tốt để đảm bảo an toàn (phòng trường hợp mở wizard theo cách khác)
        if not res.get('line_id') and self._context.get('default_line_id'):
            res['line_id'] = self._context.get('default_line_id')

        # Nếu amount_total chưa có (không truyền qua context), mới phải query lại DB
        if 'amount_total' not in res and res.get('line_id'):
            line = self.env['recruitment.needs.line'].browse(res['line_id'])
            if line.exists():
                res.update({
                    'amount_total': line.amount,
                    'qty_q1': line.qty_q1,
                    'qty_q2': line.qty_q2,
                    'qty_q3': line.qty_q3,
                    'qty_q4': line.qty_q4,
                })

        return res

    @api.constrains('qty_q1', 'qty_q2', 'qty_q3', 'qty_q4')
    def _check_total_qty(self):
        for rec in self:
            total_plan = rec.qty_q1 + rec.qty_q2 + rec.qty_q3 + rec.qty_q4
            if total_plan > rec.amount_total:
                raise UserError(
                    _("Tổng số lượng phân bổ 4 quý (%s) không được lớn hơn số lượng cần tuyển (%s).")
                    % (total_plan, rec.amount_total)
                )

    # --- LƯU VÀ RELOAD GIAO DIỆN ---
    def action_confirm(self):
        self.ensure_one()
        if self.line_id:
            # 1. Ghi dữ liệu vào line gốc
            self.line_id.write({
                'qty_q1': self.qty_q1,
                'qty_q2': self.qty_q2,
                'qty_q3': self.qty_q3,
                'qty_q4': self.qty_q4,
            })

        return {'type': 'ir.actions.act_window_close'}