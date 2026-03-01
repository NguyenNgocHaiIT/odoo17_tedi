/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CalendarModel } from "@web/views/calendar/calendar_model";

console.log("🔥 calendar model patch loaded");

patch(CalendarModel.prototype, {
    get calendarOptions() {
        const options = super.calendarOptions;
        console.log("✅ calendar options from model", options);
        options.eventStartEditable = false;
        options.eventDurationEditable = false;
        return options;
    },
});