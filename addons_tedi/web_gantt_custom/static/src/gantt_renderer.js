/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import {
    Component,
    onWillRender,
    onWillUpdateProps,
    reactive,
    toRaw,
    useExternalListener,
    useRef,
    useState,
} from "@odoo/owl";
import { hasTouch, isMobileOS } from "@web/core/browser/feature_detection";
import { Domain } from "@web/core/domain";
import { formatDateTime, serializeDate, serializeDateTime } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { usePopover } from "@web/core/popover/popover_hook";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { useService } from "@web/core/utils/hooks";
import { omit } from "@web/core/utils/objects";
import { debounce, throttleForAnimation } from "@web/core/utils/timing";
import { url } from "@web/core/utils/urls";
import { useVirtual } from "@web/core/virtual_hook";
import { formatFloatTime } from "@web/views/fields/formatters";
import { useViewCompiler } from "@web/views/view_compiler";
import { ViewScaleSelector } from "@web/views/view_components/view_scale_selector";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { GanttCompiler } from "./gantt_compiler";
import { GanttConnector } from "./gantt_connector";
import {
    dateAddFixedOffset,
    getCellColor,
    getColorIndex,
    useGanttConnectorDraggable,
    useGanttDraggable,
    useGanttResizable,
    useGanttUndraggable,
    useMultiHover,
} from "./gantt_helpers";
import { GanttPopover } from "./gantt_popover";
import { GanttResizeBadge } from "./gantt_resize_badge";
import { GanttRowProgressBar } from "./gantt_row_progress_bar";
import { computeRange } from "./gantt_model";
import { browser } from "@web/core/browser/browser";

const { DateTime } = luxon;

/**
 * @typedef {`__column__${number}`} ColumnId
 * @typedef {`__connector__${number | "new"}`} ConnectorId
 * @typedef {import("./gantt_connector").ConnectorProps} ConnectorProps
 * @typedef {luxon.DateTime} DateTime
 * @typedef {"copy" | "reschedule"} DragActionMode
 * @typedef {"drag" | "locked" | "resize"} InteractionMode
 * @typedef {`__pill__${number}`} PillId
 * @typedef {import("./gantt_model").RowId} RowId
 *
 * @typedef Column
 * @property {ColumnId} id
 * @property {GridPosition} grid
 * @property {boolean} [isToday]
 * @property {DateTime} start
 * @property {DateTime} stop
 *
 * @typedef GridPosition
 * @property {number | number[]} [row]
 * @property {number | number[]} [column]
 *
 * @typedef Group
 * @property {boolean} break
 * @property {number} col
 * @property {Pill[]} pills
 * @property {number} aggregateValue
 * @property {GridPosition} grid
 *
 * @typedef GanttRendererProps
 * @property {import("./gantt_model").GanttModel} model
 * @property {Document} arch
 * @property {string} class
 * @property {(context: Record<string, any>)} create
 * @property {{ content?: Point }} [scrollPosition]
 * @property {{ el: HTMLDivElement | null }} [contentRef]
 *
 * @typedef HoveredInfo
 * @property {Element | null} connector
 * @property {HTMLElement | null} hoverable
 * @property {HTMLElement | null} pill
 *
 * @typedef Interaction
 * @property {InteractionMode | null} mode
 * @property {DragActionMode} dragAction
 *
 * @typedef Pill
 * @property {PillId} id
 * @property {boolean} disableStartResize
 * @property {boolean} disableStopResize
 * @property {boolean} highlighted
 * @property {number} leftMargin
 * @property {number} level
 * @property {string} name
 * @property {DateTime} startDate
 * @property {DateTime} stopDate
 * @property {GridPosition} grid
 * @property {RelationalRecord} record
 * @property {number} _color
 * @property {number} _progress
 *
 * @typedef Point
 * @property {number} [x]
 * @property {number} [y]
 *
 * @typedef {Record<string, any>} RelationalRecord
 * @property {number | false} id
 *
 * @typedef ResizeBadge
 * @property {Point & { right?: number }} position
 * @property {number} diff
 * @property {string} scale
 *
 * @typedef {import("./gantt_model").Row & {
 *  grid: GridPosition,
 *  pills: Pill[],
 *  cellColors?: Record<string, string>,
 *  thumbnailUrl?: string
 * }} Row
 *
 * @typedef SubColumn
 * @property {ColumnId} columnId
 * @property {boolean} [isToday]
 * @property {DateTime} start
 * @property {DateTime} stop
 */

/** @type {[Omit<InteractionMode, "drag"> | DragActionMode, string][]} */
const INTERACTION_CLASSNAMES = [
    ["connect", "o_connect"],
    ["copy", "o_copying"],
    ["locked", "o_grabbing_locked"],
    ["reschedule", "o_grabbing"],
    ["resize", "o_resizing"],
];
const NEW_CONNECTOR_ID = "__connector__new";

/**
 * Gantt Renderer
 *
 * @extends {Component<GanttRendererProps, any>}
 */
export class GanttRenderer extends Component {
    static components = {
        GanttConnector,
        GanttResizeBadge,
        GanttRowProgressBar,
        Popover: GanttPopover,
        ViewScaleSelector,
    };
    static props = [
        "model",
        "arch",
        "class",
        "create",
        "openDialog",
        "scrollPosition?",
        "contentRef?",
    ];

    static template = "web_gantt.GanttRenderer";
    static connectorCreatorTemplate = "web_gantt.GanttRenderer.ConnectorCreator";
    static headerTemplate = "web_gantt.GanttRenderer.Header";
    static pillTemplate = "web_gantt.GanttRenderer.Pill";
    static rowContentTemplate = "web_gantt.GanttRenderer.RowContent";
    static rowHeaderTemplate = "web_gantt.GanttRenderer.RowHeader";
    static totalRowTemplate = "web_gantt.GanttRenderer.TotalRow";

    static GRID_ROW_HEIGHT = 4; // Pixels
    static GROUP_ROW_SPAN = 6; // --> 24 pixels
    static ROW_SPAN = 9; // --> 36 pixels

    static getRowHeaderWidth = (width) => 100 / (width > 768 ? 6 : 3);

    setup() {
        this.model = this.props.model;

        console.log('=== CURRENT GROUPED BY ===');
        console.log('GroupedBy:', this.model.metaData.groupedBy);
        console.log('GroupedByField:', this.model.metaData.groupedByField);

        // TẮT HOÀN TOÀN selection bằng cách ghi đè thuộc tính
        this.selection = {
            active: false,
            rowId: null,
            initialIndex: null,
            lastSelectId: null,
        };

        // Ghi đè luôn method để chắc chắn không bị gọi từ nơi khác
        this.onSelectStart = () => {};
        this.onSelectStop = () => {};
        this.loadSubtasks();

        // Debug chi tiết cấu trúc dữ liệu
        console.log('=== DETAILED DATA STRUCTURE ANALYSIS ===');
        console.log('Model meta data fields:', this.model.metaData.fields);
        // Debug chi tiết data
        console.log('=== RAW DATA DEBUG ===');
        console.log('Model data:', this.model.data);
        console.log('Model rows:', this.model.data.rows);
        console.log('Model records:', this.model.data.records);
        console.log('Total records:', this.model.data.records.length);
        // Kiểm tra xem có domain nào filter theo parent_id không
        console.log('Current domain:', this.env.searchModel?.globalDomain);

        this._userNameCache = {};

        this.parentChildMapping = {};

        this.forceSingleRowPerTask = true;
        this.nextPillId = 1;

        this.getTaskStartDate = this.getTaskStartDate.bind(this);
        this.getTaskEndDate = this.getTaskEndDate.bind(this);
        this.getTaskDuration = this.getTaskDuration.bind(this);
        this.getTaskAssignees = this.getTaskAssignees.bind(this);
        this.getAggregatedStartDate = this.getAggregatedStartDate.bind(this);
        this.getAggregatedEndDate = this.getAggregatedEndDate.bind(this);
        this.getAggregatedDuration = this.getAggregatedDuration.bind(this);
        this.getAggregatedAssignees = this.getAggregatedAssignees.bind(this);

        this.cellContainerRef = useRef("cellContainer");
        this.rootRef = useRef("root");

        this.actionService = useService("action");
        this.dialogService = useService("dialog");
        this.userService = useService("user");

        /** @type {HoveredInfo} */
        this.hovered = {
            connector: null,
            hoverable: null,
            pill: null,
        };

        this.selection = {
            active: false,
        };

        this.state = useState({ rowHeaderWidth: 0 });

        /** @type {Interaction} */
        this.interaction = reactive(
            {
                mode: null,
                dragAction: "reschedule",
            },
            () => this.onInteractionChange()
        );
        this.onInteractionChange(); // Used to hook into "interaction"
        /** @type {Record<ConnectorId, ConnectorProps>} */
        this.connectors = reactive({});
        this.progressBarsReactive = reactive({ el: null });
        /** @type {ResizeBadge} */
        this.resizeBadgeReactive = reactive({});

        /** @type {Column[]} */
        this.columns = [];
        /** @type {DateTime[]} */
        this.dateGridColumns = [];
        /** @type {Pill[]} */
        this.extraPills = [];
        /** @type {Row[]} */
        this.extraRows = [];
        /** @type {Record<PillId, Pill>} */
        this.pills = {}; // mapping to retrieve pills from pill ids
        /** @type {RowId[]} */
        this.rowIds = [];
        /** @type {Row[]} */
        this.rows = [];
        /** @type {SubColumn[]} */
        this.subColumns = [];

        const position = localization.direction === "rtl" ? "bottom" : "right";
        this.popover = usePopover(this.constructor.components.Popover, { position });

        const { popoverTemplate } = this.model.metaData;
        if (popoverTemplate) {
            this.popoverTemplate = useViewCompiler(GanttCompiler, {
                popoverTemplate,
            }).popoverTemplate;
        }

        this.throttledOnPointerMove = throttleForAnimation((ev) => this.onPointerMove(ev));

        useExternalListener(window, "keydown", (ev) => this.onWindowKeyDown(ev));
        useExternalListener(window, "keyup", (ev) => this.onWindowKeyUp(ev));
        useExternalListener(window, "pointerup", (ev) => this.onSelectStop(ev));

        const computeColumnWidth = debounce(() => this.computeColumnWidth(), 100);
        useExternalListener(window, "resize", computeColumnWidth);

        useMultiHover({
            ref: this.rootRef,
            selector: ".o_gantt_group",
            related: ["data-row-id"],
            className: "o_gantt_group_hovered",
        });

        // Draggable pills
        this.cellForDrag = { el: null, part: 0 };
        const dragState = useGanttDraggable({
            enable: () => this.cellForDrag.el,
            // Refs and selectors
            ref: this.rootRef,
            hoveredCell: this.cellForDrag,
            elements: ".o_draggable",
            ignore: ".o_resize_handle,.o_connector_creator_bullet",
            cells: ".o_gantt_cell",
            // Style classes
            cellDragClassName: "o_gantt_cell o_drag_hover",
            ghostClassName: "o_dragged_pill_ghost",
            // Handlers
            onDragStart: () => {
                this.popover.close();
                this.setStickyRowFromCell(this.cellForDrag.el);
                this.interaction.mode = "drag";
            },
            onDragEnd: () => {
                this.setStickyRowFromCell(null);
                this.interaction.mode = null;
            },
            onDrop: (params) => this.dragPillDrop(params),
        });

        // Un-draggable pills
        const unDragState = useGanttUndraggable({
            // Refs and selectors
            ref: this.rootRef,
            elements: ".o_undraggable",
            ignore: ".o_resize_handle,.o_connector_creator_bullet",
            edgeScrolling: { enabled: false },
            // Handlers
            onDragStart: () => {
                this.interaction.mode = "locked";
            },
            onDragEnd: () => {
                this.interaction.mode = null;
            },
        });

        // Resizable pills
        const resizeState = useGanttResizable({
            // Refs and selectors
            ref: this.cellContainerRef,
            elements: ".o_resizable",
            innerPills: ".o_gantt_pill",
            cells: ".o_gantt_cell",
            // Other params
            handles: "o_resize_handle",
            showHandles: (pillEl) => {
                const pill = this.pills[pillEl.dataset.pillId];
                const hideHandles = this.connectorDragState.dragging;
                return {
                    start: !pill.disableStartResize && !hideHandles,
                    end: !pill.disableStopResize && !hideHandles,
                };
            },
            rtl: () => localization.direction === "rtl",
            precision: () => this.model.metaData.scale.cellPart,
            // Handlers
            onDragStart: ({ pill, addClass }) => {
                this.popover.close();
                addClass(pill, "o_resized");
                this.interaction.mode = "resize";
            },
            onDrag: ({ pill, direction, diff }) => {
                const rect = pill.getBoundingClientRect();
                const position = { top: rect.y + rect.height };
                if (direction === "start") {
                    position.left = rect.x;
                } else {
                    position.right = document.body.offsetWidth - rect.x - rect.width;
                }
                const { cellTime, unitDescription } = this.model.metaData.scale;
                Object.assign(this.resizeBadgeReactive, {
                    position,
                    diff: diff * cellTime,
                    scale: unitDescription,
                });
            },
            onDragEnd: ({ pill, removeClass }) => {
                delete this.resizeBadgeReactive.position;
                delete this.resizeBadgeReactive.diff;
                delete this.resizeBadgeReactive.scale;
                removeClass(pill, "o_resized");
                this.interaction.mode = null;
            },
            onDrop: (params) => this.resizePillDrop(params),
        });

        // Draggable connector
        let initialPillId;
        this.connectorDragState = useGanttConnectorDraggable({
            ref: this.rootRef,
            elements: ".o_connector_creator_bullet",
            parentWrapper: ".o_gantt_cells .o_gantt_pill_wrapper",
            onDragStart: ({ sourcePill, x, y, addClass }) => {
                this.popover.close();
                initialPillId = sourcePill.dataset.pillId;
                addClass(sourcePill, "o_connector_creator_lock");
                this.setConnector({
                    id: NEW_CONNECTOR_ID,
                    highlighted: true,
                    sourcePoint: { left: x, top: y },
                    targetPoint: { left: x, top: y },
                });
                this.interaction.mode = "connect";
            },
            onDrag: ({ x, y }) => {
                this.setConnector({ id: NEW_CONNECTOR_ID, targetPoint: { left: x, top: y } });
            },
            onDragEnd: () => {
                this.setConnector({ id: NEW_CONNECTOR_ID, sourcePoint: null, targetPoint: null });
                this.interaction.mode = null;
            },
            onDrop: ({ target }) => {
                if (initialPillId === target.dataset.pillId) {
                    return;
                }
                const { id: masterId } = this.pills[initialPillId].record;
                const { id: slaveId } = this.pills[target.dataset.pillId].record;
                this.model.createDependency(masterId, slaveId);
            },
        });

        this.dragStates = [dragState, unDragState, resizeState];

        onWillUpdateProps(this.computeDerivedParams);
        onWillRender(this.onWillRender);

        /** @type {Row[]} */
        this.virtualRows = useVirtual({
            getItems: () => this.rows,
            getItemHeight: (row) => this.getRowHeight(row),
            initialScroll: this.props.scrollPosition,
            scrollableRef: this.props.contentRef,
        });

        this.computeDerivedParams();
    }

    //-------------------------------------------------------------------------
    // Getters
    //-------------------------------------------------------------------------

    get isDragging() {
        return this.dragStates.some((s) => s.dragging);
    }

    /**
     * @returns {boolean}
     */
    get isTouchDevice() {
        return isMobileOS() || hasTouch();
    }

    /**
     * @returns {number}
     */
    get pillHeight() {
        return this.constructor.GRID_ROW_HEIGHT * this.constructor.ROW_SPAN;
    }

    /**
     * @returns {number}
     */
    get rowHeight() {
        return this.constructor.GRID_ROW_HEIGHT;
    }

    //-------------------------------------------------------------------------
    // Methods
    //-------------------------------------------------------------------------

    /**
     * @param {Pill} pill
     * @param {Group} group
     */
    addTo(pill, group) {
        group.pills.push(pill);
        group.aggregateValue++; // pill count
        return true;
    }

    /**
     * Aggregates overlapping pills in group rows.
     *
     * @param {Pill[]} pills
     */
    aggregatePills(pills) {
        /** @type {Record<number, Group>} */
        const groups = {};
        for (let col = 1; col <= this.subColumns.length; col++) {
            groups[col] = {
                break: false,
                col,
                pills: [],
                aggregateValue: 0,
                grid: { column: [col, 1] },
            };
            // group.break = true means that the group cannot be merged with the previous one
            // We will merge groups that can be merged together (if this.shouldMergeGroups returns true)
        }

        for (const pill of pills) {
            let addedInPreviousCol = false;
            let col;
            for (col = this.getFirstcol(pill); col <= this.getLastCol(pill); col++) {
                const group = groups[col];
                const added = this.addTo(pill, group);
                if (addedInPreviousCol !== added) {
                    group.break = true;
                }
                addedInPreviousCol = added;
            }
            // here col = this.getLastCol(pill) + 1
            if (addedInPreviousCol && col <= this.subColumns.length) {
                groups[col].break = true;
            }
        }

        const filteredGroups = Object.values(groups).filter((g) => g.pills.length);

        if (this.shouldMergeGroups()) {
            return this.mergeGroups(filteredGroups);
        }

        return filteredGroups;
    }

    /**
     * Compute minimal levels required to display all pills without overlapping.
     * Side effect: level key is modified in pills.
     *
     * @param {Pill[]} pills
     */

    /**
     * Returns the column indexes which fits both given dates inside
     * @param {DateTime} start
     * @param {DateTime} end
     * @param {DateTime[]} dates
     * @returns {[number, number]}
     */
    computeColumnIndexes(start, end, dates) {
        let startIndex, endIndex;
        for (let index = 0; index < dates.length; index++) {
            if (dates[index].ts <= start) {
                startIndex = index;
            }
            if (dates[index].ts >= end) {
                endIndex = index;
                break;
            }
        }
        return [startIndex, endIndex];
    }

    computeColumns() {
        this.columns = [];
        this.subColumns = [];
        this.dateGridColumns = [];

        const { scale, startDate, stopDate } = this.model.metaData;
        const { cellPart, cellTime, interval, time } = scale;
        const now = DateTime.local();
        let cellIndex = 1;
        let colOffset = 1;
        let date;
        for (date = startDate; date <= stopDate; date = date.plus({ [interval]: 1 })) {
            const start = date;
            const stop = date.endOf(interval);
            const index = cellIndex++;
            const columnId = `__column__${index}`;
            const column = {
                id: columnId,
                grid: { column: [colOffset, cellPart] },
                start,
                stop,
            };
            const isToday =
                (["week", "month"].includes(scale.id) && date.hasSame(now, "day")) ||
                (scale.id === "year" && date.hasSame(now, "month")) ||
                (scale.id === "day" && date.hasSame(now, "hour"));

            if (isToday) {
                column.isToday = true;
            }

            this.columns.push(column);

            for (let i = 0; i < cellPart; i++) {
                const subCellStart = dateAddFixedOffset(start, { [time]: i * cellTime });
                const subCellStop = dateAddFixedOffset(start, {
                    [time]: (i + 1) * cellTime,
                    seconds: -1,
                });
                this.subColumns.push({ start: subCellStart, stop: subCellStop, isToday, columnId });
                this.dateGridColumns.push(subCellStart);
            }

            colOffset += cellPart;
        }

        this.dateGridColumns.push(date);
    }

    computeColumnWidth() {
        const { cellPart } = this.model.metaData.scale;
        const subColumnCount = this.columns.length * cellPart;
        const totalWidth = browser.innerWidth;

        // Set độ rộng cố định cho row header (500px để chứa 4 cột)
        const rowHeaderWidth = 600;
        const cellContainerWidth = totalWidth - rowHeaderWidth;

        this.state.rowHeaderWidth = rowHeaderWidth;
        this.state.pillsWidth = cellContainerWidth / subColumnCount;

        // Cập nhật biến CSS
        if (this.rootRef.el) {
            this.rootRef.el.style.setProperty('--Gantt__RowHeader-width', `${rowHeaderWidth}px`);
        }
    }

    computeDerivedParams() {
        const { rows: modelRows } = this.model.data;
        console.log('Model rows input:', modelRows);

        if (this.shouldRenderConnectors()) {
            /** @type {Record<number, { masterIds: number[], pills: Record<RowId, Pill> }>} */
            this.mappingRecordToPillsByRow = {};
            /** @type {Record<RowId, Record<number, Pill>>} */
            this.mappingRowToPillsByRecord = {};
            /** @type {Record<ConnectorId, { sourcePillId: PillId, targetPillId: PillId }>} */
            this.mappingConnectorToPills = {};
            /** @type {Record<PillId, ConnectorId>} */
            this.mappingPillToConnectors = {};
        }

        this.topOffset = 0;
        this.nextPillId = 1;

        this.pills = {}; // mapping to retrieve pills from pill ids
        this.rows = [];
        this.rowIds = [];

        this.computeColumns();
        this.computeColumnWidth();

        const prePills = this.getPills();

        let pillsToProcess = [...prePills];
        for (const row of modelRows) {
            const result = this.processRow(row, pillsToProcess);
            this.rows.push(...result.rows);
            pillsToProcess = result.pillsToProcess;
        }

        this.gridTemplate = this.computeGrid(this.rows, this.columns);

        const { displayTotalRow } = this.model.metaData;
        if (displayTotalRow) {
            this.totalRow = this.getTotalRow(prePills);
        }

        if (this.shouldRenderConnectors()) {
            this.initializeConnectors();
            this.generateConnectors();
            this.generateParentChildConnectors().then(connectorCount => {
                console.log(`Parent-child connectors generation completed: ${connectorCount} connectors`);
                // THÊM: Debug template rendering
                setTimeout(() => {
                    this.debugTemplateRendering();
                }, 100);
            }).catch(error => {
                console.error('Error generating parent-child connectors:', error);
            });
        }
    }

    /**
     * @param {PointerEvent} ev
     */
    computeDerivedParamsFromHover(ev) {
        const { scale } = this.model.metaData;

        const { connector, hoverable, pill } = this.hovered;

        // Update cell in drag
        const isCellHovered = hoverable?.matches(".o_gantt_cell");
        this.cellForDrag.el = isCellHovered ? hoverable : null;
        this.cellForDrag.part = 0;
        if (isCellHovered && scale.cellPart > 1) {
            const rect = hoverable.getBoundingClientRect();
            const x = Math.floor(rect.x);
            const width = Math.floor(rect.width);
            this.cellForDrag.part = Math.floor((ev.clientX - x) / (width / scale.cellPart));
        }

        if (this.isDragging) {
            this.progressBarsReactive.el = null;
            return;
        }

        if (!this.connectorDragState.dragging) {
            // Highlight connector
            const hoveredConnectorId = connector?.dataset.connectorId;
            for (const connectorId in this.connectors) {
                if (connectorId !== hoveredConnectorId) {
                    this.toggleConnectorHighlighting(connectorId, false);
                }
            }
            if (hoveredConnectorId) {
                this.progressBarsReactive.el = null;
                return this.toggleConnectorHighlighting(hoveredConnectorId, true);
            }
        }

        // Highlight pill
        const hoveredPillId = pill?.dataset.pillId;
        for (const pillId in this.pills) {
            if (pillId !== hoveredPillId) {
                this.togglePillHighlighting(pillId, false);
            }
        }
        this.togglePillHighlighting(hoveredPillId, true);

        // Update cell buttons
        if (
            this.selection.active &&
            isCellHovered &&
            Number(hoverable.dataset.columnIndex) !== this.selection.lastSelectId
        ) {
            const isUngroupedCellHovered = hoverable?.matches(".o_gantt_cell:not(.o_gantt_group)");
            if (isUngroupedCellHovered && !ev?.target.closest(".o_connector_creator")) {
                const columnIndex = Number(hoverable.dataset.columnIndex);
                const columnStart = Math.min(this.selection.initialIndex, columnIndex);
                const columnStop = Math.max(this.selection.initialIndex, columnIndex);
                this.selection.lastSelectId = columnIndex;
                for (const cell of this.getCellsOnRow(this.selection.rowId)) {
                    if (
                        cell.dataset.columnIndex < columnStart ||
                        cell.dataset.columnIndex > columnStop
                    ) {
                        cell.classList.remove("o_drag_hover");
                    } else {
                        cell.classList.add("o_drag_hover");
                    }
                }
            }
        }

        // Update progress bars
        this.progressBarsReactive.el = hoverable;
    }

    /**
     * @param {Row[]} rows
     * @param {Column[]} columns
     * @returns {{ rows: number, columns: number }}
     */
    computeGrid(rows, columns) {
        const { cellPart } = this.model.metaData.scale;
        return {
            rows: rows.reduce((acc, row) => acc + row.grid.row[1], 0),
            columns: columns.length * cellPart,
        };
    }

    /**
     * @param {ConnectorId} connectorId
     */
    deleteConnector(connectorId) {
        delete this.connectors[connectorId];
        delete this.mappingConnectorToPills[connectorId];
        delete this.parentChildMapping[connectorId];
    }

    /**
     * @param {Object} params
     * @param {Element} params.pill
     * @param {Element} params.cell
     * @param {number} params.diff
     */
    async dragPillDrop({ pill, cell, diff }) {
        const { rowId } = cell.dataset;
        const { dateStartField, dateStopField, scale } = this.model.metaData;
        const { cellTime, time } = scale;
        const { record } = this.pills[pill.dataset.pillId];

        const start =
            diff && dateAddFixedOffset(record[dateStartField], { [time]: cellTime * diff });
        const stop = diff && dateAddFixedOffset(record[dateStopField], { [time]: cellTime * diff });
        const schedule = this.model.getSchedule({ rowId, start, stop });

        if (this.interaction.dragAction === "copy") {
            await this.model.copy(record.id, schedule, this.openPlanDialogCallback);
        } else {
            await this.model.reschedule(record.id, schedule, this.openPlanDialogCallback);
        }

        // If the pill lands on a closed group -> open it
        if (cell.classList.contains("o_gantt_group") && this.model.isClosed(rowId)) {
            this.model.toggleRow(rowId);
        }
    }

    /**
     * @param {Partial<Pill>} pill
     * @returns {Pill}
     */
    enrichPill(pill) {
        const { colorField, fields, pillDecorations, progressField } = this.model.metaData;

        pill.displayName = this.getDisplayName(pill);

        const classes = [];

        if (pillDecorations) {
            const pillContext = Object.assign({}, this.userService.context);
            for (const [fieldName, value] of Object.entries(pill.record)) {
                const field = fields[fieldName];
                switch (field.type) {
                    case "date": {
                        pillContext[fieldName] = value ? serializeDate(value) : false;
                        break;
                    }
                    case "datetime": {
                        pillContext[fieldName] = value ? serializeDateTime(value) : false;
                        break;
                    }
                    default: {
                        pillContext[fieldName] = value;
                    }
                }
            }

            for (const decoration in pillDecorations) {
                const expr = pillDecorations[decoration];
                if (evaluateBooleanExpr(expr, pillContext)) {
                    classes.push(decoration);
                }
            }
        }

        if (colorField) {
            pill._color = getColorIndex(pill.record[colorField]);
            classes.push(`o_gantt_color_${pill._color}`);
        }

        if (progressField) {
            pill._progress = pill.record[progressField] || 0;
        }

        pill.className = classes.join(" ");

        return pill;
    }

    generateConnectors() {
        this.nextConnectorId = 1;
        this.setConnector({
            id: NEW_CONNECTOR_ID,
            highlighted: true,
            sourcePoint: null,
            targetPoint: null,
        });
        for (const slaveId in this.mappingRecordToPillsByRow) {
            const { masterIds, pills: slavePills } = this.mappingRecordToPillsByRow[slaveId];
            for (const masterId of masterIds) {
                if (!(masterId in this.mappingRecordToPillsByRow)) {
                    continue;
                }
                const { pills: masterPills } = this.mappingRecordToPillsByRow[masterId];
                for (const [slaveRowId, targetPill] of Object.entries(slavePills)) {
                    for (const [masterRowId, sourcePill] of Object.entries(masterPills)) {
                        if (
                            masterRowId === slaveRowId ||
                            !(
                                slaveId in this.mappingRowToPillsByRecord[masterRowId] ||
                                masterId in this.mappingRowToPillsByRecord[slaveRowId]
                            ) ||
                            Object.keys(this.mappingRecordToPillsByRow[slaveId].pills).every(
                                (rowId) =>
                                    rowId !== masterRowId &&
                                    masterId in this.mappingRowToPillsByRecord[rowId]
                            ) ||
                            Object.keys(this.mappingRecordToPillsByRow[masterId].pills).every(
                                (rowId) =>
                                    rowId !== slaveRowId &&
                                    slaveId in this.mappingRowToPillsByRecord[rowId]
                            )
                        ) {
                            const masterRecord = sourcePill.record;
                            const slaveRecord = targetPill.record;
                            this.setConnector(
                                { alert: this.getConnectorAlert(masterRecord, slaveRecord) },
                                sourcePill.id,
                                targetPill.id
                            );
                        }
                    }
                }
            }
        }
    }

    /**
     * @param {Group} group
     * @param {Group} previousGroup
     */
    getAggregateValue(group, previousGroup) {
        // both groups have the same pills by construction
        // here the aggregateValue is the pill count
        return group.aggregateValue;
    }

    /**
     * @param {number} columnStart
     * @param {number} columnStop
     */
    getColumnStartStop(columnStartIndex, columnStopIndex = columnStartIndex) {
        const { start } = this.columns[columnStartIndex];
        const { stop } = this.columns[columnStopIndex];
        return { start, stop };
    }

    /**
     *
     * @param {number} masterRecord
     * @param {number} slaveRecord
     * @returns {import("./gantt_connector").ConnectorAlert | null}
     */
    getConnectorAlert(masterRecord, slaveRecord) {
        const { dateStartField, dateStopField } = this.model.metaData;
        if (slaveRecord[dateStartField] < masterRecord[dateStopField]) {
            if (slaveRecord[dateStartField] < masterRecord[dateStartField]) {
                return "error";
            } else {
                return "warning";
            }
        }
        return null;
    }

    /**
     * @param {string} rowId
     * @returns {NodeList[]}
     */
    getCellsOnRow(rowId) {
        return this.cellContainerRef.el.querySelectorAll(
            `.o_gantt_cell[data-row-id='${CSS.escape(rowId)}']`
        );
    }

    /**
     * This function will add a 'label' property to each
     * non-consolidated pill included in the pills list.
     * This new property is a string meant to replace
     * the text displayed on a pill.
     *
     * @param {Pill} pill
     */
    getDisplayName(pill) {
        const { computePillDisplayName, dateStartField, dateStopField, scale } =
            this.model.metaData;
        const { id: scaleId } = scale;
        const { record } = pill;

        if (!computePillDisplayName) {
            return record.display_name;
        }

        const startDate = record[dateStartField];
        const stopDate = record[dateStopField];
        const yearlessDateFormat = omit(DateTime.DATE_SHORT, "year");

        const spanAccrossDays =
            stopDate.startOf("day") > startDate.startOf("day") &&
            startDate.endOf("day").diff(startDate, "hours").toObject().hours >= 3 &&
            stopDate.diff(stopDate.startOf("day"), "hours").toObject().hours >= 3;
        const spanAccrossWeeks =
            computeRange("week", stopDate).start > computeRange("week", startDate).start;
        const spanAccrossMonths = stopDate.startOf("month") > startDate.startOf("month");

        /** @type {string[]} */
        const labelElements = [];

        // Start & End Dates
        if (scaleId === "year" && !spanAccrossDays) {
            labelElements.push(startDate.toLocaleString(yearlessDateFormat));
        } else if (
            (scaleId === "day" && spanAccrossDays) ||
            (scaleId === "week" && spanAccrossWeeks) ||
            (scaleId === "month" && spanAccrossMonths) ||
            (scaleId === "year" && spanAccrossDays)
        ) {
            labelElements.push(startDate.toLocaleString(yearlessDateFormat));
            labelElements.push(stopDate.toLocaleString(yearlessDateFormat));
        }

        // Start & End Times
        if (record.allocated_hours && !spanAccrossDays && ["week", "month"].includes(scaleId)) {
            const durationStr = formatFloatTime(record.allocated_hours, {
                noLeadingZeroHour: true,
            }).replace(/(:00|:)/g, "h");
            labelElements.push(
                startDate.toFormat("t"),
                `${stopDate.toFormat("t")} (${durationStr})`
            );
        }

        // Original Display Name
        if (scaleId !== "month" || !record.allocated_hours || spanAccrossDays) {
            labelElements.push(record.display_name);
        }

        return labelElements.filter((el) => !!el).join(" - ");
    }

    /**
     * @param {Pill} pill
     * @returns {number}
     */
    getFirstcol(pill) {
        return pill.grid.column[0];
    }

    /**
     * @returns {string}
     */
    getFormattedFocusDate() {
        const { focusDate, scale } = this.model.metaData;
        const { format, id: scaleId } = scale;
        switch (scaleId) {
            case "day":
            case "month":
            case "year":
                return formatDateTime(focusDate, { format });
            case "week": {
                const { startDate, stopDate } = this.model.metaData;
                const start = formatDateTime(startDate, { format });
                const stop = formatDateTime(stopDate, { format });
                return `${start} - ${stop}`;
            }
            default:
                throw new Error(`Unknown scale id "${scaleId}".`);
        }
    }

    /**
     * @param {Pill} pill
     */
    getGroupPillDisplayName(pill) {
        return pill.aggregateValue;
    }

    /**
     * @param {{ column?: number | number[], row?: number | number[] }} position
     */
    getGridPosition(position) {
        const style = [];
        for (const prop of ["column", "row"]) {
            const [index, span] = Array.isArray(position[prop]) ? position[prop] : [position[prop]];
            if (span && span !== 1) {
                if (span === -1) {
                    style.push(`grid-${prop}:${index} / -1`);
                } else {
                    style.push(`grid-${prop}:${index} / span ${span}`);
                }
            } else if (index) {
                style.push(`grid-${prop}:${index}`);
            }
        }
        return style.join(";");
    }

    /**
     * @param {Pill} pill
     */
    getLastCol(pill) {
        const [col, colspan] = pill.grid.column;
        return col + colspan - 1;
    }

    /**
     * @param {RelationalRecord} record
     * @returns {Partial<Pill>}
     */
    getPill(record) {
        const { canEdit, dateStartField, dateStopField, disableDrag, startDate, stopDate } =
            this.model.metaData;

        const startOutside = record[dateStartField] < startDate;
        const stopOutside = record[dateStopField] > stopDate;

        /** @type {DateTime} */
        const pillStartDate = startOutside ? startDate : record[dateStartField];
        /** @type {DateTime} */
        const pillStopDate = stopOutside ? stopDate : record[dateStopField];

        const disableStartResize = !canEdit || startOutside;
        const disableStopResize = !canEdit || stopOutside;

        const [startIndex, stopIndex] = this.computeColumnIndexes(
            pillStartDate,
            pillStopDate,
            this.dateGridColumns
        );

        const firstCol = startIndex + 1;
        const span = stopIndex - startIndex;

        /** @type {Partial<Pill>} */
        const pill = {
            disableDrag: disableDrag || disableStartResize || disableStopResize,
            disableStartResize,
            disableStopResize,
            grid: { column: [firstCol, span] },
            record,
            startDate: this.dateGridColumns[startIndex],
            stopDate: this.dateGridColumns[stopIndex],
            level: 0, // QUAN TRỌNG: Luôn set level = 0
        };

        return pill;
    }

    /**
     * @param {PillId} pillId
     */
    getPillEl(pillId) {
        return this.getPillWrapperEl(pillId).querySelector(".o_gantt_pill");
    }

    /**
     * @param {Object} group
     * @param {number} maxAggregateValue
     * @param {boolean} consolidate
     */
    getPillFromGroup(group, maxAggregateValue, consolidate) {
        const { excludeField, field, maxValue } = this.model.metaData.consolidationParams;

        const minColor = 215;
        const maxColor = 100;

        const newPill = {
            id: `__pill__${this.nextPillId++}`,
            level: 0,
            aggregateValue: group.aggregateValue,
            grid: group.grid,
        };

        // Enrich the aggregates with consolidation data
        if (consolidate && field) {
            newPill.consolidationValue = 0;
            for (const pill of group.pills) {
                if (!pill.record[excludeField]) {
                    newPill.consolidationValue += pill.record[field];
                }
            }
            newPill.consolidationMaxValue = maxValue;
            newPill.consolidationExceeded =
                newPill.consolidationValue > newPill.consolidationMaxValue;
        }

        if (consolidate && maxValue) {
            const status = newPill.consolidationExceeded ? "danger" : "success";
            newPill.className = `bg-${status} border-${status}`;
            newPill.displayName = newPill.consolidationValue;
        } else {
            const color =
                minColor -
                Math.round((newPill.aggregateValue - 1) / maxAggregateValue) *
                    (minColor - maxColor);
            newPill.style = `background-color:rgba(${color},${color},${color},0.6)`;
            newPill.displayName = this.getGroupPillDisplayName(newPill);
        }

        return newPill;
    }

    /**
     * There are two forms of pills: pills comming from fetched records
     * and pills that are some kind of aggregation of the previous.
     *
     * Here we create the pills of the firs type.
     *
     * The basic properties (independent of rows,...) of the pills of
     * the first type should be computed here.
     *
     * @returns {Partial<Pill>[]}
     */
    getPills() {
        const { records } = this.model.data;
        const { dateStartField } = this.model.metaData;
        const pills = [];
        for (const record of records) {
            const pill = this.getPill(record);
            pills.push(this.enrichPill(pill));
        }
        // sorting cannot be done when fetching data --> the snapping of pills breaks order
        return pills.sort(
            (p1, p2) =>
                p1.grid.column[0] - p2.grid.column[0] ||
                p1.record[dateStartField] - p2.record[dateStartField]
        );
    }

    /**
     * @param {PillId} pillId
     */
    getPillWrapperEl(pillId) {
        const pillSelector = `:scope > [data-pill-id="${pillId}"]`;
        return this.cellContainerRef.el?.querySelector(pillSelector);
    }

    /**
     * Get domain of records for plan dialog in the gantt view.
     *
     * @param {Object} state
     * @returns {any[][]}
     */
    getPlanDialogDomain() {
        const { dateStartField, dateStopField } = this.model.metaData;
        const newDomain = Domain.removeDomainLeaves(this.env.searchModel.globalDomain, [
            dateStartField,
            dateStopField,
        ]);
        return Domain.and([
            newDomain,
            ["|", [dateStartField, "=", false], [dateStopField, "=", false]],
        ]).toList({});
    }

    /**
     * @param {PillId} pillId
     * @param {boolean} onRight
     */
    getPoint(pillId, onRight) {
        const pillWrapper = this.getPillWrapperEl(pillId);
        if (!pillWrapper) {
            console.warn("getPoint: pill wrapper not found for", pillId);
            return { left: 0, top: 0 };
        }
        const pillEl = pillWrapper.querySelector(".o_gantt_pill");
        if (!pillEl) {
            console.warn("getPoint: .o_gantt_pill not found in wrapper", pillId);
            return { left: 0, top: 0 };
        }

        const rect = pillEl.getBoundingClientRect();
        const scrollContainer = this.rootRef.el.querySelector(".o_gantt_cells");
        const scrollLeft = scrollContainer?.scrollLeft || 0;
        const scrollTop = scrollContainer?.scrollTop || 0;

        if (localization.direction === "rtl") {
            onRight = !onRight;
        }

        return {
            left: rect.left + scrollLeft + (onRight ? rect.width : 0),
            top: rect.top + scrollTop + rect.height / 2,
        };
    }

    /**
     * @param {Pill} pill
     */
    getPopoverProps(pill) {
        const { record } = pill;
        const displayName = record.display_name;
        const { canEdit, dateStartField, dateStopField } = this.model.metaData;
        const context = this.popoverTemplate
            ? { ...record }
            : /* Default context */ {
                  name: displayName,
                  start: record[dateStartField].toFormat("f"),
                  stop: record[dateStopField].toFormat("f"),
              };

        return {
            title: displayName,
            context,
            template: this.popoverTemplate,
            button: {
                text: canEdit ? _t("Edit") : _t("View"),
                // Sync with the mutex to wait for potential changes on the view
                onClick: () =>
                    this.model.mutex.exec(
                        () => this.props.openDialog({ resId: record.id }) // (canEdit is also considered in openDialog)
                    ),
            },
        };
    }

    /**
     * @param {Row} row
     */
    getProgressBarProps(row) {
        return {
            progressBar: row.progressBar,
            reactive: this.progressBarsReactive,
            rowId: row.id,
        };
    }

    /**
     * @param {Unavailability[]} unavailabilities
     */
    getRowCellColors(unavailabilities) {
        const { cellPart } = this.model.metaData.scale;
        // We assume that the unavailabilities have been normalized
        // (i.e. are naturally ordered and are pairwise disjoint).
        // A subCell is considered unavailable (and greyed) when totally covered by
        // an unavailability.
        let index = 0;
        let j = 0;
        /** @type {Record<string, string>} */
        const cellColors = {};
        const subSlotUnavailabilities = [];
        for (const subColumn of this.subColumns) {
            const { isToday, start, stop, columnId } = subColumn;
            if (unavailabilities.slice(index).length) {
                let subSlotUnavailable = 0;
                for (let i = index; i < unavailabilities.length; i++) {
                    const u = unavailabilities[i];
                    if (stop > u.stop) {
                        index++;
                    } else if (u.start <= start) {
                        subSlotUnavailable = 1;
                        break;
                    }
                }
                subSlotUnavailabilities.push(subSlotUnavailable);
                if ((j + 1) % cellPart === 0) {
                    const style = getCellColor(cellPart, subSlotUnavailabilities, isToday);
                    subSlotUnavailabilities.splice(0, cellPart);
                    if (style) {
                        cellColors[columnId] = style;
                    }
                }
                j++;
            }
        }
        return cellColors;
    }

    /**
     * @param {Row} row
     */
    getRowHeight(row) {
        return row.grid.row[1] * this.constructor.GRID_ROW_HEIGHT;
    }

    getRowTitleStyle(row) {
        return this.getGridPosition({ column: row.grid.column });
    }

    openPlanDialogCallback() {}

    getSelectCreateDialogProps(params) {
        const domain = this.getPlanDialogDomain();

        // BƯỚC 1: Lấy raw schedule từ model (có thể chứa DateTime)
        const raw = this.model.getDialogContext(params);

        // BƯỚC 2: Serialize SẠCH 100% – không để sót DateTime nào
        const schedule = {};
        for (const key in raw) {
            const val = raw[key];
            if (val === undefined || val === null) {
                schedule[key] = false;
            } else if (val && typeof val.isLuxonDateTime !== "undefined" && val.isLuxonDateTime) {
                schedule[key] = val.toISO();               // luxon DateTime
            } else if (val instanceof DateTime) {
                schedule[key] = val.toISO();
            } else if (typeof val === "object") {
                // Các default_xxx nhiều khi là [id, name] hoặc {id, ...}
                if (Array.isArray(val) && val.length === 2 && typeof val[0] === "number") {
                    schedule[key] = val[0];                // many2one dạng [id, name]
                } else if (val && val.id !== undefined) {
                    schedule[key] = val.id;
                } else {
                    schedule[key] = false;                 // bỏ hết object phức tạp
                }
            } else {
                schedule[key] = val;
            }
        }

        return {
            title: _t("Plan"),
            resModel: this.model.metaData.resModel,
            context: schedule,        // ĐÃ SẠCH HOÀN TOÀN → không còn DateTime
            domain,
            noCreate: !this.model.metaData.canCellCreate,
            onSelected: (resIds) => {
                if (resIds.length) {
                    this.model.reschedule(resIds, schedule, this.openPlanDialogCallback.bind(this));
                }
            },
        };
    }

    /**
     * @param {Pill[]} pills
     */
    getTotalRow(pills) {
        const preRow = {
            groupLevel: 0,
            id: "[]",
            isGroup: true,
            rows: [],
            name: _t("Total"),
            recordIds: pills.map(({ record }) => record.id),
        };

        this.topOffset = 0;
        const result = this.processRow(preRow, pills);
        const [totalRow] = result.rows;
        const maxAggregateValue = Math.max(...totalRow.pills.map((p) => p.aggregateValue));

        totalRow.factor = maxAggregateValue ? 90 / maxAggregateValue : 0;

        return totalRow;
    }

    getTodayDay() {
        return DateTime.local().day;
    }

    highlightPill(pillId, highlighted) {
        const pill = this.pills[pillId];
        if (!pill) {
            return;
        }
        pill.highlighted = highlighted;
        const pillWrapper = this.getPillWrapperEl(pillId);
        pillWrapper?.classList.toggle("highlight", highlighted);
        pillWrapper?.classList.toggle(
            "o_connector_creator_highlight",
            highlighted && this.connectorDragState.dragging
        );
    }

    initializeConnectors() {
        for (const connectorId in this.connectors) {
            this.deleteConnector(connectorId);
        }
    }

    isPillSmall(pill) {
        return this.state.pillsWidth * pill.grid.column[1] < (pill.displayName.length * 10);
    }

    /**
     * @param {Row} row
     */
    isDisabled(row) {
        return this.model.useSampleModel;
    }

    /**
     * @param {Row} row
     */
    isHoverable(row) {
        return !this.model.useSampleModel;
    }

    /**
     * @param {Group[]} groups
     * @returns {Group[]}
     */
    mergeGroups(groups) {
        if (groups.length <= 1) {
            return groups;
        }
        const index = Math.floor(groups.length / 2);
        const left = this.mergeGroups(groups.slice(0, index));
        const right = this.mergeGroups(groups.slice(index));
        const group = right[0];
        if (!group.break) {
            const previousGroup = left.pop();
            group.break = previousGroup.break;
            group.grid.column[0] = previousGroup.grid.column[0];
            group.grid.column[1] += previousGroup.grid.column[1];
            group.aggregateValue = this.getAggregateValue(group, previousGroup);
        }
        return [...left, ...right];
    }

    onWillRender() {
        if (this.noDisplayedConnectors && this.shouldRenderConnectors()) {
            delete this.noDisplayedConnectors;
            this.computeDerivedParams();
        }

        this.visibleRows = [...new Set([...toRaw(this.virtualRows), ...this.extraRows])];

        if (!this.shouldRenderConnectors()) {
            this.noDisplayedConnectors = true;
            return;
        }

        const displayedPills = new Set();
        const visibleConnectorIds = new Set([NEW_CONNECTOR_ID]);

        console.log('=== ON WILL RENDER DEBUG ===');
        console.log('Visible rows:', this.visibleRows.length);
        console.log('Virtual rows:', this.virtualRows.length);
        console.log('Extra rows:', this.extraRows.length);

        // 1. Collect connectors từ pills được display
        for (const row of this.visibleRows) {
            if (row.isGroup) {
                continue;
            }
            for (const pill of row.pills) {
                displayedPills.add(pill.id);
                for (const connectorId of this.mappingPillToConnectors[pill.id] || []) {
                    visibleConnectorIds.add(connectorId);
                }
            }
        }

        // 2. QUAN TRỌNG: Thêm TẤT CẢ parent-child connectors vào visible
        console.log('Parent-child mapping:', Object.keys(this.parentChildMapping));
        for (const connectorId in this.parentChildMapping) {
            if (this.connectors[connectorId]) {
                visibleConnectorIds.add(connectorId);
                console.log('✓ Adding parent-child connector to visible:', connectorId);
            }
        }

        // 3. THÊM: Include tất cả connectors có source và target points hợp lệ
        for (const connectorId in this.connectors) {
            const connector = this.connectors[connectorId];
            // Nếu connector có source và target points, thêm vào visible
            if (connector.sourcePoint && connector.targetPoint &&
                !visibleConnectorIds.has(connectorId) &&
                connectorId !== NEW_CONNECTOR_ID) {
                visibleConnectorIds.add(connectorId);
                console.log('✓ Adding connector with valid points:', connectorId);
            }
        }

        console.log('Displayed pills:', displayedPills.size);
        console.log('Visible connector IDs:', Array.from(visibleConnectorIds));
        console.log('All connectors in memory:', Object.keys(this.connectors));

        this.visibleConnectors = [];
        const extraPillIds = new Set();

        for (const connectorId in this.connectors) {
            if (!visibleConnectorIds.has(connectorId)) {
                console.log('✗ Skipping connector:', connectorId);
                continue;
            }

            this.visibleConnectors.push(this.connectors[connectorId]);
            console.log('✓ Visible connector:', connectorId, this.connectors[connectorId]);

            const { sourcePillId, targetPillId } = this.mappingConnectorToPills[connectorId] || {};
            if (sourcePillId && !displayedPills.has(sourcePillId)) {
                extraPillIds.add(sourcePillId);
            }
            if (targetPillId && !displayedPills.has(targetPillId)) {
                extraPillIds.add(targetPillId);
            }
        }

        console.log('Total visible connectors:', this.visibleConnectors.length);
        console.log('Extra pill IDs:', Array.from(extraPillIds));

        this.extraPills = [];
        for (const id of extraPillIds) {
            this.extraPills.push(this.pills[id]);
        }
    }

    /**
     * @param {Row} row
     * @param {Pill[]} pills
     */
    processRow(row, pills) {
        console.log('=== PROCESS ROW DEBUG START ===');
        console.log('Row input:', {
            name: row.name || row.display_name || 'No name',
            id: row.id,
            isGroup: row.isGroup,
            groupLevel: row.groupLevel,
            hasRecord: !!row.record,
            recordId: row.record?.id,
            recordName: row.record?.display_name,
            hasRecordIds: !!row.recordIds,
            recordIdsCount: row.recordIds?.length || 0,
            hasRows: row.rows?.length > 0,
            rowsCount: row.rows?.length || 0
        });

        const { GROUP_ROW_SPAN, ROW_SPAN } = this.constructor;
        const { dependencyField, fields } = this.model.metaData;
        const {
            consolidate,
            fromServer,
            groupedBy,
            groupField,
            groupLevel,
            id,
            isGroup,
            name,
            progressBar,
            resId,
            rows: subRows,
            unavailabilities,
            recordIds,
            record, // QUAN TRỌNG: Lấy record từ row
        } = row;

        // TRƯỜNG HỢP ĐẶC BIỆT: Row có record và có parent_id -> ĐÂY LÀ SUBTASK
        // NHƯNG cần kiểm tra xem có nên tạo row riêng không
        if (record && record.parent_id) {
            console.log(`📌 FOUND SUBTASK: ${record.display_name} (Parent: ${record.parent_id})`);
            // Có 2 khả năng:
            // 1. Parent và subtask đều có trong cùng một group -> giữ nguyên
            // 2. Parent ở group khác -> cần tạo row riêng
            // Tạm thời cứ tạo row riêng cho subtask
            return this.createSubtaskRow(row, pills);
        }

        const currentGroupField = groupField || (groupedBy && groupedBy[groupLevel]);

        // TRƯỜNG HỢP 1: Group node từ server (có groupedBy và recordIds)
        if (currentGroupField && recordIds && recordIds.length > 0) {
            console.log(`Processing as SERVER GROUP: ${currentGroupField} at level ${groupLevel}`);
            return this.processMultiLevelGroup(row, pills, groupLevel, currentGroupField);
        }

        // TRƯỜNG HỢP 2: Group node thông thường (có rows)
        if (isGroup || (subRows && subRows.length > 0)) {
            console.log('Processing as REGULAR GROUP with sub-rows');
            return this.processGroupRow(row, pills);
        }

        // TRƯỜNG HỢP 3: Task node thông thường (không có rows, không phải group)
        console.log('Processing as REGULAR TASK NODE');
        console.log('Record:', record);
        console.log('Record IDs in row:', recordIds);

        const result = { rows: [], pillsToProcess: [] };

        const rowPills = [];
        const remainingPills = [];

        // QUAN TRỌNG: Sửa logic tìm pills
        if (recordIds && recordIds.length > 0) {
            // Trường hợp row có recordIds (từ server grouping)
            console.log('Row has recordIds, finding pills for these IDs');
            for (const pill of pills) {
                if (recordIds.includes(pill.record.id)) {
                    console.log(`Found pill for record ${pill.record.id}: ${pill.record.display_name}`);
                    rowPills.push(pill);
                } else {
                    remainingPills.push(pill);
                }
            }
        } else if (record && record.id) {
            // Trường hợp row có record trực tiếp
            console.log('Row has direct record, finding pill for this record');
            for (const pill of pills) {
                if (pill.record.id === record.id) {
                    console.log(`Found pill for record ${record.id}: ${record.display_name}`);
                    rowPills.push(pill);
                } else {
                    remainingPills.push(pill);
                }
            }
        } else {
            // Không có recordIds và không có record -> đây là lỗi
            console.error('❌ Row has no recordIds and no record! Row:', row);
            console.log('Available pills:', pills.length);
            // Fallback: giữ nguyên tất cả pills để xử lý sau
            result.pillsToProcess = pills;
            return result;
        }

        console.log(`Found ${rowPills.length} pills for this row`);
        console.log(`Remaining pills: ${remainingPills.length}`);

        // TẠO MỖI TASK MỘT ROW RIÊNG
        for (const pill of rowPills) {
            const taskRow = this.createTaskRow(row, pill);
            console.log(`Created task row: ${taskRow.name}`);
            result.rows.push(taskRow);
        }

        result.pillsToProcess = remainingPills;

        console.log('=== PROCESS ROW DEBUG END ===');
        console.log(`Created ${result.rows.length} rows, ${result.pillsToProcess.length} pills remaining`);

        return result;
    }

    /**
     * Tạo row riêng cho subtask
     * @param {Row} row
     * @param {Pill[]} pills
     */
    createSubtaskRow(row, pills) {
        console.log('=== CREATING SUBTASK ROW ===');
        console.log('Subtask:', row.record.display_name);
        console.log('Parent ID:', row.record.parent_id);

        const result = { rows: [], pillsToProcess: [] };

        // Tìm pill tương ứng với subtask này
        const matchingPills = pills.filter(pill => {
            if (!row.record) return false;
            return pill.record.id === row.record.id;
        });

        if (matchingPills.length === 0) {
            console.log('No matching pill found for subtask:', row.record.display_name);
            result.pillsToProcess = pills;
            return result;
        }

        // Tạo task row cho subtask (tương tự như createTaskRow nhưng thêm flags)
        const taskRow = this.createTaskRow(row, matchingPills[0]);

        // Đánh dấu đây là subtask
        taskRow.isSubtask = true;
        taskRow.parentTaskId = row.record.parent_id;

        // Parse parent ID
        if (Array.isArray(row.record.parent_id)) {
            taskRow.parentTaskId = row.record.parent_id[0]; // [id, name]
        } else if (typeof row.record.parent_id === 'object' && row.record.parent_id.id) {
            taskRow.parentTaskId = row.record.parent_id.id; // {id: ..., name: ...}
        }

        console.log('Created subtask row:', {
            name: taskRow.name,
            parentTaskId: taskRow.parentTaskId,
            isSubtask: taskRow.isSubtask
        });

        result.rows.push(taskRow);

        // Loại bỏ pill đã sử dụng khỏi danh sách
        result.pillsToProcess = pills.filter(pill => pill.record.id !== row.record.id);

        return result;
    }

    /**
     * @param {Object} params
     * @param {Element} params.pill
     * @param {number} params.diff
     * @param {"start" | "end"} params.direction
     */
    async resizePillDrop({ pill, diff, direction }) {
        const { dateStartField, dateStopField, scale } = this.model.metaData;
        const { cellTime, time } = scale;
        const { record } = this.pills[pill.dataset.pillId];
        const params = {};

        if (direction === "start") {
            params.start = dateAddFixedOffset(record[dateStartField], { [time]: cellTime * diff });
        } else {
            params.stop = dateAddFixedOffset(record[dateStopField], { [time]: cellTime * diff });
        }
        const schedule = this.model.getSchedule(params);

        await this.model.reschedule(record.id, schedule, this.openPlanDialogCallback);
    }

    /**
     * @param {Partial<ConnectorProps>} params
     * @param {PillId | null} [sourceId=null]
     * @param {PillId | null} [targetId=null]
     */
    setConnector(params, sourceId = null, targetId = null) {
        const connectorParams = { ...params };
        const connectorId = params.id || `__connector__${this.nextConnectorId++}`;

        // Thêm style đặc biệt cho parent-child connectors
        if (connectorId.startsWith('__parent_child__')) {
            connectorParams.className = 'o_parent_child_connector';
            connectorParams.alert = null; // Đảm bảo không có alert
            connectorParams.displayButtons = false; // Ẩn buttons
        }

        if (sourceId) {
            connectorParams.sourcePoint = () => this.getPoint(sourceId, true);
        }

        if (targetId) {
            connectorParams.targetPoint = () => this.getPoint(targetId, false);
        }

        if (this.connectors[connectorId]) {
            Object.assign(this.connectors[connectorId], connectorParams);
        } else {
            this.connectors[connectorId] = {
                id: connectorId,
                highlighted: false,
                displayButtons: false,
                ...connectorParams,
            };
            this.mappingConnectorToPills[connectorId] = {
                sourcePillId: sourceId,
                targetPillId: targetId,
            };
        }

        if (sourceId) {
            if (!this.mappingPillToConnectors[sourceId]) {
                this.mappingPillToConnectors[sourceId] = [];
            }
            this.mappingPillToConnectors[sourceId].push(connectorId);
        }

        if (targetId) {
            if (!this.mappingPillToConnectors[targetId]) {
                this.mappingPillToConnectors[targetId] = [];
            }
            this.mappingPillToConnectors[targetId].push(connectorId);
        }
    }

    /**
     * @param {HTMLElement | null} [cellEl]
     */
    setStickyRowFromCell(cellEl) {
        this.extraRows = [];
        if (cellEl) {
            const { rowId } = cellEl.dataset;
            const row = this.rows.find((row) => row.id === rowId);
            if (row) {
                this.extraRows.push(row);
            }
        }
    }

    /**
     * @param {Row} row
     */
    shouldComputeAggregateValues(row) {
        return true;
    }

    shouldMergeGroups() {
        return true;
    }

    /**
     * Returns whether connectors should be rendered or not.
     * The connectors won't be rendered on sampleData as we can't be sure that data are coherent.
     * The connectors won't be rendered on mobile as the usability is not guarantied.
     * The connectors won't be rendered on multiple groupBy as we would need to manage groups folding which seems
     *     overkill at this stage.
     *
     * @return {boolean}
     */
    shouldRenderConnectors() {
        return (
            this.model.metaData.dependencyField ||
            this.hasParentChildRelationships() || // THÊM ĐIỀU KIỆN NÀY
            (!this.model.useSampleModel &&
             !this.env.isSmall &&
             this.model.metaData.groupedBy.length <= 1)
        );
    }

    /**
     * Returns whether connectors should be rendered on particular records or not.
     * This method is intended to be overridden in particular modules in order to set particular record's condition.
     *
     * @param {RelationalRecord} record
     * @return {boolean}
     */
    shouldRenderRecordConnectors(record) {
        return this.shouldRenderConnectors();
    }

    /**
     * @param {ConnectorId | null} connectorId
     * @param {boolean} highlighted
     */
    toggleConnectorHighlighting(connectorId, highlighted) {
        const connector = this.connectors[connectorId];
        if (!connector || (!connector.highlighted && !highlighted)) {
            return;
        }

        connector.highlighted = highlighted;
        connector.displayButtons = highlighted;

        const { sourcePillId, targetPillId } = this.mappingConnectorToPills[connectorId];

        this.highlightPill(sourcePillId, highlighted);
        this.highlightPill(targetPillId, highlighted);
    }

    /**
     * @param {PillId} pillId
     * @param {boolean} highlighted
     */
    togglePillHighlighting(pillId, highlighted) {
        const pill = this.pills[pillId];
        if (!pill || pill.highlighted === highlighted) {
            return;
        }

        const { record } = pill;
        const pillIdsToHighlight = new Set([pillId]);

        if (record && this.shouldRenderRecordConnectors(record)) {
            // Find other related pills
            const { pills: relatedPills } = this.mappingRecordToPillsByRow[record.id];
            for (const pill of Object.values(relatedPills)) {
                pillIdsToHighlight.add(pill.id);
            }

            // Highlight related connectors
            for (const [connectorId, connector] of Object.entries(this.connectors)) {
                const ids = Object.values(this.getRecordIds(connectorId));
                if (ids.includes(record.id)) {
                    connector.highlighted = highlighted;
                    connector.displayButtons = false;
                }
            }
        }

        // Highlight pills from found IDs
        for (const id of pillIdsToHighlight) {
            this.highlightPill(id, highlighted);
        }
    }

    //-------------------------------------------------------------------------
    // Handlers
    //-------------------------------------------------------------------------

    /**
     * @param {Object} params
     * @param {RowId} params.rowId
     * @param {number} params.columnIndex
     */
    onCreate(rowId, columnStart, columnStop) {
        const { start, stop } = this.getColumnStartStop(columnStart, columnStop);
        const context = this.model.getDialogContext({
            rowId,
            start,
            stop,
            withDefault: true,
        });
        this.props.create(context);
    }

    onInteractionChange() {
        let { dragAction, mode } = this.interaction;
        if (mode === "drag") {
            mode = dragAction;
        }
        if (this.rootRef.el) {
            for (const [action, className] of INTERACTION_CLASSNAMES) {
                this.rootRef.el.classList.toggle(className, mode === action);
            }
        }
    }

    onSelectStart(ev) {
        if (ev.button !== 0) {
            return;
        }
        const { hoverable } = this.hovered;
        const { canCellCreate, canPlan } = this.model.metaData;
        if (canCellCreate || canPlan) {
            const isUngroupedCellHovered = hoverable?.matches(".o_gantt_cell:not(.o_gantt_group)");
            if (isUngroupedCellHovered && !ev?.target.closest(".o_connector_creator")) {
                this.selection.active = true;
                this.selection.rowId = hoverable.dataset.rowId;
                this.selection.initialIndex = Number(hoverable.dataset.columnIndex);
                this.selection.lastSelectId = this.selection.initialIndex;
                hoverable.classList.add("o_drag_hover");
            }
        }
    }

    onSelectStop() {
        const { canPlan } = this.model.metaData;
        if (this.selection.active) {
            this.selection.active = false;
            const { rowId, initialIndex, lastSelectId } = this.selection;
            const columnStart = Math.min(initialIndex, lastSelectId);
            const columnStop = Math.max(initialIndex, lastSelectId);
            for (const cell of this.getCellsOnRow(rowId)) {
                cell.classList.remove("o_drag_hover");
            }
            if (canPlan) {
                this.onPlan(rowId, columnStart, columnStop);
            } else {
                this.onCreate(rowId, columnStart, columnStop);
            }
        }
    }

    onPointerLeave() {
        this.throttledOnPointerMove.cancel();

        if (!this.isDragging) {
            const hoveredConnectorId = this.hovered.connector?.dataset.connectorId;
            this.toggleConnectorHighlighting(hoveredConnectorId, false);

            const hoveredPillId = this.hovered.pill?.dataset.pillId;
            this.togglePillHighlighting(hoveredPillId, false);
        }

        this.hovered.connector = null;
        this.hovered.pill = null;
        this.hovered.hoverable = null;

        this.computeDerivedParamsFromHover();
    }

    /**
     * Updates all hovered elements, then calls "computeDerivedParamsFromHover".
     *
     * @see computeDerivedParamsFromHover
     * @param {PointerEvent} ev
     */
    onPointerMove(ev) {
        // Lazily compute elements from point as it is a costly operation
        let els = null;
        const pointedEls = () => els || (els = document.elementsFromPoint(ev.clientX, ev.clientY));

        // To find hovered elements, also from pointed elements
        const find = (selector) =>
            ev.target.closest?.(selector) ||
            pointedEls().find((el) => el.matches(selector)) ||
            null;

        this.hovered.connector = find(".o_gantt_connector");
        this.hovered.hoverable = find(".o_gantt_hoverable");
        this.hovered.pill = find(".o_gantt_pill_wrapper");

        this.computeDerivedParamsFromHover(ev);
    }

    /**
     * @param {PointerEvent} ev
     * @param {Pill} pill
     */
    onPillClicked(ev, pill) {
        if (this.popover.isOpen) {
            return;
        }
        const popoverTarget = ev.target.closest(".o_gantt_pill_wrapper");
        this.popover.open(popoverTarget, this.getPopoverProps(pill));
    }

    /**
     * @param {Object} params
     * @param {RowId} params.rowId
     * @param {number} params.columnIndex
     */
    onPlan(rowId, columnStart, columnStop) {
        const { start, stop } = this.getColumnStartStop(columnStart, columnStop);
        this.dialogService.add(
            SelectCreateDialog,
            this.getSelectCreateDialogProps({ rowId, start, stop, withDefault: true })
        );
    }

    getRecordIds(connectorId) {
        const { sourcePillId, targetPillId } = this.mappingConnectorToPills[connectorId];
        return {
            masterId: this.pills[sourcePillId]?.record.id,
            slaveId: this.pills[targetPillId]?.record.id,
        };
    }

    /**
     *
     * @param {Object} params
     * @param {ConnectorId} connectorId
     */
    onRemoveButtonClick(connectorId) {
        const { masterId, slaveId } = this.getRecordIds(connectorId);
        this.model.removeDependency(masterId, slaveId);
    }

    /**
     *
     * @param {"forward" | "backward"} direction
     * @param {ConnectorId} connectorId
     */
    async onRescheduleButtonClick(direction, connectorId) {
        const { masterId, slaveId } = this.getRecordIds(connectorId);
        const result = await this.model.rescheduleAccordingToDependency(
            direction,
            masterId,
            slaveId
        );
        if (result && typeof result === "object") {
            this.actionService.doAction(result);
        }
    }

    /**
     * @param {KeyboardEvent} ev
     */
    onWindowKeyDown(ev) {
        if (ev.key === "Control") {
            this.prevDragAction =
                this.interaction.dragAction === "copy" ? "reschedule" : this.interaction.dragAction;
            this.interaction.dragAction = "copy";
        }
        if (ev.key === "Escape") {
            this.selection.active = false;
            document
                .querySelectorAll(".o_gantt_cell")
                .forEach((cell) => cell.classList.remove("o_drag_hover"));
        }
    }

    /**
     * @param {KeyboardEvent} ev
     */
    onWindowKeyUp(ev) {
        if (ev.key === "Control") {
            this.interaction.dragAction = this.prevDragAction || "reschedule";
        }
    }

    onCollapseClicked() {
        this.model.collapseRows();
    }

    onExpandClicked() {
        this.model.expandRows();
    }

    onNextPeriodClicked() {
        this.model.setFocusDate("next");
    }

    onPreviousPeriodClicked() {
        this.model.setFocusDate("previous");
    }

    onTodayClicked() {
        this.model.setFocusDate();
    }

    get displayExpandCollapseButtons() {
        return this.model.data.rows[0]?.isGroup; // all rows on same level have same type
    }

    // Thêm method này vào class GanttRenderer
    getRowDuration(row) {
        if (!row.pills || row.pills.length === 0) {
            return "-";
        }

        let earliestStart = row.pills[0].startDate;
        let latestEnd = row.pills[0].stopDate;

        for (const pill of row.pills) {
            if (pill.startDate < earliestStart) {
                earliestStart = pill.startDate;
            }
            if (pill.stopDate > latestEnd) {
                latestEnd = pill.stopDate;
            }
        }

        const duration = latestEnd.diff(earliestStart, 'days').days;
        return duration + ' ngày';
    }

    isMyTasksView() {
        return this.model.metaData.groupedBy.includes('project_id');
    }


    /**
     * Override to force single level for all pills
     * @param {Pill[]} pills
     */
    calculatePillsLevel(pills) {
        // Với single row per task, luôn return 1
        if (this.forceSingleRowPerTask) {
            for (const pill of pills) {
                pill.level = 0;
            }
            return 1;
        }

        // Fallback logic
        let maxLevel = 0;
        const occupied = new Map();

        for (const pill of pills) {
            let level = 0;
            const startCol = this.getFirstcol(pill);
            const endCol = this.getLastCol(pill);

            while (true) {
                let conflict = false;
                for (let col = startCol; col <= endCol; col++) {
                    if (occupied.has(col) && occupied.get(col).includes(level)) {
                        conflict = true;
                        break;
                    }
                }
                if (!conflict) break;
                level++;
            }

            for (let col = startCol; col <= endCol; col++) {
                if (!occupied.has(col)) {
                    occupied.set(col, []);
                }
                occupied.get(col).push(level);
            }

            pill.level = level;
            maxLevel = Math.max(maxLevel, level);
        }

        return maxLevel + 1;
    }

    /**
     * Original level calculation logic (backup)
     */
    _originalCalculatePillsLevel(pills) {
        // This is a simplified version - you might need to adjust based on your original logic
        let maxLevel = 0;
        const occupied = new Map();

        for (const pill of pills) {
            let level = 0;
            const startCol = this.getFirstcol(pill);
            const endCol = this.getLastCol(pill);

            // Find the first available level
            while (true) {
                let conflict = false;
                for (let col = startCol; col <= endCol; col++) {
                    if (occupied.has(col) && occupied.get(col).includes(level)) {
                        conflict = true;
                        break;
                    }
                }
                if (!conflict) break;
                level++;
            }

            // Mark this level as occupied for these columns
            for (let col = startCol; col <= endCol; col++) {
                if (!occupied.has(col)) {
                    occupied.set(col, []);
                }
                occupied.get(col).push(level);
            }

            pill.level = level;
            maxLevel = Math.max(maxLevel, level);
        }

        return maxLevel + 1;
    }

    /**
     * Xử lý group row (dự án) bình thường
     * @param {Row} row
     * @param {Pill[]} pills
     */
    processGroupRow(row, pills) {
        const { GROUP_ROW_SPAN, ROW_SPAN } = this.constructor;
        const {
            consolidate,
            fromServer,
            groupedByField,
            groupLevel,
            id,
            name,
            progressBar,
            resId,
            rows: subRows,
            unavailabilities,
            recordIds,
        } = row;

        console.log(`Processing regular group: ${name} with ${subRows?.length} sub-rows`);

        const remainingPills = [];
        let rowPills = [];
        const groupPills = [];

        for (const pill of pills) {
            const { record } = pill;
            const pushPill = recordIds.includes(record.id);
            if (pushPill) {
                const rowPill = { ...pill };
                rowPills.push(rowPill);
                groupPills.push(pill);
            } else {
                remainingPills.push(pill);
            }
        }

        const baseSpan = GROUP_ROW_SPAN;
        let span = baseSpan;

        // LUÔN TẠO ROW CHO DỰ ÁN, ngay cả khi không có pills
        if (rowPills.length && this.shouldComputeAggregateValues(row)) {
            const groups = this.aggregatePills(rowPills);
            const maxAggregateValue = Math.max(
                ...groups.map((group) => group.aggregateValue)
            );
            rowPills = groups.map((group) =>
                this.getPillFromGroup(group, maxAggregateValue, consolidate)
            );
        }

        for (const rowPill of rowPills) {
            rowPill.id = `__pill__${this.nextPillId++}`;
            rowPill.level = 0;
            rowPill.grid = {
                ...rowPill.grid,
                row: [this.topOffset + 1, baseSpan],
            };
            this.pills[rowPill.id] = rowPill;
        }

        // LUÔN TẠO ROW CHO DỰ ÁN
        const processedRow = {
            fromServer,
            groupedByField,
            groupLevel,
            id,
            isGroup: true,
            name,
            pills: rowPills, // Có thể là mảng rỗng
            progressBar,
            resId,
            grid: {
                row: [this.topOffset + 1, span],
                column: [groupLevel + 2, -1],
            },
            cellColors: {},
        };

        this.topOffset += span;

        const field = this.model.metaData.thumbnails[groupedByField];
        if (field) {
            const model = this.model.metaData.fields[groupedByField].relation;
            processedRow.thumbnailUrl = url("/web/image", {
                model,
                id: resId,
                field,
            });
        }

        const result = { rows: [processedRow], pillsToProcess: remainingPills };

        // Xử lý các sub-rows (tasks) nếu group không bị đóng
        let pillsToProcess = groupPills;
        if (!this.model.isClosed(id)) {
            // ƯU TIÊN: Xử lý sub-rows từ server
            if (subRows && subRows.length > 0) {
                console.log(`Processing ${subRows.length} sub-rows for group ${name}`);
                for (const subRow of subRows) {
                    const res = this.processRow(subRow, pillsToProcess);
                    result.rows.push(...res.rows);
                    pillsToProcess = res.pillsToProcess;
                }
            }
            // FALLBACK: Nếu không có sub-rows, tạo task rows từ pills
            else if (groupPills.length > 0) {
                console.log(`Creating ${groupPills.length} task rows for group ${name}`);
                for (const pill of groupPills) {
                    const taskRow = this.createTaskRow(processedRow, pill);
                    result.rows.push(taskRow);
                }
                pillsToProcess = remainingPills;
            }
        }

        console.log(`Regular group result: ${result.rows.length} rows created`);
        return result;
    }

    /**
     * Lấy tất cả task con của một dự án
     * @param {Row} projectRow
     */
    getAllChildTasks(projectRow) {
        const tasks = [];

        const collectTasks = (row) => {
            if (!row.isGroup && row.pills && row.pills.length > 0) {
                tasks.push({
                    id: row.id,
                    startDate: row.pills[0].startDate,
                    stopDate: row.pills[row.pills.length - 1].stopDate
                });
            }

            if (row.rows) {
                for (const subRow of row.rows) {
                    collectTasks(subRow);
                }
            }
        };

        if (projectRow.rows) {
            for (const subRow of projectRow.rows) {
                collectTasks(subRow);
            }
        }

        return tasks;
    }

    /**
     * Lấy ngày bắt đầu của dự án (từ task sớm nhất)
     * @param {Row} projectRow
     */
    getProjectStartDate(projectRow) {
        if (!projectRow.rows || projectRow.rows.length === 0) {
            return "-";
        }

        let earliestStart = null;

        const findEarliestStart = (row) => {
            if (!row.isGroup && row.pills && row.pills.length > 0) {
                const startDate = row.pills[0].startDate;
                if (!earliestStart || startDate < earliestStart) {
                    earliestStart = startDate;
                }
            }

            if (row.rows) {
                for (const subRow of row.rows) {
                    findEarliestStart(subRow);
                }
            }
        };

        for (const subRow of projectRow.rows) {
            findEarliestStart(subRow);
        }

        return earliestStart ? earliestStart.toFormat('dd/MM/yyyy') : "-";
    }

    /**
     * Lấy ngày kết thúc của dự án (từ task muộn nhất)
     * @param {Row} projectRow
     */
    getProjectEndDate(projectRow) {
        if (!projectRow.rows || projectRow.rows.length === 0) {
            return "-";
        }

        let latestEnd = null;

        const findLatestEnd = (row) => {
            if (!row.isGroup && row.pills && row.pills.length > 0) {
                const endDate = row.pills[row.pills.length - 1].stopDate;
                if (!latestEnd || endDate > latestEnd) {
                    latestEnd = endDate;
                }
            }

            if (row.rows) {
                for (const subRow of row.rows) {
                    findLatestEnd(subRow);
                }
            }
        };

        for (const subRow of projectRow.rows) {
            findLatestEnd(subRow);
        }

        return latestEnd ? latestEnd.toFormat('dd/MM/yyyy') : "-";
    }

    /**
     * Tính thời lượng của dự án
     * @param {Row} projectRow
     */
    getProjectDuration(projectRow) {
        const startDateStr = this.getProjectStartDate(projectRow);
        const endDateStr = this.getProjectEndDate(projectRow);

        if (startDateStr === "-" || endDateStr === "-") {
            return "-";
        }

        try {
            const startDate = DateTime.fromFormat(startDateStr, 'dd/MM/yyyy');
            const endDate = DateTime.fromFormat(endDateStr, 'dd/MM/yyyy');
            const duration = endDate.diff(startDate, 'days').days;
            return duration > 0 ? `${duration} ngày` : "-";
        } catch (error) {
            return "-";
        }
    }



    /**
     * Tạo một row riêng cho mỗi task (cho trường hợp task đơn lẻ)
     * @param {Row} parentRow - Row cha
     * @param {Pill} pill - Pill của task
     */
    createTaskRow(parentRow, pill) {
        console.log('=== CREATE TASK ROW START ===');
        console.log('Parent row:', parentRow.name || 'No parent name');
        console.log('Pill record:', pill.record);

        const { GROUP_ROW_SPAN, ROW_SPAN } = this.constructor;
        const { dependencyField } = this.model.metaData;
        const {
            fromServer,
            groupedByField,
            groupLevel,
            id,
            progressBar,
            resId,
            unavailabilities,
        } = parentRow;

        const baseSpan = ROW_SPAN;
        let span = baseSpan;

        // Tạo pill mới cho task
        const taskPill = {
            id: `__pill__${this.nextPillId++}`,
            record: pill.record,  // giữ nguyên record (cần cho popover)
            startDate: pill.startDate,
            stopDate: pill.stopDate,
            level: 0,
            highlighted: false,
            grid: {
                column: pill.grid.column,
                row: [this.topOffset + 1, baseSpan],
            },
            // Chỉ copy những field cần thiết, không copy hết pill
            displayName: pill.displayName,
            className: pill.className || '',
            _color: pill._color,
            _progress: pill._progress,
            disableStartResize: pill.disableStartResize,
            disableStopResize: pill.disableStopResize,
            disableDrag: pill.disableDrag,
        };

        // Lưu pill vào mapping
        this.pills[taskPill.id] = taskPill;
        console.log(`Created pill ${taskPill.id} for record ${pill.record.id}`);

        // Cập nhật connectors nếu cần
        const { record } = taskPill;
        if (this.shouldRenderRecordConnectors(record)) {
            if (!this.mappingRecordToPillsByRow[record.id]) {
                this.mappingRecordToPillsByRow[record.id] = {
                    masterIds: record[dependencyField],
                    pills: {},
                };
            }
            this.mappingRecordToPillsByRow[record.id].pills[taskPill.id] = taskPill;
            if (!this.mappingRowToPillsByRecord[taskPill.id]) {
                this.mappingRowToPillsByRecord[taskPill.id] = {};
            }
            this.mappingRowToPillsByRecord[taskPill.id][record.id] = taskPill;
        }

        if (progressBar && this.isTouchDevice) {
            span += ROW_SPAN;
        }

        // Tạo row cho task - QUAN TRỌNG: Đảm bảo record được truyền
        const taskRow = {
            fromServer,
            groupedByField,
            groupLevel: groupLevel,
            id: `${id || 'root'}_${record.id}`, // ID duy nhất cho task row
            isGroup: false,
            name: record.display_name,
            pills: [taskPill],
            record: record, // QUAN TRỌNG: Thêm record từ pill
            progressBar,
            resId: record.id,
            grid: {
                row: [this.topOffset + 1, span],
                column: [groupLevel + 2, -1],
            },
            cellColors: {},
            // THÊM: parent_id nếu có
            parentTaskId: record.parent_id,
            isSubtask: !!record.parent_id
        };

        // Xử lý unavailabilities nếu có
        if (unavailabilities) {
            taskRow.cellColors = this.getRowCellColors(unavailabilities);
        }

        this.topOffset += span;

        console.log(`Created task row: ${taskRow.name} ${taskRow.isSubtask ? '(SUBTASK)' : ''}`);
        if (taskRow.isSubtask) {
            console.log(`  Parent ID: ${taskRow.parentTaskId}`);
        }

        console.log('=== CREATE TASK ROW END ===');
        return taskRow;
    }

    /**
     * Xử lý trường hợp đặc biệt: row có recordIds (project với các task)
     * @param {Row} row
     * @param {Pill[]} pills
     */
    processProjectWithTasks(row, pills) {
        const { GROUP_ROW_SPAN, ROW_SPAN } = this.constructor;
        const {
            consolidate,
            fromServer,
            groupedByField,
            groupLevel,
            id,
            name,
            progressBar,
            resId,
            unavailabilities,
            recordIds,
        } = row;

        const remainingPills = [];
        const projectPills = [];

        // Tách pills thuộc về project này
        for (const pill of pills) {
            if (recordIds.includes(pill.record.id)) {
                projectPills.push(pill);
            } else {
                remainingPills.push(pill);
            }
        }

        const baseSpan = GROUP_ROW_SPAN;
        let span = baseSpan;

        // TẠO DÒNG DỰ ÁN
        const projectRow = {
            fromServer,
            groupedByField,
            groupLevel,
            id: `project_${id}`, // ID mới cho dự án
            isGroup: true, // QUAN TRỌNG: Set thành true
            name,
            pills: [], // Dự án không hiển thị pills
            progressBar,
            resId,
            grid: {
                row: [this.topOffset + 1, span],
                column: [groupLevel + 2, -1],
            },
            cellColors: {},
            recordIds: [], // Dự án không có recordIds trực tiếp
            unavailabilities,
        };

        this.topOffset += span;

        const field = this.model.metaData.thumbnails[groupedByField];
        if (field) {
            const model = this.model.metaData.fields[groupedByField].relation;
            projectRow.thumbnailUrl = url("/web/image", {
                model,
                id: resId,
                field,
            });
        }

        const result = { rows: [projectRow], pillsToProcess: remainingPills };

        // TẠO CÁC DÒNG TASK CHO DỰ ÁN
        for (const pill of projectPills) {
            const taskRow = this.createTaskRowForProject(projectRow, pill);
            result.rows.push(taskRow);
        }

        console.log('Created project with tasks:', {
            project: projectRow.name,
            tasks: projectPills.length,
            resultRows: result.rows.map(r => ({ name: r.name, isGroup: r.isGroup }))
        }); // DEBUG

        return result;
    }

    /**
     * Tạo task row cho dự án
     * @param {Row} projectRow
     * @param {Pill} pill
     */
    createTaskRowForProject(projectRow, pill) {
        const { GROUP_ROW_SPAN, ROW_SPAN } = this.constructor;
        const { dependencyField } = this.model.metaData;
        const {
            fromServer,
            groupedByField,
            groupLevel,
            id,
            progressBar,
            resId,
            unavailabilities,
        } = projectRow;

        const baseSpan = ROW_SPAN;
        let span = baseSpan;

        // Tạo pill mới cho task
        const taskPill = {
            id: `__pill__${this.nextPillId++}`,
            record: pill.record,  // giữ nguyên record (cần cho popover)
            startDate: pill.startDate,
            stopDate: pill.stopDate,
            level: 0,
            highlighted: false,
            grid: {
                column: pill.grid.column,
                row: [this.topOffset + 1, baseSpan],
            },
            // Chỉ copy những field cần thiết, không copy hết pill
            displayName: pill.displayName,
            className: pill.className || '',
            _color: pill._color,
            _progress: pill._progress,
            disableStartResize: pill.disableStartResize,
            disableStopResize: pill.disableStopResize,
            disableDrag: pill.disableDrag,
        };

        // Lưu pill vào mapping
        this.pills[taskPill.id] = taskPill;

        // Cập nhật connectors nếu cần
        const { record } = taskPill;
        if (this.shouldRenderRecordConnectors(record)) {
            if (!this.mappingRecordToPillsByRow[record.id]) {
                this.mappingRecordToPillsByRow[record.id] = {
                    masterIds: record[dependencyField],
                    pills: {},
                };
            }
            this.mappingRecordToPillsByRow[record.id].pills[taskPill.id] = taskPill;
            if (!this.mappingRowToPillsByRecord[taskPill.id]) {
                this.mappingRowToPillsByRecord[taskPill.id] = {};
            }
            this.mappingRowToPillsByRecord[taskPill.id][record.id] = taskPill;
        }

        if (progressBar && this.isTouchDevice) {
            span += ROW_SPAN;
        }

        // Tạo row cho task
        const taskRow = {
            fromServer,
            groupedByField,
            groupLevel: groupLevel + 1, // Tăng level để thụt lề
            id: `${id}_task_${record.id}`, // ID duy nhất cho task row
            isGroup: false,
            name: record.display_name,
            pills: [taskPill],
            progressBar,
            resId: record.id,
            grid: {
                row: [this.topOffset + 1, span],
                column: [groupLevel + 3, -1], // Thụt lề thêm 1 level
            },
            cellColors: {},
        };

        // Xử lý unavailabilities nếu có
        if (unavailabilities) {
            taskRow.cellColors = this.getRowCellColors(unavailabilities);
        }

        this.topOffset += span;
        return taskRow;
    }

    /**
     * Xử lý group row cho multi-level grouping
     * @param {Row} row
     * @param {Pill[]} pills
     * @param {number} groupLevel
     * @param {string} groupField
     */
    processMultiLevelGroup(row, pills, groupLevel, groupField) {
        const { GROUP_ROW_SPAN, ROW_SPAN } = this.constructor;
        const {
            id,
            name,
            progressBar,
            resId,
            recordIds,
            unavailabilities,
            groupedBy,
            rows: subRows, // Các sub-rows từ server
        } = row;

        console.log(`Processing multi-level group: ${name} (${groupField}) with ${recordIds?.length} records`);

        const remainingPills = [];
        const groupPills = [];

        // Lọc pills thuộc về group hiện tại
        for (const pill of pills) {
            if (recordIds.includes(pill.record.id)) {
                groupPills.push(pill);
            } else {
                remainingPills.push(pill);
            }
        }

        const baseSpan = GROUP_ROW_SPAN;
        let span = baseSpan;

        // Tạo row cho group hiện tại
        const groupRow = {
            ...row,
            groupedBy,           // Toàn bộ array groupBy
            groupLevel,          // Level hiện tại
            groupField,          // Field của level hiện tại
            isGroup: true,
            pills: [],           // Group row không hiển thị pills
            grid: {
                row: [this.topOffset + 1, span],
                column: [groupLevel + 2, -1], // Column phụ thuộc vào level
            },
            cellColors: {},
        };

        this.topOffset += span;

        // Thumbnail cho group (nếu có)
        const thumbnailField = this.model.metaData.thumbnails[groupField];
        if (thumbnailField) {
            const model = this.model.metaData.fields[groupField].relation;
            groupRow.thumbnailUrl = url("/web/image", {
                model,
                id: resId,
                field: thumbnailField,
            });
        }

        const result = { rows: [groupRow], pillsToProcess: remainingPills };

        // Xử lý các sub-rows (có thể là groups tiếp theo hoặc tasks)
        let pillsToProcess = groupPills;

        if (!this.model.isClosed(id)) {
            // ƯU TIÊN 1: Xử lý sub-rows từ server (nếu có)
            if (subRows && subRows.length > 0) {
                console.log(`Processing ${subRows.length} sub-rows from server`);
                for (const subRow of subRows) {
                    const res = this.processRow({
                        ...subRow,
                        groupLevel: groupLevel + 1,
                        groupedBy: groupedBy // Truyền xuống array groupBy
                    }, pillsToProcess);
                    result.rows.push(...res.rows);
                    pillsToProcess = res.pillsToProcess;
                }
            }
            // ƯU TIÊN 2: Nếu không có sub-rows từ server, tạo task rows từ pills
            else if (groupPills.length > 0) {
                console.log(`Creating ${groupPills.length} task rows from pills`);
                for (const pill of groupPills) {
                    const taskRow = this.createTaskRowForMultiLevel(groupRow, pill);
                    result.rows.push(taskRow);
                }
                pillsToProcess = remainingPills; // Đã xử lý hết groupPills
            }
        }

        console.log(`Multi-level group result: ${result.rows.length} rows created`);
        return result;
    }

    /**
     * Tạo task row cho multi-level grouping
     * @param {Row} parentGroupRow
     * @param {Pill} pill
     */
    createTaskRowForMultiLevel(parentGroupRow, pill) {
        const { GROUP_ROW_SPAN, ROW_SPAN } = this.constructor;
        const { dependencyField } = this.model.metaData;
        const {
            fromServer,
            groupedBy,
            groupLevel,
            groupField,
            id,
            progressBar,
            resId,
            unavailabilities,
        } = parentGroupRow;

        const baseSpan = ROW_SPAN;
        let span = baseSpan;

        // Tạo pill mới cho task
        const taskPill = {
            id: `__pill__${this.nextPillId++}`,
            record: pill.record,  // giữ nguyên record (cần cho popover)
            startDate: pill.startDate,
            stopDate: pill.stopDate,
            level: 0,
            highlighted: false,
            grid: {
                column: pill.grid.column,
                row: [this.topOffset + 1, baseSpan],
            },
            // Chỉ copy những field cần thiết, không copy hết pill
            displayName: pill.displayName,
            className: pill.className || '',
            _color: pill._color,
            _progress: pill._progress,
            disableStartResize: pill.disableStartResize,
            disableStopResize: pill.disableStopResize,
            disableDrag: pill.disableDrag,
        };

        // Lưu pill vào mapping
        this.pills[taskPill.id] = taskPill;

        // Cập nhật connectors nếu cần
        const { record } = taskPill;
        if (this.shouldRenderRecordConnectors(record)) {
            if (!this.mappingRecordToPillsByRow[record.id]) {
                this.mappingRecordToPillsByRow[record.id] = {
                    masterIds: record[dependencyField],
                    pills: {},
                };
            }
            this.mappingRecordToPillsByRow[record.id].pills[taskPill.id] = taskPill;
            if (!this.mappingRowToPillsByRecord[taskPill.id]) {
                this.mappingRowToPillsByRecord[taskPill.id] = {};
            }
            this.mappingRowToPillsByRecord[taskPill.id][record.id] = taskPill;
        }

        if (progressBar && this.isTouchDevice) {
            span += ROW_SPAN;
        }

        // Tạo row cho task
        const taskRow = {
            fromServer,
            groupedBy,
            groupLevel: groupLevel + 1, // Tăng level để thụt lề
            groupField: null, // Task không có groupField
            id: `${id}_task_${record.id}`, // ID duy nhất cho task row
            isGroup: false,
            name: record.display_name,
            pills: [taskPill],
            progressBar,
            resId: record.id,
            grid: {
                row: [this.topOffset + 1, span],
                column: [groupLevel + 3, -1], // Thụt lề thêm 1 level
            },
            cellColors: {},
            recordIds: [record.id], // Task chỉ có 1 record
        };

        // Xử lý unavailabilities nếu có
        if (unavailabilities) {
            taskRow.cellColors = this.getRowCellColors(unavailabilities);
        }

        this.topOffset += span;

        console.log(`Created task row: ${record.display_name} at level ${groupLevel + 1}`);
        return taskRow;
    }

    /**
     * Lấy ngày bắt đầu từ field planed_date_begin của task
     * @param {Row} row
     */
    getTaskStartDate(row) {
        const record = this.getRecordFromRow(row);
        if (!record) {
            console.log('No record found for row:', row.name);
            return '';
        }

        const startDate = record.planned_date_begin || record.planed_date_begin;
        if (!startDate) return '';

        try {
            return DateTime.fromISO(startDate).toFormat('dd/MM/yyyy');
        } catch (error) {
            return '';
        }
    }

    /**
     * Lấy ngày kết thúc từ field date_deadline của task
     * @param {Row} row
     */
    getTaskEndDate(row) {
        const record = this.getRecordFromRow(row);
        if (!record) return '';

        const endDate = record.date_deadline;
        if (!endDate) return '';

        try {
            return DateTime.fromISO(endDate).toFormat('dd/MM/yyyy');
        } catch (error) {
            return '';
        }
    }

    /**
     * Tính thời lượng từ planned_date_begin và date_deadline
     * @param {Row} row
     */
    getTaskDuration(row) {
        const record = this.getRecordFromRow(row);
        if (!record) return '';

        const startDate = record.planned_date_begin || record.planed_date_begin;
        const endDate = record.date_deadline;

        if (!startDate || !endDate) return '';

        try {
            const start = DateTime.fromISO(startDate);
            const end = DateTime.fromISO(endDate);
            const duration = end.diff(start, 'days').days;
            return duration > 0 ? `${Math.ceil(duration)} ngày` : '';
        } catch (error) {
            return '';
        }
    }

    /**
     * Lấy danh sách người phụ trách từ field user_ids (many2many)
     * Hỗ trợ cả trường hợp chỉ có ID → tự resolve name từ cache của Odoo
     * @param {Row} row
     */
    getTaskAssignees(row) {
        const record = this.getRecordFromRow(row);
        if (!record?.user_ids?.length) return '';

        return record.user_ids
            .map(u => {
                if (Array.isArray(u)) {
                    // [id, "name"]
                    return u[1] || `User ${u[0]}`;
                } else if (u && typeof u === 'object') {
                    // {id, display_name}
                    return u.display_name || `User ${u.id}`;
                } else if (typeof u === 'number') {
                    return this._userNameCache?.[u] || `User ${u}`;
                }
                return '';
            })
            .filter(Boolean)
            .join(', ');
    }



    /**
     * Lấy ngày bắt đầu sớm nhất từ tất cả tasks trong dự án
     * @param {Row} groupRow
     */
    getAggregatedStartDate(groupRow) {
        if (!groupRow.rows || groupRow.rows.length === 0) return '';

        let earliestStart = null;

        const findEarliestStart = (row) => {
            if (!row.isGroup && row.record) {
                const startDate = row.record.planned_date_begin;
                if (startDate) {
                    const date = DateTime.fromISO(startDate);
                    if (!earliestStart || date < earliestStart) {
                        earliestStart = date;
                    }
                }
            }

            if (row.rows) {
                for (const subRow of row.rows) {
                    findEarliestStart(subRow);
                }
            }
        };

        for (const subRow of groupRow.rows) {
            findEarliestStart(subRow);
        }

        return earliestStart ? earliestStart.toFormat('dd/MM/yyyy') : '';
    }

    /**
     * Lấy ngày kết thúc muộn nhất từ tất cả tasks trong dự án
     * @param {Row} groupRow
     */
    getAggregatedEndDate(groupRow) {
        if (!groupRow.rows || groupRow.rows.length === 0) return '';

        let latestEnd = null;

        const findLatestEnd = (row) => {
            if (!row.isGroup && row.record) {
                const endDate = row.record.date_deadline;
                if (endDate) {
                    const date = DateTime.fromISO(endDate);
                    if (!latestEnd || date > latestEnd) {
                        latestEnd = date;
                    }
                }
            }

            if (row.rows) {
                for (const subRow of row.rows) {
                    findLatestEnd(subRow);
                }
            }
        };

        for (const subRow of groupRow.rows) {
            findLatestEnd(subRow);
        }

        return latestEnd ? latestEnd.toFormat('dd/MM/yyyy') : '';
    }

    /**
     * Tính thời lượng tổng của dự án
     * @param {Row} groupRow
     */
    getAggregatedDuration(groupRow) {
        const startDateStr = this.getAggregatedStartDate(groupRow);
        const endDateStr = this.getAggregatedEndDate(groupRow);

        if (startDateStr === '' || endDateStr === '') {
            return '';
        }

        try {
            const startDate = DateTime.fromFormat(startDateStr, 'dd/MM/yyyy');
            const endDate = DateTime.fromFormat(endDateStr, 'dd/MM/yyyy');
            const duration = endDate.diff(startDate, 'days').days;
            return duration > 0 ? `${Math.ceil(duration)} ngày` : '';
        } catch (error) {
            return '';
        }
    }

    /**
     * Lấy danh sách tất cả người phụ trách trong dự án
     * @param {Row} groupRow
     */
    getAggregatedAssignees(groupRow) {
        if (!groupRow.rows || groupRow.rows.length === 0) return '';

        const allAssignees = new Set();

        const collectAssignees = (row) => {
            if (!row.isGroup) {
                const assignees = this.getTaskAssignees(row);
                if (assignees !== '') {
                    // Tách chuỗi assignees thành các tên riêng lẻ
                    const names = assignees.split(', ');
                    names.forEach(name => {
                        if (name && name !== '') {
                            allAssignees.add(name.trim());
                        }
                    });
                }
            }

            if (row.rows) {
                for (const subRow of row.rows) {
                    collectAssignees(subRow);
                }
            }
        };

        for (const subRow of groupRow.rows) {
            collectAssignees(subRow);
        }

        return allAssignees.size > 0 ? Array.from(allAssignees).join(', ') : '';
    }

    /**
     * Debug method to check record structure
     */
    debugRecordFields(row) {
        if (!row.record) {
            console.log('No record for row:', row.name);
            return;
        }

        console.log('=== DEBUG RECORD FIELDS ===');
        console.log('Row:', row.name);
        console.log('Record ID:', row.record.id);
        console.log('All fields:', Object.keys(row.record));

        // Check specific fields we need
        const neededFields = ['planed_date_begin', 'planned_date_begin', 'date_deadline', 'user_ids'];
        neededFields.forEach(field => {
            console.log(`${field}:`, row.record[field]);
            console.log(`${field} type:`, typeof row.record[field]);
        });

        // Special debug for user_ids
        if (row.record.user_ids) {
            console.log('user_ids structure:', row.record.user_ids);
            if (Array.isArray(row.record.user_ids)) {
                console.log('user_ids length:', row.record.user_ids.length);
                row.record.user_ids.forEach((user, index) => {
                    console.log(`User ${index}:`, user);
                    console.log(`User ${index} type:`, typeof user);
                    if (Array.isArray(user)) {
                        console.log(`User ${index} is array, length:`, user.length);
                    }
                });
            }
        }
        console.log('=== END DEBUG ===');
    }
    /**
     * Fallback method để lấy record từ pills nếu row không có record
     * @param {Row} row
     */
    getRecordFromRow(row) {
        if (row.record) {
            return row.record;
        }

        // Thử lấy từ pills
        if (row.pills && row.pills.length > 0) {
            const pill = row.pills[0];
            if (pill && pill.record) {
                return pill.record;
            }
        }

        return null;
    }

    async preloadUsersFromRows(rows) {
        const userIds = new Set();

        const collect = (row) => {
            if (!row.isGroup && row.record?.user_ids) {
                row.record.user_ids.forEach(u => {
                    const id = Array.isArray(u) ? u[0] : u;
                    if (id) userIds.add(id);
                });
            }
            if (row.rows) row.rows.forEach(collect);
        };

        rows.forEach(collect);

        if (!userIds.size) return;

        const result = await this.env.services.orm.call(
            'res.users',
            'name_get',
            [[...userIds]]
        );

        result.forEach(([id, name]) => {
            this._userNameCache[id] = name;
        });
    }

    /**
     * Tạo connector giữa parent và child
     */
    createParentChildConnector(parentPills, childPills, parentId, childId) {
        const connectorId = `__parent_child__${parentId}_${childId}`;

        // Sử dụng pill đầu tiên của parent và child
        const parentPill = parentPills[0];
        const childPill = childPills[0];

        if (parentPill && childPill) {
            console.log(`Creating parent-child connector: ${connectorId}`);
            console.log(`Parent pill: ${parentPill.id}, Child pill: ${childPill.id}`);

            this.setConnector(
                {
                    id: connectorId,
                    className: "o_parent_child_connector",   // bắt buộc thêm class
                    alert: null,
                    displayButtons: false,
                    highlighted: false,
                },
                parentPill.id,   // source
                childPill.id     // target
            );

            // QUAN TRỌNG: Đảm bảo mapping được lưu
            this.parentChildMapping[connectorId] = true;
            console.log(`Parent-child mapping updated:`, this.parentChildMapping);
        } else {
            console.log('✗ Cannot create parent-child connector - missing pills:', {
                parentPill: !!parentPill,
                childPill: !!childPill
            });
        }
    }

    /**
     * Xóa tất cả parent-child connectors
     */
    deleteParentChildConnectors() {
        for (const connectorId in this.parentChildMapping) {
            this.deleteConnector(connectorId);
        }
        this.parentChildMapping = {};
    }

    /**
     * Tạo connectors dựa trên parent-child relationships
     */
    async generateParentChildConnectors() {
        console.log('=== GENERATING PARENT-CHILD CONNECTORS ===');
        console.log('Total pills:', Object.keys(this.pills).length);

        // Tạo mapping từ record ID sang pills
        const recordToPills = {};
        for (const pillId in this.pills) {
            const pill = this.pills[pillId];
            const recordId = pill.record.id;
            if (!recordToPills[recordId]) {
                recordToPills[recordId] = [];
            }
            recordToPills[recordId].push(pill);
        }

        console.log('Record to pills mapping:', Object.keys(recordToPills).length);
        console.log('Available record IDs:', Object.keys(recordToPills));

        let connectorCount = 0;
        const createdConnectors = new Set();

        // Duyệt qua tất cả pills để tìm parent-child relationships
        for (const pillId in this.pills) {
            const pill = this.pills[pillId];
            const record = pill.record;

            // Kiểm tra xem record có parent_id không
            if (!record.parent_id) {
                continue;
            }

            // Parse parent_id
            let parentId;
            if (Array.isArray(record.parent_id)) {
                parentId = record.parent_id[0]; // [id, name]
            } else if (typeof record.parent_id === 'object' && record.parent_id.id) {
                parentId = record.parent_id.id; // {id: ..., name: ...}
            } else {
                parentId = record.parent_id; // số đơn thuần
            }

            console.log(`Found parent-child relationship: ${record.id} -> ${parentId}`);

            // Tìm pills của parent và child
            const parentPills = recordToPills[parentId];
            const childPills = recordToPills[record.id];

            console.log(`Parent pills: ${parentPills ? parentPills.length : 0}`);
            console.log(`Child pills: ${childPills ? childPills.length : 0}`);

            if (!parentPills || parentPills.length === 0) {
                console.log(`✗ Missing parent pills for parent ID: ${parentId}`);
                continue;
            }

            if (!childPills || childPills.length === 0) {
                console.log(`✗ Missing child pills for child ID: ${record.id}`);
                continue;
            }

            // Lấy pill đầu tiên của mỗi bên
            const parentPill = parentPills[0];
            const childPill = childPills[0];

            // Tạo connector ID duy nhất
            const connectorId = `__parent_child__${parentId}_${record.id}`;

            // Tránh tạo trùng
            if (createdConnectors.has(connectorId)) {
                console.log(`Connector ${connectorId} already created`);
                continue;
            }

            console.log(`Creating parent-child connector: ${connectorId}`);
            console.log(`Parent pill: ${parentPill.id}, Child pill: ${childPill.id}`);

            // Tạo connector
            this.setConnector(
                {
                    id: connectorId,
                    className: "o_parent_child_connector", // QUAN TRỌNG: class để style
                    alert: null,
                    displayButtons: false,
                    highlighted: false,
                },
                parentPill.id,   // source
                childPill.id     // target
            );

            // Đánh dấu connector này là parent-child
            this.parentChildMapping[connectorId] = true;
            createdConnectors.add(connectorId);
            connectorCount++;

            console.log(`✓ Created parent-child connector: ${connectorId}`);
        }

        console.log(`Total parent-child connectors created: ${connectorCount}`);

        // Debug: kiểm tra connectors đã tạo
        console.log('Created connectors:', Array.from(createdConnectors));

        return connectorCount;
    }

    /**
     * Kiểm tra và xử lý parent_id field từ record
     */
    getParentId(record) {
        console.log('=== PARENT_ID FIELD DEBUG ===');
        console.log('Record:', record);
        console.log('Record ID:', record.id);
        console.log('Record display_name:', record.display_name);

        // Kiểm tra trực tiếp parent_id field
        console.log('parent_id field exists:', 'parent_id' in record);
        console.log('parent_id value:', record.parent_id);
        console.log('parent_id type:', typeof record.parent_id);

        // Kiểm tra tất cả fields có trong record
        console.log('All record fields:', Object.keys(record));

        // Tìm tất cả fields có thể liên quan đến parent
        const parentRelatedFields = Object.keys(record).filter(key =>
            key.toLowerCase().includes('parent') ||
            key.toLowerCase().includes('child')
        );
        console.log('Parent/child related fields:', parentRelatedFields);

        // Debug chi tiết các fields liên quan
        parentRelatedFields.forEach(field => {
            console.log(`Field ${field}:`, record[field], 'type:', typeof record[field]);
        });

        if (record.parent_id) {
            console.log('Found parent_id, parsing...');
            return this.parseParentId(record.parent_id);
        }

        console.log('No parent_id found in record');
        return null;
    }

    /**
     * Parse parent ID từ các định dạng khác nhau
     */
    parseParentId(parentValue) {
        if (!parentValue) {
            return null;
        }

        // Đơn giản: nếu là array [id, name] thì lấy id
        if (Array.isArray(parentValue)) {
            return parentValue[0];
        }

        // Nếu là object {id, name} thì lấy id
        if (typeof parentValue === 'object' && parentValue.id) {
            return parentValue.id;
        }

        // Nếu là number hoặc string có thể parse thành number
        const numValue = Number(parentValue);
        if (!isNaN(numValue)) {
            return numValue;
        }

        return null;
    }

    /**
     * Kiểm tra xem có tồn tại parent-child relationships không
     */
    hasParentChildRelationships() {
        const { records } = this.model.data;

        // Kiểm tra cả trong records hiện tại và sau khi load
        const hasParentId = records.some(record => record.parent_id);
        console.log('Has parent-child relationships (current):', hasParentId);

        // Luôn return true để đảm bảo connectors được thử tạo
        return true;
    }

    /**
     * Đảm bảo parent_id được load trong dữ liệu
     */
    ensureParentIdLoaded() {
        console.log('=== ENSURING PARENT_ID LOADED ===');

        const { records } = this.model.data;
        const { fields } = this.model.metaData;

        // Kiểm tra xem parent_id có trong metaData nhưng không trong records không
        if ('parent_id' in fields && records.length > 0 && !('parent_id' in records[0])) {
            console.log('parent_id exists in metaData but not loaded in records');
            console.log('Need to reload data with parent_id field');

            // Gọi method để reload với parent_id
            this.reloadDataWithParentId();
            return true;
        }

        console.log('parent_id status:', {
            inMetaData: 'parent_id' in fields,
            inRecords: records.length > 0 ? 'parent_id' in records[0] : false
        });

        return false;
    }

    /**
     * Reload dữ liệu với parent_id field
     */
    async reloadDataWithParentId() {
        console.log('=== RELOADING DATA WITH PARENT_ID ===');

        try {
            // Lấy fields hiện tại từ search model
            const currentFields = this.env.searchModel?.fields;
            if (currentFields && !('parent_id' in currentFields)) {
                console.log('Adding parent_id to search fields');

                // Thêm parent_id vào fields cần load
                // Cách này phụ thuộc vào implementation cụ thể của model
                await this.model.load({
                    fields: { ...currentFields, parent_id: true }
                });

                console.log('Data reloaded with parent_id');
            }
        } catch (error) {
            console.error('Error reloading data with parent_id:', error);
        }
    }

    /**
     * Load parent_id data từ server qua RPC
     */
    async loadParentIdData() {
        console.log('=== LOADING PARENT_ID DATA VIA RPC ===');

        const { records } = this.model.data;

        if (records.length === 0) {
            console.log('No records to load parent_id for');
            return;
        }

        try {
            const recordIds = records.map(record => record.id);

            console.log('Loading parent_id for records:', recordIds);

            // Gọi RPC để lấy parent_id data
            const result = await this.env.services.orm.read(
                'project.task', // Sử dụng resModel từ metaData
                recordIds,
                ['parent_id', 'display_name'] // Chỉ load các field cần thiết
            );

            console.log('Parent_id data loaded from server:', result);

            // Merge parent_id data vào records hiện tại
            this.mergeParentIdIntoRecords(result);

        } catch (error) {
            console.error('Error loading parent_id data:', error);
        }
    }

    /**
     * Merge parent_id data vào records hiện tại
     */
    mergeParentIdIntoRecords(parentIdData) {
        const { records } = this.model.data;

        console.log('=== MERGING PARENT_ID DATA ===');

        // Tạo mapping ID -> record để merge dễ dàng
        const recordMap = {};
        records.forEach(record => {
            recordMap[record.id] = record;
        });

        parentIdData.forEach(parentData => {
            const record = recordMap[parentData.id];
            if (record) {
                record.parent_id = parentData.parent_id;
                console.log(`✓ Merged parent_id for record ${record.id}:`, parentData.parent_id);
            }
        });

        console.log('Records after merge:', records.map(r => ({ id: r.id, parent_id: r.parent_id })));
    }

    /**
     * Tạo mapping record id -> pills
     */
    createRecordToPillsMapping() {
        const recordToPills = {};
        for (const pillId in this.pills) {
            const pill = this.pills[pillId];
            const recordId = pill.record.id;
            if (!recordToPills[recordId]) {
                recordToPills[recordId] = [];
            }
            recordToPills[recordId].push(pill);
        }
        console.log('Record to pills mapping created:', Object.keys(recordToPills));
        return recordToPills;
    }

    // Thêm method để debug template
    debugTemplateRendering() {
        console.log('=== TEMPLATE RENDERING DEBUG ===');

        // Kiểm tra xem có element connectors không
        const connectorElements = document.querySelectorAll('.o_gantt_connector');
        console.log('Connector elements in DOM:', connectorElements.length);

        // Kiểm tra SVG elements
        const svgElements = document.querySelectorAll('svg.o_gantt_connector');
        console.log('SVG connector elements:', svgElements.length);

        // Kiểm tra từng connector
        connectorElements.forEach((el, index) => {
            console.log(`Connector ${index}:`, el.getAttribute('data-connector-id'), el);
        });
    }

    /**
     * Load subtasks từ server
     */
    async loadSubtasks() {
        console.log('=== LOADING SUBTASKS - DETAILED DEBUG ===');

        const { records } = this.model.data;
        console.log('Initial records count:', records.length);
        console.log('First few records:', records.slice(0, 5).map(r => ({
            id: r.id,
            name: r.display_name,
            parent_id: r.parent_id
        })));

        // Tìm tất cả parent IDs từ records hiện có
        const mainTaskIds = new Set();

        records.forEach(record => {
            if (record.parent_id) {
                // Parse parent ID
                let parentId;
                if (Array.isArray(record.parent_id)) {
                    parentId = record.parent_id[0];
                    console.log(`Record ${record.id} has array parent_id:`, record.parent_id);
                } else if (typeof record.parent_id === 'object' && record.parent_id.id) {
                    parentId = record.parent_id.id;
                    console.log(`Record ${record.id} has object parent_id:`, record.parent_id);
                } else {
                    parentId = record.parent_id;
                    console.log(`Record ${record.id} has simple parent_id:`, record.parent_id);
                }

                if (parentId) {
                    mainTaskIds.add(parentId);
                    console.log(`✓ Added parent_id ${parentId} for record ${record.id}`);
                }
            } else {
                console.log(`Record ${record.id} has NO parent_id`);
            }
        });

        console.log('Main task IDs to fetch subtasks for:', Array.from(mainTaskIds));

        if (mainTaskIds.size === 0) {
            console.log('❌ No main tasks found to load subtasks - maybe parent_id field is not loaded?');
            console.log('Checking if parent_id field exists in metaData:',
                'parent_id' in this.model.metaData.fields);
            return;
        }

        try {
            // QUAN TRỌNG: Kiểm tra xem model có resModel không
            const resModel = this.model.metaData.resModel || 'project.task';
            console.log(`Using resModel: ${resModel}`);

            // QUAN TRỌNG: Chỉ lấy các field thực sự có trong metaData
            const fields = Object.keys(this.model.metaData.fields || {});
            console.log(`Fields to fetch: ${fields.length} fields`, fields.slice(0, 10));

            // Tạo domain để tìm subtask
            const domain = [['parent_id', 'in', Array.from(mainTaskIds)]];
            console.log('Search domain for subtasks:', domain);

            // Load subtasks từ server
            const subtasks = await this.env.services.orm.searchRead(
                resModel,
                domain,
                fields
            );

            console.log('✅ Loaded subtasks from server:', subtasks.length);

            // Debug subtasks structure
            if (subtasks.length > 0) {
                console.log('Sample subtask structure:', Object.keys(subtasks[0]));
                console.log('Sample subtask:', {
                    id: subtasks[0].id,
                    name: subtasks[0].display_name,
                    parent_id: subtasks[0].parent_id,
                    has_date_start: !!subtasks[0][this.model.metaData.dateStartField],
                    has_date_stop: !!subtasks[0][this.model.metaData.dateStopField]
                });
            } else {
                console.log('⚠️ No subtasks found for parent IDs:', Array.from(mainTaskIds));
            }

            // Merge subtasks vào records (kiểm tra trùng lặp)
            const existingIds = new Set(records.map(r => r.id));
            const newSubtasks = subtasks.filter(st => !existingIds.has(st.id));

            console.log(`Adding ${newSubtasks.length} new subtasks to records`);
            console.log('Existing record IDs:', Array.from(existingIds).slice(0, 10));

            // Thêm subtasks vào records
            this.model.data.records = [...records, ...newSubtasks];
            console.log('Total records after merging subtasks:', this.model.data.records.length);

            // QUAN TRỌNG: Cần update model để trigger re-render
            this.model.notify();

            // Force re-compute
            this.computeDerivedParams();

            console.log('✅ Subtasks loaded and merged successfully');

        } catch (error) {
            console.error('❌ Error loading subtasks:', error);
            console.error('Error details:', error.message, error.stack);
        }
    }

    /**
     * Debug tất cả rows đầu vào
     */
    debugAllInputRows() {
        console.log('=== ALL INPUT ROWS DEBUG ===');
        const { rows: modelRows } = this.model.data;

        console.log(`Total rows from model: ${modelRows.length}`);

        modelRows.forEach((row, index) => {
            console.log(`\nRow ${index}:`);
            console.log('  Name:', row.name || row.display_name || 'No name');
            console.log('  ID:', row.id);
            console.log('  Is Group:', row.isGroup);
            console.log('  Group Level:', row.groupLevel);
            console.log('  Has Record:', !!row.record);
            if (row.record) {
                console.log('  Record ID:', row.record.id);
                console.log('  Record Name:', row.record.display_name);
                console.log('  Record Parent ID:', row.record.parent_id);
            }
            console.log('  Has RecordIds:', !!row.recordIds);
            if (row.recordIds) {
                console.log('  RecordIds count:', row.recordIds.length);
                console.log('  RecordIds first 5:', row.recordIds.slice(0, 5));
            }
            console.log('  Has SubRows:', !!row.rows);
            if (row.rows) {
                console.log('  SubRows count:', row.rows.length);
            }
        });
    }

    /**
     * Debug tất cả pills
     */
    debugAllPills(prePills) {
        console.log('=== ALL PILLS DEBUG ===');
        console.log(`Total pills: ${prePills.length}`);

        prePills.forEach((pill, index) => {
            console.log(`\nPill ${index}:`);
            console.log('  Record ID:', pill.record.id);
            console.log('  Record Name:', pill.record.display_name);
            console.log('  Record Parent ID:', pill.record.parent_id);
            console.log('  Start Date:', pill.startDate?.toISO());
            console.log('  Stop Date:', pill.stopDate?.toISO());
            console.log('  Grid Column:', pill.grid.column);
        });
    }
}