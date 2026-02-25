/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useRef, onMounted, onWillUnmount, useEffect, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class PdfViewerReload extends Component {
    static template = "quan_ly_cong_van.PdfViewerReload";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.iframeRef = useRef("iframe");
        this.containerRef = useRef("container");
        this._isResizing = false;
        this._startY = 0;
        this._startHeight = 0;

        this.state = useState({
            lastAttachmentId: null,
            reloadCount: 0,
            height: 600,
            isFullscreen: false,
        });

        this._onMouseMove = this._onMouseMove.bind(this);
        this._onMouseUp = this._onMouseUp.bind(this);
        this._onFullscreenChange = this._onFullscreenChange.bind(this);

        onMounted(() => {
            this.loadPdf();
            document.addEventListener("fullscreenchange", this._onFullscreenChange);
        });

        onWillUnmount(() => {
            document.removeEventListener("mousemove", this._onMouseMove);
            document.removeEventListener("mouseup", this._onMouseUp);
            document.removeEventListener("fullscreenchange", this._onFullscreenChange);
        });

        useEffect(() => {
            const currentAttachmentId = this.props.record.data.attachment_id?.[0];
            if (currentAttachmentId !== this.state.lastAttachmentId) {
                this.state.lastAttachmentId = currentAttachmentId;
                this.state.reloadCount += 1;
                this.loadPdf();
            }
        }, () => [this.props.record.data.attachment_id?.[0]]);
    }

    _onFullscreenChange() {
        const isFs = !!document.fullscreenElement;
        this.state.isFullscreen = isFs;

        const container = this.containerRef.el;
        const pdfContainer = container?.querySelector(".pdf-container");
        const iframe = container?.querySelector("iframe");

        if (isFs) {
            if (pdfContainer) {
                pdfContainer.style.width = "100vw";
                pdfContainer.style.height = "100vh";
                pdfContainer.style.position = "fixed";
                pdfContainer.style.top = "0";
                pdfContainer.style.left = "0";
                pdfContainer.style.zIndex = "9999";
                pdfContainer.style.border = "none";
                pdfContainer.style.borderRadius = "0";
                pdfContainer.style.margin = "0";
            }
            if (iframe) {
                iframe.style.width = "100%";
                iframe.style.height = "100%";
            }
        } else {
            if (pdfContainer) {
                pdfContainer.style.width = "100%";
                pdfContainer.style.height = this.state.height + "px";
                pdfContainer.style.position = "relative";
                pdfContainer.style.top = "";
                pdfContainer.style.left = "";
                pdfContainer.style.zIndex = "";
                pdfContainer.style.border = "1px solid #ddd";
                pdfContainer.style.borderRadius = "4px 4px 0 0";
                pdfContainer.style.margin = "";
            }
            if (iframe) {
                iframe.style.width = "100%";
                iframe.style.height = "100%";
            }
        }
    }

    toggleFullscreen() {
        const el = this.containerRef.el;
        if (!document.fullscreenElement) {
            if (el.requestFullscreen) el.requestFullscreen();
            else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
            else if (el.msRequestFullscreen) el.msRequestFullscreen();
        } else {
            if (document.exitFullscreen) document.exitFullscreen();
            else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
            else if (document.msExitFullscreen) document.msExitFullscreen();
        }
    }

    onResizeStart(ev) {
        this._isResizing = true;
        this._startY = ev.clientY;
        this._startHeight = this.state.height;

        const iframe = this.iframeRef.el;
        if (iframe) iframe.style.pointerEvents = "none";

        document.addEventListener("mousemove", this._onMouseMove);
        document.addEventListener("mouseup", this._onMouseUp);
        ev.preventDefault();
    }

    _onMouseMove(ev) {
        if (!this._isResizing) return;
        const delta = ev.clientY - this._startY;
        this.state.height = Math.max(200, Math.min(1200, this._startHeight + delta));
    }

    _onMouseUp() {
        this._isResizing = false;
        const iframe = this.iframeRef.el;
        if (iframe) iframe.style.pointerEvents = "";
        document.removeEventListener("mousemove", this._onMouseMove);
        document.removeEventListener("mouseup", this._onMouseUp);
    }

    loadPdf() {
        if (!this.iframeRef.el) return;
        const attachmentId = this.props.record.data.attachment_id?.[0];
        if (!attachmentId) {
            this.iframeRef.el.src = "about:blank";
            return;
        }
        const url = `/web/content/${attachmentId}?t=${Date.now()}&unique=${this.state.reloadCount}`;
        this.iframeRef.el.src = url;
    }

    get hasContent() {
        return !!this.props.record.data.attachment_id?.[0];
    }
}

registry.category("fields").add("pdf_viewer_reload", {
    component: PdfViewerReload,
});