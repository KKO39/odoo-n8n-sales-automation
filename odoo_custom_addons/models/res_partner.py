from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    _sql_constraints = [
            (
                'n8n_telegram_id_unique',
                'unique(n8n_telegram_id)',
                'Telegram User ID must be unique.',
            ),
        ]

    n8n_telegram_id = fields.Char(
        string='Telegram User ID',
        copy=False,
        index=True,
    )

    n8n_telegram_username = fields.Char(
        string='Telegram Username',
        copy=False,
    )

    