/* @odoo-module */

import { Attachment } from "@mail/core/common/attachment_model";
import { patch } from "@web/core/utils/patch";

patch(Attachment.prototype, {
    get isDoc() {
        return this.mimetype.includes("msword");
    },
    get isDocx() {
        return this.mimetype.includes("officedocument.wordprocessingml.document");
    },
    get isPPT() {
        return this.mimetype.includes("ms-powerpoint");
    },
    get isPPTX() {
        return this.mimetype.includes("officedocument.presentationml.presentation");
    },
    get isXLS() {
        return this.mimetype.includes("ms-excel");
    },
    get isXLSX() {
        return this.mimetype.includes("officedocument.spreadsheetml.sheet");
    },

    get isOfficeFile() {
        return ((this.isDocx || this.isPPTX || this.isXLSX || this.isXLS) && !this.uploading);
    },

    get isVideo() {
        const videoMimeTypes = [
            "audio/mpeg", "audio/x-wav",
            "video/x-matroska", "video/mp4", "video/webm", "video/quicktime"
        ];
        return super.isVideo || videoMimeTypes.includes(this.mimetype);
    },

    get isViewable() {
        return this.isOfficeFile || super.isViewable;
    },

});
