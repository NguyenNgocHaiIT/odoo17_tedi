{
    'name': 'TEDI: Quản lý đội xe',
    'version': '1.0',
    'category': 'TEDI/Quản lý đội xe',
    'author': 'HaiNN',
    'sequence': 1,  # Số nguyên (Interger) chuẩn hơn là String '1'
    'summary': 'Quản lý phương tiện, lịch sử công tác và sửa chữa',


    'depends': ['base', 'mail', 'hr', 'project', 'web', 'fleet'],

    'data': [
        'security/security_data.xml',
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        'security/ir.model.access.csv',


        'views/vehicle_view.xml',
        'views/vehicle_register.xml',
        'views/vehicle_fix.xml',
        'views/vehicle_odometer.xml',
        'views/bao_cao_wizard.xml',
        'views/chi_phi_phat_sinh.xml',
        'views/menu.xml',
    ],


    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',  # Nên thêm license để tránh cảnh báo
}