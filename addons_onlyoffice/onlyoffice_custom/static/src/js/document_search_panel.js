/** @odoo-module **/
import { DocumentsSearchPanel, DocumentsSearchPanelItemSettingsPopover } from "@documents/views/search/documents_search_panel";
import { patch } from "@web/core/utils/patch";

if (!DocumentsSearchPanelItemSettingsPopover.props.includes("onShare")) {
    DocumentsSearchPanelItemSettingsPopover.props.push("onShare");
}

patch(DocumentsSearchPanel.prototype, {

    async openEditPopover(ev, section, value, group) {
        const [resModel, resId] = this.getResModelResIdFromValueGroup(section, value, group);
        const target = ev.currentTarget || ev.target;
        const label = target.closest(".o_search_panel_label");
        const counter = label && label.querySelector(".o_search_panel_counter");

        this.popover.open(ev.target, {
            onEdit: () => {
                this.popover.close();
                this.state.showMobileSearch = false;
                this.editSectionValue(resModel, resId);
            },
            onCreateChild: () => {
                this.popover.close();
                this.addNewSectionValue(section, value || group);
            },
            createChildEnabled: this.supportedNewChildModels.includes(resModel),

            onShare: () => {
                this.popover.close();
                this.share_folder_onlyoffice(resId);
            }
        });

        target.classList.add("d-block");
        if (counter) {
            counter.classList.add("d-none");
        }
        this.onPopoverClose = () => {
            this.onPopoverClose = null;
            target.classList.remove("d-block");
            if (counter) {
                counter.classList.remove("d-none");
            }
        };
    },

    async share_folder_onlyoffice(folderId) {
        try {
            const action = await this.orm.call("documents.folder", "open_share_onlyoffice", [folderId]);
            if (action) {
                await this.action.doAction(action);
            }
        } catch (e) {
            this.notification.add("Lỗi khi Share!", { type: "danger" });
        }
    }
});