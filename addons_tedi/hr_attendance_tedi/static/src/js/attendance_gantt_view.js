/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

// ... (Giữ nguyên component AttendanceActionDialog như cũ) ...
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

    // ... (Giữ nguyên các hàm Navigation và Import) ...
    canEditRow(targetEmployeeId) {
        if (this.state.isManager) return true;
        return this.state.currentUserEmployeeId && this.state.currentUserEmployeeId === targetEmployeeId;
    }
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
    onImportClick = async () => {
        await this.actionService.doAction("hr_attendance_tedi.action_tedi_attendance_import", {
            onClose: async () => { await this.reloadData(); }
        });
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
    // LOGIC LẤY CẤU HÌNH LỊCH LÀM VIỆC
    // =========================================================================
    getWorkIntervalsFromConfig(employeeId, date) {
        const calendarId = this.employeeCalendarMap[employeeId];
        // Nếu không có lịch làm việc, trả về null để xử lý fallback
        if (!calendarId || !this.calendarCache[calendarId]) {
            return null;
        }
        const jsDay = date.getDay();
        const odooDay = jsDay === 0 ? 6 : jsDay - 1;
        const dayConfig = this.calendarCache[calendarId][odooDay];
        // Trả về mảng các ca (vd: [{start:8, end:12}, {start:13, end:17}])
        if (!dayConfig || dayConfig.length === 0) return [];
        return dayConfig;
    }

    // =========================================================================
    // [LOGIC MỚI] CẮT GIỜ LÀM THEO HỢP ĐỒNG (INTERSECTION)
    // =========================================================================
    getShiftIntervals(start, end, employeeId, type = 'attendance') {
        // 1. Nếu là Xin nghỉ (Leave), thường giữ nguyên hoặc xử lý riêng.
        //    Ở đây ta giữ nguyên để tránh xung đột với đơn từ.
        if (type !== 'attendance') return [{ start, end }];

        // 2. Lấy cấu hình ca làm việc của nhân viên ngày hôm đó
        const workIntervals = this.getWorkIntervalsFromConfig(employeeId, start);

        // 3. Fallback: Nếu không tìm thấy lịch (ví dụ chưa cấu hình, hoặc ngày CN không có lịch)
        //    Logic cũ: hiển thị full. Logic mới: Nếu user muốn strict thì có thể trả về rỗng.
        //    Nhưng để an toàn hiển thị, nếu không có lịch thì hiển thị Full giờ thực tế.
        if (!workIntervals) return [{ start, end }];
        if (workIntervals.length === 0) {
             // Ngày nghỉ (theo lịch), nhưng nhân viên vẫn đi làm (OT ngày nghỉ)
             // Tùy yêu cầu, ta có thể hiển thị full hoặc ẩn.
             // Hiện tại trả về mảng rỗng nghĩa là không tính giờ công (nếu muốn tính OT ngày nghỉ phải cấu hình lịch kiểu khác).
             // Để an toàn (tránh mất dữ liệu hiển thị), ta cứ hiển thị full nhưng có thể đổi màu ở bước sau.
             // TUY NHIÊN, theo yêu cầu "max không quá thời gian hợp đồng", nếu hợp đồng = 0h thì hiển thị 0h?
             // Hãy giả định: Ngày thường -> Cắt theo ca. Ngày nghỉ -> Cho hiển thị full (hoặc cắt hết).
             // Code dưới đây sẽ cho phép hiển thị full nếu ngày đó không có cấu hình (tránh mất bar).
             return [{ start, end }];
        }

        // 4. Chuẩn bị dữ liệu tính toán
        const segments = [];
        const startFloat = start.getHours() + start.getMinutes() / 60;
        let endFloat = end.getHours() + end.getMinutes() / 60;
        // Xử lý trường hợp làm qua đêm đơn giản (trong cùng 1 lần checkin)
        if (end.getDate() !== start.getDate()) endFloat = 24 + end.getHours() + end.getMinutes()/60;

        // 5. Lặp qua từng ca làm việc quy định (Vd: Ca sáng 8-12, Ca chiều 13-17)
        for (const shift of workIntervals) {
            // shift.start (8.0), shift.end (12.0)

            // Tìm giao điểm (Intersection): Max(Start) -> Min(End)
            const effectiveStart = Math.max(startFloat, shift.start);
            const effectiveEnd = Math.min(endFloat, shift.end);

            // Nếu có giao nhau hợp lệ (Start < End)
            if (effectiveStart < effectiveEnd) {
                const sDate = new Date(start);
                sDate.setHours(Math.floor(effectiveStart), (effectiveStart % 1) * 60, 0, 0);

                const eDate = new Date(start);
                // Xử lý giờ kết thúc (có thể là 17.5 -> 17:30)
                eDate.setHours(Math.floor(effectiveEnd), (effectiveEnd % 1) * 60, 0, 0);

                // Nếu giờ là 24 (qua đêm hoặc cuối ngày), JS setHours tự xử lý ngày hôm sau
                if (effectiveEnd >= 24) {
                    // Logic xử lý qua đêm nâng cao nếu cần, ở đây giữ đơn giản
                }

                segments.push({ start: sDate, end: eDate });
            }
        }

        // 6. Nếu không giao nhau chút nào (Ví dụ: Ca 8-17, đi làm lúc 18-19h)
        //    Theo yêu cầu "max không qua hợp đồng", thì khoảng này sẽ bị ẩn đi (segments rỗng).
        return segments;
    }

    // =========================================================================
    // LOAD DATA (GIỮ NGUYÊN LOGIC, CHỈ GỌI getShiftIntervals MỚI)
    // =========================================================================
    async reloadData() {
        const { startDate, endDate } = this.state;
        this.state.days = this.computeDays(startDate, endDate);
        this.state.viewLabel = this.computeViewLabel(startDate, endDate);

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

        if (calendarIds.length > 0) {
            const calendarLines = await this.orm.searchRead(
                "resource.calendar.attendance",
                [
                    ["calendar_id", "in", calendarIds],
                    ["display_type", "!=", "line_section"],
                    ["day_period", "!=", "lunch"]
                ],
                ["calendar_id", "dayofweek", "hour_from", "hour_to", "day_period"]
            );
            this.calendarCache = {};
            for (const line of calendarLines) {
                const cId = line.calendar_id[0];
                const day = parseInt(line.dayofweek);
                if (!this.calendarCache[cId]) this.calendarCache[cId] = {};
                if (!this.calendarCache[cId][day]) this.calendarCache[cId][day] = [];
                this.calendarCache[cId][day].push({ start: line.hour_from, end: line.hour_to });
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

            // --- GỌI HÀM CẮT GIỜ MỚI TẠI ĐÂY ---
            const splitIntervals = this.getShiftIntervals(start, end, empId, type);

            let intervalIndex = 0;
            for (const interval of splitIntervals) {
                 const label = this.buildLabel(interval.start, interval.end, type);
                 intervalsByEmp[empId].push({
                    id: rec.id, start: interval.start, end: interval.end, status: rec.status, label,
                    type: type, colorClass: colorClass, index: intervalIndex,
                 });
                 intervalIndex++;
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

    // --- Giữ nguyên hàm này, nó sẽ gọi getShiftIntervals để xử lý từng ngày ---
    splitShiftIntoSegments(rawStart, rawEnd, status, id, empId, type = 'attendance', colorClass = '', customLabel = null) {
        const segments = [];
        if (!rawStart || !rawEnd || rawEnd <= rawStart) return segments;
        let current = new Date(rawStart);
        let index = 0;
        while (current < rawEnd) {
            const dateKey = this.formatDateKey(current);
            const endOfDay = new Date(current); endOfDay.setHours(23, 59, 59, 999);
            const calcEnd = rawEnd < endOfDay ? rawEnd : endOfDay;

            // Hàm này bây giờ sẽ trả về các đoạn đã được cắt gọn (clipped)
            const splitIntervals = this.getShiftIntervals(current, calcEnd, empId, type);

            for (const interval of splitIntervals) {
                const s = interval.start;
                const e = interval.end;
                const style = this.computeBarStyleInDay(s, e);
                const label = customLabel ? customLabel : this.buildLabel(s, e, type);
                let finalClass = colorClass;
                if (!finalClass) finalClass = status === 'late' ? 'bg-danger' : 'bg-success';
                segments.push({ dateKey, id, label, status: status || "ontime", style, startTime: s.getTime(), type: type, resModel: 'hr.attendance', colorClass: finalClass, index: index });
                index++;
            }
            current.setDate(current.getDate() + 1); current.setHours(0, 0, 0, 0);
        }
        return segments;
    }

    // ... (Giữ nguyên các hàm helper khác: buildLabel, computeBarStyleInDay, computeTimelineBars, ...)
    buildLabel(start, end, type = 'attendance') {
        const diffMs = end - start;
        const totalMinutes = Math.floor(diffMs / 60000);
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        let durationStr = "";
        if (hours > 0) durationStr += `${hours}h`;
        if (minutes > 0) durationStr += `${String(minutes).padStart(2, "0")}`;
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
            const groupedBars = {};

            for (const interval of list) {
                // [THAY ĐỔI 1]: Bỏ index ra khỏi key để gộp các đoạn cắt (sáng/chiều) chung 1 ID lại với nhau
                const key = `${interval.id}_${interval.type}`;

                if (!groupedBars[key]) {
                    groupedBars[key] = {
                        id: interval.id,
                        type: interval.type,
                        status: interval.status,
                        colorClass: interval.colorClass,
                        resModel: 'hr.attendance',
                        start: interval.start,
                        end: interval.end,
                        originalIntervals: [interval],
                        // index: interval.index // Không cần quan tâm index nữa khi gộp
                    };
                } else {
                    // Mở rộng thời gian bắt đầu và kết thúc của thanh lớn để bao trùm cả ngày
                    if (interval.start < groupedBars[key].start) groupedBars[key].start = interval.start;
                    if (interval.end > groupedBars[key].end) groupedBars[key].end = interval.end;
                    groupedBars[key].originalIntervals.push(interval);
                }
            }

            let bars = [];
            for (const key in groupedBars) {
                const grouped = groupedBars[key];
                let realStart = grouped.start < viewStart ? viewStart : grouped.start;
                let realEnd = grouped.end > viewEnd ? viewEnd : grouped.end;
                if (realEnd <= realStart) continue;

                let visualStart = new Date(realStart);
                if (this.state.mode === 'month') visualStart.setHours(0, 0, 0, 0);

                const left = ((visualStart - viewStart) / totalMs) * 100;
                let width = ((realEnd - visualStart) / totalMs) * 100;

                // [THAY ĐỔI 2]: Tính toán lại Label để hiển thị tổng giờ làm thực tế (trừ giờ nghỉ trưa)
                // Thay vì gọi this.buildLabel(grouped.start, grouped.end) sẽ bị tính cả giờ nghỉ
                const label = this.buildMergedLabel(grouped.start, grouped.end, grouped.originalIntervals, grouped.type);

                if (this.state.mode === 'month' && grouped.start.getDate() === grouped.end.getDate()) {
                    const oneDay = (24*3600*1000/totalMs)*100;
                    if (width < oneDay*0.7) width = oneDay*0.7;
                }
                const endOfDay = new Date(realEnd); endOfDay.setHours(23, 59, 59, 999);

                bars.push({
                    id: grouped.id, status: grouped.status, label,
                    startMs: realStart.getTime(), endMs: realEnd.getTime(),
                    collisionEndMs: endOfDay.getTime(), left, width,
                    type: grouped.type, resModel: grouped.resModel,
                    colorClass: grouped.colorClass, level: 0
                });
            }
            // Sắp xếp và tính level hiển thị (chồng nhau)
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

    // [THÊM HÀM MỚI]: Hàm helper để tính tổng giờ từ các đoạn rời rạc
   buildMergedLabel(start, end, intervals, type) {
        // 1. Tính tổng thời gian thực tế (cộng dồn các đoạn)
        let totalMinutes = 0;
        intervals.forEach(i => {
            const diffMs = i.end - i.start;
            totalMinutes += Math.floor(diffMs / 60000);
        });

        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;

        let durationStr = "";
        if (hours > 0) durationStr += `${hours}h`;
        if (minutes > 0) durationStr += `${String(minutes).padStart(2, "0")}`;
        if (!durationStr) durationStr = "0h";

        // Nếu là view tháng/tuần chỉ cần hiển thị tổng giờ
        if (this.state.mode === 'month' || this.state.mode === 'week') return durationStr;

        // Nếu view chi tiết hơn thì hiển thị: 08:00-17:00 (8h)
        const opt = { hour: "2-digit", minute: "2-digit", hour12: false };
        const s = start.toLocaleTimeString("vi-VN", opt);
        let eText = end.toLocaleTimeString("vi-VN", opt);
        if (end.getHours() === 23 && end.getMinutes() === 59) eText = "24:00";

        let prefix = type === 'leave' ? "Nghỉ: " : "";
        return `${prefix}${s}-${eText} (${durationStr})`;
    }

    // ... (Giữ nguyên các hàm helper tính toán ngày, openDocument, ...)
    computeDays(start, end) {
        const days = [];
        let d = new Date(start);
        while (d <= end) {
            const dayOfWeek = d.getDay();
            days.push({
                keyStr: this.formatDateKey(d),
                weekday: d.toLocaleDateString("vi-VN", { weekday: "short" }),
                dayNum: d.getDate(),
                fullDate: d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" }),
                isWeekend: dayOfWeek === 0 || dayOfWeek === 6,
                isSunday: dayOfWeek === 0
            });
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
    openDocument = (resId, resModel) => {
        this.dialogService.add(FormViewDialog, {
            resModel: resModel,
            resId: resId,
            context: this.props.context,
            title: "Chi tiết", // Tiêu đề popup
            onRecordSaved: async () => {
                // Khi người dùng bấm Lưu trên Popup, load lại dữ liệu Gantt
                await this.reloadData();
            },
        });
    };
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
AttendanceGantt.props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    className: { type: String, optional: true },
    resId: { type: [Number, Boolean], optional: true },
    resModel: { type: String, optional: true },
    viewId: { type: Number, optional: true },
    context: { type: Object, optional: true },
    display: { type: Object, optional: true },
    globalState: { type: Object, optional: true },
};

registry.category("actions").add("tedi_attendance_gantt_view", AttendanceGantt);