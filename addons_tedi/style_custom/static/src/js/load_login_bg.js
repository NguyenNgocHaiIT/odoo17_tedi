odoo.define('style_custom.load_login_bg', [], function (require) {
    "use strict";
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/style_custom/static/src/css/login_custom.css';
    document.head.appendChild(link);
});