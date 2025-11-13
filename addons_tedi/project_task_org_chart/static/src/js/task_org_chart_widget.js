/** @odoo-module alias=project_task_org_chart.task_org_chart_widget **/
import { Component, onWillStart, onMounted, onWillUpdateProps, onPatched, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

const fieldRegistry = registry.category("fields");

export class OrgChartField extends Component {
  static template = "project_task_org_chart.OrgChart";

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.rootRef = useRef("root");
    this._data = null;

    // density: 'compact' | 'comfy'
    this.density = (this.props?.options?.density || "compact").toLowerCase();

    // Trạng thái node thu gọn
    // - Mặc định: sau khi load lần đầu, chỉ mở root và con trực tiếp,
    //   các node sâu hơn được add vào collapsed.
    this.collapsed = new Set();

    // Lần đầu: load data theo task hiện tại
    onWillStart(async () => {
      const id = this._getTaskId();
      if (id) {
        await this.loadData(id);
      }
    });

    // Sau khi mount: render sơ đồ từ data hiện có
    onMounted(() => {
      this.renderChart(this._data);
    });

    // Khi field bị patch (resize, thay nội dung…)
    onPatched(() => {
      this.renderChart(this._data);
    });

    // Khi record đổi (chuyển sang task khác)
    onWillUpdateProps(async (nextProps) => {
      const prevId = this._getTaskId(this.props);
      const nextId = this._getTaskId(nextProps);
      if (nextId && nextId !== prevId) {
        await this.loadData(nextId); // loadData đã init collapse
        this.renderChart(this._data);
      }
    });
  }

  /* ===== Helpers ===== */

  _getTaskId(props = this.props) {
    const rec = props?.record;
    return rec?.resId || rec?.data?.id || rec?.evalContext?.id || null;
  }

  /**
   * Khởi tạo trạng thái collapsed:
   * - Root: luôn mở
   * - Mọi node (không phải root) có children => collapsed (ẩn con của nó)
   * => Lần đầu render: chỉ thấy root + con trực tiếp, không thấy cháu.
   */
  _initCollapseState() {
    this.collapsed.clear();
    const root = this._data;
    if (!root) return;

    const walk = (node, isRoot = false) => {
      if (!node) return;

      if (!isRoot && node.children && node.children.length) {
        this.collapsed.add(Number(node.task_id));
      }

      (node.children || []).forEach((child) => walk(child, false));
    };

    walk(root, true);
  }

  async loadData(id) {
    try {
      this._data = await this.orm.call("project.task", "get_task_org_chart_data", [id]);
      // 🔥 Sau khi có data, set trạng thái collapse ban đầu
      this._initCollapseState();
    } catch (err) {
      console.error("[OrgChart] ORM error:", err);
      this._data = null;
      this.collapsed.clear();
    }
  }

  _getRoot() {
    const el = this.rootRef?.el || null;
    if (el) {
      el.classList.toggle("density-compact", this.density === "compact");
      el.classList.toggle("density-comfy", this.density === "comfy");
    }
    return el || null;
  }

  renderChart(node) {
    const root = this._getRoot();
    if (!root) return false;

    const chart = root.querySelector(".org-chart");
    if (!chart) return false;

    chart.innerHTML = "";

    if (!node || !Object.keys(node).length) {
      chart.innerHTML = `<div class="org-empty">Không có dữ liệu sơ đồ</div>`;
      this._bindToolbar(root);
      return true;
    }

    // Bọc root node để căn giữa
    const rootNodeWrapper = document.createElement("div");
    rootNodeWrapper.className = "org-root-node";
    this._buildNode(rootNodeWrapper, node);
    chart.appendChild(rootNodeWrapper);

    this._bindToolbar(root);
    return true;
  }

  /* ===== Toggle helpers ===== */
  _isCollapsed(taskId) {
    return this.collapsed.has(Number(taskId));
  }

  _toggleNode(taskId) {
    taskId = Number(taskId);
    if (this.collapsed.has(taskId)) {
      this.collapsed.delete(taskId);
    } else {
      this.collapsed.add(taskId);
    }
    this.renderChart(this._data);
  }

  _expandAll(node) {
    const ids = [];
    const walk = (n) => {
      if (!n) return;
      ids.push(n.task_id);
      (n.children || []).forEach(walk);
    };
    walk(node || this._data);
    ids.forEach((id) => this.collapsed.delete(id));
    this.renderChart(this._data);
  }

  _collapseAll(node) {
    const ids = [];
    const walk = (n) => {
      if (!n) return;
      ids.push(n.task_id);
      (n.children || []).forEach(walk);
    };
    walk(node || this._data);
    ids.forEach((id) => this.collapsed.add(id));
    this.renderChart(this._data);
  }

  /* ===== Toolbar ===== */
  _bindToolbar(root) {
    const expandBtn = root.querySelector(".org-toolbar .expand-all");
    const collapseBtn = root.querySelector(".org-toolbar .collapse-all");

    if (expandBtn) {
      expandBtn.onclick = (e) => {
        e.preventDefault();
        this._expandAll(this._data);
      };
    }
    if (collapseBtn) {
      collapseBtn.onclick = (e) => {
        e.preventDefault();
        this._collapseAll(this._data);
      };
    }
  }

  /* ===== Open task form ===== */
  async _openTask(taskId) {
    if (!taskId) return;

    const viewXmlId = "project_tedi.view_task_form";
    let action = false;
    try {
      action = await this.orm.call(
        "project.task",
        "action_open_task_form_by_xmlid",
        [taskId, viewXmlId]
      );
    } catch (e) {
      console.warn("[OrgChart] Fallback to default form:", e);
    }

    this.action.doAction(
      action || {
        type: "ir.actions.act_window",
        res_model: "project.task",
        res_id: taskId,
        views: [[false, "form"]],
        view_mode: "form",
        target: "current",
      }
    );
  }

  /* ===== Build node DOM =====
   * DÙNG FIELD:
   *  - node.task_id
   *  - node.task_name
   *  - node.direct_subtask_count
   *  - node.progress
   *  - node.children
   */
  _buildNode(parent, node) {
    if (!node) return;

    const hasChildren = !!(node.children && node.children.length);
    const isCollapsed = this._isCollapsed(node.task_id);

    const rawTitle = (node.task_name || "").trim();
    const title = rawTitle || `(Task #${node.task_id})`;

    // Nếu không có title và không có children thì thôi khỏi vẽ
    if (!rawTitle && !hasChildren) {
      return;
    }

    const div = document.createElement("div");
    div.className = "org-node";
    div.setAttribute("data-task-id", String(node.task_id));

    const toggleHtml = hasChildren
      ? `<button class="toggle"
                 aria-label="${isCollapsed ? "Mở node" : "Thu gọn node"}"
                 title="${isCollapsed ? "Mở node" : "Thu gọn node"}">
           ${isCollapsed ? "▸" : "▾"}
         </button>`
      : "";

    /* Progress bar – chỉ show nếu có số */
    let progressHtml = "";
    if (typeof node.progress === "number") {
      let value = node.progress;
      if (isNaN(value)) value = 0;
      value = Math.max(0, Math.min(100, value));

      progressHtml = `
        <div class="progress-row" title="Tiến độ">
          <div class="progress-track">
            <div class="progress-fill" style="width: ${value.toFixed(0)}%;"></div>
          </div>
          <span class="progress-label">${value.toFixed(0)}%</span>
        </div>
      `;
    }

    div.innerHTML = `
      <div class="card"
           role="button"
           tabindex="0"
           aria-label="${this._escape(title)}">
        <div class="card-top">
          ${toggleHtml}
          ${
            node.direct_subtask_count > 0
              ? `<div class="count" title="Số công việc con trực tiếp">${node.direct_subtask_count}</div>`
              : ""
          }
        </div>

        <div class="task-title" title="${this._escape(title)}">
          ${this._escape(title)}
        </div>

        ${progressHtml}
      </div>
    `;

    parent.appendChild(div);

    const card = div.querySelector(".card");
    if (card) {
      card.style.cursor = "pointer";
      card.addEventListener("click", () => this._openTask(node.task_id));
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this._openTask(node.task_id);
        }
      });
    }

    const toggleBtn = div.querySelector(".toggle");
    if (toggleBtn && hasChildren) {
      toggleBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = Number(div.getAttribute("data-task-id"));
        this._toggleNode(id);
      });
      toggleBtn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          const id = Number(div.getAttribute("data-task-id"));
          this._toggleNode(id);
        }
      });
    }

    // 🔑 Quan trọng: chỉ render children nếu KHÔNG collapsed
    if (hasChildren && !isCollapsed) {
      const wrap = document.createElement("div");
      wrap.className = "org-children";
      node.children.forEach((child) => {
        const col = document.createElement("div");
        col.className = "org-child-col";
        this._buildNode(col, child);
        wrap.appendChild(col);
      });
      parent.appendChild(wrap);
    }
  }

  _escape(s) {
    return String(s || "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));
  }
}

fieldRegistry.add("org_chart", { component: OrgChartField, supportedOptions: [] });
