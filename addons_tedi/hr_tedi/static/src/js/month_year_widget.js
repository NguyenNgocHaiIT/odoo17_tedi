/** @odoo-module **/

import { DateTimeField, dateField } from "@web/views/fields/datetime/datetime_field";
import { registry } from "@web/core/registry";
import { useDateTimePicker } from "@web/core/datetime/datetime_hook";
import { useState, onWillRender } from "@odoo/owl";

export class MonthPickerField extends DateTimeField {
    setup() {
        // Giữ nguyên phần setup đã chạy tốt của bạn
        const getPickerProps = () => {
            const value = this.getRecordValue();
            return {
                value,
                type: this.field.type,
                range: this.isRange(value),
                minPrecision: "months",
                maxPrecision: "decades",
            };
        };

        const dateTimePicker = useDateTimePicker({
            target: "root",
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

    /**
     * Ghi đè hàm hiển thị để định dạng lại chuỗi Tháng/Năm
     * @override
     */
    getFormattedValue(valueIndex) {
        const value = this.values[valueIndex];
        if (value) {
            // Trả về định dạng Tháng/Năm (ví dụ: 12/2025)
            // Lưu ý: value ở đây là đối tượng DateTime của luxon
            return value.toFormat("MM/yyyy");
        }
        return "";
    }
}

// Đăng ký widget
registry.category("fields").add("month_picker", {
    ...dateField,
    component: MonthPickerField,
});