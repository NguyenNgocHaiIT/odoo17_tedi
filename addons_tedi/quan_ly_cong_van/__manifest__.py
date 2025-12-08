
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
		'views/cau_hinh.xml',
		'views/menu.xml',
	],
	'assets': {
        'web.assets_backend': [
            #'quan_ly_cong_van/static/src/css/danh_sach_phan_phat.css',
			'quan_ly_cong_van/static/src/js/form_editable.js',
            'quan_ly_cong_van/static/src/css/tree_color.css',
            'quan_ly_cong_van/static/src/js/tree_color_custom.js',
        ],
    },

	'installable': True,
	'application': True,
	'auto_install': False,
	'qweb': [],
}
