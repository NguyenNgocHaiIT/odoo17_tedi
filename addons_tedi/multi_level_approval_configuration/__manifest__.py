{
    "name": "Odoo Approval All in One",
    "version": "17.0.1.0.0",
    "category": "Approvals",
    "summary": """
    Setup the approval flow for all the models: Sale Order,
    Purchase Order, MRP Order,.. Centralize all the approval requests
    in one place which help the manager reviews easily
    """,
    "live_test_url": "https://demo17.domiup.com",
    "author": "Domiup (domiup.contact@gmail.com)",
    "price": 110,
    "currency": "USD",
    "license": "OPL-1",
    "support": "domiup.contact@gmail.com",
    "depends": ["base_sparse_field", "multi_level_approval"],
    "data": [
        # Security
        "security/ir.model.access.csv",
        "security/security.xml",
        # Data
        "data/ir_cron.xml",
        # Wizards
        "wizard/cancel_approval_views.xml",
        "wizard/change_approver_views.xml",
        # Views
        "views/multi_approval_type_views.xml",
        "views/multi_approval_views.xml",
        # Add actions after all views.
        # Add menu after actions.
        # Wizards
        "wizard/request_approval_views.xml",
        "wizard/rework_approval_views.xml",
        "wizard/test_approval_views.xml",
    ],
    "images": ["static/description/banner.gif"],
    "test": [],
    "demo": [],
    "installable": True,
    "application": True,
}
