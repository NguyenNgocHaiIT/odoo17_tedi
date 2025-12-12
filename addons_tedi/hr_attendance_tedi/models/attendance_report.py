# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # =========================================================================
    # 1. KHAI BÁO DANH SÁCH GIỜ
    # =========================================================================
    _HOUR_SELECTION = [
        ('0', '12:00 AM'), ('0.5', '12:30 AM'),
        ('1', '1:00 AM'), ('1.5', '1:30 AM'),
        ('2', '2:00 AM'), ('2.5', '2:30 AM'),
        ('3', '3:00 AM'), ('3.5', '3:30 AM'),
        ('4', '4:00 AM'), ('4.5', '4:30 AM'),
        ('5', '5:00 AM'), ('5.5', '5:30 AM'),
        ('6', '6:00 AM'), ('6.5', '6:30 AM'),
        ('7', '7:00 AM'), ('7.5', '7:30 AM'),
        ('8', '8:00 AM'), ('8.5', '8:30 AM'),
        ('9', '9:00 AM'), ('9.5', '9:30 AM'),
        ('10', '10:00 AM'), ('10.5', '10:30 AM'),
        ('11', '11:00 AM'), ('11.5', '11:30 AM'),
        ('12', '12:00 PM'), ('12.5', '12:30 PM'),
        ('13', '1:00 PM'), ('13.5', '1:30 PM'),
        ('14', '2:00 PM'), ('14.5', '2:30 PM'),
        ('15', '3:00 PM'), ('15.5', '3:30 PM'),
        ('16', '4:00 PM'), ('16.5', '4:30 PM'),
        ('17', '5:00 PM'), ('17.5', '5:30 PM'),
        ('18', '6:00 PM'), ('18.5', '6:30 PM'),
        ('19', '7:00 PM'), ('19.5', '7:30 PM'),
        ('20', '8:00 PM'), ('20.5', '8:30 PM'),
        ('21', '9:00 PM'), ('21.5', '9:30 PM'),
        ('22', '10:00 PM'), ('22.5', '10:30 PM'),
        ('23', '11:00 PM'), ('23.5', '11:30 PM')
    ]

    # =========================================================================
    # 2. CORE FIX: CHẶN ODOO TỰ ĐỘNG SỬA GIỜ
    # =========================================================================

    request_unit_hours = fields.Boolean(
        string='Custom Hours',
        compute='_compute_request_unit_hours_custom',
        store=True,
        default=True
    )

    request_unit_half = fields.Boolean(
        string='Half Day',
        compute='_compute_request_unit_half_custom',
        store=True,
        default=False
    )

    request_hour_from = fields.Selection(
        selection=_HOUR_SELECTION,
        compute='_compute_fake_hours',
        store=True,
        readonly=False
    )
    request_hour_to = fields.Selection(
        selection=_HOUR_SELECTION,
        compute='_compute_fake_hours',
        store=True,
        readonly=False
    )

    @api.depends('request_unit_hours')
    def _compute_fake_hours(self):
        for rec in self:
            if not rec.request_hour_from:
                rec.request_hour_from = '0'
            if not rec.request_hour_to:
                rec.request_hour_to = '0'

    @api.depends('holiday_status_id')
    def _compute_request_unit_hours_custom(self):
        for leave in self:
            leave.request_unit_hours = True

    @api.depends('holiday_status_id')
    def _compute_request_unit_half_custom(self):
        for leave in self:
            leave.request_unit_half = False

    @api.depends('request_date_from_period', 'request_hour_from', 'request_hour_to',
                 'request_date_from', 'request_date_to',
                 'request_unit_half', 'request_unit_hours', 'employee_id')
    def _compute_date_from_to(self):
        for holiday in self:
            if holiday.date_from and holiday.date_to:
                continue
            pass

    # =========================================================================
    # 3. FIELD CUSTOM
    # =========================================================================
    leaves_taken_count = fields.Float(string='Số ngày phép đã nghỉ', compute='_compute_leave_stats')
    remaining_leaves_count = fields.Float(string='Số ngày phép còn lại', compute='_compute_leave_stats')
    my_history_ids = fields.Many2many('hr.leave', string='Các đơn báo của tôi', compute='_compute_my_history')

    request_date = fields.Date(string='Ngày làm đơn', default=fields.Date.context_today, readonly=True)
    report_title = fields.Char(string='Tiêu đề')
    employee_code = fields.Char(related='employee_id.employee_code', string='Mã NV', store=True)

    # [SỬA ĐỔI] Bỏ compute, bỏ store=True (vì mặc định là True), thêm readonly=True để user không tự chọn
    manager_id = fields.Many2one(
        'hr.employee',
        string='Người phê duyệt',
        readonly=True,
        help="Người thực tế đã bấm nút duyệt đơn này."
    )

    # =========================================================================
    # 4. LOGIC XỬ LÝ & FIX LỖI CREATE/WRITE
    # =========================================================================

    @api.onchange('date_from', 'date_to')
    def _onchange_custom_dates(self):
        for rec in self:
            rec.request_hour_from = '0'
            rec.request_hour_to = '0'

            if rec.date_from:
                rec.request_date_from = rec.date_from.date()
                if rec.date_to and rec.date_from > rec.date_to:
                    rec.date_to = rec.date_from
                    rec.request_date_to = rec.date_from.date()

            if rec.date_to:
                rec.request_date_to = rec.date_to.date()
                if rec.date_from and rec.date_to < rec.date_from:
                    rec.date_from = rec.date_to
                    rec.request_date_from = rec.date_to.date()

    @api.model
    def create(self, vals):
        if vals.get('date_from'):
            vals['request_date_from'] = fields.Datetime.to_datetime(vals['date_from']).date()
        if vals.get('date_to'):
            vals['request_date_to'] = fields.Datetime.to_datetime(vals['date_to']).date()

        vals['request_unit_hours'] = True
        vals['request_unit_half'] = False
        vals['request_hour_from'] = '0'
        vals['request_hour_to'] = '0'

        return super(HrLeave, self).create(vals)

    def write(self, vals):
        if len(self) == 1 and ('date_from' in vals or 'date_to' in vals):
            new_date_from_dt = vals.get('date_from') and fields.Datetime.to_datetime(
                vals['date_from']) or self.date_from
            new_date_to_dt = vals.get('date_to') and fields.Datetime.to_datetime(vals['date_to']) or self.date_to

            if new_date_from_dt and new_date_to_dt and new_date_from_dt > new_date_to_dt:
                if 'date_from' in vals:
                    new_date_to_dt = new_date_from_dt
                    vals['date_to'] = vals['date_from']
                elif 'date_to' in vals:
                    new_date_from_dt = new_date_to_dt
                    vals['date_from'] = vals['date_to']

            if new_date_from_dt:
                vals['request_date_from'] = new_date_from_dt.date()
            if new_date_to_dt:
                vals['request_date_to'] = new_date_to_dt.date()

        if 'date_from' in vals or 'date_to' in vals or 'request_date_from' in vals:
            vals['request_hour_from'] = '0'
            vals['request_hour_to'] = '0'

        return super(HrLeave, self).write(vals)

    # =========================================================================
    # [SỬA ĐỔI] 5. OVERRIDE HÀM DUYỆT ĐỂ GHI NHẬN NGƯỜI DUYỆT
    # =========================================================================

    def action_approve(self):
        """
        Duyệt lần 1 (nếu có cấu hình 2 bước) hoặc Duyệt luôn (nếu 1 bước)
        """
        res = super(HrLeave, self).action_approve()
        # Ghi nhận người đang đăng nhập (self.env.user) là người phê duyệt
        if self.env.user.employee_id:
            self.write({'manager_id': self.env.user.employee_id.id})
        return res

    def action_validate(self):
        """
        Duyệt lần 2 (nếu cấu hình 2 bước)
        """
        res = super(HrLeave, self).action_validate()
        # Ghi nhận người đang đăng nhập là người phê duyệt cuối cùng
        if self.env.user.employee_id:
            self.write({'manager_id': self.env.user.employee_id.id})
        return res

    # =========================================================================
    # 6. FIX WORK ENTRY CHỒNG LẤN
    # =========================================================================

    def _validate_leave_request(self):
        # 1. Chạy logic gốc
        res = super(HrLeave, self)._validate_leave_request()

        # 2. FIX: TỰ ĐỘNG REGENERATE WORK ENTRY
        sudo_we = self.env['hr.work.entry'].sudo()

        for leave in self:
            if leave.employee_id and leave.date_from and leave.date_to:
                d_from = leave.date_from.date()
                d_to = leave.date_to.date()

                to_remove = sudo_we.search([
                    ('employee_id', '=', leave.employee_id.id),
                    ('date_stop', '>=', d_from),
                    ('date_start', '<=', d_to),
                    ('state', '!=', 'validated')
                ])
                if to_remove:
                    to_remove.unlink()

                leave.employee_id.sudo().generate_work_entries(d_from, d_to, True)

        return res

    # =========================================================================
    # 7. CÁC HÀM COMPUTE KHÁC
    # =========================================================================
    @api.depends('employee_id', 'holiday_status_id', 'date_from')
    def _compute_leave_stats(self):
        for rec in self:
            rec.leaves_taken_count = 0.0
            rec.remaining_leaves_count = 0.0
            if rec.employee_id and rec.holiday_status_id:
                leave_type = rec.holiday_status_id.with_context(
                    employee_id=rec.employee_id.id,
                    date=rec.date_from or fields.Date.today()
                )
                rec.remaining_leaves_count = leave_type.virtual_remaining_leaves
                rec.leaves_taken_count = leave_type.leaves_taken

    @api.depends('employee_id')
    def _compute_my_history(self):
        for rec in self:
            if rec.employee_id:
                domain = [
                    ('employee_id', '=', rec.employee_id.id),
                    ('id', '!=', rec.id if rec.id else False)
                ]
                rec.my_history_ids = self.env['hr.leave'].search(domain, order='create_date desc', limit=10)
            else:
                rec.my_history_ids = False

