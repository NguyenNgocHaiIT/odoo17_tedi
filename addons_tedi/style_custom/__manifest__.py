{
    'name': 'Style_Custom',
    'version': '1.0',
    'summary': 'Customize tree view and navbar color',
    'category': 'Tools',
    'author': 'Duong',
    'depends': ['web'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/login_template_inherit.xml',
        'views/login_custom.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/style_custom/static/src/css/tree_view_style.css',
            '/style_custom/static/src/css/custom_dynamic_styles.css',
            # '/style_custom/static/src/css/custom_font_size.css',
            '/style_custom/static/src/js/load_dynamic_css.js',
            '/style_custom/static/src/js/load_font_size.js',
            '/style_custom/static/src/js/load_login_bg.js',
            '/style_custom/static/src/css/notebook_custom.css',
            '/style_custom/static/src/css/breadcrumb_color.css',
            '/style_custom/static/src/css/save_cancel_button.css',
            '/style_custom/static/src/js/load_user_name.js',
            '/style_custom/static/src/css/hidden_button.css',
            '/style_custom/static/src/css/search_custom.css',
        ],
        'web.assets_frontend': [
            '/style_custom/static/src/css/login_custom.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

