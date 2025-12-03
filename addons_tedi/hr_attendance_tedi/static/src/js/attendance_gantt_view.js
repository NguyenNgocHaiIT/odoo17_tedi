/** @odoo-module **/
//==================BASE=============================
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

// =========================================================
// COMPONENT: DIALOG LỰA CHỌN (POPUP)
// =========================================================
class AttendanceActionDialog extends Component {
    onSelectAttendance() { this.props.onChoice('attendance'); this.props.close(); }
    onSelectLeave() { this.props.onChoice('leave'); this.props.close(); }
}
AttendanceActionDialog.template = xml`
    <Dialog title="props.title" size="'sm'">
        <t t-set-slot="footer"><span class="d-none">Empty Footer</span></t>
        <div class="bg-white">
            <div class="text-center py-3 border-bottom bg-light">
                <span class="text-muted small text-uppercase fw-bold" style="font-size: 0.75rem; letter-spacing: 1px;">Ngày đã chọn</span>
                <div class="h4 m-0 mt-1 text-dark fw-bolder"><t t-esc="props.dateStr"/></div>
            </div>
            <div class="d-flex p-4 gap-3 justify-content-center">
                <t t-if="props.isManager">
                    <button class="btn btn-light border p-3 shadow-sm d-flex flex-column align-items-center gap-2 flex-fill" t-on-click="onSelectAttendance">
                        <div class="rounded-circle bg-primary bg-opacity-10 text-primary d-flex align-items-center justify-content-center mb-1" style="width: 48px; height: 48px;"><i class="fa fa-clock-o fa-2x"/></div>
                        <span class="fw-bold text-dark small">Chấm công</span>
                    </button>
                </t>
                <button class="btn btn-light border p-3 shadow-sm d-flex flex-column align-items-center gap-2 flex-fill" t-on-click="onSelectLeave">
                    <div class="rounded-circle bg-warning bg-opacity-10 text-warning d-flex align-items-center justify-content-center mb-1" style="width: 48px; height: 48px;"><i class="fa fa-plane fa-2x"/></div>
                    <span class="fw-bold text-dark small">Xin nghỉ</span>
                </button>
            </div>
        </div>
    </Dialog>
`;
AttendanceActionDialog.components = { Dialog };

// =========================================================
// COMPONENT: MAIN GANTT VIEW
// =========================================================
export class AttendanceGantt extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.dialogService = useService("dialog");
        this.userService = useService("user");

        this.display = { controlPanel: true };

        const today = new Date();
        const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
        const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0);

        this.state = useState({
            mode: "month",
            startDate: startOfMonth,
            endDate: endOfMonth,
            inputStart: this.formatDateInput(startOfMonth),
            days: [],
            hours: Array.from({ length: 24 }, (_, i) => i),
            viewLabel: "",
            rowsData: [],
            weekBars: {},
            currentUserEmployeeId: null,
            isManager: false,
        });

        // Cache lưu cấu hình lịch: { calendar_id: { day_index: [ {start:8, end:12}, {start:13, end:17} ] } }
        this.calendarCache = {};
        this.employeeCalendarMap = {};

        onWillStart(async () => {
            const isAttendanceOfficer = await this.userService.hasGroup("hr_attendance.group_hr_attendance_user");
            const isLeaveOfficer = await this.userService.hasGroup("hr_holidays.group_hr_holidays_user");
            this.state.isManager = isAttendanceOfficer || isLeaveOfficer;

            const employees = await this.orm.searchRead(
                "hr.employee",
                [["user_id", "=", this.userService.userId]],
                ["id"],
                { limit: 1 }
            );

            if (employees.length > 0) {
                this.state.currentUserEmployeeId = employees[0].id;
            }

            await this.reloadData();
        });
    }

    canEditRow(targetEmployeeId) {
        if (this.state.isManager) return true;
        return this.state.currentUserEmployeeId && this.state.currentUserEmployeeId === targetEmployeeId;
    }

    // --- Navigation ---
    goPrev = async () => { await this.shiftPeriod(-1); };
    goNext = async () => { await this.shiftPeriod(1); };
    goToToday = async () => {
        const today = new Date(); today.setHours(0, 0, 0, 0);
        if (this.state.mode === "day") { this.state.startDate = today; this.state.endDate = today; }
        else if (this.state.mode === "week") {
            const monday = this.getStartOfWeek(today); this.state.startDate = monday;
            const end = new Date(monday); end.setDate(monday.getDate() + 6); this.state.endDate = end;
        } else {
            this.state.startDate = new Date(today.getFullYear(), today.getMonth(), 1);
            this.state.endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        }
        this.state.inputStart = this.formatDateInput(this.state.startDate);
        await this.reloadData();
    };

    formatDateInput(date) {
        const y = date.getFullYear(); const m = String(date.getMonth() + 1).padStart(2, "0");
        const d = String(date.getDate()).padStart(2, "0"); return `${y}-${m}-${d}`;
    }
    formatDateKey(date) { return this.formatDateInput(date); }
    getStartOfWeek(date) {
        const d = new Date(date); const day = d.getDay();
        const diff = d.getDate() - day + (day === 0 ? -6 : 1);
        const monday = new Date(d.setDate(diff)); monday.setHours(0, 0, 0, 0); return monday;
    }

    // =========================================================================
    // LOGIC TÁCH CA TỪ CẤU HÌNH ODOO (Resource Calendar)
    // =========================================================================

    /**
     * Lấy danh sách ca làm việc trong ngày (Bỏ qua giờ nghỉ trưa)
     */
    getWorkIntervalsFromConfig(employeeId, date) {
        const calendarId = this.employeeCalendarMap[employeeId];
        // Nếu không có lịch, fallback về mặc định hành chính
        if (!calendarId || !this.calendarCache[calendarId]) {
            return [{start: 8, end: 12}, {start: 13, end: 17}];
        }

        // Chuyển đổi JS Day (0=Sun, 1=Mon) -> Odoo Day (0=Mon, 6=Sun)
        const jsDay = date.getDay();
        const odooDay = jsDay === 0 ? 6 : jsDay - 1;

        const dayConfig = this.calendarCache[calendarId][odooDay];
        if (!dayConfig || dayConfig.length === 0) {
            return []; // Ngày nghỉ
        }
        return dayConfig;
    }

    getShiftIntervals(start, end, employeeId, type = 'attendance') {
        if (type !== 'attendance') return [{ start, end }];

        const workIntervals = this.getWorkIntervalsFromConfig(employeeId, start);
        // Nếu không có lịch hoặc chỉ có 1 ca xuyên suốt -> không tách
        if (!workIntervals.length || workIntervals.length < 2) return [{ start, end }];

        // Sắp xếp các ca làm việc (Sáng trước, Chiều sau)
        workIntervals.sort((a, b) => a.start - b.start);

        // Tìm "Khoảng nghỉ trưa" (Gap) giữa các ca làm việc
        // Gap = Kết thúc ca 1 -> Bắt đầu ca 2
        // Thường lấy ca đầu tiên và ca thứ 2 (Sáng/Chiều)
        const breakStartVal = workIntervals[0].end;   // VD: 12.0
        const breakEndVal = workIntervals[1].start;   // VD: 13.0

        // Chuyển giờ chấm công thực tế sang số float (VD: 08:30 -> 8.5)
        const startFloat = start.getHours() + start.getMinutes() / 60;
        let endFloat = end.getHours() + end.getMinutes() / 60;
        if (end.getDate() !== start.getDate()) endFloat = 24;

        // KIỂM TRA: Nếu giờ làm việc "băng qua" khoảng nghỉ trưa
        // Tức là: Vào làm trước khi nghỉ trưa VÀ ra về sau khi hết nghỉ trưa
        if (startFloat < breakStartVal && endFloat > breakEndVal) {
            const segments = [];

            // Ca 1: Từ lúc vào -> Đến giờ nghỉ trưa (VD: 08:00 -> 12:00)
            const s1 = new Date(start);
            const e1 = new Date(start);
            e1.setHours(Math.floor(breakStartVal), (breakStartVal % 1) * 60, 0, 0);
            segments.push({ start: s1, end: e1 });

            // Ca 2: Từ giờ hết nghỉ trưa -> Đến lúc về (VD: 13:00 -> 17:00)
            const s2 = new Date(start);
            s2.setHours(Math.floor(breakEndVal), (breakEndVal % 1) * 60, 0, 0);
            const e2 = new Date(end); // Giữ nguyên giờ về thực tế (bao gồm cả OT nếu có)
            segments.push({ start: s2, end: e2 });

            return segments;
        }

        // Nếu không băng qua trưa (VD: chỉ làm sáng, hoặc chỉ làm chiều, hoặc OT tối) -> Giữ nguyên
        return [{ start, end }];
    }

    // =========================================================================
    // LOAD DATA (Đã sửa để lọc bỏ dòng 'lunch' trong cấu hình)
    // =========================================================================
    async reloadData() {
        const { startDate, endDate } = this.state;
        this.state.days = this.computeDays(startDate, endDate);
        this.state.viewLabel = this.computeViewLabel(startDate, endDate);

        // 1. Lấy thông tin nhân viên + ID Lịch làm việc
        const allEmployees = await this.orm.searchRead(
            "hr.employee",
            [["active", "=", true]],
            ["name", "resource_calendar_id"]
        );

        const calendarIds = [];
        this.employeeCalendarMap = {};
        allEmployees.forEach(emp => {
            if (emp.resource_calendar_id) {
                const calId = emp.resource_calendar_id[0];
                this.employeeCalendarMap[emp.id] = calId;
                if (!calendarIds.includes(calId)) calendarIds.push(calId);
            }
        });

        // 2. Lấy chi tiết lịch (resource.calendar.attendance)
        // QUAN TRỌNG: Lọc bỏ dòng 'lunch' để code không hiểu nhầm 12-13h là giờ làm
        if (calendarIds.length > 0) {
            const calendarLines = await this.orm.searchRead(
                "resource.calendar.attendance",
                [
                    ["calendar_id", "in", calendarIds],
                    ["display_type", "!=", "line_section"],
                    ["day_period", "!=", "lunch"] // <--- LỌC BỎ DÒNG 'NGHỈ' TRONG ẢNH
                ],
                ["calendar_id", "dayofweek", "hour_from", "hour_to", "day_period"]
            );

            this.calendarCache = {};
            for (const line of calendarLines) {
                const cId = line.calendar_id[0];
                const day = parseInt(line.dayofweek); // 0=Mon

                if (!this.calendarCache[cId]) this.calendarCache[cId] = {};
                if (!this.calendarCache[cId][day]) this.calendarCache[cId][day] = [];

                this.calendarCache[cId][day].push({
                    start: line.hour_from,
                    end: line.hour_to
                });
            }
        }

        const s = new Date(startDate); s.setDate(s.getDate() - 1);
        const e = new Date(endDate); e.setDate(e.getDate() + 1);
        const sStr = this.formatDateKey(s);
        const eStr = this.formatDateKey(e);

        const segmentsByEmp = {};
        const intervalsByEmp = {};

        const initEmpObj = (empId) => {
            if (!segmentsByEmp[empId]) segmentsByEmp[empId] = {};
            if (!intervalsByEmp[empId]) intervalsByEmp[empId] = [];
        };

        const attendances = await this.orm.searchRead(
            "hr.attendance",
            [["attendance_date", ">=", sStr], ["attendance_date", "<=", eStr]],
            ["employee_id", "attendance_date", "status", "check_in", "check_out", "attendance_type"],
            { limit: 5000 }
        );

        for (const rec of attendances) {
            if (!rec.employee_id || !rec.check_in) continue;
            const empId = rec.employee_id[0];
            initEmpObj(empId);

            const start = new Date(rec.check_in.endsWith("Z") ? rec.check_in : rec.check_in + "Z");
            let end;
            if (rec.check_out) {
                end = new Date(rec.check_out.endsWith("Z") ? rec.check_out : rec.check_out + "Z");
            } else {
                const now = new Date();
                const startDay = new Date(start); startDay.setHours(0,0,0,0);
                const today = new Date(); today.setHours(0,0,0,0);
                end = startDay < today ? new Date(start.getTime()).setHours(23, 59, 59, 999) : now;
                end = new Date(end);
            }

            if (!end || end <= start) continue;

            let colorClass = 'bg-success';
            let type = 'attendance';
            if (rec.attendance_type === 'leave') {
                colorClass = 'bg-warning';
                type = 'leave';
            }

            // Gọi hàm tách ca (Dynamic theo config)
            const splitIntervals = this.getShiftIntervals(start, end, empId, type);

            for (const interval of splitIntervals) {
                 const label = this.buildLabel(interval.start, interval.end, type);
                 intervalsByEmp[empId].push({
                    id: rec.id, start: interval.start, end: interval.end, status: rec.status, label,
                    type: type, colorClass: colorClass
                });
            }

            const daySegs = this.splitShiftIntoSegments(start, end, rec.status, rec.id, empId, type, colorClass, null);
            for (const seg of daySegs) {
                if (!segmentsByEmp[empId][seg.dateKey]) segmentsByEmp[empId][seg.dateKey] = [];
                segmentsByEmp[empId][seg.dateKey].push(seg);
            }
        }

        this.state.rowsData = allEmployees.map((emp) => {
            return {
                id: emp.id,
                name: emp.name,
                segmentsByDate: segmentsByEmp[emp.id] || {},
                isEditable: this.canEditRow(emp.id)
            };
        });

        this.computeTimelineBars(intervalsByEmp);
    }

    // Update signature: Thêm empId
    splitShiftIntoSegments(rawStart, rawEnd, status, id, empId, type = 'attendance', colorClass = '', customLabel = null) {
        const segments = [];
        if (!rawStart || !rawEnd || rawEnd <= rawStart) return segments;
        let current = new Date(rawStart);
        while (current < rawEnd) {
            const dateKey = this.formatDateKey(current);
            const endOfDay = new Date(current); endOfDay.setHours(23, 59, 59, 999);
            const calcEnd = rawEnd < endOfDay ? rawEnd : endOfDay;

            // Gọi hàm tách ca
            const splitIntervals = this.getShiftIntervals(current, calcEnd, empId, type);

            for (const interval of splitIntervals) {
                const s = interval.start;
                const e = interval.end;
                const style = this.computeBarStyleInDay(s, e);
                const label = customLabel ? customLabel : this.buildLabel(s, e, type);
                let finalClass = colorClass;
                if (!finalClass) finalClass = status === 'late' ? 'bg-danger' : 'bg-success';
                segments.push({ dateKey, id, label, status: status || "ontime", style, startTime: s.getTime(), type: type, resModel: 'hr.attendance', colorClass: finalClass });
            }
            current.setDate(current.getDate() + 1); current.setHours(0, 0, 0, 0);
        }
        return segments;
    }

    // ... (Giữ nguyên các hàm Utils hiển thị: buildLabel, computeBarStyleInDay, computeTimelineBars...) ...
    // Copy lại phần cuối của file JS trước đó vào đây nếu chưa có
    buildLabel(start, end, type = 'attendance') {
        const diffMs = end - start;
        const totalMinutes = Math.floor(diffMs / 60000);
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        let durationStr = "";
        if (hours > 0) durationStr += `${hours}h`;
        if (minutes > 0) durationStr += `${String(minutes).padStart(2, '0')}`;
        if (!durationStr) durationStr = "0h";
        if (this.state.mode === 'month' || this.state.mode === 'week') return durationStr;
        const opt = { hour: "2-digit", minute: "2-digit", hour12: false };
        const s = start.toLocaleTimeString("vi-VN", opt);
        let eText = end.toLocaleTimeString("vi-VN", opt);
        if (end.getHours() === 23 && end.getMinutes() === 59) eText = "24:00";
        let prefix = type === 'leave' ? "Nghỉ: " : "";
        return `${prefix}${s}-${eText} (${durationStr})`;
    }
    computeBarStyleInDay(startInfo, endInfo) {
        let startMins = startInfo.getHours() * 60 + startInfo.getMinutes();
        let endMins = endInfo.getHours() * 60 + endInfo.getMinutes();
        if (endInfo.getHours() === 23 && endInfo.getMinutes() === 59) endMins = 1440;
        if (endMins === 0 && endInfo.getDate() !== startInfo.getDate()) endMins = 1440;
        return `left:${(startMins / 1440) * 100}%; width:${((endMins - startMins) / 1440) * 100}%;`;
    }
    computeTimelineBars(intervalsByEmp) {
        if (this.state.mode === "day") { this.state.weekBars = {}; return; }
        const viewStart = new Date(this.state.startDate); viewStart.setHours(0, 0, 0, 0);
        const viewEnd = new Date(this.state.endDate); viewEnd.setDate(viewEnd.getDate() + 1); viewEnd.setHours(0, 0, 0, 0);
        const totalMs = viewEnd - viewStart || 1;
        const timelineBars = {};
        for (const [empIdStr, list] of Object.entries(intervalsByEmp)) {
            const empId = parseInt(empIdStr, 10);
            let bars = [];
            for (const interval of list) {
                let realStart = interval.start < viewStart ? viewStart : interval.start;
                let realEnd = interval.end > viewEnd ? viewEnd : interval.end;
                if (realEnd <= realStart) continue;
                let visualStart = new Date(realStart);
                if (this.state.mode === 'month') visualStart.setHours(0, 0, 0, 0);
                const left = ((visualStart - viewStart) / totalMs) * 100;
                let width = ((realEnd - visualStart) / totalMs) * 100;
                if (this.state.mode === 'month') {
                    if (interval.start.getDate() === interval.end.getDate()) {
                         const oneDay = (24*3600*1000/totalMs)*100;
                         if (width < oneDay*0.7) width = oneDay*0.7;
                    }
                }
                const endOfDay = new Date(realEnd); endOfDay.setHours(23, 59, 59, 999);
                bars.push({ id: interval.id, status: interval.status, label: interval.label, startMs: realStart.getTime(), endMs: realEnd.getTime(), collisionEndMs: endOfDay.getTime(), left, width, type: interval.type, resModel: 'hr.attendance', colorClass: interval.colorClass, level: 0 });
            }
            bars.sort((a, b) => a.startMs - b.startMs);
            const levels = [];
            for (let bar of bars) {
                let placed = false;
                for (let i = 0; i < levels.length; i++) {
                    if (bar.startMs > levels[i]) { bar.level = i; levels[i] = bar.collisionEndMs; placed = true; break; }
                }
                if (!placed) { bar.level = levels.length; levels.push(bar.collisionEndMs); }
            }
            const maxLevels = levels.length > 0 ? levels.length : 1;
            bars = bars.map(b => ({ ...b, maxLevels }));
            timelineBars[empId] = bars;
        }
        this.state.weekBars = timelineBars;
    }
    computeDays(start, end) {
        const days = []; let d = new Date(start);
        while (d <= end) {
            days.push({ keyStr: this.formatDateKey(d), label: this.state.mode === "month" ? d.getDate() : d.toLocaleDateString("vi-VN", { weekday: "short", day: "numeric" }), fullDate: d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" }), });
            d.setDate(d.getDate() + 1);
        }
        return days;
    }
    computeViewLabel(start, end) {
        const fmt = (d) => d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
        if (this.state.mode === "day") return start.toLocaleDateString("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });
        if (start.getTime() === end.getTime()) return fmt(start);
        return `${fmt(start)} - ${fmt(end)}`;
    }
    openDocument = async (id, model) => { await this.actionService.doAction({ type: "ir.actions.act_window", res_model: model, res_id: id, views: [[false, "form"]], target: "current" }); };
    openActionDialog = (employeeId, dateStr, employeeName) => {
        if (!this.canEditRow(employeeId)) return;
        this.dialogService.add(AttendanceActionDialog, {
            title: `Thao tác: ${employeeName}`, dateStr: dateStr, isManager: this.state.isManager,
            onChoice: async (choice) => {
                if (choice === 'attendance') { await this.actionService.doAction({ type: "ir.actions.act_window", res_model: "hr.attendance", views: [[false, "form"]], target: "current", context: { default_employee_id: employeeId, default_attendance_date: dateStr, default_check_in: dateStr + " 08:00:00" }, }); }
                else if (choice === 'leave') { await this.actionService.doAction({ type: "ir.actions.act_window", res_model: "hr.leave", views: [[false, "form"]], target: "current", context: { default_employee_id: employeeId, default_date_from: dateStr, default_date_to: dateStr, default_request_date_from: dateStr, }, }); }
            }
        });
    };
    onCreateFromEmployee = async (employeeId) => { if (!employeeId || this.state.mode !== "day" || !this.canEditRow(employeeId)) return; const emp = this.state.rowsData.find(r => r.id === employeeId); this.openActionDialog(employeeId, this.state.inputStart, emp ? emp.name : "NV"); };
    onDayCellClick = async (employeeId, dateStr) => { if (!employeeId || !this.canEditRow(employeeId)) return; const emp = this.state.rowsData.find(r => r.id === employeeId); this.openActionDialog(employeeId, dateStr, emp ? emp.name : "NV"); };
    onWeekCellClick = async (ev, employeeId) => { if (!employeeId || !this.canEditRow(employeeId)) return; const container = ev.currentTarget; const rect = container.getBoundingClientRect(); const x = ev.clientX - rect.left; const width = rect.width || 1; const ratio = x / width; const days = this.state.days || []; if (!days.length) return; let index = Math.floor(ratio * days.length); if (index < 0) index = 0; if (index >= days.length) index = days.length - 1; await this.onDayCellClick(employeeId, days[index].keyStr); };
    onDateChange = async (ev) => { const val = ev.target.value; if (!val) return; const d = new Date(val); d.setHours(0, 0, 0, 0); if (this.state.mode === "day") { this.state.startDate = d; this.state.endDate = d; } else if (this.state.mode === "week") { const m = this.getStartOfWeek(d); this.state.startDate = m; const e = new Date(m); e.setDate(m.getDate() + 6); this.state.endDate = e; } else { this.state.startDate = new Date(d.getFullYear(), d.getMonth(), 1); this.state.endDate = new Date(d.getFullYear(), d.getMonth() + 1, 0); } this.state.inputStart = this.formatDateInput(this.state.startDate); await this.reloadData(); };
    async setViewMode(mode) { if (this.state.mode === mode) return; this.state.mode = mode; const t = new Date(); t.setHours(0, 0, 0, 0); if (mode === "day") { this.state.startDate = t; this.state.endDate = t; } else if (mode === "week") { const m = this.getStartOfWeek(t); this.state.startDate = m; const e = new Date(m); e.setDate(m.getDate() + 6); this.state.endDate = e; } else { this.state.startDate = new Date(t.getFullYear(), t.getMonth(), 1); this.state.endDate = new Date(t.getFullYear(), t.getMonth() + 1, 0); } this.state.inputStart = this.formatDateInput(this.state.startDate); await this.reloadData(); }
    async shiftPeriod(amount) { const { mode, startDate, endDate } = this.state; let s = new Date(startDate); let e = new Date(endDate); if (mode === "day") { s.setDate(s.getDate() + amount); e = new Date(s); } else if (mode === "week") { s.setDate(s.getDate() + amount * 7); e.setDate(e.getDate() + amount * 7); } else { s.setMonth(s.getMonth() + amount); s = new Date(s.getFullYear(), s.getMonth(), 1); e = new Date(s.getFullYear(), s.getMonth() + 1, 0); } this.state.startDate = s; this.state.endDate = e; this.state.inputStart = this.formatDateInput(s); await this.reloadData(); }
}

AttendanceGantt.template = "hr_attendance_tedi.AttendanceGantt";
AttendanceGantt.components = { Layout };
registry.category("actions").add("tedi_attendance_gantt_view", AttendanceGantt);