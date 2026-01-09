/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";

patch(ListRenderer.prototype, {
    getRowClass(record) {
        const classes = super.getRowClass ? super.getRowClass(record) : "";

        // Lấy giá trị trường tt_vb (selection field)
        const tt_vb = record.data.tt_vb;

        if (['phat_hanh', 'cho_xu_ly'].includes(tt_vb)) {
            return `${classes} soft-green-row`;;     // Nền xanh lá + chữ đen
        }
        if (['cho_duyet', 'da_duyet'].includes(tt_vb)) {
            return `${classes} soft-yellow-row`;;       // Nền vàng + chữ đen
        }
        if (['cho_but_phe'].includes(tt_vb)){
            return `${classes} soft-red-row`;; //nền đỏ, chữ đen
        }
        return classes;
    }
});