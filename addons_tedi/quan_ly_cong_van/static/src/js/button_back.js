/** @odoo-module **/

import { registry } from '@web/core/registry';

// Đăng ký client action mới
registry.category('actions').add('history_back', async () => {
    // Gọi back trên window
    window.history.back();
});
