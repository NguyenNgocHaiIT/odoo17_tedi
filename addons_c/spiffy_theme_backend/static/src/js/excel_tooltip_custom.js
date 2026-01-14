/** @odoo-module **/
import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched } from "@odoo/owl";

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        onMounted(() => this.addExcelTooltips());
        onPatched(() => this.addExcelTooltips());
    },

    addExcelTooltips() {
        const table = this.tableRef?.el;
        if (!table || !table.closest('.excel_style_list_view')) return;

        // Thêm tooltip cho tất cả header cells
        const headers = table.querySelectorAll('thead th');
        headers.forEach(th => {
            // Lấy text từ nhiều nguồn khác nhau
            let fullText = '';

            // 1. Thử lấy từ title attribute (widget section_and_note_one2many có sẵn)
            if (th.hasAttribute('title') && th.getAttribute('title')) {
                fullText = th.getAttribute('title');
            }
            // 2. Thử lấy từ text-truncate
            else if (th.querySelector('.text-truncate')) {
                fullText = th.querySelector('.text-truncate').textContent.trim();
            }
            // 3. Thử lấy từ span/div bất kỳ
            else if (th.querySelector('span, div')) {
                fullText = th.querySelector('span, div').textContent.trim();
            }
            // 4. Lấy trực tiếp từ th
            else {
                fullText = th.textContent.trim();
            }

            // Thêm data-tooltip nếu có text
            if (fullText && fullText.length > 0) {
                th.setAttribute('data-tooltip', fullText);
            }
        });

    }
});