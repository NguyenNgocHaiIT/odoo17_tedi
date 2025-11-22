{
    'name': 'HR Tedi',
    'version': '1.0',
    'summary': 'Quản lý nhân viên Tedi',
    'category': 'Human Resources',
    'author': 'Phạm Hải Huy',
    'website': 'https://yourcompany.com',
    'depends': ['hr', 'base', 'hr_attendance', 'hr_skills'],  # Đã xóa 'hr_attendance' bị lặp
    'data': [
        "security/ir.model.access.csv",
        "views/employee_education_views.xml",
        "views/employee_certificate_views.xml",
        "views/employee_trip_views.xml",
        'views/hr_employee_views.xml',
        "views/attendance_views.xml",
        "views/holiday_config_views.xml",
        'views/request_views.xml',
    ],
    'installable': True,
    'application': True,
}