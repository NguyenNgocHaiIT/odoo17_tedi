from odoo import models, fields, api


class TediRequest(models.Model):
    _name = 'tedi.request'
    _description = 'Đơn báo'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- CÁC FIELD CƠ BẢN ---
    code = fields.Char(string='Mã đơn', readonly=True, copy=False, index=True, default='Mới')
    name = fields.Char(string='Tiêu đề', required=True)
    date_request = fields.Date(string='Ngày đề nghị', default=fields.Date.context_today)

    employee_id = fields.Many2one(
        'hr.employee',
        string='Người đề nghị',
        # Lệnh này giúp lấy nhân viên đang đăng nhập
        default=lambda self: self.env.user.employee_id,
        required=True
    )

    # Field related lấy mã nhân viên
    employee_code = fields.Char(
        related='employee_id.employee_code',
        string='Mã số NV',
        store=True
    )

    request_type = fields.Selection([
        ('leave', 'Nghỉ phép'),
        ('ot', 'Tăng ca'),
        ('other', 'Khác')
    ], string='Loại đơn báo', required=True, default='leave')

    content = fields.Char(string='Nội dung')
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', string='Bộ phận', store=True)
    leave_taken = fields.Float(string='Số ngày phép đã nghỉ', default=1.0)
    leave_remaining = fields.Float(string='Số ngày phép còn lại', default=10.0)

    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('confirm', 'Trình duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Từ chối')
    ], string='Trạng thái', default='draft', tracking=True)

    # ========================================================================
    # ĐÚNG: Khai báo field ở đây (Ngang hàng với các field trên)
    # ========================================================================
    history_ids = fields.Many2many(
        'tedi.request',
        string='Lịch sử đơn báo',
        compute='_compute_history_ids'
    )

    # Hàm tính toán (đã sửa lỗi _origin)
    @api.depends('employee_id')
    def _compute_history_ids(self):
        for rec in self:
            if rec.employee_id:
                domain = [('employee_id', '=', rec.employee_id.id)]
                # Kiểm tra _origin để tránh lỗi
                if rec._origin.id:
                    domain.append(('id', '!=', rec._origin.id))

                rec.history_ids = self.env['tedi.request'].search(domain)
            else:
                rec.history_ids = False

    # --- LOGIC SINH MÃ ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'Mới') == 'Mới':
                vals['code'] = self.env['ir.sequence'].next_by_code('tedi.request.seq') or 'Mới'
        return super(TediRequest, self).create(vals_list)

    # --- CÁC HÀM BUTTON (Nằm riêng biệt phía dưới) ---
    def action_confirm(self):
        self.write({'state': 'confirm'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})