from odoo import models, fields

class StockLocation(models.Model):
    _inherit = 'stock.location'

    is_warehouse_location = fields.Boolean(
        string='Is Warehouse Location',
        default=False,
        index=True,
        help="Check this box if this location represents a main warehouse storage area."
    )