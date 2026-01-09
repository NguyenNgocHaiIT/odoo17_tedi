/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";

class CalendarTVDashboard extends Component {

    setup() {
        this.state = useState({
            time: "--:--:--",
            date: "",
            events: [],
            meetings: [],
        });

        onWillStart(() => this.loadData());

        onMounted(() => {
            // Đồng hồ realtime
            setInterval(() => {
                const now = new Date();
                this.state.time = now.toLocaleTimeString("vi-VN", {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                });
            }, 1000);

            // Auto refresh data (60s)
            setInterval(() => this.loadData(), 60000);
        });
    }

    async loadData() {
        const data = await rpc("/calendar/tv/data");
        this.state.date = data.date_today;
        this.state.events = data.events;
        this.state.meetings = data.meetings;
    }
}

CalendarTVDashboard.template = "calendar_tv_owl";
registry.category("actions").add("calendar_tv_owl", CalendarTVDashboard);
