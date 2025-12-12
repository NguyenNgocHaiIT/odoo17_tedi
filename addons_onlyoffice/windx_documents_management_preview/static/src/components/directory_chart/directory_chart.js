/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { onWillStart, useState, onWillUpdateProps, Component } from "@odoo/owl";

export class DocumentDirectoryChart extends Component {
    setup() {
        super.setup();

        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({
            hierarchy: {},
        });
        onWillStart(async () => await this.fetchHierarchy(this.props.record.resId));

        onWillUpdateProps(async (nextProps) => {
            await this.fetchHierarchy(nextProps.record.resId);
        });
    }

    async fetchHierarchy(directoryId) {
        this.state.hierarchy = await this.orm.call("document.directory", "get_document_directory_hierarchy", [
            directoryId,
        ]);
    }

    openDirectoryAttachments(directoryId) {
        this.action.doAction("windx_documents_management_preview.act_attachment_from_document_directory", {
            additionalContext: {
                active_id: directoryId,
            },
        });
    }
}
DocumentDirectoryChart.template = "windx_documents_management_preview.DocumentDirectoryChart";
DocumentDirectoryChart.props = {
    ...standardWidgetProps,
};

export const documentDirectoryChart = {
    component: DocumentDirectoryChart,
};
registry.category("view_widgets").add("document_directory_chart_preview", documentDirectoryChart);
