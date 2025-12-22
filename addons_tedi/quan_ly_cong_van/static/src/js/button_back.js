/** @odoo-module **/
import { registry } from '@web/core/registry';

registry.category('actions').add('history_back', async (env, context) => {
    // Đóng popup trước
    env.services.dialog.closeAll();

    // Quay lại trang trước
    window.history.back();

    // Hoặc có thể reload parent window
    if (window.opener) {
        window.opener.location.reload();
        window.close();
    }

    return Promise.resolve();
});

// Don't forget to add this JS file in your assets