{
    'name': 'Email OTP Login',
    'version': '1.0',
    'category': 'TEDI/ToolsEMAIL',
    'summary': 'Đăng nhập 2 lớp (2FA) bằng OTP qua Gmail',
    'depends': ['base', 'web', 'mail', 'base_setup'],
    'data': [
        'data/mail_template.xml',
        'views/res_config_settings_views.xml', # <== THÊM DÒNG NÀY
        'views/login_templates.xml',
    ],
    'installable': True,
    'application': True,
}