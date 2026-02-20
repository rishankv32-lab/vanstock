from odoo import models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _get_pos_location(self):
        """Get POS stock location from picking_type_id.default_location_src_id"""
        if self.config_id.picking_type_id:
            return self.config_id.picking_type_id.default_location_src_id
        return False

    def _get_warehouse_locations(self):
        """Return all internal stock locations marked as warehouse locations."""

        return self.env["stock.location"].search([
            ("is_warehouse_location", "=", True),
            ("usage", "=", "internal"),
        ])

    def _get_primary_warehouse_location(self):
        """Return a single location to be used as source/destination in transfers."""

        locations = self._get_warehouse_locations()
        return locations[:1]

    def get_warehouse_stock_products(self):
        """Get products available in warehouse for van request

        Fetches products from warehouse location marked with is_warehouse_location if set,
        """

        warehouse_locations = self._get_warehouse_locations()
        if not warehouse_locations:
            return []

        # Get product IDs that are available in POS
        pos_product_ids = self.env['product.product'].search([
            ('available_in_pos', '=', True),  # Only POS products
        ]).ids

        quants = self.env['stock.quant'].search([
            ('location_id', 'in', warehouse_locations.ids),
            ('quantity', '>', 0),
            ('product_id', 'in', pos_product_ids),
        ])

        # Group products by ID to avoid duplicates and sum quantities
        product_dict = {}
        for quant in quants:
            product_id = quant.product_id.id
            if product_id in product_dict:
                product_dict[product_id]['quantity'] += quant.quantity
            else:
                product_dict[product_id] = {
                    'id': product_id,
                    'name': quant.product_id.display_name,
                    'display_name': quant.product_id.display_name,
                    'default_code': quant.product_id.default_code,
                    'barcode': quant.product_id.barcode,
                    'quantity': quant.quantity,
                    'uom': quant.product_id.uom_id.name,
                }

        return list(product_dict.values())

    def create_van_request_from_pos(self, request_type, lines):
        """Create van request from POS

        For Van Item Request (load):
            - Source: Warehouse Stock Location (warehouse.lot_stock_id)
            - Destination: POS Stock Location (picking_type_id.default_location_src_id)

        For Van Item Return (return):
            - Source: POS Stock Location (picking_type_id.default_location_src_id)
            - Destination: Warehouse Stock Location (warehouse.lot_stock_id)
        """
        _logger.info("=== create_van_request_from_pos START ===")
        _logger.info("Request Type: %s", request_type)
        _logger.info("Lines: %s", lines)
        _logger.info("POS Config ID: %s", self.config_id.id)
        _logger.info("POS Config Name: %s", self.config_id.name)

        # Get POS stock location from picking_type_id.default_location_src_id
        pos_location = self._get_pos_location()
        _logger.info("POS Stock Location: %s (ID: %s)", pos_location.display_name if pos_location else None, pos_location.id if pos_location else None)

        if not pos_location:
            raise UserError("No stock location configured for this POS. Please set Operation Type with Source Location in POS Configuration.")

        # Get warehouse from picking_type_id.warehouse_id
        warehouse = self._get_warehouse()
        _logger.info("POS Picking Type: %s", self.config_id.picking_type_id.name if self.config_id.picking_type_id else None)
        _logger.info("Warehouse from Picking Type: %s (ID: %s)", warehouse.name if warehouse else None, warehouse.id if warehouse else None)

        if not warehouse:
            # Fallback: search warehouse by company
            warehouse = self.env['stock.warehouse'].search([
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            _logger.info("Fallback - Warehouse by company: %s", warehouse.name if warehouse else None)

        if not warehouse:
            raise UserError("No warehouse found. Please configure warehouse in POS Operation Type settings.")

        warehouse_location = self._get_primary_warehouse_location()
        _logger.info("Warehouse Stock Location (flagged or default): %s (ID: %s)", warehouse_location.display_name if warehouse_location else None, warehouse_location.id if warehouse_location else None)

        if not warehouse_location:
            raise UserError("No stock location found for warehouse '%s'." % warehouse.name)

        if request_type == 'return':
            source = pos_location
            dest = warehouse_location
            stock_type = 'return_stock'
        else:
            source = warehouse_location
            dest = pos_location
            stock_type = 'request_stock'

        if source.id == dest.id:
            raise UserError("Source and destination locations cannot be the same. Please review POS and warehouse configuration.")

        _logger.info("Source Location: %s (ID: %s)", source.display_name, source.id)
        _logger.info("Destination Location: %s (ID: %s)", dest.display_name, dest.id)
        _logger.info("Stock Type: %s", stock_type)

        # Create van request record
        try:
            request = self.env['stock.van.request'].create({
                'counter_id': self.config_id.id,
                'stock_type': stock_type,
                'source_location_id': source.id,
                'destination_location_id': dest.id,
                'user_id': self.env.user.id,
                'state': 'draft',
            })
            _logger.info("Van Request Created: %s (ID: %s)", request.name, request.id)
        except Exception as e:
            _logger.error("Error creating van request: %s", str(e))
            raise UserError("Error creating van request: %s" % str(e))

        # Create product lines
        for line in lines:
            _logger.info("Creating line for product_id: %s, quantity: %s", line['product_id'], line['quantity'])
            # Get source quantity from source location
            quant = self.env['stock.quant'].search([
                ('product_id', '=', line['product_id']),
                ('location_id', '=', source.id),
            ], limit=1)
            source_qty = quant.quantity if quant else 0

            self.env['stock.van.product.lines'].create({
                'van_request_id': request.id,
                'product_id': line['product_id'],
                'quantity': line['quantity'],
                'source_quantity': source_qty,
                'source_location_id': source.id,
            })

        # Confirm the request to create internal transfer
        _logger.info("Confirming van request...")
        return {'id': request.id, 'name': request.name}

    def get_van_requests(self, request_type=None):
        """Get van requests for this POS"""
        domain = [('counter_id', '=', self.config_id.id)]
        if request_type:
            stock_type = 'request_stock' if request_type == 'load' else 'return_stock'
            domain.append(('stock_type', '=', stock_type))

        requests = self.env['stock.van.request'].search(domain, order='create_date desc', limit=50)
        result = []
        for req in requests:
            result.append({
                'id': req.id,
                'name': req.name,
                'state': req.state,
                'stock_type': req.stock_type,
                'request_date': req.request_date.strftime('%Y-%m-%d') if req.request_date else '',
                'user': req.user_id.name if req.user_id else '',
                'lines': [{
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.display_name,
                    'quantity': line.quantity,
                    'uom': line.unit.name if line.unit else '',
                } for line in req.product_line_ids]
            })
        return result

