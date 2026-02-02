/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useRef, onMounted, useEffect, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class PdfViewerReload extends Component {
    static template = "quan_ly_cong_van.PdfViewerReload";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.iframeRef = useRef("iframe");
        this.state = useState({
            lastAttachmentId: null,
            reloadCount: 0
        });

        onMounted(() => {
            this.loadPdf();
        });

        // Sử dụng useEffect để theo dõi changes
        useEffect(() => {
            const currentAttachmentId = this.props.record.data.attachment_id?.[0];

            if (currentAttachmentId !== this.state.lastAttachmentId) {
                console.log('Attachment changed from', this.state.lastAttachmentId, 'to', currentAttachmentId);
                this.state.lastAttachmentId = currentAttachmentId;
                this.state.reloadCount += 1;
                this.loadPdf();
            }
        }, () => [
            // Theo dõi attachment_id
            this.props.record.data.attachment_id?.[0]
        ]);
    }

    loadPdf() {
        if (!this.iframeRef.el) return;

        const attachmentId = this.props.record.data.attachment_id?.[0];
        console.log('Loading PDF for attachment:', attachmentId, 'reload count:', this.state.reloadCount);

        if (!attachmentId) {
            this.iframeRef.el.src = "about:blank";
            return;
        }

        // Tạo URL với cache busting
        const url = `/web/content/${attachmentId}?t=${Date.now()}&unique=${this.state.reloadCount}`;

        // Set src trực tiếp
        this.iframeRef.el.src = url;

        // Force reload bằng cách thay đổi iframe
        this.iframeRef.el.onload = () => {
            console.log('PDF loaded successfully');
        };
    }

    get hasContent() {
        const has = !!this.props.record.data.attachment_id?.[0];
        console.log('hasContent:', has, 'attachment_id:', this.props.record.data.attachment_id);
        return has;
    }
}

registry.category("fields").add("pdf_viewer_reload", {
    component: PdfViewerReload,
});