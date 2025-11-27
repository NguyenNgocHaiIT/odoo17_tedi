odoo.define('style_custom.load_font_size', [], function (require) {
    "use strict";
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/style_custom/custom_font_size.css';
    document.head.appendChild(link);
});