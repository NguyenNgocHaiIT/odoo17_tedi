/** @odoo-module **/

import { DocumentsInspector } from "@documents/views/inspector/documents_inspector";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(DocumentsInspector.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.onOpenShareOnlyOffice = this.onOpenShareOnlyOffice.bind(this);
        this.user = useService("user");
    },

    showOnlyofficeButton(records) {
        if (this.user.userId != records[0].data.create_uid[0]) {
            return false
        }

        if (records.length !== 1) {
          return false
        }
        const ext = records[0].data.display_name.split(".").pop()
        return records.length === 1 && (this.onlyofficeCanEdit(ext) || this.onlyofficeCanView(ext))
    },

    open_only_office_share_doc(id){
        window.open(`/onlyoffice/share/${id}`, "_blank")
    },

    async onOpenShareOnlyOffice(id) {
        try {
            const action = await this.orm.call(
                "documents.document",
                "open_share_onlyoffice",
                [id]
            );

            if (action) {
                this.actionService.doAction(action);
            }
        } catch (error) {
            console.error("Lỗi khi gọi action share:", error);
        }
    }
});
