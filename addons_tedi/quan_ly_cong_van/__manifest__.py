
{
	'name': 'TEDI: Quản lý công văn',
	'version': '1.0',
	'category': 'TEDI/Quản lý công văn',
	'author': 'HaiNN',
	'sequence': '1',
	'summary': '',
	'depends': [ 'base', 'mail', 'hr', 'project', 'web'],
	'data': [
		'security/office_document_security.xml',
		'security/ir.model.access.csv',
		'views/quan_ly_cong_viec.xml',
		'views/cong_van.xml',
		'views/quan_ly_doi_xe.xml',
		'views/cau_hinh.xml',
		'views/menu.xml',
	],

	'installable': True,
	'application': True,
	'auto_install': False,
	'qweb': [],
}
