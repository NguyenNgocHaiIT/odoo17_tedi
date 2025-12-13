{
    'name': 'TEDI: Quản lý chấm công',
    'version': '1.0',
    'category': 'TEDI/Quản lý chấm công',
    'author': 'Thưởng',
    'sequence': 1,
    'summary': '',
    'depends': ['base', 'web', 'hr', 'hr_attendance', 'hr_tedi', 'hr_contract', 'hr_holidays', 'hr_work_entry' , 'hr_work_entry_contract'],
    'data': [
        "security/ir.model.access.csv",
        "wizard/attendance_import_views.xml",
        "wizard/generate_work_entry_wizard_views.xml",
        "views/attendance_views.xml",
        "views/holiday_config_views.xml",
        'views/attendance_report_views.xml',
        'views/hr_leave_type_views.xml',
        'views/work_entry_views.xml',
        # 'data/data_work_entry_type.xml',

        "views/menu.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'hr_attendance_tedi/static/src/js/attendance_gantt_view.js',
            'hr_attendance_tedi/static/src/xml/attendance_gantt_templates.xml',
            'hr_attendance_tedi/static/src/css/attendance_gantt.css',

            'hr_attendance_tedi/static/src/js/work_entry_grid.js',
            'hr_attendance_tedi/static/src/xml/work_entry_grid.xml',

            'hr_attendance_tedi/static/src/js/conflictResolverDialog.js',
            'hr_attendance_tedi/static/src/xml/conflictResolverDialog.xml',

        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [],
}
