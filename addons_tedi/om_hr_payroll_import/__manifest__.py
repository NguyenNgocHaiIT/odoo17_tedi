{
    'name': 'TEDI: PayRoll Import',
    'version': '1.0',
    'category': 'TEDI/PayRoll Import',
    'author': 'Thưởng',
    'sequence': 1,
    'summary': '',
    'depends': ['om_hr_payroll'],
    'data': [
        "security/ir.model.access.csv",
        "wizard/import_allowance_view.xml",
        "wizard/import_insurance_view.xml",

        "views/menu.xml"

    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [],
}
