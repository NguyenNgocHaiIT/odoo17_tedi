{
    'name': 'TEDI: Quản lý chấm công',
    'version': '1.0',
    'category': 'TEDI/Quản lý chấm công',
    'author': 'Thưởng',
    'sequence': 1,
    'summary': '',
    'depends': ['base', 'web', 'hr', 'hr_attendance', 'hr_tedi', 'hr_contract', 'hr_holidays'],
    'data': [
        "security/ir.model.access.csv",
        "wizard/attendance_import_views.xml",
        "views/attendance_views.xml",
        "views/holiday_config_views.xml",
        'views/attendance_report_views.xml',


        "views/menu.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'hr_attendance_tedi/static/src/js/attendance_gantt_view.js',
            'hr_attendance_tedi/static/src/xml/attendance_gantt_templates.xml',
            'hr_attendance_tedi/static/src/css/attendance_gantt.css',

        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [],
}
