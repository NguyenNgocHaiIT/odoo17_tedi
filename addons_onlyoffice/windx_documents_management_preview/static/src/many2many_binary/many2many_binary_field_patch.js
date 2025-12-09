/** @odoo-module */

import { registry } from "@web/core/registry";
import { Many2ManyBinaryField, many2ManyBinaryField } from "@web/views/fields/many2many_binary/many2many_binary_field";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(Many2ManyBinaryField.prototype, {

    setup() {
        super.setup(...arguments);
        this.fileViewer = useFileViewer();
        this.store = useService("mail.store");
    },

    getAttachments() {

        var attachments =  this.props.record.data[this.props.name].records.map((record) => {
            var attachment = this.store.Attachment.insert({
                id: record.resId,
                filename: record.data.name,
                name: record.data.name,
                mimetype: record.data.mimetype,
            });
            return attachment;
        });
        return attachments.filter((attachment) => attachment.isViewable);
    },

    getAttachment(id) {
        const record = this.props.record.data[this.props.name].records.find(
            (record) => record.resId === id
        );
        var attachment = this.store.Attachment.insert({
            id: record.resId,
            filename: record.data.name,
            name: record.data.name,
            mimetype: record.data.mimetype,
        });
        return attachment;
    },

});
