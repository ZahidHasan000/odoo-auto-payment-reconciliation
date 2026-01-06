{
    'name': 'Odoo Technical Assessment',
    'version': '17.0.1.0.0',
    'category': 'Technical',
    'summary': 'Payment Reconciliation, Password Change, Employee Letters',
    'description': """
        Technical Assessment Module
        ===========================
        
        Features:
        ---------
        1. Automatic Payment Reconciliation using Sales Order Reference
        2. Change Password Option in User Profile Menu
        3. Dynamic Employee Letter Generation Wizard
        
        Author: Your Name
        Repository: https://github.com/yourusername/odoo_assessment
    """,
    'author': 'Your Name',
    'website': 'https://github.com/yourusername/odoo_assessment',
    'depends': [
        'base',
        'account',
        'sale'
    ],
    'data': [
        # 'security/ir.model.access.csv',
        # 'views/res_users_views.xml',
        # 'views/employee_letter_wizard_views.xml',
        # 'reports/employee_letter_templates.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         'odoo_assessment/static/src/js/user_menu.js',
    #     ],
    # },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}