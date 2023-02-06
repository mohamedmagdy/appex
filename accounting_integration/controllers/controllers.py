# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, Response
from odoo import SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


class AccountingIntegration(http.Controller):
    def _check_token(self, token=None):
        user_token = request.env['res.users'].with_user(SUPERUSER_ID).search([('access_token', '=', token)],
                                                                             limit=1)
        return user_token or False

    def create_partner(self,user, partner_name):
        created_partner = request.env['res.partner'].with_user(user).create({'name':partner_name})
        return created_partner

    @http.route('/create/invoice', auth='public', type='json', methods=['POST'])
    def create_appex_invoice(self, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {"code": 401, 'message': "No valid token provided"}
            Response.status = "401"
            return response


        # {
        #     "currency": "USD",
        # }
        partner_env = request.env['res.partner'].with_user(SUPERUSER_ID)
        currency_env = request.env['res.currency'].with_user(SUPERUSER_ID)
        partner_obj = partner_env.search([('name', '=', kw.get('clientname'))], limit=1)
        currency_obj = currency_env.search([('name', '=', kw.get('currency'))], limit=1)
        if partner_obj:
            partner_id = partner_obj.id
        else:
            partner_id = partner_env.create({'name': kw.get('clientname'), })
        env_config_parameter = request.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        product = env_config_parameter.get_param('accounting_integration.invoice_product_id')
        try:
            invoice = request.env['account.move'].with_user(user).create({
                'partner_id': partner_id,
                'appex_id': kw.get('invoiceid'),
                'move_type': 'out_invoice',
                'invoice_user_id': user.id,
                'currency_id': currency_obj and currency_obj.id,
                'invoice_payment_term_id': request.env.ref('account.account_payment_term_immediate').id,
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': int(product),
                        'currency_id': currency_obj and currency_obj.id,
                        'account_id': product.categ_id.property_account_income_categ_id.id,
                        'quantity': 1,
                        'price_unit': kw.get('amount'),
                        'name': kw.get('description'),
                    }),
                ]
            })
            if invoice:
                response = {"code": 200, "message": "Invoice: %s Created successfully!" % invoice.id, "odoo_invoice_id": invoice.id}
                Response.status = "200"
                return response
        except Exception as e:
            _logger.error(e)
            response = {"code": 400, "message": "An Error Prevents Invoice Creation"}
            Response.status = "400"
            return response
