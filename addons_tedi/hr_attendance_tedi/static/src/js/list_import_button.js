/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";

console.log(">>> TEDI Import Button Activated <<<");


// NÚT IMPORT — OWL COMPONENT
export class ImportExcelButton extends Component {
    static template = xml/* xml */`
        <button class="btn btn-secondary" t-on-click="onClick">
            <i class="fa fa-upload"/> Import Excel
        </button>
    `;

    onClick() {
        this.env.services.action.doAction("action_tedi_attendance_import");
    }
}


// OVERRIDE LIST CONTROLLER
export class TediListController extends ListController {

    async setup() {
        super.setup();
    }

    // API CHUẨN OWL 17
    async onMounted() {
        super.onMounted?.();

        // Đợi ControlPanel render xong
        setTimeout(() => {
            const cp = document.querySelector(".o_control_panel_main_buttons .d-xl-inline-flex");
            if (cp) {
                const btn = new ImportExcelButton(null, { env: this.env });
                btn.mount(cp);
            }
        }, 50);
    }
}


// ĐĂNG KÝ VIEW
export const TediListView = {
    ...listView,
    Controller: TediListController,
};

registry.category("views").add("tedi_attendance_list", TediListView);
