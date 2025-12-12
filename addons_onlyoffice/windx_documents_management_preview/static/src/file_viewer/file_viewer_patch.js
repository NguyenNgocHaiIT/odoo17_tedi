/* @odoo-module */

import { FileViewer } from "@web/core/file_viewer/file_viewer";
import { useRef, useEffect } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

patch(FileViewer.prototype, {
    setup() {
        super.setup();
        this.viewerMsOfficeRef = useRef("ViewerMsOffice");
        // Preview Office file: docx, pptx, xlsx
        useEffect(() => {
            if (this.viewerMsOfficeRef.el) {
                this.previewMsOffice(this.viewerMsOfficeRef.el);
            }
        });
        this.instancePreviewOffice = null;
    },

    async getFileFromUrl(url, name, defaultType = 'image/jpeg'){
        const blob = await (await fetch(url)).blob();
        return new File([blob], name, { type: blob.type || defaultType });
    },

    async previewMsOffice(rootElement) {
        var self = this;

        if (!this.state.file.isOfficeFile || !$.isFunction(window.createDocxJS)
            || !$.isFunction(window.createCellJS) || !$.isFunction(window.createSlideJS)) {
            this.close();
            return;
        }

        if (this.state.file.isDocx) {
            this.instancePreviewOffice = window.docxJS = window.createDocxJS();
            if (this.state.file.name.indexOf('.docx') === -1) this.state.file.name += '.docx';
        } else if (this.state.file.isXLSX) {
            this.instancePreviewOffice = window.cellJS = window.createCellJS();
            if (this.state.file.name.indexOf('.xlsx') === -1) this.state.file.name += '.xlsx';
        } else if (this.state.file.isPPTX) {
            this.instancePreviewOffice = window.slideJS = window.createSlideJS();
            if (this.state.file.name.indexOf('.pptx') === -1) this.state.file.name += '.pptx';
        } else if (this.state.file.isXLS) {
            this.instancePreviewOffice = window.cellJS = window.createCellJS();
             if (this.state.file.name.indexOf('.xls') === -1) this.state.file.name += '.xls';
             }

        if (this.instancePreviewOffice) {
            var file = await this.getFileFromUrl(this.state.file.defaultSource, this.state.file.name);
            this.instancePreviewOffice.parse(
                file,
                function () {
                    self.afterRender(file, rootElement);
                }, function (e) {
                    if(e.isError && e.msg){
                        alert(e.msg);
                    }
                    self.instancePreviewOffice.destroy(function(){
                        self.instancePreviewOffice = null;
                    });
                }, null
            );
        }
    },

    afterRender(file, element) {
        if (!$('#' + element.getAttribute('id')).length) {
            return;
        }
        $(element).css('height','calc(100% - 55px)');

        var endCallBackFn = function(result){
            if (result.isError) {
                // console.error("Error Render");
            }
        };

        if (this.state.file.isDocx) {
            window.docxAfterRender(element, endCallBackFn);
        } else if (this.state.file.isXLSX) {
            window.cellAfterRender(element, endCallBackFn);
        } else if (this.state.file.isPPTX) {
            window.slideAfterRender(element, endCallBackFn, 0);
        } else if (this.state.file.isXLS) {
            window.cellAfterRender(element, endCallBackFn);
        }
    },

});
