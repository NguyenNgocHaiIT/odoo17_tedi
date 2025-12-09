/** @odoo-module */

import { registry } from "@web/core/registry";
import { BinaryField, binaryField } from "@web/views/fields/binary/binary_field";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

import { useState, onWillStart, onWillRender } from "@odoo/owl";

export class BinaryFieldPreview extends BinaryField {
    static template = "windx_documents_management_preview.BinaryFieldPreview";

    setup() {
        super.setup(...arguments);
        this.fileViewer = useFileViewer();
        this.store = useService("mail.store");
        this.rpc = useService("rpc");
        this.state = useState({
            data_file: undefined,
            attachment: undefined,
        });
        onWillStart(async () => {
            this.getAttachmentInfo();
        });
        onWillRender(async () => {
            this.getAttachmentInfo();
        });
    }

    async getAttachmentInfo() {
        try {
            var data_file = await this.rpc("/get/attachment/details", {
                'res_id': this.props.record.resId,
                'model': this.props.record.resModel,
                'size': this.props.record.data[this.props.name],
                'res_field': this.props.name || this.props.fileNameField,
            });
            if (data_file) {
                var attachment = this.store.Attachment.insert({
                    id: data_file.id,
                    filename: data_file.name,
                    name: data_file.name,
                    mimetype: data_file.type,
                });
                this.state.data_file = data_file;
                this.state.attachment = attachment;
            } else {
                this.state.data_file = undefined;
                this.state.attachment = undefined;
            }
        } catch (e) {
            this.state.data_file = undefined;
            this.state.attachment = undefined;
        }
    }

    async previewAttachment() {
        if (this.state.attachment && this.state.attachment.isViewable) {
            this.fileViewer.open(this.state.attachment)
        }
        return;
    }

}

export const binaryFieldPreview = {
    ...binaryField,
    component: BinaryFieldPreview,
};

registry.category("fields").add("binary_attachment_preview", binaryFieldPreview);
