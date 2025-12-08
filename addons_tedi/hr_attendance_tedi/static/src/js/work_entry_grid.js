/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

export class WorkEntryMonthlyGrid extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.userService = useService("user");
        this.notificationService = useService("notification"); // Thêm service thông báo

        const today = new Date();

        this.state = useState({
            currentDate: new Date(today.getFullYear(), today.getMonth(), 1),
            viewLabel: "",
            days: [],
            rowsData: [],
            legendData: [],
            isLoading: false,
            collapsedGroupIds: new Set(),
            filterState: 'all',
        });

        onWillStart(async () => {
            await this.reloadData();
        });
    }

    get inputValue() {
        return this.formatDate(this.state.currentDate);
    }

    onDateChange = async (ev) => {
        const inputDate = ev.target.value;
        if (inputDate) {
            const dateObj = new Date(inputDate);
            this.state.currentDate = new Date(dateObj.getFullYear(), dateObj.getMonth(), 1);
            await this.reloadData();
        }
    }

    onFilterStateChange = async (ev) => {
        this.state.filterState = ev.target.value;
        await this.reloadData();
    }

    openGenerateWizard = () => {
        const year = this.state.currentDate.getFullYear();
        const month = this.state.currentDate.getMonth();
        const startDate = new Date(year, month, 1);
        const endDate = new Date(year, month + 1, 0);

        // --- XÓA ĐOẠN NÀY ---
        // const visibleEmployeeIds = this.state.rowsData.map(row => row.id);
        // --------------------

        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'tedi.work.entry.generate.wizard',
            name: 'Tạo công cho TẤT CẢ nhân viên', // Đổi tên tiêu đề cho hợp lý
            views: [[false, 'form']],
            target: 'new',
            context: {
                default_date_from: this.formatDate(startDate),
                default_date_to: this.formatDate(endDate),
                // KHÔNG TRUYỀN default_employee_ids Ở ĐÂY NỮA
                // Để Python tự đi tìm trong database
            }
        }, { onClose: () => { this.reloadData(); } });
    }

     openRegenerateWizard = () => {
        const year = this.state.currentDate.getFullYear();
        const month = this.state.currentDate.getMonth();

        const startDate = new Date(year, month, 1);
        const endDate = new Date(year, month + 1, 0);

        this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "hr.work.entry.regeneration.wizard",
                name: "Tạo lại mục công việc",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_date_from: this.formatDate(startDate),
                    default_date_to: this.formatDate(endDate),
                },
            },
            {
                onClose: () => {
                    this.reloadData();
                },
            }
        );
    };


    // --- HÀM MỚI: ĐỒNG BỘ CHẤM CÔNG ---
    onSyncAttendance = async () => {
        const year = this.state.currentDate.getFullYear();
        const month = this.state.currentDate.getMonth();

        // Xác định ngày đầu tháng và cuối tháng của view hiện tại
        const startStr = this.formatDate(new Date(year, month, 1));
        const endStr = this.formatDate(new Date(year, month + 1, 0, 23, 59, 59));

        // Tìm các Work Entry chưa chốt trong tháng này
        const domain = [
            ['date_start', '>=', startStr],
            ['date_stop', '<=', endStr],
            ['state', 'in', ['draft', 'conflict']]
        ];

        this.state.isLoading = true;
        try {
            const ids = await this.orm.search("hr.work.entry", domain);

            if (ids.length === 0) {
                this.notificationService.add("Không có công việc nào (Draft/Conflict) cần đồng bộ.", { type: "info" });
            } else {
                // Gọi hàm Python action_sync_attendance
                await this.orm.call("hr.work.entry", "action_sync_attendance", [ids]);
                this.notificationService.add("Đã đồng bộ chấm công thành công!", { type: "success" });
                await this.reloadData();
            }
        } catch (error) {
            console.error(error);
            this.notificationService.add("Lỗi khi đồng bộ: " + error.message, { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }
    // ----------------------------------

    createWorkEntry = () => {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.work.entry',
            views: [[false, 'form']],
            target: 'new',
            name: "Tạo thủ công"
        }, { onClose: () => { this.reloadData(); } });
    }

    get columns() {
        const result = [];
        const processedGroups = new Set();
        for (const day of this.state.days) {
            if (day.hasData) {
                result.push({ type: 'day', ...day });
                continue;
            }
            if (day.groupId) {
                const isCollapsed = this.state.collapsedGroupIds.has(day.groupId);
                if (isCollapsed) {
                    if (!processedGroups.has(day.groupId)) {
                        result.push({ type: 'placeholder', groupId: day.groupId, label: '...' });
                        processedGroups.add(day.groupId);
                    }
                } else {
                    result.push({ type: 'day', ...day, canCollapse: true });
                }
            } else {
                result.push({ type: 'day', ...day });
            }
        }
        return result;
    }

    toggleGroup = (groupId) => {
        if (this.state.collapsedGroupIds.has(groupId)) {
            this.state.collapsedGroupIds.delete(groupId);
        } else {
            this.state.collapsedGroupIds.add(groupId);
        }
        this.state.collapsedGroupIds = new Set(this.state.collapsedGroupIds);
    }

    goPrev = async () => { this.state.currentDate.setMonth(this.state.currentDate.getMonth() - 1); await this.reloadData(); };
    goNext = async () => { this.state.currentDate.setMonth(this.state.currentDate.getMonth() + 1); await this.reloadData(); };
    goToToday = async () => {
        const today = new Date();
        this.state.currentDate = new Date(today.getFullYear(), today.getMonth(), 1);
        await this.reloadData();
    };

    async reloadData() {
        this.state.isLoading = true;
        const year = this.state.currentDate.getFullYear();
        const month = this.state.currentDate.getMonth();
        const daysInMonth = new Date(year, month + 1, 0).getDate();

        this.state.days = [];
        for (let i = 1; i <= daysInMonth; i++) {
            const d = new Date(year, month, i);
            this.state.days.push({
                day: i,
                dateObj: d,
                isWeekend: d.getDay() === 0 || d.getDay() === 6,
                label: String(i).padStart(2, '0'),
                hasData: false,
                groupId: null,
            });
        }

        this.state.viewLabel = `Tháng ${month + 1} ${year}`;

        const startStr = this.formatDate(new Date(year, month, 1));
        const endStr = this.formatDate(new Date(year, month, daysInMonth, 23, 59, 59));

        const domain = [
            ['date_start', '>=', startStr],
            ['date_stop', '<=', endStr]
        ];

        if (this.state.filterState === 'all') {
            domain.push(['state', '!=', 'cancelled']);
        } else {
            domain.push(['state', '=', this.state.filterState]);
        }

        const workEntries = await this.orm.searchRead("hr.work.entry", domain,
            ['id', 'employee_id', 'date_start', 'duration', 'work_entry_type_id', 'color'],
            { order: "date_start asc" }
        );

        const employees = await this.orm.searchRead("hr.employee", [], ['name', 'avatar_128']);

        const rowMap = {};
        employees.forEach(emp => {
            rowMap[emp.id] = {
                id: emp.id,
                name: emp.name,
                hasAvatar: !!emp.avatar_128,
                cells: {},
                totalDuration: 0
            };
        });

        const daysWithData = new Set();
        const legendMap = new Map();

        workEntries.forEach(we => {
            const empId = we.employee_id[0];
            if (!rowMap[empId]) return;
            const date = new Date(we.date_start);
            const offset = date.getTimezoneOffset();
            const day = new Date(date.getTime() - (offset * 60 * 1000)).getDate();

            daysWithData.add(day);
            rowMap[empId].totalDuration += (we.duration || 0);

            const typeId = we.work_entry_type_id ? we.work_entry_type_id[0] : 0;
            const typeName = we.work_entry_type_id ? we.work_entry_type_id[1] : 'Undefined';
            const colorInt = we.color || 0;

            if (!legendMap.has(typeId)) {
                legendMap.set(typeId, { id: typeId, name: typeName, colorClass: `o_color_${colorInt}` });
            }

            if (!rowMap[empId].cells[day]) {
                rowMap[empId].cells[day] = [];
            }

            rowMap[empId].cells[day].push({
                id: we.id,
                label: this.formatCellDuration(we.duration),
                colorClass: `o_color_${colorInt}`
            });
        });

        let currentGroupId = 0;
        let inEmptyBlock = false;
        const allEmptyGroups = new Set();

        this.state.days.forEach(d => {
            if (daysWithData.has(d.day)) {
                d.hasData = true;
                inEmptyBlock = false;
            } else {
                if (!inEmptyBlock) {
                    currentGroupId++;
                    inEmptyBlock = true;
                    allEmptyGroups.add(currentGroupId);
                }
                d.groupId = currentGroupId;
            }
        });

        this.state.collapsedGroupIds = allEmptyGroups;
        this.state.rowsData = Object.values(rowMap).sort((a, b) => a.name.localeCompare(b.name));
        this.state.legendData = Array.from(legendMap.values()).sort((a, b) => a.id - b.id);
        this.state.isLoading = false;
    }

    openEntry(entryId) {
        if (!entryId) return;
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.work.entry',
            res_id: entryId,
            views: [[false, 'form']],
            target: 'new',
            name: "Chi tiết Work Entry"
        });
    }

    formatDate(date) { const offset = date.getTimezoneOffset(); return new Date(date.getTime() - (offset * 60 * 1000)).toISOString().split('T')[0]; }
    formatHours(h) { return `${Math.floor(h)}h${String(Math.round((h - Math.floor(h)) * 60)).padStart(2, '0')}`; }

    formatCellDuration(floatHours) {
        if (!floatHours) return '';
        const h = Math.floor(floatHours);
        const m = Math.round((floatHours - h) * 60);
        if (m === 0) return `${h}`;
        return `${h}h${String(m).padStart(2, '0')}`;
    }

    openEmployee = (id) => {
        this.actionService.doAction({ type: 'ir.actions.act_window', res_model: 'hr.employee', res_id: id, views: [[false, 'form']], target: 'current' });
    }
}

WorkEntryMonthlyGrid.template = "hr_attendance_tedi.WorkEntryMonthlyGrid";
WorkEntryMonthlyGrid.components = { Layout };
registry.category("actions").add("tedi_work_entry_monthly_grid", WorkEntryMonthlyGrid);