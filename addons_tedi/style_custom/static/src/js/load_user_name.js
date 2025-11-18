/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";
import { onMounted } from "@odoo/owl";

patch(NavBar.prototype, {
    setup() {
        super.setup();
        this.userName = this.env.services.user.name;

        // Gọi khi component đã mount
        onMounted(() => {
            this.__setupUserName();
        });
    },

    __setupUserName() {
        try {
            const avatar = document.querySelector('.o_user_avatar');
            if (avatar) {
                if (!avatar.previousElementSibling?.classList?.contains('o_user_name')) {
                    const nameEl = document.createElement('span');
                    nameEl.className = 'o_user_name me-2 fw-bold';
                    nameEl.textContent = this.userName;
                    avatar.before(nameEl);
                }
            } else {
                console.warn("Không tìm thấy avatar element");
            }
        } catch (error) {
            console.error("Lỗi khi thêm tên user:", error);
        }
    }
});
