# -*- coding: utf-8 -*-
# from odoo import http


# class EmployeeManager(http.Controller):
#     @http.route('/employee_manager/employee_manager/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/employee_manager/employee_manager/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('employee_manager.listing', {
#             'root': '/employee_manager/employee_manager',
#             'objects': http.request.env['employee_manager.employee_manager'].search([]),
#         })

#     @http.route('/employee_manager/employee_manager/objects/<model("employee_manager.employee_manager"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('employee_manager.object', {
#             'object': obj
#         })
