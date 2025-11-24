/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

// Patch OWL 17
patch(FormRenderer.prototype, {
    _isFieldEditable(field) {
        const editable = this._super(field);
        if (!editable) return false;

        if (field.record && field.record.tt_vb && field.record.tt_vb.value !== 'draft') {
            return false;
        }
        return editable;
    },
});
