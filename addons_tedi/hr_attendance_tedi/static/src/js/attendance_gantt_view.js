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
    onSelectAttendance() {
        this.props.onChoice('attendance');
        this.props.close();
    }

    onSelectLeave() {
        this.props.onChoice('leave');
        this.props.close();
    }
}

AttendanceActionDialog.template = xml`
    <Dialog title="props.title" size="'sm'">
        <t t-set-slot="footer">
            <span class="d-none">Empty Footer</span>
        </t>

        <div class="bg-white">
            <div class="text-center py-3 border-bottom bg-light">
                <span class="text-muted small text-uppercase fw-bold" style="font-size: 0.75rem; letter-spacing: 1px;">Ngày đã chọn</span>
                <div class="h4 m-0 mt-1 text-dark fw-bolder"><t t-esc="props.dateStr"/></div>
            </div>

            <div class="d-flex p-4 gap-3 justify-content-center">
                <t t-if="props.isManager">
                    <button class="btn btn-light border p-3 shadow-sm d-flex flex-column align-items-center gap-2 flex-fill position-relative overflow-hidden"
                            t-on-click="onSelectAttendance"
                            style="transition: all 0.2s; min-width: 100px;">
                        <div class="rounded-circle bg-primary bg-opacity-10 text-primary d-flex align-items-center justify-content-center mb-1"
                             style="width: 48px; height: 48px;">
                            <i class="fa fa-clock-o fa-2x"/>
                        </div>
                        <span class="fw-bold text-dark small">Chấm công</span>
                    </button>
                </t>

                <button class="btn btn-light border p-3 shadow-sm d-flex flex-column align-items-center gap-2 flex-fill position-relative overflow-hidden"
                        t-on-click="onSelectLeave"
                        style="transition: all 0.2s; min-width: 100px;">
                    <div class="rounded-circle bg-warning bg-opacity-10 text-warning d-flex align-items-center justify-content-center mb-1"
                         style="width: 48px; height: 48px;">
                        <i class="fa fa-plane fa-2x"/>
                    </div>
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
        if (this.state.currentUserEmployeeId && this.state.currentUserEmployeeId === targetEmployeeId) {
            return true;
        }
        return false;
    }

    // =========================================================
    // 1. NAVIGATION ACTIONS
    // =========================================================
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

    // =========================================================
    // 2. UTILS
    // =========================================================
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

    // --- SỬA LABEL ĐỂ HIỂN THỊ ĐÚNG CHO NGHỈ PHÉP ---
    buildLabel(start, end, type = 'attendance') {
        // Tính Duration
        const diffMs = end - start;
        const totalMinutes = Math.floor(diffMs / 60000);
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        let durationStr = "0h";
        if (hours > 0 || minutes > 0) {
            durationStr = `${hours}h`;
            if (minutes > 0) durationStr += `${String(minutes).padStart(2, '0')}`;
        }

        // Nếu là mode Month/Week -> Chỉ hiện thời gian (rút gọn)
        if (this.state.mode === 'month' || this.state.mode === 'week') {
            return durationStr;
        }

        // Mode Day -> Hiện chi tiết
        const opt = { hour: "2-digit", minute: "2-digit", hour12: false };
        const s = start.toLocaleTimeString("vi-VN", opt);
        let eText = end.toLocaleTimeString("vi-VN", opt);
        if (end.getHours() === 23 && end.getMinutes() === 59) eText = "24:00";

        let prefix = "";
        if (type === 'leave') prefix = "Nghỉ: ";

        return `${prefix}${s} - ${eText} (${durationStr})`;
    }

    computeBarStyleInDay(startInfo, endInfo) {
        let startMins = startInfo.getHours() * 60 + startInfo.getMinutes();
        let endMins = endInfo.getHours() * 60 + endInfo.getMinutes();
        if (endInfo.getHours() === 23 && endInfo.getMinutes() === 59) endMins = 1440;
        if (endMins === 0 && endInfo.getDate() !== startInfo.getDate()) endMins = 1440;
        return `left:${(startMins / 1440) * 100}%; width:${((endMins - startMins) / 1440) * 100}%;`;
    }

    splitShiftIntoSegments(start, end, status, id, type = 'attendance', colorClass = '', customLabel = null) {
        const segments = [];
        if (!start || !end || end <= start) return segments;
        let current = new Date(start);
        while (current < end) {
            const dateKey = this.formatDateKey(current);
            const endOfDay = new Date(current); endOfDay.setHours(23, 59, 59, 999);
            const calcEnd = end < endOfDay ? end : endOfDay;
            const style = this.computeBarStyleInDay(current, calcEnd);
            const label = customLabel ? customLabel : this.buildLabel(current, calcEnd, type);

            // Nếu không truyền colorClass từ ngoài vào thì dùng default logic
            let finalClass = colorClass;
            if (!finalClass) {
                finalClass = status === 'late' ? 'bg-danger' : 'bg-success';
            }

            segments.push({ dateKey, id, label, status: status || "ontime", style, startTime: current.getTime(), type: type, resModel: 'hr.attendance', colorClass: finalClass });
            current.setDate(current.getDate() + 1); current.setHours(0, 0, 0, 0);
        }
        return segments;
    }

    computeTimelineBars(intervalsByEmp) {
        if (this.state.mode === "day") { this.state.weekBars = {}; return; }
        const viewStart = new Date(this.state.startDate); viewStart.setHours(0, 0, 0, 0);
        const viewEnd = new Date(this.state.endDate); viewEnd.setDate(viewEnd.getDate() + 1); viewEnd.setHours(0, 0, 0, 0);
        const totalMs = viewEnd - viewStart || 1;
        const oneDayPercent = (24 * 60 * 60 * 1000 / totalMs) * 100;
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
                    const isSameDay = interval.start.getDate() === interval.end.getDate();
                    if (isSameDay) {
                        const minW = oneDayPercent * 0.7; const maxW = oneDayPercent * 0.95;
                        if (width < minW) width = minW; if (width > maxW) width = maxW;
                    }
                }

                // MÀU SẮC ĐÃ ĐƯỢC XỬ LÝ Ở RELOAD DATA, LẤY TRỰC TIẾP
                let finalClass = interval.colorClass || 'bg-secondary';

                const endOfDay = new Date(realEnd); endOfDay.setHours(23, 59, 59, 999);
                bars.push({ id: interval.id, status: interval.status || "ontime", label: interval.label, startMs: realStart.getTime(), endMs: realEnd.getTime(), collisionEndMs: endOfDay.getTime(), left, width, type: interval.type, resModel: 'hr.attendance', colorClass: finalClass, level: 0 });
            }
            bars.sort((a, b) => a.startMs - b.startMs);
            const levels = [];
            for (let bar of bars) {
                let placed = false;
                for (let i = 0; i < levels.length; i++) {
                    if (bar.startMs > levels[i]) {
                        bar.level = i; levels[i] = bar.collisionEndMs; placed = true; break;
                    }
                }
                if (!placed) { bar.level = levels.length; levels.push(bar.collisionEndMs); }
            }
            const maxLevels = levels.length > 0 ? levels.length : 1;
            bars = bars.map(b => ({ ...b, maxLevels }));
            timelineBars[empId] = bars;
        }
        this.state.weekBars = timelineBars;
    }

    // =========================================================
    // 3. LOAD DATA (QUAN TRỌNG: SỬA LOGIC MÀU SẮC TẠI ĐÂY)
    // =========================================================
    async reloadData() {
        const { startDate, endDate } = this.state;
        this.state.days = this.computeDays(startDate, endDate);
        this.state.viewLabel = this.computeViewLabel(startDate, endDate);

        const allEmployees = await this.orm.searchRead(
            "hr.employee",
            [["active", "=", true]],
            ["name"]
        );

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

        // -------------------------------------------------------------
        // A. LOAD ATTENDANCE (Bao gồm cả Chấm công & Nghỉ phép đã sync)
        // -------------------------------------------------------------
        const attendances = await this.orm.searchRead(
            "hr.attendance",
            [
                ["attendance_date", ">=", sStr],
                ["attendance_date", "<=", eStr],
            ],
            ["employee_id", "attendance_date", "status", "check_in", "check_out", "attendance_type"], // Thêm field attendance_type
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

            // --- XỬ LÝ MÀU SẮC ---
            let colorClass = 'bg-success'; // Mặc định XANH (Chấm công thường)
            let type = 'attendance';

            if (rec.attendance_type === 'leave') {
                colorClass = 'bg-warning'; // Nếu là nghỉ phép -> CAM
                type = 'leave';
            }

            // Tạo Label
            const label = this.buildLabel(start, end, type);

            // Add vào Week/Month View
            intervalsByEmp[empId].push({
                id: rec.id, start, end, status: rec.status, label,
                type: type,
                colorClass: colorClass // <-- Truyền màu vào đây
            });

            // Add vào Day View
            const daySegs = this.splitShiftIntoSegments(start, end, rec.status, rec.id, type, colorClass, null);
            for (const seg of daySegs) {
                if (!segmentsByEmp[empId][seg.dateKey]) segmentsByEmp[empId][seg.dateKey] = [];
                segmentsByEmp[empId][seg.dateKey].push(seg);
            }
        }

        // -------------------------------------------------------------
        // B. LOAD LEAVES -> ĐÃ XÓA (Vì dữ liệu đã có trong A)
        // -------------------------------------------------------------

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

    // ... (Giữ nguyên các Event Handlers: openDocument, openActionDialog, onCreateFromEmployee, v.v.)
    openDocument = async (id, model) => {
        await this.actionService.doAction({ type: "ir.actions.act_window", res_model: model, res_id: id, views: [[false, "form"]], target: "current" });
    };
    openActionDialog = (employeeId, dateStr, employeeName = "Nhân viên") => {
        if (!this.canEditRow(employeeId)) return;
        this.dialogService.add(AttendanceActionDialog, {
            title: `Thao tác: ${employeeName}`, dateStr: dateStr, isManager: this.state.isManager,
            onChoice: async (choice) => {
                if (choice === 'attendance') {
                    await this.actionService.doAction({ type: "ir.actions.act_window", res_model: "hr.attendance", views: [[false, "form"]], target: "current", context: { default_employee_id: employeeId, default_attendance_date: dateStr, default_check_in: dateStr + " 08:00:00" }, });
                } else if (choice === 'leave') {
                    await this.actionService.doAction({ type: "ir.actions.act_window", res_model: "hr.leave", views: [[false, "form"]], target: "current", context: { default_employee_id: employeeId, default_date_from: dateStr, default_date_to: dateStr, default_request_date_from: dateStr, }, });
                }
            }
        });
    };
    onCreateFromEmployee = async (employeeId) => {
        if (!employeeId || this.state.mode !== "day") return;
        if (!this.canEditRow(employeeId)) return;
        const emp = this.state.rowsData.find(r => r.id === employeeId); const empName = emp ? emp.name : "Nhân viên"; const dateStr = this.state.inputStart;
        this.openActionDialog(employeeId, dateStr, empName);
    };
    onDayCellClick = async (employeeId, dateStr) => {
        if (!employeeId || !dateStr) return;
        if (!this.canEditRow(employeeId)) return;
        const emp = this.state.rowsData.find(r => r.id === employeeId); const empName = emp ? emp.name : "Nhân viên";
        this.openActionDialog(employeeId, dateStr, empName);
    };
    onWeekCellClick = async (ev, employeeId) => {
        if (!employeeId) return;
        if (!this.canEditRow(employeeId)) return;
        const container = ev.currentTarget; const rect = container.getBoundingClientRect(); const x = ev.clientX - rect.left; const width = rect.width || 1; const ratio = x / width;
        const days = this.state.days || []; if (!days.length) return;
        let index = Math.floor(ratio * days.length); if (index < 0) index = 0; if (index >= days.length) index = days.length - 1;
        const dayKey = days[index].keyStr;
        await this.onDayCellClick(employeeId, dayKey);
    };
    onDateChange = async (ev) => {
        const val = ev.target.value; if (!val) return;
        const d = new Date(val); d.setHours(0, 0, 0, 0);
        if (this.state.mode === "day") { this.state.startDate = d; this.state.endDate = d; }
        else if (this.state.mode === "week") { const monday = this.getStartOfWeek(d); this.state.startDate = monday; const end = new Date(monday); end.setDate(monday.getDate() + 6); this.state.endDate = end; }
        else { this.state.startDate = new Date(d.getFullYear(), d.getMonth(), 1); this.state.endDate = new Date(d.getFullYear(), d.getMonth() + 1, 0); }
        this.state.inputStart = this.formatDateInput(this.state.startDate);
        await this.reloadData();
    };
    async setViewMode(mode) {
        if (this.state.mode === mode) return;
        this.state.mode = mode; const t = new Date(); t.setHours(0, 0, 0, 0);
        if (mode === "day") { this.state.startDate = t; this.state.endDate = t; }
        else if (mode === "week") { const monday = this.getStartOfWeek(t); this.state.startDate = monday; const end = new Date(monday); end.setDate(monday.getDate() + 6); this.state.endDate = end; }
        else { this.state.startDate = new Date(t.getFullYear(), t.getMonth(), 1); this.state.endDate = new Date(t.getFullYear(), t.getMonth() + 1, 0); }
        this.state.inputStart = this.formatDateInput(this.state.startDate);
        await this.reloadData();
    }
    async shiftPeriod(amount) {
        const { mode, startDate, endDate } = this.state; let s = new Date(startDate); let e = new Date(endDate);
        if (mode === "day") { s.setDate(s.getDate() + amount); e = new Date(s); }
        else if (mode === "week") { s.setDate(s.getDate() + amount * 7); e.setDate(e.getDate() + amount * 7); }
        else { s.setMonth(s.getMonth() + amount); s = new Date(s.getFullYear(), s.getMonth(), 1); e = new Date(s.getFullYear(), s.getMonth() + 1, 0); }
        this.state.startDate = s; this.state.endDate = e; this.state.inputStart = this.formatDateInput(s);
        await this.reloadData();
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
}

AttendanceGantt.template = "hr_attendance_tedi.AttendanceGantt";
AttendanceGantt.components = { Layout };
registry.category("actions").add("tedi_attendance_gantt_view", AttendanceGantt);

// --- FILE XML GIỮ NGUYÊN NHƯ CŨ (KHÔNG CẦN THAY ĐỔI GÌ NỮA) ---