{
    'name': 'HR Tedi',
    'version': '1.0',
    'summary': 'Quản lý nhân viên Tedi',
    'category': 'TEDI/Quản lý nhân viên',
    'author': 'Phạm Hải Huy',
    'website': 'https://yourcompany.com',
    'depends': ['hr', 'base','web','hr_skills','hr_contract'],  # thêm 'base' cho chắc chắn khi có model/attachment
    'data': [
        "security/ir.model.access.csv",
        "views/employee_education_views.xml",
        "views/employee_certificate_views.xml",
        "views/employee_trip_views.xml",
        'views/hr_employee_views.xml',
        "views/experience_position_view.xml",
        "views/employee_experience_view.xml",
        "views/folk_view.xml",

        "views/hr_training_field_view.xml"
    ],
    'assets': {
        'web.assets_backend': [
            'hr_tedi/static/src/js/month_year_widget.js',
        ],
    },
    'installable': True,
    'application': True,
}
