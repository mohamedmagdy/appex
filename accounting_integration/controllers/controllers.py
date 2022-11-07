# -*- coding: utf-8 -*-
# from odoo import http


# class AccountingIntegration(http.Controller):
#     @http.route('/accounting_integration/accounting_integration/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/accounting_integration/accounting_integration/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('accounting_integration.listing', {
#             'root': '/accounting_integration/accounting_integration',
#             'objects': http.request.env['accounting_integration.accounting_integration'].search([]),
#         })

#     @http.route('/accounting_integration/accounting_integration/objects/<model("accounting_integration.accounting_integration"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('accounting_integration.object', {
#             'object': obj
#         })
