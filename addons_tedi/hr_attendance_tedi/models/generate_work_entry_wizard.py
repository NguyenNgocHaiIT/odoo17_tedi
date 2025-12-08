# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TediMassWorkEntryWizard(models.TransientModel):
    _name = 'tedi.work.entry.generate.wizard'
    _description = 'Tạo Work Entry Hàng Loạt (Chuẩn Logic Base)'

    date_from = fields.Date(string="Từ ngày", required=True)
    date_to = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Công ty", default=lambda self: self.env.company, required=True)

    employee_ids = fields.Many2many('hr.employee', string="Nhân viên",
                                    help="Mặc định hệ thống sẽ chọn tất cả nhân viên có hợp đồng đang chạy.")

    @api.model
    def default_get(self, fields_list):
        """
        Logic của bạn: Tự động chọn tất cả nhân viên có hợp đồng trong khoảng thời gian này.
        """
        res = super(TediMassWorkEntryWizard, self).default_get(fields_list)
        d_from = res.get('date_from') or self._context.get('default_date_from')
        d_to = res.get('date_to') or self._context.get('default_date_to')
        c_id = res.get('company_id') or self._context.get('default_company_id') or self.env.company.id

        if d_from and d_to:
            # Tìm hợp đồng có hiệu lực trong khoảng thời gian chọn
            contracts = self.env['hr.contract'].search([
                ('company_id', '=', c_id),
                ('state', 'in', ['open', 'close']),
                ('date_start', '<=', d_to),
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', d_from)
            ])
            employees = contracts.mapped('employee_id')
            res['employee_ids'] = [(6, 0, employees.ids)]
        return res

    def action_mass_regenerate(self):
        """
        Logic của Base: Xử lý sạch dữ liệu cũ và Force Regenerate.
        """
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_("Vui lòng chọn ít nhất một nhân viên."))

        date_from = self.date_from
        date_to = self.date_to

        # --- LOGIC GIỐNG BASE: DỌN DẸP DỮ LIỆU CŨ ---
        # Base tìm các work entry trong khoảng thời gian để xử lý (archive hoặc unlink)
        # Ở đây ta sẽ unlink (xóa) các bản ghi chưa chốt (Draft/Conflict/Cancelled)
        # để đảm bảo sạch sẽ hoàn toàn như cách bạn muốn.
        work_entries_to_remove = self.env['hr.work.entry'].search([
            ('employee_id', 'in', self.employee_ids.ids),
            ('date_stop', '>=', date_from),
            ('date_start', '<=', date_to),
            ('state', '!=', 'validated')  # QUAN TRỌNG: Không được xóa cái đã chốt (Validated)
        ])

        # Base thường dùng write active=False, nhưng unlink sạch hơn cho wizard tạo lại
        if work_entries_to_remove:
            work_entries_to_remove.unlink()

        # --- LOGIC GIỐNG BASE: TẠO LẠI ---
        # Gọi hàm generate_work_entries của model hr.employee
        # Tham số thứ 3 là True (force_generation) -> Đây là key của logic Base
        # Nó giúp bỏ qua các check không cần thiết và ép buộc tính lại theo lịch làm việc.
        self.employee_ids.generate_work_entries(date_from, date_to, True)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Hoàn tất'),
                'message': _('Đã tái tạo dữ liệu công cho %s nhân viên.') % len(self.employee_ids),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }