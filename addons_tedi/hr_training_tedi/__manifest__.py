{
    'name': 'TEDI: Quản lý đào tạo',
    'version': '1.0',
    'category': 'TEDI/Quản lý đào tạo',
    'author': 'Thưởng',
    'sequence': 1,
    'summary': '',
    'depends': ['base','web','quan_ly_tuyen_dung'],
    'data': [
        'data/ir_cron.xml',
        "data/training_field_data.xml",
        "security/training_security.xml",
        "security/ir.model.access.csv",


        "views/training_needs_view.xml",
        "views/training_needs_survey_view.xml",
        "views/training_course_view.xml",
        "views/training_plan_view.xml",
        "views/training_plan_participation_view.xml",
        "views/training_review_view.xml",

        "views/menu.xml",

    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [],
}
