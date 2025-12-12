/** @odoo-module */

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { registry } from '@web/core/registry';
import { kanbanView } from '@web/views/kanban/kanban_view';

export class DocumentKanbanController  extends KanbanController  {

   setup() {
       super.setup();
   }

   async onCreateDocumentClick() {
       const ctx = {};

        const dirId = this.props.context?.default_document_directory_id;
        if (dirId) {
            ctx.default_document_directory_id = dirId;
        }
       this.actionService.doAction({
          type: 'ir.actions.act_window',
          res_model: 'documents.create',
          name:'Create Document',
          view_mode: 'form',
          view_type: 'form',
          views: [[false, 'form']],
          target: 'new',
          res_id: false,
          search_view_id: false,
          context: ctx,
      });
   }
}
registry.category("views").add("button_in_kanban", {
   ...kanbanView,
   Controller: DocumentKanbanController,
   buttonTemplate: "button_document.KanbanView.Buttons",
});
