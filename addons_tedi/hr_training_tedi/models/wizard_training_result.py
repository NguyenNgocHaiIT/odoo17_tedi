from odoo import api, fields, models, tools

class TrainingResultWizard(models.TransientModel):
    _name = 'training.result.wizard'
    _description = 'Cập nhật kết quả đào tạo hàng loạt'

    # Link đến đợt đăng ký (lớp học)
    participation_id = fields.Many2one(
        'training.plan.participation',
        string="Đợt đào tạo",
        readonly=True
    )

    # Danh sách học viên trong wizard
    line_ids = fields.One2many(
        'training.result.wizard.line',
        'wizard_id',
        string="Danh sách học viên"
    )

    @api.model
    def default_get(self, fields_list):
        """
        Hàm này chạy khi Wizard vừa mở lên.
        Nó sẽ lấy danh sách học viên từ màn hình bên ngoài (active_id)
        và điền vào bảng line_ids của wizard.
        """
        res = super(TrainingResultWizard, self).default_get(fields_list)

        active_id = self.env.context.get('active_id')
        if active_id:
            participation = self.env['training.plan.participation'].browse(active_id)

            # Tạo danh sách dữ liệu cho One2many
            lines = []
            for detail in participation.participation_detail_ids:
                lines.append((0, 0, {
                    'detail_id': detail.id,
                    'user_id': detail.user_id.id,
                    'department_id': detail.department_id.id,
                    'training_result': detail.training_result,  # Load kết quả cũ lên (nếu có)
                    'note': detail.note
                }))

            res.update({
                'participation_id': active_id,
                'line_ids': lines
            })
        return res

    def action_apply(self):
        """Lưu kết quả từ Wizard ngược lại vào Database thật"""
        self.ensure_one()
        for line in self.line_ids:
            # Ghi đè kết quả từ dòng wizard vào dòng dữ liệu gốc
            line.detail_id.write({
                'training_result': line.training_result,
                # 'note': line.note # Nếu muốn cập nhật cả ghi chú thì bỏ comment
            })
        return {'type': 'ir.actions.act_window_close'}


# ---------------------------------------------------------
# 2. WIZARD LINE (DÒNG CHI TIẾT TRONG WIZARD)
# ---------------------------------------------------------
class TrainingResultWizardLine(models.TransientModel):
    _name = 'training.result.wizard.line'
    _description = 'Chi tiết cập nhật kết quả'

    wizard_id = fields.Many2one('training.result.wizard', string="Wizard gốc")

    # Link đến bản ghi gốc để update ngược lại
    detail_id = fields.Many2one('training.plan.participation.detail', string="Bản ghi gốc")

    # Các field hiển thị (readonly hoặc edit)
    user_id = fields.Many2one('res.users', string="Họ và tên", readonly=True)
    department_id = fields.Many2one('hr.department', string="Đơn vị", readonly=True)

    training_result = fields.Selection([
        ('pass', 'Đạt'),
        ('fail', 'Không đạt')
    ], string="Kết quả")

    note = fields.Char(string="Ghi chú", readonly=True)