/** @odoo-module **/

import { CalendarController } from "@web/views/calendar/calendar_controller";
import { patch } from "@web/core/utils/patch";

patch(CalendarController.prototype, {
    get eventStartEditable() {
        return false;
    },

    get eventDurationEditable() {
        return false;
    },

    get eventResizableFromStart() {
        return false;
    },
});