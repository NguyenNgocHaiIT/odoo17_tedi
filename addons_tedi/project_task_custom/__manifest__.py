# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Project Task Gantt",
    'summary': """Bridge module for project and enterprise""",
    'description': """
Bridge module for project and enterprise
    """,
    'category': 'Services/Project',
    'version': '2.0',
    'depends': ['project', 'web_gantt_custom'],
    'data': [

        'views/project_task_gantt.xml',
    ],
    'assets': {
        'web.assets_backend': [
            #'project_task_custom/static/src/*',
            #'project_task_custom/static/src/**/*.xml',

        ],
    },
    "application": True,
    "installable": True,
    'auto_install': False,
    "license": "LGPL-3",
}
