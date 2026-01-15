/** @odoo-module **/

import { DocumentsKanbanRecord as KanbanRecordView } from "@documents/views/kanban/documents_kanban_record";
import { DocumentsKanbanRecord as KanbanRecordModel } from "@documents/views/kanban/documents_kanban_model";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

// Load OnlyOffice formats (same as inspector)
let formats = [];
const loadFormats = async () => {
    try {
        const response = await fetch("/onlyoffice_odoo/static/assets/document_formats/onlyoffice-docs-formats.json");
        formats = await response.json();
    } catch (error) {
        console.error("Error loading formats data:", error);
    }
};
loadFormats();

// ========================================
// PATCH 1: DocumentsKanbanRecord (View/Component)
// ========================================
patch(KanbanRecordView.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.user = useService("user");
    },

    /**
     * Check if extension can be edited in OnlyOffice
     */
    onlyofficeCanEdit(extension) {
        const format = formats.find((f) => f.name === extension.toLowerCase());
        return format && format.actions && format.actions.includes("edit");
    },

    /**
     * Check if extension can be viewed in OnlyOffice
     */
    onlyofficeCanView(extension) {
        const format = formats.find((f) => f.name === extension.toLowerCase());
        return format && format.actions && (format.actions.includes("view") || format.actions.includes("edit"));
    },

    /**
     * Check if document can show OnlyOffice button
     */
    showOnlyofficeButton(record) {
        if (!record) {
            return false;
        }
        const ext = record.data.display_name?.split(".").pop() || '';
        return this.onlyofficeCanEdit(ext) || this.onlyofficeCanView(ext);
    },

    /**
     * Check if document can be opened with OnlyOffice
     */
    canOpenWithOnlyOffice(record) {
        if (!record || record.data.type === 'empty') {
            return false;
        }
        return this.showOnlyofficeButton(record);
    },

    /**
     * Override onGlobalClick to handle OnlyOffice preview
     */
    async onGlobalClick(ev) {
        const CANCEL_GLOBAL_CLICK = ["a", ".dropdown", ".oe_kanban_action"].join(",");

        if (ev.target.closest(CANCEL_GLOBAL_CLICK)) {
            return;
        }

        const record = this.props.record;

        // Check if clicking on preview area
        if (ev.target.closest("div[name='document_preview']")) {
            // Check if it's OnlyOffice compatible but not default viewable
            if (!record.isViewable() && this.canOpenWithOnlyOffice(record)) {
                ev.stopPropagation();
                ev.preventDefault();

                // Call OnlyOffice editor
                await this.onlyofficeEditorUrl(record.data.id);
                return;
            }

            // Otherwise use default preview behavior
            record.onClickPreview(ev);
            if (ev.cancelBubble) {
                return;
            }
        }

        const options = {};
        if (ev.target.classList.contains("o_record_selector")) {
            options.isKeepSelection = true;
        }
        record.onRecordClick(ev, options);
    },

    /**
     * Open OnlyOffice Editor
     */
    async onlyofficeEditorUrl(id) {
        try {
            // Step 1: Check demo mode (30-day trial)
            const demo = JSON.parse(await this.env.services.orm.call("onlyoffice.odoo", "get_demo"));

            if (demo && demo.mode && demo.date) {
                const isValidDate = (d) => d instanceof Date && !isNaN(d);
                demo.date = new Date(Date.parse(demo.date));

                if (isValidDate(demo.date)) {
                    const today = new Date();
                    const difference = Math.floor((today - demo.date) / (1000 * 60 * 60 * 24));

                    if (difference > 30) {
                        this.notification.add(
                            this.env._t("The 30-day test period is over, you can no longer connect to demo ONLYOFFICE Docs server"),
                            {
                                title: this.env._t("ONLYOFFICE Docs server"),
                                type: "warning",
                            }
                        );
                        return;
                    }
                }
            }

            // Step 2: Check same_tab setting
            const { same_tab } = JSON.parse(await this.env.services.orm.call("onlyoffice.odoo", "get_same_tab"));

            if (same_tab) {
                // Open in current tab (client action)
                const action = {
                    params: { document_id: id },
                    tag: "onlyoffice_editor",
                    target: "current",
                    type: "ir.actions.client",
                };
                return this.actionService.doAction(action);
            }

            // Open in new tab (direct URL)
            window.open(`/onlyoffice/editor/document/${id}`, "_blank");
        } catch (error) {
            console.error("Error opening OnlyOffice editor:", error);
            this.notification.add(
                "Failed to open OnlyOffice editor. Please try again or contact administrator.",
                { type: "danger" }
            );
        }
    }
});

// ========================================
// PATCH 2: DocumentsKanbanRecord (Model)
// ========================================
patch(KanbanRecordModel.prototype, {
    /**
     * Check if extension can be edited in OnlyOffice
     */
    onlyofficeCanEdit(ext) {
        const format = formats.find((f) => f.name === ext?.toLowerCase());
        return format && format.actions && format.actions.includes("edit");
    },

    /**
     * Check if extension can be viewed in OnlyOffice
     */
    onlyofficeCanView(ext) {
        const format = formats.find((f) => f.name === ext?.toLowerCase());
        return format && format.actions && (format.actions.includes("view") || format.actions.includes("edit"));
    },

    /**
     * Override onClickPreview to handle OnlyOffice documents
     */
    async onClickPreview(ev) {
        const record = this;

        // Check if it's an OnlyOffice compatible document
        const ext = record.data.display_name?.split(".").pop()?.toLowerCase() || '';
        const canUseOnlyOffice = this.onlyofficeCanEdit(ext) || this.onlyofficeCanView(ext);

        // If it's OnlyOffice compatible and not default viewable,
        // skip default preview and let kanban record handle it
        if (canUseOnlyOffice && !this.isViewable()) {
            return;
        }

        // Otherwise use default behavior
        if (record.data.type === "empty") {
            ev.stopPropagation();
            ev.target.querySelector(".o_kanban_replace_document")?.click();
        } else if (this.isViewable()) {
            ev.stopPropagation();
            ev.preventDefault();
            const folder = this.model.env.searchModel
                .getFolders()
                .filter((folder) => folder.id === record.data.folder_id?.[0]);
            const hasPdfSplit =
                (!record.data.lock_uid || record.data.lock_uid[0] === this.model.user.userId) &&
                folder[0]?.has_write_access;
            const selection = this.model.root.selection;
            const documents = selection.length > 1 && selection.find(rec => rec === this) && selection.filter(rec => rec.isViewable()) || [this];
            await this.model.env.documentsView.bus.trigger("documents-open-preview", {
                documents,
                mainDocument: this,
                isPdfSplit: false,
                rules: record.data.available_rule_ids.records,
                hasPdfSplit,
            });
        }
    }
});