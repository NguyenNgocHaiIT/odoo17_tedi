/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

patch(FormRenderer, {  // <- trực tiếp class + object patch
    isFieldEditable(fieldInfo) {
        const record = this.props.record;
        if (record?.data?.tt_vb && record.data.tt_vb !== 'draft') {
            return false;  // chặn tất cả field
        }
        return super.isFieldEditable?.(fieldInfo) ?? true;
    },

    isX2ManyEditable() {
        const record = this.props.record;
        if (record?.data?.tt_vb && record.data.tt_vb !== 'draft') {
            return false; // chặn One2many/Many2many
        }
        return super.isX2ManyEditable?.() ?? true;
    }

});
