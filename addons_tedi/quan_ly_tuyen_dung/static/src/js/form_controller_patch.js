/** @odoo-module */

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

// 1. Tạo một Controller mới kế thừa từ FormController gốc
class NoAutosaveFormController extends FormController {
    /**
     * Hàm này chạy khi người dùng rời khỏi form (bấm menu khác, breadcrumb...)
     */
    async beforeLeave() {
        // Nếu form có dữ liệu thay đổi (dirty)
        if (this.model.root.isDirty) {
            // Hiện thông báo xác nhận
            const confirmSave = confirm("Dữ liệu đã bị thay đổi.\n\n- Nhấn OK: Để LƯU và thoát.\n- Nhấn Cancel: Để KHÔNG LƯU và thoát.");

            if (confirmSave) {
                // Nếu chọn OK -> Lưu
                await this.model.root.save();
            } else {
                // Nếu chọn Cancel -> Hủy bỏ thay đổi (Revert) về trạng thái cũ
                await this.model.root.discard();
            }
        }
        // Sau khi xử lý xong (Lưu hoặc Hủy), cho phép rời đi
        return super.beforeLeave(...arguments);
    }
}

// 2. Tạo một View mới sử dụng Controller trên
export const noAutosaveFormView = {
    ...formView, // Copy toàn bộ tính năng của form view chuẩn
    Controller: NoAutosaveFormController, // Thay thế Controller bằng cái mới
};

// 3. Đăng ký vào hệ thống với tên 'no_autosave_form'
registry.category("views").add("no_autosave_form", noAutosaveFormView);