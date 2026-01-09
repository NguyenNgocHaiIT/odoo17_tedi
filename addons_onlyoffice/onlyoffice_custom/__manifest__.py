# -*- coding: utf-8 -*-

{
    "name": "Onlyoffice Custom",
    "summary": "",
    "description": "",
    "author": "ONLYOFFICE",
    "website": "https://www.facebook.com/profile.php?id=61568116597340",
    "category": "Productivity",
    "version": "1.0.0",
    "depends": ["base", "mail", "hr", "alnas_docx", "alnas_xlsx", "onlyoffice_odoo", "documents","onlyoffice_odoo_documents"],
    "data": [
        "data/role_access.xml",

        "security/ir.model.access.csv",
        "security/document_security.xml",

        "views/hr_employee.xml",
        "views/document_share.xml",
        "views/document_folder_views.xml",
        "views/fields_document_views.xml",
        "views/document_create_views.xml",

        "wizard/report_preview_view.xml",

        "views/menuitem.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'onlyoffice_custom/static/src/js/document_kanban_button.js',
            'onlyoffice_custom/static/src/js/m2m_field_preview.js',
            'onlyoffice_custom/static/src/js/docx_action_manager_report.esm.js',
            'onlyoffice_custom/static/src/js/xlsx_action_manager_report.esm.js',
            'onlyoffice_custom/static/src/js/document_inspection_onlyoffice.js',
            'onlyoffice_custom/static/src/js/document_search_panel.js',

            'onlyoffice_custom/static/src/xml/document_kanban_button.xml',
            'onlyoffice_custom/static/src/xml/document_inspector_onlyoffice.xml',
            'onlyoffice_custom/static/src/xml/document_search_panel.xml',
            'onlyoffice_custom/static/src/xml/m2m_field_preview.xml',
            'onlyoffice_custom/static/src/css/report.scss',
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": True,
    'post_init_hook': 'disable_standard_folder_rule',
    'uninstall_hook': 'restore_standard_folder_rule',
}
