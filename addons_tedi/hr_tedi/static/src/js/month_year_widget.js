/** @odoo-module **/

import { DateTimeField, dateField } from "@web/views/fields/datetime/datetime_field";
import { registry } from "@web/core/registry";
import { useDateTimePicker } from "@web/core/datetime/datetime_hook";
import { useState, onWillRender } from "@odoo/owl";

export class MonthPickerField extends DateTimeField {
    // 1. Định nghĩa format chung
    get format() {
        return "MM/yyyy";
    }

    setup() {
        const getPickerProps = () => {
            const value = this.getRecordValue();
            return {
                value,
                type: this.field.type,
                range: this.isRange(value),
                format: this.format, // Format cho Popup
                minPrecision: "months",
                maxPrecision: "decades",
            };
        };

        const dateTimePicker = useDateTimePicker({
            target: "root",
            format: this.format, // Format cho ô Input khi đang nhập/click vào
            get pickerProps() {
                return getPickerProps();
            },
            onChange: () => {
                this.state.range = this.isRange(this.state.value);
            },
            onApply: () => {
                const toUpdate = {};
                if (Array.isArray(this.state.value)) {
                    [toUpdate[this.startDateField], toUpdate[this.endDateField]] = this.state.value;
                } else {
                    toUpdate[this.props.name] = this.state.value;
                }
                if (Object.keys(toUpdate).length) {
                    this.props.record.update(toUpdate);
                }
            },
        });

        this.state = useState(dateTimePicker.state);
        this.openPicker = dateTimePicker.open;

        onWillRender(() => this.triggerIsDirty());
    }

    // --- KHẮC PHỤC LỖI TẠI ĐÂY ---
    // Hàm này quyết định giá trị hiển thị sau khi render lại (lúc đã chọn xong)
    getFormattedValue(valueIndex) {
        const value = this.values[valueIndex];
        // value là object Luxon DateTime
        if (value && value.isValid) {
            return value.toFormat(this.format); // Ép hiển thị theo format MM/yyyy
        }
        return "";
    }
}

registry.category("fields").add("month_picker", {
    ...dateField,
    component: MonthPickerField,
});