# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Web Gantt Custom',
    'category': 'Hidden',
    'description': """
Odoo Web Gantt chart view.
=============================

    """,
    'version': '2.0',
    'depends': ['web'],
    'assets': {
        'web._assets_primary_variables': [
            'web_gantt_custom/static/src/gantt_view.variables.scss',
        ],
        'web.assets_backend': [
            'web_gantt_custom/static/src/**/*',

            # Don't include dark mode files in light mode
            ('remove', 'web_gantt_custom/static/src/**/*.dark.scss'),
        ],
        'web.qunit_suite_tests': [
            'web_gantt_custom/static/tests/**/*',
            ('remove', 'web_gantt_custom/static/tests/**/*_mobile_tests.js'),
        ],
        'web.qunit_mobile_suite_tests': [
            'web_gantt_custom/static/tests/helpers.js',
            'web_gantt_custom/static/tests/**/*_mobile_tests.js',
        ],
    },
    'installable': True,
	'application': True,
	'auto_install': False,
    'license': 'OEEL-1',
}
