# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


# --- MODEL DÒNG CHI TIẾT ĐỂ CHỌN ---
class EvaluationKPIGenerateLine(models.TransientModel):
    _name = 'evaluation.kpi.generate.line'
    _description = 'Dòng chọn nhân viên tạo KPI'

    wizard_id = fields.Many2one('evaluation.kpi.generate.wizard', string="Wizard")

    # --- SỬA Ở ĐÂY: Bỏ readonly=True ---
    employee_id = fields.Many2one('hr.employee', string="Nhân viên", required=True)

    job_id = fields.Many2one('hr.job', related='employee_id.job_id', string="Chức danh", readonly=True)
    is_selected = fields.Boolean(string="Chọn", default=False)


# --- MODEL WIZARD CHÍNH ---
class EvaluationKPIGenerateWizard(models.TransientModel):
    _name = 'evaluation.kpi.generate.wizard'
    _description = 'Wizard tạo phiếu KPI hàng loạt'

    report_id = fields.Many2one('evaluation.report', string="Báo cáo gốc", required=True)
    department_id = fields.Many2one('hr.department', related='report_id.department_id', string="Phòng ban",
                                    readonly=True)

    selection_mode = fields.Selection([
        ('all', 'Tất cả nhân viên thuộc phòng ban'),
        ('specific', 'Chọn nhân viên cụ thể')
    ], string="Phương thức tạo", default='all', required=True)

    # Thay thế field employee_ids cũ bằng field line_ids mới
    line_ids = fields.One2many('evaluation.kpi.generate.line', 'wizard_id', string="Danh sách nhân viên")

    # --- HÀM TỰ ĐỘNG LOAD DANH SÁCH NHÂN VIÊN ---
    @api.onchange('selection_mode', 'department_id')
    def _onchange_load_employees(self):
        """Khi chọn chế độ Specific, tự động load list nhân viên ra bảng"""
        # Xóa danh sách cũ
        self.line_ids = [(5, 0, 0)]

        if self.selection_mode == 'specific' and self.department_id:
            employees = self.env['hr.employee'].search([
                ('department_id', '=', self.department_id.id),
                ('active', '=', True)
            ])

            lines = []
            for emp in employees:
                lines.append((0, 0, {
                    'employee_id': emp.id,
                    'is_selected': False  # Mặc định là chưa chọn
                }))
            self.line_ids = lines

    def action_confirm_generate(self):
        """Logic tạo dòng dự kiến (Report Line) cập nhật trực tiếp vào form cha"""
        self.ensure_one()
        # Sử dụng sudo() nếu cần quyền admin để ghi vào báo cáo cha,
        # nhưng thường thì user hiện tại có quyền ghi.
        report = self.report_id

        # Chỉ cho phép chạy wizard khi báo cáo ở trạng thái Nháp
        if report.state != 'draft':
            raise UserError(_("Chỉ có thể thêm nhân viên khi báo cáo ở trạng thái Nháp!"))

        # --- Phần chọn nhân viên giữ nguyên ---
        target_employees = self.env['hr.employee']
        if self.selection_mode == 'all':
            target_employees = self.env['hr.employee'].search([
                ('department_id', '=', self.department_id.id),
                ('active', '=', True)
            ])
        else:
            selected_lines = self.line_ids.filtered(lambda l: l.is_selected)
            if not selected_lines:
                raise UserError(_("Vui lòng tích chọn ít nhất một nhân viên!"))
            target_employees = selected_lines.mapped('employee_id')
        # -------------------------------------

        # --- THAY ĐỔI LOGIC TẠO DÒNG Ở ĐÂY ---

        # 1. Tạo một danh sách chứa các lệnh cập nhật
        new_lines_commands = []
        count = 0

        # Lấy danh sách ID nhân viên đã có sẵn trong báo cáo để check trùng nhanh hơn
        existing_employee_ids = report.report_line_ids.mapped('employee_id.id')

        for emp in target_employees:
            # Check trùng: Nếu nhân viên đã có trong danh sách thì bỏ qua
            if emp.id in existing_employee_ids:
                continue

            # TẠO LỆNH THÊM DÒNG MỚI VÀO ONE2MANY
            # Cú pháp: (0, 0, {dictionary_giá_trị_các_field})
            # Lưu ý: Không cần truyền 'report_id' vì chúng ta đang ghi thẳng vào report đó.
            new_lines_commands.append((0, 0, {
                'employee_id': emp.id,
                # Thêm các field khác nếu model line của bạn yêu cầu
            }))
            count += 1

        # 2. Thực hiện ghi vào bản ghi cha một lần duy nhất
        if new_lines_commands:
            # Lệnh này sẽ kích hoạt việc cập nhật giao diện ở client
            # Field 'report_line_ids' là tên field One2many trên model evaluation.report
            report.write({
                'report_line_ids': new_lines_commands
            })

        # --- THAY ĐỔI RETURN ACTION ---
        # Thay vì 'tag': 'reload', chúng ta chỉ cần đóng wizard lại.
        # Odoo client thông minh sẽ tự nhận biết bản ghi cha (report_id) vừa bị thay đổi
        # và tự động làm mới các field của nó trên giao diện hiện tại.
        return {
            'type': 'ir.actions.act_window_close', # Đóng cửa sổ popup
            'effect': {
                'fadeout': 'slow',
                'message': _(f'Đã thêm {count} nhân viên vào danh sách dự kiến!'),
                'type': 'rainbow_man',
            }
        }