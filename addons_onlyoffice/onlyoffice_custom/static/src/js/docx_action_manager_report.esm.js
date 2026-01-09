/** @odoo-module **/

import { registry } from "@web/core/registry";

registry
    .category("ir.actions.report handlers")
    .add("docx_handler", async function (action, options, env) {
        if (action.report_type !== "docx") {
            return Promise.resolve(false);
        }

        const type = action.report_type;
        let url = `/report/${type}/${action.report_name}`;
        const actionContext = action.context || {};

        if (action.data && JSON.stringify(action.data) !== "{}") {
            const action_options = encodeURIComponent(JSON.stringify(action.data));
            const context = encodeURIComponent(JSON.stringify(actionContext));
            url += `?options=${action_options}&context=${context}`;
        } else {
            if (actionContext.active_ids) {
                url += `/${actionContext.active_ids.join(",")}`;
            }
            if (type === "docx") {
                const context = encodeURIComponent(
                    JSON.stringify(env.services.user.context)
                );
                url += `?context=${context}`;
            }
        }

        env.services.ui.block();

        let result;
        try {
            result = await env.services.rpc("/report/docx_preview", {
                data: JSON.stringify([url, action.report_type]),
                context: JSON.stringify(env.services.user.context),
            });
        } catch (err) {
            env.services.ui.unblock();
            throw err;
        }

        env.services.ui.unblock();

        if (result && result.action) {
            return env.services.action.doAction(result.action, options);
        }

        return Promise.resolve(true);
    });
