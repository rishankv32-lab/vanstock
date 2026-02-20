from odoo import _, api, fields, models

class StockVanProduct(models.Model):
    _name = 'stock.van.product.lines'
    _description = 'Stock Van Product'

    product_id = fields.Many2one('product.product', string='Product')
    source_quantity = fields.Float(string='Source Quantity')
    quantity = fields.Float(string='Quantity')
    source_location_id = fields.Many2one('stock.location', string='Source Location')
    unit = fields.Many2one(
        'uom.uom', "UoM",
        compute="_compute_product_uom_van", store=True, precompute=True,
    )
    van_request_id = fields.Many2one('stock.van.request', string='Van Request')

    @api.depends('product_id')
    def _compute_product_uom_van(self):
        for move in self:
            move.unit = move.product_id.uom_id.id
            # addons/stock/models/stock_move.py

class StockVanMove(models.Model):
    _inherit = 'stock.picking'

    van_request_id = fields.Many2one('stock.van.request', string='Van Request')