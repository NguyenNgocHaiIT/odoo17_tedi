
{
	'name': 'TEDI: Quản lý công văn',
	'version': '1.0',
	'category': 'TEDI/Quản lý công văn',
	'author': 'HaiNN',
	'sequence': '1',
	'summary': '',
    'icon': '/quan_ly_cong_van/static/description/icon.png',
	'depends': [ 'base', 'mail', 'hr', 'project', 'web', 'partner_extend', 'hr_expense'],
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
            'quan_ly_cong_van/static/src/js/button_back.js',
            'quan_ly_cong_van/static/src/css/label_custom.css',
            'quan_ly_cong_van/static/src/js/back_to_tree.js',
        ],
    },

	'installable': True,
	'application': True,
	'auto_install': False,
	'qweb': [],
}
