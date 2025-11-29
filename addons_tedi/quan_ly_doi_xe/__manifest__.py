
{
	'name': 'TEDI: Quản lý đội xe',
	'version': '1.0',
	'category': 'TEDI/Quản lý đội xe',
	'author': 'HaiNN',
	'sequence': '1',
	'summary': '',
	'depends': [ 'base', 'mail', 'hr', 'project', 'web'],
	'data': [
		'security/ir.model.access.csv',
		'views/quan_ly_doi_xe.xml',
		'views/menu.xml',
	],

	'installable': True,
	'application': True,
	'auto_install': False,
	'qweb': [],
}
