# -*- coding: utf-8 -*-
{
    'name': 'Ecabinet: Documents Management - Preview',
    'summary': "Document management odoo, odoo documents management preview attachment, odoo document management with preview, documents management and preview odoo, odoo dms with file preview, odoo document system preview attachments, manage documents and preview files odoo, odoo document workflow with inline preview, odoo document storage preview pdf image video, odoo enterprise documents file preview, preview attachments odoo, file preview odoo, document preview odoo, image preview odoo, video preview odoo, pdf preview odoo, ms word preview odoo, excel preview odoo, powerpoint preview odoo, odoo preview attachments in documents module, preview attachments before download odoo, inline file preview in odoo documents, preview docx odoo, preview xlsx odoo, preview pptx odoo, odoo pdf image video preview, odoo preview word excel powerpoint, odoo preview ms office attachments, odoo multimedia preview, preview binary attachments odoo, document preview, file viewer, file preview, attachment preview, document viewer, preview attachment, video preview, image preview, pdf preview, word preview, excel preview, ppt preview, office preview, documents management, document management, file management, dms odoo, documents viewer, preview files, inline preview, preview documents, documents, document, file, files, docs, dms, archive, storage, workflow, approval, version, signature, sharing, tagging, ocr, search, secure, paperless, viewer, manage, management, portal, previewer, document management system, odoo document manager, odoo documents app, odoo dms, odoo file management, odoo file storage, odoo file archive, odoo document workflow, odoo document approval, odoo document versioning, odoo document collaboration, odoo document tagging, odoo document ocr, odoo document search, odoo full text search, odoo document security, odoo access rights documents, odoo document portal, odoo document share, odoo document signature, odoo documents dashboard, odoo records management, odoo paperless office, enterprise content management, ecm system, file management system, digital archive, records management, paperless office, document workflow software, document approval workflow, document version control, document collaboration tool, document storage system, odoo attachment viewer, odoo media preview, preview in chatter odoo, preview in portal odoo, preview in kanban odoo, preview in form view odoo, attachment lightbox odoo, attachment quick view, attachment carousel odoo, file viewer widget odoo, media player odoo, odoo documents preview, odoo dms preview, documents management with preview, document management with preview, dms with inline preview, file management with preview, document storage preview, document workflow preview, paperless preview, integrated preview attachments, all in one document preview, document portal preview, document manager with preview, documents preview module odoo, documents preview app odoo, binary preview, quick preview, media preview, content management, records management, document sharing, manage company files, organize documents app",
    'version': '17.0.1.0.0',
    'category': 'TEDI/Ecabinet: Documents Management - Preview',
    'author': 'Win DX JSC',
    'company': 'Win DX JSC',
    'maintainer': 'Win DX JSC',
    'price': 139,
    'currency': 'USD',
    'sequence': 110,
    'website': 'https://windx.com.vn',
    'support': 'windxcontact@gmail.com',
    'category': 'Tools',
    'depends': ['base', 'attachment_indexation'],
    'data': [
        'security/document_security.xml',
        'security/ir.model.access.csv',

        'views/directory_tag.xml',
        'views/document_tag.xml',
        'views/ir_attachments_views.xml',
        'views/document_directory.xml',

        'menu/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'windx_documents_management_preview/static/src/**/*',

            'windx_documents_management_preview/static/src/scss/file_viewer.scss',
        ],
    },
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
