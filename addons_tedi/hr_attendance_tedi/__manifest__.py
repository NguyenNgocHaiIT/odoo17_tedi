{
    'name': 'TEDI: Quản lý chấm công',
    'version': '1.0',
    'category': 'TEDI/Quản lý chấm công',
    'author': 'Thưởng',
    'sequence': 1,
    'summary': '',
    'depends': ['base','web', 'hr' ,"hr_attendance" , 'hr_tedi'],
    'data': [
        "security/ir.model.access.csv",

        "views/attendance_views.xml",
        "views/holiday_config_views.xml",
        'views/request_views.xml',
        "views/menu.xml",

    ],


    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [],
}