# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    # ========================================================
    # 1. FIELD NHÂN VIÊN (MỚI)
    # ========================================================

    # Tài xế hiện tại (Chọn Nhân viên)
    tedi_driver_employee_id = fields.Many2one(
        'hr.employee',
        string="Tài xế (Nhân viên)",
        help="Chọn nhân viên lái xe."
    )

    # Tài xế tiếp theo (Chọn Nhân viên) - THÊM MỚI
    tedi_future_driver_employee_id = fields.Many2one(
        'hr.employee',
        string="Tài xế tiếp theo (Nhân viên)",
        help="Chọn nhân viên dự kiến lái tiếp theo."
    )


    country_of_manufacture = fields.Many2one('res.country', string="Nước sản xuất")
    engine_no = fields.Char(string="Số máy")
    year_manufacture = fields.Char(string="Năm sản xuất")
    year_in_use = fields.Char(string="Năm đưa vào sử dụng")
    color_select = fields.Selection([
        ('red', 'Đỏ'), ('black', 'Đen'), ('blue', 'Xanh'),
        ('white', 'Trắng'), ('silver', 'Bạc')], string="Màu sơn")
    cylinder_capacity = fields.Char(string="Dung tích xilanh")
    original_cost = fields.Float(string="Nguyên giá TSCĐ")
    purchase_value = fields.Float(string="Giá trị mua")
    registration_fee = fields.Float(string="Lệ phí trước bạ")
    fuel_rate = fields.Char(string="Định mức nhiên liệu")
    oil_change_rate = fields.Char(string="Định mức thay dầu")

    trip_history_ids = fields.One2many('hr_tedi.vehicle.registration', 'assigned_vehicle_id', string="Lịch sử công tác")
    service_history_ids = fields.One2many('fleet.vehicle.log.services', 'vehicle_id', string="Lịch sử sửa chữa")

    # ========================================================
    # 2. LOGIC ĐỒNG BỘ (EMPLOYEE -> PARTNER)
    # ========================================================

    def _get_partner_from_employee(self, employee):
        """Hàm phụ trợ: Lấy Partner từ Employee"""
        if not employee:
            return False

        # Ưu tiên 1: Lấy từ tài khoản người dùng (User) liên kết
        if employee.user_id and employee.user_id.partner_id:
            return employee.user_id.partner_id

        # Ưu tiên 2: Lấy từ "Work Contact" (Liên hệ công việc - trường chuẩn Odoo 17)
        # Sử dụng getattr để an toàn, nếu không có trường này cũng không bị lỗi
        if getattr(employee, 'work_contact_id', False):
            return employee.work_contact_id

        # Ưu tiên 3: Lấy từ "Private Address" (Địa chỉ riêng) nếu có
        # Dùng getattr để tránh lỗi "AttributeError" như bạn vừa gặp
        if getattr(employee, 'address_home_id', False):
            return employee.address_home_id

        return False

    @api.onchange('tedi_driver_employee_id')
    def _onchange_tedi_driver_employee_id(self):
        # Khi chọn nhân viên TEDI -> Tự động điền vào Partner gốc
        self.driver_id = self._get_partner_from_employee(self.tedi_driver_employee_id)

    @api.onchange('tedi_future_driver_employee_id')
    def _onchange_tedi_future_driver_employee_id(self):
        self.future_driver_id = self._get_partner_from_employee(self.tedi_future_driver_employee_id)

    def _prepare_driver_vals(self, vals):
        """
        Kiểm tra vals, nếu có thay đổi nhân viên thì tự động tính toán lại Partner
        và cập nhật vào vals trước khi lưu.
        """
        # 1. Xử lý Tài xế chính
        if 'tedi_driver_employee_id' in vals:
            emp_id = vals.get('tedi_driver_employee_id')
            if emp_id:
                emp = self.env['hr.employee'].browse(emp_id)
                partner = self._get_partner_from_employee(emp)
                vals['driver_id'] = partner.id if partner else False
            else:
                # Nếu xóa nhân viên -> Xóa luôn driver_id
                vals['driver_id'] = False

        # 2. Xử lý Tài xế tiếp theo
        if 'tedi_future_driver_employee_id' in vals:
            emp_id = vals.get('tedi_future_driver_employee_id')
            if emp_id:
                emp = self.env['hr.employee'].browse(emp_id)
                partner = self._get_partner_from_employee(emp)
                vals['future_driver_id'] = partner.id if partner else False
            else:
                vals['future_driver_id'] = False

        return vals

    @api.model
    def create(self, vals):
        # 1. Chuẩn bị dữ liệu tài xế (Sync Employee -> Partner)
        vals = self._prepare_driver_vals(vals)

        # 2. Tạo xe
        vehicle = super(FleetVehicle, self).create(vals)

        # 3. Tạo Odometer log khởi tạo (nếu có nhập odometer ban đầu)
        initial_odometer = vals.get('odometer', 0.0)

        # Kiểm tra: Chỉ tạo nếu chưa có log nào (để tránh trùng lặp)
        Odometer = self.env['fleet.vehicle.odometer']
        if Odometer.search_count([('vehicle_id', '=', vehicle.id)]) == 0:
            today = fields.Date.today()
            Odometer.create({
                'vehicle_id': vehicle.id,
                'value': initial_odometer,
                'date': today,
                'report_type': 'log',  # Nên để 'log' để khớp với Selection chuẩn, hoặc thêm 'khoi_tao' vào selection
                'driver_id': vehicle.driver_id.id or False,
                'unit': 'kilometers',

                # --- Custom Fields ---
                'month': today.month,
                'year': today.year,
            })

        return vehicle

    def write(self, vals):
        """
        Hàm write mở rộng:
        1. Đồng bộ tài xế (Employee -> Partner).
        2. Nếu có sửa Odometer trên form xe -> Cập nhật tháng/năm cho log vừa sinh ra.
        """
        # 1. Chuẩn bị dữ liệu tài xế
        vals = self._prepare_driver_vals(vals)

        # 2. Gọi hàm gốc để lưu dữ liệu (Lúc này Odoo sẽ tự tạo log Odometer nếu 'odometer' thay đổi)
        res = super(FleetVehicle, self).write(vals)

        # 3. Xử lý bổ sung nếu Odometer thay đổi
        if 'odometer' in vals:
            today = fields.Date.today()
            # Tìm log odometer vừa được tạo ra bởi hàm super() ở trên
            # Logic: Tìm log của xe này, ngày hôm nay, sắp xếp mới nhất
            latest_log = self.env['fleet.vehicle.odometer'].search([
                ('vehicle_id', 'in', self.ids),
                ('date', '=', today),
                ('report_type', '=', 'log')  # Chỉ tìm log thường
            ], order='id desc', limit=1)

            if latest_log:
                # Cập nhật bổ sung Tháng/Năm cho log đó
                latest_log.write({
                    'month': today.month,
                    'year': today.year
                })

        return res


        return super(FleetVehicle, self).write(vals)

    def action_open_custom_odometer(self):
        self.ensure_one()
        # Lấy XML ID từ nút bấm (được truyền qua context ở file XML)
        xml_id = self.env.context.get('xml_id')
        if not xml_id:
            # Fallback nếu quên cấu hình ở XML
            xml_id = "quan_ly_doi_xe.action_fleet_vehicle_odometer_monthly_report"

        # Lấy Action từ DB
        action = self.env['ir.actions.act_window']._for_xml_id(xml_id)

        # --- [ĐOẠN FIX LỖI QUAN TRỌNG] ---
        # Lấy context gốc của Action (đang là dạng chuỗi text)
        context_str = action.get('context', '{}')

        # Dùng safe_eval để chuyển chuỗi thành Dict (xử lý được xuống dòng/khoảng trắng)
        if isinstance(context_str, str):
            context = safe_eval(context_str)
        else:
            context = context_str or {}
        # ---------------------------------

        # Cập nhật thêm context riêng của nút này
        context.update({
            'default_vehicle_id': self.id,
            'default_report_type': 'monthly',
            'group_by': False
        })

        # Gán ngược lại vào action
        action['context'] = context
        action['domain'] = [('vehicle_id', '=', self.id)]

        return action