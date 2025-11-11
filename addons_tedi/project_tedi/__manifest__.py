{
    'name': "TEDI: Dự án",
    'version': "1.0",
    'summary': "",
    'description': """""",
    'category': 'Project',
    'author': "YourCompany",
    'depends': ['project', 'account', 'web'],
    'data': [
        'security/ir.model.access.csv',
        # 'views/asset_inherit.xml',
        'views/project.xml',
        'views/task.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
