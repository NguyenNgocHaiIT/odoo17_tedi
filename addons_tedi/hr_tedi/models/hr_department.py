from odoo import  models , fields, api

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    # 1. Tạo field mới cho phép chọn nhiều người
    manager_ids = fields.Many2many(
        'hr.employee',
        'hr_department_manager_rel',  # Tên bảng trung gian
        'department_id',
        'employee_id',
        string="Ban Quản lý",
        help="Danh sách các quản lý của phòng ban này."
    )

    # 2. Logic đồng bộ: Khi chọn danh sách quản lý, tự động lấy người đầu tiên làm 'Trưởng phòng' (manager_id)
    # Việc này giúp Sơ đồ tổ chức và các luồng duyệt mặc định của Odoo vẫn chạy được.
    @api.onchange('manager_ids')
    def _onchange_manager_ids(self):
        if self.manager_ids:
            # Lấy người đầu tiên trong danh sách gán vào field gốc của Odoo
            self.manager_id = self.manager_ids[0]
        else:
            self.manager_id = False

    @api.depends('parent_path')
    def _compute_master_department_id(self):
        for department in self:
            if department.parent_path:
                # Chỉ convert nếu có dữ liệu
                department.master_department_id = int(department.parent_path.split('/')[0])
            else:
                # Nếu không có parent_path, coi chính nó là master hoặc để False
                department.master_department_id = department.id

    # (Tùy chọn) Đồng bộ ngược: Nếu người dùng sửa field manager_id gốc, cập nhật lại vào list
    @api.onchange('manager_id')
    def _onchange_manager_id(self):
        if self.manager_id:
            # Nếu người quản lý này chưa có trong list thì thêm vào
            if self.manager_id not in self.manager_ids:
                self.manager_ids = [(4, self.manager_id.id)]