{
	'name': 'TEDI: Quản lý lịch họp',
	'version': '1.0',
	'category': 'TEDI/Quản lý lịch họp',
	'author': 'Duong',
	'sequence': '2',
	'summary': '',
    'icon': '/Quan_ly_lich_hop/static/description/icon.png',
	'depends': [ 'base', 'mail', 'hr', 'project', 'web', 'calendar'],
	'data': [
        'data/cron_data.xml',

        'security/security_data.xml',
		'security/ir.model.access.csv',
		'views/lich_hop_views.xml',
		'views/lich_phong_hop_views.xml',
		'views/lich_cong_tac_views.xml',
		'views/cau_hinh.xml',
		'views/template_dashboard.xml',
		'views/menu.xml',
	],
	'assets': {
        'web.assets_backend': [
            'Quan_ly_lich_hop/static/src/css/table_display.css',
        ],
    },

	'installable': True,
	'application': True,
	'auto_install': False,
	'qweb': [],
}
