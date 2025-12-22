/** @odoo-module **/

import { registry } from '@web/core/registry';

/**
 * Action để điều hướng về tree view của office.document
 * Xử lý đóng popup và điều hướng thẳng đến tree view tương ứng
 */
registry.category('actions').add('office_document_back_to_tree', async (env, context) => {
    const { actionService, dialog, notification } = env.services;
    const params = context.params || {};

    try {
        // 1. Hiển thị thông báo thành công nếu có
        if (params.notification) {
            const { title, message, type = 'success', sticky = false } = params.notification;
            if (notification && message) {
                notification.add(message, {
                    type: type,
                    title: title || undefined,
                    sticky: sticky,
                });
            }
        }

        // 2. Đóng tất cả dialog/popup
        if (dialog) {
            try {
                await dialog.closeAll();
            } catch (e) {
                console.debug('Error closing dialogs:', e);
            }
        }

        // 3. Lấy action_id từ params
        const actionId = params.action_id;

        if (actionId) {
            // 4. Thực hiện action tree view TRỰC TIẾP
            await actionService.doAction(actionId, {
                clearBreadcrumbs: true,           // QUAN TRỌNG: Xóa lịch sử điều hướng
                viewMode: 'tree',                // Ép chế độ xem là tree
                additionalContext: {
                    // Thêm context nếu cần
                    ...params.context,
                },
                onClose: () => {
                    // Callback khi đóng action
                },
                onFailure: (error) => {
                    console.error('Failed to open tree view:', error);
                    // Fallback về dashboard nếu lỗi
                    actionService.doAction('home');
                }
            });
        } else {
            // 5. Fallback: Mở tree view với model và domain
            const model = params.model || 'office.document';
            const domain = params.domain || [];
            const context = params.context || {};

            await actionService.doAction({
                type: 'ir.actions.act_window',
                name: params.name || 'Danh sách',
                res_model: model,
                views: [[false, 'tree']],      // CHỈ tree view
                view_mode: 'tree',             // CHỈ tree view
                target: 'current',
                domain: domain,
                context: context,
            }, {
                clearBreadcrumbs: true,
            });
        }

    } catch (error) {
        // Về dashboard
        env.services.action.doAction('home');
    }

    return Promise.resolve();
});
