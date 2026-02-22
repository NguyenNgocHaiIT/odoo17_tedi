/** @odoo-module **/
import { registry } from "@web/core/registry";
import { session } from "@web/session";

export const firebasePushService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        this._initFirebase(orm);
    },

    async _initFirebase(orm) {
        if (!('serviceWorker' in navigator)) return;

        try {
            const config = await orm.call("web.push.config", "get_config", []).catch(() => null);
            if (!config || !config.apiKey) return;

            const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');

            // Chờ đến khi SW Ready
            await navigator.serviceWorker.ready;

            // CỐ ĐỊNH: Nếu chưa có active worker, đợi một chút hoặc ép kích hoạt
            if (!registration.active) {
                console.log("FCM: Đang chờ Worker kích hoạt...");
                await new Promise(resolve => setTimeout(resolve, 500));
            }

            if (typeof firebase === 'undefined') return;
            if (!firebase.apps.length) firebase.initializeApp(config);

            const messaging = firebase.messaging();
            const permission = await Notification.requestPermission();

            if (permission === 'granted') {
                // Quan trọng: Phải truyền registration vào getToken
                const currentToken = await messaging.getToken({
                    vapidKey: config.vapidKey,
                    serviceWorkerRegistration: registration
                });

                if (currentToken) {
                    // Sử dụng orm.call để gọi hàm python save_fcm_token
                    await orm.call("res.users", "save_fcm_token", [session.uid, currentToken]);
                    console.log("FCM: Đã đồng bộ Token.");
                }
            }
        } catch (err) {
            console.error('FCM Error:', err);
        }
    }
};

registry.category("services").add("firebase_push_notification", firebasePushService);