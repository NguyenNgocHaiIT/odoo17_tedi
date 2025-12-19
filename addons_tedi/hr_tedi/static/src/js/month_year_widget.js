/** @odoo-module **/

import { DateTimeField, dateField } from "@web/views/fields/datetime/datetime_field";
import { registry } from "@web/core/registry";
import { useDateTimePicker } from "@web/core/datetime/datetime_hook";
import { useState, onWillRender } from "@odoo/owl";

export class MonthPickerField extends DateTimeField {
    setup() {
        // KHÔNG gọi super.setup() vì nó sẽ khởi tạo hook mặc định chọn ngày

        const getPickerProps = () => {
            const value = this.getRecordValue();
            return {
                value,
                type: this.field.type,
                range: this.isRange(value),
                minPrecision: "months", // Ép buộc mức tối thiểu là tháng
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

        // Đảm bảo vẫn đăng ký sự kiện kiểm tra thay đổi dữ liệu (Dirty check)
        onWillRender(() => this.triggerIsDirty());
    }

    getFormattedValue(valueIndex) {
        const value = this.values[valueIndex];
        if (value && value.isValid) {
            return value.toFormat("MM/yyyy");
        }
        return "";
    }
}

registry.category("fields").add("month_picker", {
    ...dateField,
    component: MonthPickerField,
});