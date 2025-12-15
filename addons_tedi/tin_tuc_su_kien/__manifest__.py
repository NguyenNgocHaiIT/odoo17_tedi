{
	'name': 'TEDI: Quản lý tin tức và sự kiện',
	'version': '1.0',
	'category': 'TEDI/Quản lý tin tức và sự kiện',
	'author': 'Duong',
	'sequence': '3',
	'summary': '',
    'icon': '/tin_tuc_su_kien/static/description/icon.png',
	'depends': [ 'base', 'mail', 'hr', 'project', 'web', 'event'],
	'data': [
		'security/ir.model.access.csv',
		'views/su_kien_views.xml',
		'views/thong_bao_views.xml',
		'views/website_views.xml',
		'views/menu.xml',
	],

	'installable': True,
	'application': True,
	'auto_install': False,
	'qweb': [],
}
