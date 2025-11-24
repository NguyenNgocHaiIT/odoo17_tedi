{
    'name': 'TEDI: Quản lý chấm công',
    'version': '1.0',
    'category': 'TEDI/Quản lý chấm công',
    'author': 'Thưởng',
    'sequence': 1,
    'summary': '',
    'depends': ['base', 'web', 'hr', 'hr_attendance', 'hr_tedi'],
    'data': [
        "security/ir.model.access.csv",
        "wizard/attendance_import_views.xml",
        "views/attendance_views.xml",
        "views/holiday_config_views.xml",
        'views/request_views.xml',
        "views/menu.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'hr_attendance_tedi/static/src/js/list_import_button.js',
            # TẠM THỜI BỎ XML NÀY RA, NÓ LÀM VỠ ASSETS
            # 'hr_attendance_tedi/static/src/xml/list_import_button.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [],
}
