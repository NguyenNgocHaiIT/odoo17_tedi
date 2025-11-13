{
    "name": "Project Task Org Chart",
    "category": "TEDI/Project chart",
    "summary": "Hiển thị sơ đồ tổ chức các công việc con (Org Chart) trong project task",
    "version": "17.0.1.0.0",
    "depends": ["project", "web", "project_tedi"],
    "data": [
        "views/project_task_org_chart_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "project_task_org_chart/static/src/js/task_org_chart_widget.js",
            "project_task_org_chart/static/src/scss/task_org_chart.css",
            "project_task_org_chart/static/src/xml/task_org_chart_templates.xml",  # thêm tạm
        ],
        "web.assets_qweb": [
            "project_task_org_chart/static/src/xml/task_org_chart_templates.xml",
        ],

    },
    "application": True,
    "installable": True,
    "license": "LGPL-3",
}
