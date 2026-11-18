import logging

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError


_logger = logging.getLogger(__name__)


class N8nOdooBridgeController(http.Controller):

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _response(self, data, status=200):
        return request.make_json_response(data, status=status)

    def _get_json_body(self):
        data = request.httprequest.get_json(silent=True)
        return data if isinstance(data, dict) else None

    def _find_contact_by_email(self, email):
        email = (email or '').strip().lower()

        if not email:
            return request.env['res.partner']

        return request.env['res.partner'].search(
            [('email', '=ilike', email)],
            limit=1,
        )

    # ---------------------------------------------------------
    # Health Check
    # ---------------------------------------------------------

    @http.route(
        '/api/n8n/v1/health',
        type='http',
        auth='bearer',
        methods=['GET'],
        csrf=False,
    )
    def health_check(self, **kwargs):
        return self._response({
            'success': True,
            'service': 'n8n_odoo_bridge',
            'version': '19.0',
        })
        

    # ---------------------------------------------------------
    # Search Customer
    # ---------------------------------------------------------

    @http.route(
        '/api/n8n/v1/customers/search',
        type='http',
        auth='bearer',
        methods=['POST'],
        csrf=False,
    )
    def search_customer(self, **kwargs):
        data = self._get_json_body()

        if data is None:
            return self._response({
                'success': False,
                'message': 'A valid JSON object is required.',
            }, status=400)

        search = data.get('search')

        if not isinstance(search, str) or len(search.strip()) < 2:
            return self._response({
                'success': False,
                'message': 'Search keyword must contain at least 2 characters.',
            }, status=400)

        search = search.strip()

        try:
            Partner = request.env['res.partner']

            domain = [
                    '|', '|', '|',
                    ('name', 'ilike', search),
                    ('email', 'ilike', search),
                    ('phone', 'ilike', search),
                    ('vat', 'ilike', search),
                ]

            customers = Partner.search(
                domain,
                limit=10,
                order='name asc',
            )

            result = []

            for customer in customers:
                result.append({
                    'id': customer.id,
                    'name': customer.name,
                    'email': customer.email or '',
                    'phone': customer.phone or '',
                    'vat': customer.vat or '',
                    'is_company': customer.is_company,
                    'parent_company': customer.parent_id.name or '',
                })

            return self._response({
                'success': True,
                'found': bool(customers),
                'count': len(customers),
                'customers': result,
            })

        except AccessError:
            return self._response({
                'success': False,
                'message': 'Access denied.',
            }, status=403)

    # ---------------------------------------------------------
    # Check Products Stock
    # ---------------------------------------------------------
    
    @http.route(
        '/api/n8n/v1/stock',
        type='http',
        auth='bearer',
        methods=['GET'],
        csrf=False
    )
    def check_stock(self, **kwargs):
        product_id = request.httprequest.args.get('product_id')
        warehouse_id = request.httprequest.args.get('warehouse_id')

        if not product_id:
            return request.make_json_response({
                'success': False,
                'message': 'Product ID is required.'
            }, status=400)

        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return request.make_json_response({
                'success': False,
                'message': 'Invalid Product ID.'
            }, status=400)

        product = request.env['product.product'].sudo().browse(
            product_id
        ).exists()

        if not product:
            return request.make_json_response({
                'success': False,
                'message': 'Product not found.'
            }, status=404)

        stock_env = request.env['product.product'].sudo()

        if warehouse_id:
            try:
                warehouse_id = int(warehouse_id)
            except (ValueError, TypeError):
                return request.make_json_response({
                    'success': False,
                    'message': 'Invalid Warehouse ID.'
                }, status=400)

            warehouse = request.env['stock.warehouse'].sudo().browse(
                warehouse_id
            ).exists()

            if not warehouse:
                return request.make_json_response({
                    'success': False,
                    'message': 'Warehouse not found.'
                }, status=404)

            stock_env = stock_env.with_context(
                warehouse=warehouse.id
            )

        stock_product = stock_env.browse(product.id)

        return request.make_json_response({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.display_name,
                'default_code': product.default_code or '',
                'uom': product.uom_id.name,
                'qty_available': stock_product.qty_available,
                'free_qty': stock_product.free_qty,
                'virtual_available': stock_product.virtual_available,
                'incoming_qty': stock_product.incoming_qty,
                'outgoing_qty': stock_product.outgoing_qty,
            }
        }, status=200)

    # ---------------------------------------------------------
    # Get product price
    # ---------------------------------------------------------

    @http.route(
        '/api/n8n/v1/price',
        type='http',
        auth='bearer',
        methods=['GET'],
        csrf=False
    )
    def get_product_price(self, **kwargs):
        args = request.httprequest.args

        product_id = args.get('product_id')
        partner_id = args.get('partner_id')
        pricelist_id = args.get('pricelist_id')
        quantity = args.get('quantity', '1')

        if not product_id:
            return request.make_json_response({
                'success': False,
                'message': 'Product ID is required.'
            }, status=400)

        try:
            product_id = int(product_id)
            quantity = float(quantity)

            if quantity <= 0:
                raise ValueError()

            if partner_id:
                partner_id = int(partner_id)

            if pricelist_id:
                pricelist_id = int(pricelist_id)

        except (ValueError, TypeError):
            return request.make_json_response({
                'success': False,
                'message': 'Invalid input parameters.'
            }, status=400)

        product = request.env['product.product'].sudo().browse(
            product_id
        ).exists()

        if not product:
            return request.make_json_response({
                'success': False,
                'message': 'Product not found.'
            }, status=404)

        pricelist = request.env['product.pricelist']

        if partner_id:
            partner = request.env['res.partner'].sudo().browse(
                partner_id
            ).exists()

            if not partner:
                return request.make_json_response({
                    'success': False,
                    'message': 'Customer not found.'
                }, status=404)

            if not pricelist_id:
                pricelist_id = (
                    partner.property_product_pricelist.id
                )

        if pricelist_id:
            pricelist = request.env['product.pricelist'].sudo().browse(
                pricelist_id
            ).exists()

            if not pricelist:
                return request.make_json_response({
                    'success': False,
                    'message': 'Pricelist not found.'
                }, status=404)

            price = pricelist._get_product_price(
                product,
                quantity
            )

            currency = pricelist.currency_id.name
            price_type = 'pricelist'

        else:
            price = product.lst_price
            currency = request.env.company.currency_id.name
            price_type = 'sales_price'

        return request.make_json_response({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.display_name,
            },
            'quantity': quantity,
            'price': price,
            'currency': currency,
            'price_type': price_type,
            'pricelist_id': pricelist.id or False,
        }, status=200)
        
    # ---------------------------------------------------------
    # Create Draft Quotation
    # ---------------------------------------------------------

    
    @http.route(
        '/api/n8n/v1/quotations',
        type='http',
        auth='bearer',
        methods=['POST'],
        csrf=False
    )
    def create_quotation(self, **kwargs):
        try:
            data = request.httprequest.get_json(silent=True) or {}

            partner_id = int(data.get('partner_id') or 0)
            lines = data.get('lines') or []
            delivery_address = (data.get('delivery_address') or '').strip()

            # Validate customer and order lines
            if not partner_id or not isinstance(lines, list) or not lines:
                return request.make_json_response({
                    'success': False,
                    'message': 'Customer ID and order lines are required.'
                }, status=400)

            # Find Customer
            partner = request.env['res.partner'].browse(
                partner_id
            ).exists()

            if not partner:
                return request.make_json_response({
                    'success': False,
                    'message': 'Customer not found.'
                }, status=404)

            # Get Customer Pricelist
            pricelist = partner.property_product_pricelist

            if not pricelist:
                return request.make_json_response({
                    'success': False,
                    'message': 'Customer pricelist not found.'
                }, status=400)

            order_lines = []
            line_details = []

            # Process Multiple Products
            for line in lines:
                product_id = int(line.get('product_id') or 0)
                quantity = float(line.get('quantity') or 0)

                if not product_id:
                    return request.make_json_response({
                        'success': False,
                        'message': 'Product ID is required.'
                    }, status=400)

                if quantity <= 0:
                    return request.make_json_response({
                        'success': False,
                        'message': 'Quantity must be greater than zero.'
                    }, status=400)

                product = request.env['product.product'].browse(
                    product_id
                ).exists()

                if not product or not product.sale_ok:
                    return request.make_json_response({
                        'success': False,
                        'message': 'Sellable product not found: %s' % product_id
                    }, status=404)

                # Let Odoo calculate the price from the pricelist
                order_lines.append((0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': quantity,
                }))

                line_details.append({
                    'product_id': product.id,
                    'product_name': product.display_name,
                    'quantity': quantity,
                })

            # Create ONE Draft Quotation with MULTIPLE lines
            quotation = request.env['sale.order'].create({
                'partner_id': partner.id,
                'pricelist_id': pricelist.id,
                'order_line': order_lines,
            })

            # Append delivery address without removing existing terms
            if delivery_address:
                quotation.note = (
                    (quotation.note or '') +
                    '<p><strong>Delivery Address:</strong> %s</p>'
                    % delivery_address
                )

            return request.make_json_response({
                'success': True,
                'created': True,
                'message': 'Draft quotation created successfully.',
                'data': {
                    'quotation_id': quotation.id,
                    'quotation_name': quotation.name,
                    'customer': partner.name,
                    'partner_id': partner.id,
                    'item_count': len(quotation.order_line),
                    'lines': line_details,
                    'total': quotation.amount_total,
                    'currency': quotation.currency_id.name,
                    'pricelist_id': pricelist.id,
                    'state': quotation.state,
                    'delivery_address': delivery_address,
                }
            }, status=201)

        except (ValueError, TypeError):
            return request.make_json_response({
                'success': False,
                'message': 'Invalid request parameters.'
            }, status=400)

        except Exception as e:
            return request.make_json_response({
                'success': False,
                'message': str(e)
            }, status=500)

     
    # ---------------------------------------------------------
    #  Confirm Quotation
    # ---------------------------------------------------------

    @http.route(
        '/api/n8n/v1/quotations/<int:quotation_id>/<string:action>',
        type='http',
        auth='bearer',
        methods=['POST'],
        csrf=False
    )
    def quotation_action(self, quotation_id, action, **kwargs):
        try:
            quotation = request.env['sale.order'].browse(
                quotation_id
            ).exists()

            if not quotation:
                return request.make_json_response({
                    'success': False,
                    'message': 'Quotation not found.'
                }, status=404)

            if quotation.state not in ('draft', 'sent'):
                return request.make_json_response({
                    'success': False,
                    'message': 'Quotation cannot be modified in its current state.',
                    'state': quotation.state,
                }, status=400)

            if action == 'confirm':

                quotation.action_confirm()

                return request.make_json_response({
                    'success': True,
                    'message': 'Quotation confirmed successfully.',
                    'data': {
                        'quotation_id': quotation.id,
                        'quotation_name': quotation.name,
                        'state': quotation.state,
                        'customer': quotation.partner_id.name,
                        'total': quotation.amount_total,
                        'currency': quotation.currency_id.name,
                    }
                }, status=200)

            elif action == 'cancel':

                quotation.action_cancel()

                return request.make_json_response({
                    'success': True,
                    'message': 'Quotation cancelled successfully.',
                    'data': {
                        'quotation_id': quotation.id,
                        'quotation_name': quotation.name,
                        'state': quotation.state,
                    }
                }, status=200)

            else:
                return request.make_json_response({
                    'success': False,
                    'message': 'Unsupported action: %s' % action,
                    'allowed_actions': ['confirm', 'cancel'],
                }, status=400)

        except Exception as e:
            return request.make_json_response({
                'success': False,
                'message': str(e)
            }, status=500)


    # ---------------------------------------------------------
    # Sales Order Details
    # ---------------------------------------------------------
    
    @http.route(
        '/api/n8n/v1/sales-orders/<int:order_id>',
        type='http',
        auth='bearer',
        methods=['GET'],
        csrf=False
    )
    def get_sales_order(self, order_id, **kwargs):
        try:
            # Find Sales Order / Quotation
            order = request.env['sale.order'].browse(
                order_id
            ).exists()

            if not order:
                return request.make_json_response({
                    'success': False,
                    'message': 'Sales Order not found.'
                }, status=404)

            # Get Order Lines
            order_lines = []

            for line in order.order_line:
                order_lines.append({
                    'product_id': line.product_id.id,
                    'product': line.product_id.display_name,
                    'quantity': line.product_uom_qty,
                    'delivered_quantity': line.qty_delivered,
                    'invoiced_quantity': line.qty_invoiced,
                    'unit_price': line.price_unit,
                    'subtotal': line.price_subtotal,
                    'tax': line.price_tax,
                    'total': line.price_total,
                })

            return request.make_json_response({
                'success': True,
                'data': {
                    'order_id': order.id,
                    'order_name': order.name,
                    'customer': order.partner_id.name,
                    'partner_id': order.partner_id.id,
                    'order_date': str(order.date_order),
                    'state': order.state,
                    'delivery_status': getattr(
                        order, 'delivery_status', False
                    ),
                    'invoice_status': order.invoice_status,
                    'currency': order.currency_id.name,
                    'amount_untaxed': order.amount_untaxed,
                    'amount_tax': order.amount_tax,
                    'amount_total': order.amount_total,
                    'order_lines': order_lines,
                }
            }, status=200)

        except Exception:
            return request.make_json_response({
                'success': False,
                'message': 'Unable to retrieve sales order.'
            }, status=500)

    # ---------------------------------------------------------
    # Telegram Customer Upsert
    # ---------------------------------------------------------

    @http.route(
        '/api/n8n/v1/customers/telegram/upsert',
        type='http',
        auth='bearer',
        methods=['POST'],
        csrf=False,
    )
    def telegram_customer_upsert(self, **kwargs):

        data = self._get_json_body()

        if data is None:
            return self._response({
                'success': False,
                'message': 'A valid JSON object is required.',
            }, status=400)

        name = (data.get('name') or '').strip()
        telegram_id = str(data.get('telegram_id') or '').strip()
        telegram_username = (
            data.get('telegram_username') or ''
        ).strip()
        email = (data.get('email') or '').strip().lower()
        phone = (data.get('phone') or '').strip()

        if not name or not telegram_id:
            return self._response({
                'success': False,
                'message': 'Name and Telegram ID are required.',
            }, status=400)

        try:
            Partner = request.env['res.partner'].sudo()

            # 1. Search by Telegram ID
            customer = Partner.search([
                ('n8n_telegram_id', '=', telegram_id),
            ], limit=1)

            if customer:
                return self._response({
                    'success': True,
                    'created': False,
                    'message': 'Customer already exists.',
                    'data': {
                        'partner_id': customer.id,
                        'name': customer.name,
                        'email': customer.email or '',
                        'telegram_id': customer.n8n_telegram_id,
                    },
                })

            # 2. Search by email if available
            if email:
                customer = Partner.search([
                    ('email', '=ilike', email),
                ], limit=1)

                if customer:
                    if customer.n8n_telegram_id:
                        return self._response({
                            'success': False,
                            'message': 'Email is already linked to another Telegram account.',
                        }, status=409)

                    # Link existing customer to Telegram
                    customer.write({
                        'n8n_telegram_id': telegram_id,
                        'n8n_telegram_username': telegram_username,
                    })

                    return self._response({
                        'success': True,
                        'created': False,
                        'linked': True,
                        'message': 'Existing customer linked to Telegram.',
                        'data': {
                            'partner_id': customer.id,
                            'name': customer.name,
                            'email': customer.email or '',
                            'telegram_id': telegram_id,
                        },
                    })

            # 3. Create new customer
            customer = Partner.create({
                'name': name,
                'email': email or False,
                'phone': phone or False,
                'n8n_telegram_id': telegram_id,
                'n8n_telegram_username': telegram_username,
                'customer_rank': 1,
            })

            return self._response({
                'success': True,
                'created': True,
                'message': 'Customer created successfully.',
                'data': {
                    'partner_id': customer.id,
                    'name': customer.name,
                    'email': customer.email or '',
                    'telegram_id': customer.n8n_telegram_id,
                },
            }, status=201)

        except ValidationError as error:
            return self._response({
                'success': False,
                'message': str(error),
            }, status=400)
            
    # ---------------------------------------------------------
    # Search Products
    # ---------------------------------------------------------
    
    @http.route(
        '/api/n8n/v1/search_products',
        type='http',
        auth='bearer',
        methods=['GET'],
        csrf=False
    )
    def get_products(self, **kwargs):
        try:
            limit = min(max(int(request.params.get('limit', 20)), 1), 100)
            offset = max(int(request.params.get('offset', 0)), 0)

            Product = request.env['product.template']

            domain = [
                ('active', '=', True),
                ('sale_ok', '=', True),
            ]

            products = Product.search_read(
                domain,
                fields=[
                    'name',
                    'default_code',
                    'list_price',
                    'qty_available',
                    'uom_id',
                ],
                limit=limit,
                offset=offset,
                order='name asc'
            )

            data = []

            for product in products:
                data.append({
                    'id': product['id'],
                    'name': product['name'],
                    'default_code': product['default_code'] or '',
                    'price': product['list_price'],
                    'stock': product['qty_available'],
                    'uom': product['uom_id'][1]
                        if product['uom_id'] else '',
                    'currency': request.env.company.currency_id.name,
                })

            return self._response({
                'success': True,
                'count': len(data),
                'limit': limit,
                'offset': offset,
                'data': data,
            })

        except (ValueError, TypeError):
            return self._response({
                'success': False,
                'message': 'Invalid limit or offset'
            }, status=400)

    # ---------------------------------------------------------
    #  Download Quotation PDF
    # ---------------------------------------------------------
    
    @http.route(
        '/api/n8n/v1/quotations/<int:quotation_id>/pdf',
        type='http',
        auth='bearer',
        methods=['GET'],
        csrf=False
    )
    def download_quotation_pdf(self, quotation_id, **kwargs):
        try:
            quotation = request.env['sale.order'].browse(
                quotation_id
            ).exists()

            if not quotation:
                return request.make_json_response({
                    'success': False,
                    'message': 'Quotation not found.'
                }, status=404)

            if quotation.state not in ('draft', 'sent'):
                return request.make_json_response({
                    'success': False,
                    'message': 'Quotation is not in draft or sent state.'
                }, status=400)

            report = request.env.ref(
                'sale.action_report_saleorder'
            )

            pdf_content, content_type = report._render_qweb_pdf(
                report,
                res_ids=quotation.ids
            )

            filename = '%s.pdf' % quotation.name.replace('/', '_')

            return request.make_response(
                pdf_content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Length', str(len(pdf_content))),
                    (
                        'Content-Disposition',
                        'attachment; filename="%s"' % filename
                    ),
                ]
            )

        except AccessError:
            return request.make_json_response({
                'success': False,
                'message': 'Access denied.'
            }, status=403)

        except Exception:
            _logger.exception('Quotation PDF generation failed')

            return request.make_json_response({
                'success': False,
                'message': 'Unable to generate quotation PDF.'
            }, status=500)
