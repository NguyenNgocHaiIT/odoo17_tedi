# -*- coding: utf-8 -*-
from dateutil.utils import today
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from datetime import date
_logger = logging.getLogger(__name__) # Khai báo logger

class VehicleNoCarWizard(models.TransientModel):
    _name = 'vehicle.no.car.wizard'
    _description = 'Wizard báo hết xe'
    booking_option = fields.Selection([
        ('manager', 'Quản lý đặt xe bên ngoài'),
        ('unit', 'Đơn vị tự đặt xe bên ngoài')
    ], string="Phương án xử lý", required=True, default='manager')
    note = fields.Text(string="Ghi chú thêm")

    def action_confirm(self):
        self.ensure_one()
        active_id = self.env.context.get('active_id')
        if active_id:
            record = self.env['hr_tedi.vehicle.registration'].browse(active_id)

            # 1. Cập nhật thông tin
            record.write({
                'state': 'no_car',
                'external_booking_type': self.booking_option,
                'no_car_note': self.note
            })

            # 2. Ghi log chatter
            option_label = dict(self._fields['booking_option'].selection).get(self.booking_option)
            record.message_post(body=f"Báo hết xe. Phương án: {option_label}. Ghi chú: {self.note or 'Không'}")

            # 3. GỬI EMAIL & LOG KIỂM TRA
            template = self.env.ref('quan_ly_doi_xe.email_template_vehicle_registration_no_car',
                                    raise_if_not_found=False)

            if template:
                # --- TÍNH TOÁN EMAIL ---
                # Lấy email người nhận
                email_to = record.requester_id.work_email or record.requester_id.user_id.email or record.create_uid.email or False

                # Lấy email người gửi (User hiện tại đang bấm nút)
                email_from = self.env.user.email_formatted or self.env.company.email or 'unknown@example.com'

                # --- IN LOG RA MÀN HÌNH CONSOLE (Server Log) ---
                _logger.info("=" * 50)
                _logger.info(f"DEBUG EMAIL - ID Phiếu: {record.id}")
                _logger.info(f"TEMPLATE ID: {template.id}")
                _logger.info(f"FROM (Người gửi): {email_from}")
                _logger.info(f"TO (Người nhận): {email_to}")
                _logger.info("=" * 50)

                if email_to:
                    email_values = {'email_to': email_to}
                    # Thêm try-except để bắt lỗi SMTP nếu có ngay tại đây
                    try:
                        template.send_mail(record.id, force_send=True, email_values=email_values)
                        _logger.info(">>> Gửi lệnh Send Mail thành công!")
                    except Exception as e:
                        _logger.error(f">>> LỖI GỬI MAIL: {str(e)}")
                else:
                    _logger.warning(">>> KHÔNG TÌM THẤY EMAIL NGƯỜI NHẬN!")
            else:
                _logger.warning(">>> KHÔNG TÌM THẤY TEMPLATE XML!")

        return {'type': 'ir.actions.act_window_close'}


class HrTediVehicleRegistration(models.Model):
    _name = "hr_tedi.vehicle.registration"
    _description = "Phiếu đăng ký xe"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "code"
    _order = "start_date desc"

    # ========================================================
    # 1. CÁC TRƯỜNG DỮ LIỆU
    # ========================================================
    code = fields.Char(string="Mã phiếu", default="New", readonly=True)

    request_date = fields.Date(string="Ngày tạo", default=fields.Date.context_today)

    requester_id = fields.Many2one(
        'hr.employee',
        string="Người đề nghị",
        default=lambda self: self.env.user.employee_id,
        required=True,
        tracking=True
        # Đã xóa readonly=True để có thể xử lý điều kiện bên XML
    )


    def _default_can_edit_requester(self):
        return self.env.user.has_group('fleet.fleet_group_manager')

    # 2. Thêm default vào field boolean
    can_edit_requester = fields.Boolean(
        compute='_compute_can_edit_requester',
        default=_default_can_edit_requester, # <--- QUAN TRỌNG: Thêm dòng này
        store=False
    )

    @api.depends_context('uid')
    def _compute_can_edit_requester(self):
        is_manager = self.env.user.has_group('fleet.fleet_group_manager')
        for rec in self:
            rec.can_edit_requester = is_manager

    start_date = fields.Datetime(string="Thời gian bắt đầu", required=True, tracking=True)
    end_date = fields.Datetime(string="Thời gian kết thúc", required=True, tracking=True)
    trip_type = fields.Selection([('noi_thanh', 'Nội thành'), ('ngoai_thanh', 'Ngoại thành')], string="Loại công tác",
                                 required=True)
    destination = fields.Char(string="Địa điểm cụ thể", required=True, tracking=True)
    work_content = fields.Text(string="Nội dung công việc", required=True)
    num_passengers = fields.Integer(string="Số người đi kèm", default=1)
    attachment_ids = fields.Many2many('ir.attachment', string="Tệp đính kèm")

    assigned_vehicle_id = fields.Many2one(
        'fleet.vehicle', string="Phân công xe", tracking=True,
        domain="[('state_id.name', '=', 'Đã đăng kiểm')]"
    )


    tedi_driver_employee_id = fields.Many2one('hr.employee', string="Tài xế (Nhân viên)", tracking=True)
    driver_id = fields.Many2one('res.partner', string="Tài xế (Partner)", tracking=True)

    distance_km = fields.Float(string="Số km thực tế đi được", tracking=True)

    rating = fields.Selection([
        ('0', 'Chưa đánh giá'),
        ('1', 'Rất tệ'), ('2', 'Tệ'), ('3', 'Bình thường'), ('4', 'Tốt'), ('5', 'Tuyệt vời')
    ], string='Đánh giá sao', default='0', tracking=True)
    feedback_comment = fields.Text(string="Ý kiến đóng góp", tracking=True)

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Chờ duyệt'),
        ('approved', 'Chờ xếp xe'),
        ('refused', 'Từ chối'),
        ('assigned', 'Đã phân xe'),
        ('waiting_return', 'Chờ trả xe'),
        ('no_car', 'Hết xe'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    external_booking_type = fields.Selection([
        ('manager', 'Quản lý đặt xe bên ngoài'),
        ('unit', 'Đơn vị tự đặt xe bên ngoài')
    ], string="Phương án khi hết xe", readonly=True)

    no_car_note = fields.Text(string="Ghi chú báo hết xe", readonly=True)

    calendar_title = fields.Char(
        string="Hiển thị trên lịch",
        compute='_compute_calendar_title'
    )

    @api.depends('state', 'code', 'assigned_vehicle_id', 'tedi_driver_employee_id', 'driver_id',
                 'external_booking_type')
    def _compute_calendar_title(self):
        for rec in self:
            # =========================================================
            # NHÓM 1: ĐÃ CÓ XE (Assigned, Waiting Return, Done)
            # =========================================================
            if rec.assigned_vehicle_id:
                # 1. Biển số (Ưu tiên số 1)
                plate = rec.assigned_vehicle_id.license_plate or 'Đang cập nhật'

                # 2. Hãng xe
                brand = rec.assigned_vehicle_id.model_id.brand_id.name or ''

                # 3. Tên lái xe (Lấy tên tắt cho ngắn gọn)
                # Ví dụ: "Nguyễn Văn A" -> hiển thị "A" hoặc giữ nguyên tùy ý
                driver_full_name = rec.tedi_driver_employee_id.name or rec.driver_id.name or 'Chưa có TX'

                # Tạo chuỗi: "30A-123.45 (Toyota - Tài xế A)"
                # Tôi đưa Biển số lên đầu vì trên Lịch nó quan trọng nhất để phân biệt
                detail_parts = [brand, driver_full_name]
                detail_str = " - ".join(filter(None, detail_parts))

                rec.calendar_title = f"{plate} ({detail_str})"

            # =========================================================
            # NHÓM 2: CÁC TRẠNG THÁI KHÁC (Chưa có xe / Hủy / ...)
            # =========================================================
            elif rec.state == 'no_car':
                # Hết xe: Hiển thị phương án xử lý (Tự đặt / VP đặt)
                # Lấy nhãn hiển thị của selection field thay vì key 'manager/unit'
                booking_label = dict(rec._fields['external_booking_type'].selection).get(
                    rec.external_booking_type) or 'Ngoài'
                rec.calendar_title = f"HẾT XE: {booking_label}"

            elif rec.state == 'approved':
                rec.calendar_title = "CHỜ XẾP XE"  # Đã duyệt, đang đợi văn phòng gán xe

            elif rec.state == 'submitted':
                rec.calendar_title = "CHỜ DUYỆT"  # Lãnh đạo chưa duyệt

            elif rec.state == 'draft':
                rec.calendar_title = "NHÁP"

            elif rec.state == 'refused':
                rec.calendar_title = "ĐÃ TỪ CHỐI"

            elif rec.state == 'cancel':
                rec.calendar_title = "ĐÃ HỦY"

            else:
                # Fallback cho các trường hợp lạ
                rec.calendar_title = "ĐANG XỬ LÝ"

    @api.depends('code', 'calendar_title')
    def _compute_display_name(self):
        for rec in self:
            # Format: [Mã phiếu] Thông tin xe
            # Ví dụ: [DX/2025/001] Toyota - 30A.12345 - Nguyễn Văn A
            if rec.calendar_title:
                rec.display_name = f" {rec.calendar_title} [{rec.code}]"
            else:
                rec.display_name = rec.code or "New"
    # ========================================================
    # 2. LOGIC TỰ ĐỘNG
    # ========================================================
    def _get_partner_from_employee(self, employee):
        if not employee: return False
        if employee.user_id and employee.user_id.partner_id: return employee.user_id.partner_id
        if getattr(employee, 'work_contact_id', False): return employee.work_contact_id
        if getattr(employee, 'address_home_id', False): return employee.address_home_id
        return False

    @api.onchange('tedi_driver_employee_id')
    def _onchange_tedi_driver_employee_id(self):
        self.driver_id = self._get_partner_from_employee(self.tedi_driver_employee_id)

    @api.onchange('assigned_vehicle_id')
    def _onchange_assigned_vehicle_id(self):
        if self.assigned_vehicle_id:
            if hasattr(self.assigned_vehicle_id,
                       'tedi_driver_employee_id') and self.assigned_vehicle_id.tedi_driver_employee_id:
                self.tedi_driver_employee_id = self.assigned_vehicle_id.tedi_driver_employee_id
                self._onchange_tedi_driver_employee_id()
            elif self.assigned_vehicle_id.driver_id:
                self.driver_id = self.assigned_vehicle_id.driver_id

    @api.model
    def create(self, vals):
        # current_employee = self.env.user.employee_id
        # if not current_employee: raise ValidationError("Tài khoản chưa liên kết hồ sơ Nhân viên.")
        # vals['requester_id'] = current_employee.id
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('hr_tedi.vehicle.registration') or 'New'
        if vals.get('tedi_driver_employee_id') and not vals.get('driver_id'):
            emp = self.env['hr.employee'].browse(vals['tedi_driver_employee_id'])
            partner = self._get_partner_from_employee(emp)
            if partner: vals['driver_id'] = partner.id
        return super(HrTediVehicleRegistration, self).create(vals)

    # ========================================================
    # 3. ACTIONS
    # ========================================================

    def action_submit(self):
        self.ensure_one()
        if not self.start_date or not self.end_date: raise ValidationError("Nhập đủ thời gian.")
        if self.start_date >= self.end_date: raise ValidationError("Thời gian kết thúc phải lớn hơn bắt đầu.")
        self.state = 'submitted'
        self.message_post(body="Đã gửi yêu cầu.")

    def action_fleet_approve(self):
        self.ensure_one()
        self.state = 'approved'
        self.message_post(body=f"Đã tiếp nhận bởi {self.env.user.name}.")

    def action_fleet_refuse(self):
        self.ensure_one()
        self.state = 'refused'
        self.message_post(body=f"Từ chối bởi {self.env.user.name}.")

    def action_office_assign(self):
        self.ensure_one()
        if self.state != 'approved': raise ValidationError("Phiếu chưa được duyệt.")
        if not self.assigned_vehicle_id: raise ValidationError("Chưa chọn xe.")

        domain = [('id', '!=', self.id), ('assigned_vehicle_id', '=', self.assigned_vehicle_id.id),
                  ('state', 'in', ['assigned', 'waiting_return', 'done']),
                  ('start_date', '<', self.end_date), ('end_date', '>', self.start_date)]
        if self.search(domain):
            raise ValidationError(f"Xe {self.assigned_vehicle_id.license_plate} bị trùng lịch!")

        if not self.tedi_driver_employee_id and hasattr(self.assigned_vehicle_id,
                                                        'tedi_driver_employee_id') and self.assigned_vehicle_id.tedi_driver_employee_id:
            self.tedi_driver_employee_id = self.assigned_vehicle_id.tedi_driver_employee_id
            self._onchange_tedi_driver_employee_id()
        if not self.driver_id: raise ValidationError("Chưa có thông tin tài xế.")

        if self.assigned_vehicle_id:
            vals_update = {'driver_id': self.driver_id.id}
            if hasattr(self.assigned_vehicle_id, 'tedi_driver_employee_id'):
                vals_update['tedi_driver_employee_id'] = self.tedi_driver_employee_id.id
            self.assigned_vehicle_id.write(vals_update)

        self.state = 'assigned'
        self.message_post(body=f"Đã phân xe: {self.assigned_vehicle_id.license_plate}.")

    def action_send_feedback(self):
        """Bước 1: Người dùng đánh giá xong -> Chuyển sang chờ trả xe"""
        self.ensure_one()
        if self.rating == '0':
            raise ValidationError("Vui lòng chọn số sao để đánh giá chuyến đi.")

        self.state = 'waiting_return'
        rating_label = dict(self._fields['rating'].selection).get(self.rating)
        self.message_post(body=f"Người dùng đã đánh giá: {rating_label}. Đang chờ Văn phòng xác nhận xe về.")

    def action_confirm_return(self):
        self.ensure_one()
        # 1. Check quyền
        if not self.env.user.has_group('fleet.fleet_group_user') and not self.env.user.has_group('base.group_system'):
            raise AccessError("Chỉ bộ phận Quản lý đội xe mới được xác nhận hoàn thành.")

        if not self.attachment_ids:
            raise ValidationError("Vui lòng thêm đính kèm xác nhận hoàn thành.")

        if self.distance_km <= 0:
            raise ValidationError("Vui lòng nhập 'Số km thực tế đi được' trước khi xác nhận.")

        # ==========================================================================
        # 2. TÍNH TOÁN SỐ LIỆU
        # ==========================================================================
        # Lấy số Odometer hiện tại trên hệ thống (coi như là số đầu của chuyến này)
        current_odometer = self.assigned_vehicle_id.odometer

        # Số Odometer mới (Sau khi cộng chuyến này)
        new_odometer_value = current_odometer + self.distance_km

        trip_month = self.end_date.month
        trip_year = self.end_date.year

        # ==========================================================================
        # 3. CẬP NHẬT BÁO CÁO THÁNG
        # ==========================================================================
        # Tìm báo cáo tháng hiện tại
        report = self.env['fleet.vehicle.odometer'].search([
            ('vehicle_id', '=', self.assigned_vehicle_id.id),
            ('month', '=', trip_month),
            ('year', '=', trip_year),
            ('report_type', '=', 'monthly')
        ], limit=1)

        if not report:
            # === TRƯỜNG HỢP 1: TẠO MỚI (Chưa có báo cáo tháng này) ===
            # Km chạy trong tháng = Chính là km của chuyến này
            km_total_month = self.distance_km

            # Số đầu kỳ của báo cáo = Số hiện tại (trước khi cộng chuyến này)
            # Lưu ý: Logic này đúng nếu đây là chuyến đầu tiên trong tháng được ghi nhận
            start_val = current_odometer

            report = self.env['fleet.vehicle.odometer'].create({
                'vehicle_id': self.assigned_vehicle_id.id,
                'month': trip_month,
                'year': trip_year,
                'report_type': 'monthly',
                'date': self.end_date.date(),
                'driver_id': self.driver_id.id,

                'odometer_start': start_val,  # Số đầu kỳ
                'value': new_odometer_value,  # Số cuối kỳ

                # --- SỬA TÊN TRƯỜNG KHỚP VỚI CODE BẠN GỬI ---
                'odometer_total': km_total_month,  # Tổng km hoạt động
            })
        else:
            # === TRƯỜNG HỢP 2: CẬP NHẬT (Đã có báo cáo) ===
            # Logic: Tổng km tháng = (Số cuối mới) - (Số đầu kỳ đã lưu)
            # Ta không cộng dồn thủ công mà lấy (Cuối - Đầu) cho chính xác tuyệt đối
            km_total_month = new_odometer_value - report.odometer_start

            report.write({
                'value': new_odometer_value,  # Cập nhật số cuối
                'odometer_total': km_total_month,  # Cập nhật tổng chạy
                'date': self.end_date.date(),  # Cập nhật ngày mới nhất
                'driver_id': self.driver_id.id
            })

        # Bước 4: Chuyển trạng thái phiếu về Done
        self.state = 'done'

        # Bước 5 (Tùy chọn): Gọi hàm tính toán lại của Odoo để đồng bộ hóa nếu cần
        # Hàm này trong model fleet.vehicle.odometer sẽ quét lại toàn bộ các phiếu 'done' để tính tổng
        # Việc gọi lại ở đây giúp đảm bảo số liệu chắc chắn khớp với danh sách phiếu
        if hasattr(report, 'action_calculate_data'):
            report.action_calculate_data()

        self.message_post(body=f"Xe về kho. Odoo mới: {new_odometer_value}. Tổng tháng: {km_total_month}.")

    def action_office_no_car(self):
        self.ensure_one()
        if not self.env.user.has_group('fleet.fleet_group_user'):
            raise AccessError("Quyền hạn không hợp lệ.")

        # Mở Wizard thay vì đổi state ngay lập tức
        return {
            'name': 'Xác nhận báo hết xe',
            'type': 'ir.actions.act_window',
            'res_model': 'vehicle.no.car.wizard',
            'view_mode': 'form',
            'target': 'new',  # Quan trọng: Mở dạng Popup
            'context': {'active_id': self.id}  # Truyền ID phiếu sang Wizard
        }

    def action_draft(self):
        self.state = 'draft'