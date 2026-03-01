/** @odoo-module **/

import { DocumentsSearchPanel } from "@documents/views/documents_search_panel";

export class CustomDocumentsSearchPanel extends DocumentsSearchPanel {
    static template = "documents.SearchPanel";
    static subTemplates = DocumentsSearchPanel.subTemplates;

    // Ghi đè phương thức render để thêm nút tùy chỉnh
    setup() {
        super.setup();

        // Ghi đè template phụ category để thêm nút của chúng ta
        this.constructor.subTemplates = {
            ...this.constructor.subTemplates,
            category: "custom_documents.SearchPanel.Category",
        };
    }
}

// Đăng ký extension mới
CustomDocumentsSearchPanel.modelExtension = "DocumentsSearchPanel";