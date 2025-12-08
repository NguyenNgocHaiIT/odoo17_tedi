/** @odoo-module **/
import { Dialog } from "@web/core/dialog/dialog";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ConflictResolverDialog extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.title = "Giải quyết xung đột";
    }

    formatDateTime(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) +
               ' ' + date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
    }

    getTextColorClass(colorIndex) {

        const lightColors = [0, 3, 7];

        const colorId = parseInt(colorIndex);

        if (lightColors.includes(colorId)) {
            return "text-dark"; // Chữ đen
        }
        return "text-white"; // Chữ trắng (cho các màu đỏ, xanh đậm, cam...)
    }

    async onAccept(entryId) {
        try {
            await this.orm.call("hr.work.entry", "action_resolve_conflict_git_style", [[entryId]]);
            this.notification.add("Đã giải quyết xung đột thành công!", { type: "success" });
            this.props.close();
            this.props.onResolved();
        } catch (error) {
            this.notification.add("Lỗi: " + error.message, { type: "danger" });
        }
    }
}

ConflictResolverDialog.template = "tedi.ConflictResolverDialog";
ConflictResolverDialog.components = { Dialog };