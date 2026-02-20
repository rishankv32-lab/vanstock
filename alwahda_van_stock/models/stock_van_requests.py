from collections import defaultdict
from datetime import date

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockVanRequest(models.Model):
    _name = 'stock.van.request'
    _description = 'Van Stock'

    name = fields.Char(string='Name', default='Draft')
    counter_id = fields.Many2one('pos.config', string='POS Counter')
    state = fields.Selection([('draft', 'Draft'),('confirmed', 'Requested')], string='State', default='draft')
    request_date = fields.Date(string='Request Date')
    # pos_config_id =
    user_id = fields.Many2one('res.users', string='User')
    # source_location = fields.Char(string='Source Location')
    source_location_id = fields.Many2one('stock.location', string='Source Location')
    destination_location_id = fields.Many2one('stock.location', string='Destination Location')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    product_line_ids = fields.One2many('stock.van.product.lines', 'van_request_id', string='Products')
    internal_transfer_ids = fields.One2many('stock.picking','van_request_id', string='Internal Transfers')
    stock_type = fields.Selection([('request_stock', 'Request Stock'), ('return_stock', 'Return Stock')], string='Type')

    # @api.model
    # def default_get(self, fields):
    #     res = super(StockVanRequest, self).default_get(fields)
    #     pos_config = self.env['stock.picking.type'].sudo().search([('sequence_code', '=', 'POS'),('company_id','=',self.env.company.id)], limit=1)
    #     if pos_config:
    #         res['destination_location_id'] = pos_config.default_location_src_id
    #     return res

    def action_load_product_from_source(self):
        self.product_line_ids.unlink()
        quants = self.env['stock.quant'].search([('location_id', '=', self.source_location_id.id),('quantity', '>', 0),])

        lines = []
        for quant in quants:
            lines.append((0, 0, {
                'product_id': quant.product_id.id,
                'quantity': quant.quantity,
                'source_location_id': self.source_location_id.id,
            }))

        self.product_line_ids = lines

    def action_confirm_van_request(self):
        for record in self:
            record.state = 'confirmed'
            record.request_date = date.today()
            sequence = self.env['ir.sequence'].next_by_code('van.request.sequence')
            record.name = sequence

            picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal'),('company_id', '=', record.company_id.id)],limit=1)
            if not picking_type:
                raise UserError(_("Internal Transfer picking type not found."))
            # else:
            #     print("yay") # Even though the print was grey, it printed
            lines_by_source = defaultdict(list)
            for line in record.product_line_ids:
                lines_by_source[line.source_location_id].append(line)

            for source_location, lines in lines_by_source.items():
                # Create picking
                picking = self.env['stock.picking'].create({
                    'picking_type_id': picking_type.id,
                    'location_id': source_location.id,
                    'location_dest_id': record.destination_location_id.id,
                    'origin': record.name,
                    'van_request_id': record.id,
                    # 'batch_transfer': True,
                })

                # Create stock moves
                for line in lines:
                    self.env['stock.move'].create({
                        # 'name': line.product_id.display_name,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'product_uom': line.unit.id,
                        'location_id': source_location.id,
                        'location_dest_id': record.destination_location_id.id,
                        'picking_id': picking.id,
                    })
