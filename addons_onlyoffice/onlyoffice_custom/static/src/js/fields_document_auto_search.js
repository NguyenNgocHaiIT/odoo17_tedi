/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onMounted, useRef } from "@odoo/owl";

const fieldFilterAutoUpdate = {
    selector: 'field[name="field_filter"]',
    isInline: true,
    async start() {
        const orm = useService("orm");
        const model = this.el.closest('form').dataset.resModel;
        const recordId = this.el.closest('form').dataset.resId;

        // Debounce để tránh gọi quá nhiều lần
        let timeout = null;
        const debounceTime = 500; // 0.5 giây

        const handleInput = async () => {
            if (timeout) clearTimeout(timeout);

            timeout = setTimeout(async () => {
                try {
                    // Gọi action_filter_fields
                    await orm.call(model, 'action_filter_fields', [[recordId]]);

                    // Reload form để cập nhật field_docx_ids
                    this.el.form.querySelector('.o_form_button_save').click();
                    // Hoặc có thể reload toàn bộ form nếu cần
                    // window.location.reload();
                } catch (error) {
                    console.error("Error updating field filter:", error);
                }
            }, debounceTime);
        };

        // Gắn sự kiện
        this.el.addEventListener('input', handleInput);
    }
};

registry.category("form_compilers").add("field_filter_auto_update", fieldFilterAutoUpdate);