{
    'name': 'n8n Odoo Bridge',
'version': 'saas~19.3.1.0.0',
'category': 'Technical',
    'summary': 'REST API integration between Odoo 19 and n8n',
    'description': """
        REST API integration for AI-powered CRM automation.
        Supports contact search, contact creation and CRM opportunity creation.
    """,
    'author': 'KKO39',
    'license': 'LGPL-3',
    'depends': [
        'base',
    'crm',
    'sale_stock',
            'purchase_stock',
            'account',
    ],
    'data': [],
    'installable': True,
    'application': False,
}