{
    'name': 'TEDI: Quản lý tuyển dụng',
    'version': '1.0',
    'category': 'TEDI/Quản lý tuyển dụng',
    'author': 'Thưởng',
    'sequence': 1,
    'summary': '',
    'depends': ['base','web', 'hr' , 'hr_recruitment', 'hr_contract'],
    'data': [
        "security/recruitment_security.xml",
        "security/ir.model.access.csv",

        "data/experience_request_data.xml",
        'data/recruitment_sequence.xml',

        "views/report_applicant_evaluation.xml",
        'views/applicant_eval_page.xml',
        "views/applicant_views.xml",
        "views/recruitment_plan_view.xml",
        "views/hr_job_form_tedi.xml",
        'views/applicant_actions_menu.xml',
        "views/wizard_old_applicant.xml",
        'views/experience_request_views.xml',

        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "quan_ly_tuyen_dung/static/src/scss/recruitment_plan.scss",
            "quan_ly_tuyen_dung/static/src/scss/tree_custom.scss",
        ],
    },

    'installable': True,
    'application': False,
    'auto_install': False,
    'qweb': [],
}
