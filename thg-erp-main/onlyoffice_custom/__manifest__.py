# -*- coding: utf-8 -*-

{
    "name": "Onlyoffice Custom",
    "summary": "",
    "description": "",
    "author": "ONLYOFFICE",
    "website": "https://www.facebook.com/profile.php?id=61568116597340",
    "category": "Productivity",
    "version": "1.0.0",
    "depends": ["base", "mail", "hr", "alnas_docx", "alnas_xlsx", "onlyoffice_odoo", "windx_documents_management_preview"],
    "data": [
        "data/role_access.xml",
        
        "security/ir.model.access.csv",

        "views/hr_employee.xml",
        "views/fields_document_views.xml",
        "views/document_share.xml",
        "views/inherit_form_document_direc.xml",
        "views/inherit_ir_attachment_kanban.xml",
        "views/menuitem.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'onlyoffice_custom/static/src/js/m2m_field_preview.js',
            'onlyoffice_custom/static/src/xml/m2m_field_preview.xml',
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": True,
}
