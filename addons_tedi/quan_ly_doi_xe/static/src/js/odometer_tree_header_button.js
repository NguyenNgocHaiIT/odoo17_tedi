/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { useService } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";

patch(ControlPanel.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");

        onMounted(() => {
            this._addExportButton();
        });
    },

    _addExportButton() {
        const action = this.env.config.action;
        if (!action) return;

        // CHỈ áp dụng cho action báo cáo Km tháng
        if (action.res_model !== "fleet.vehicle.odometer") return;
        if (action.xml_id !== "your_module.action_fleet_vehicle_odometer_monthly_report") return;

        const btnArea = this.el.querySelector(".o_cp_buttons");
        if (!btnArea || btnArea.querySelector(".o_btn_export_monthly")) return;

        const btn = document.createElement("button");
        btn.className = "btn btn-secondary o_btn_export_monthly";
        btn.innerText = "Xuất báo cáo";

        btn.addEventListener("click", () => this._onExport());

        btnArea.prepend(btn);
    },

    async _onExport() {
        // GỌI Y HỆT type="object" name="action_open_vehicle_report"
        await this.orm.call(
            "fleet.vehicle.odometer",
            "action_open_vehicle_report",
            [],
            { context: this.env.context }
        );
    },
});
