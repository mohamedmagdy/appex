# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID
from odoo.http import request, Controller, route, Response
import erppeek
import random
import time

class AppexInstancesManagement(Controller):

    def _check_token(self, token=None):
        user_token = request.env['res.users'].with_user(SUPERUSER_ID).search([('access_token', '=', token)],
                                                                             limit=1)
        return user_token or False

    def create_partner(self,user, partner_name, country_id):
        created_partner = request.env['res.partner'].with_user(user).create({'name':partner_name, 'country_id': country_id})
        return created_partner

    # def create_user(self, instance_url, db_name, count):
    #     time.sleep(40)
    #     created_user = []
    #     client = erppeek.Client(server=instance_url)
    #     client.login('admin', 'admin', db_name)
    #     for user_count in range(1, count+1):
    #         password = random.randint(9999, 99999)
    #         username = 'user%s' % user_count
    #         name = 'USER %s' % user_count
    #         client.create('res.users', {'login': username, 'password': password, 'name': name})
    #         created_user.append({"username": username, "password": password})
    #     return created_user
    #
    # def create_api_user(self, instance_url, db_name):
    #     time.sleep(20)
    #     client = erppeek.Client(server=instance_url)
    #     client.login('admin', 'admin', db_name)
    #     api_password = random.randint(9999, 99999)
    #     client.create('res.users', {'login': "api_user", 'password': api_password, 'name': "API User"})
    #     return {"name": "API User", "login": "api_user", "password": api_password}


    @route('/api/countries', type='json', auth='public', methods=['POST'], sitemap=False, csrf=False)
    def get_countries(self, **kw):
        return request.env['res.country'].with_user(SUPERUSER_ID).search_read(domain=[], fields={'id', 'name', 'code'})

    @route('/api/print_request', type='json', auth='public', methods=['POST'], sitemap=False, csrf=False)
    def get_request(self, **kw):
        print(kw)
        return {}

    @route('/api/instance/create', type='json', auth='public', methods=['POST'], sitemap=False, csrf=False)
    def create_instance(self, **kw):
        access_token = request.httprequest.headers['Authorization']
        user = self._check_token(token=access_token)

        if not user:
            response = {"code": 200, 'message': "No valid token provided"}
            Response.status = "200"
            return response

        company_name = kw.get('company_name')
        country_obj = request.env['res.country'].search([('code', '=', kw.get('country_code'))], limit=1)
        if country_obj:
            partner_obj = self.create_partner(user, company_name, country_obj.id)
        else:
            response = {"code": 400, 'message': "No valid country code!"}
            Response.status = "400"
            return response

        instance_obj = request.env['odoo.instances.management'].with_user(user).create({'partner_id': partner_obj.id,
                                                                                        'country_id': country_obj.id,
                                                                                        'creation_mode': 'api', 'users_count': kw.get('users_count')})
        # instance_obj.create_odoo_instance()
        # time.sleep(50)
        if instance_obj:
        #     created_users = self.create_user(instance_obj.instance_url, instance_obj.db_name, kw.get('users_count'))
        #     created_api_user = self.create_api_user(instance_obj.instance_url, instance_obj.db_name)
        #     response = {"code": 200, "message": "Instance: %s Created successfully!" % instance_obj.name, "data": {"id": instance_obj.id, "instance_id": instance_obj.name, "url": instance_obj.instance_url, "users": created_users, "api_user": created_api_user}}
            response = {"code": 200, "message": "Instance: %s Created successfully!" % instance_obj.name, "data": {"id": instance_obj.id, "instance_name": instance_obj.name, "instance_id": instance_obj.instance_token}}
            Response.status = "200"
            return response

    @route('/api/instance/stop', type='json', auth='public', methods=['POST'], sitemap=False, csrf=False)
    def stop_instance(self, **kw):
        instance_obj = request.env['odoo.instances.management'].with_user(SUPERUSER_ID).search([('instance_token', '=', kw.get('instance_id'))])
        if instance_obj:
            instance_obj.pause_odoo_instance()
            response = {"code": 200, "message": "Instance: %s Stopped successfully!" % instance_obj.name}
            Response.status = "200"
            return response
        else:
            response = {"code": 400, "message": "Instance was not found!"}
            Response.status = "400"
            return response

    @route('/api/instance/start', type='json', auth='public', methods=['POST'], sitemap=False, csrf=False)
    def start_instance(self, **kw):
        instance_obj = request.env['odoo.instances.management'].with_user(SUPERUSER_ID).search(
            [('instance_token', '=', kw.get('instance_id'))])
        if instance_obj:
            instance_obj.run_odoo_instance()
            response = {"code": 200, "message": "Instance: %s Started successfully!" % instance_obj.name}
            Response.status = "200"
            return response
        else:
            response = {"code": 400, "message": "Instance was not found!"}
            Response.status = "400"
            return response

    @route('/api/instance/delete', type='json', auth='public', methods=['POST'], sitemap=False, csrf=False)
    def delete_instance(self, **kw):
        instance_obj = request.env['odoo.instances.management'].with_user(SUPERUSER_ID).search(
            [('instance_token', '=', kw.get('instance_id'))])
        if instance_obj:
            instance_obj.delete_odoo_instance()
            response = {"code": 200, "message": "Instance: %s Deleted successfully!" % instance_obj.name}
            Response.status = "200"
            return response
        else:
            response = {"code": 400, "message": "Instance was not found!"}
            Response.status = "400"
            return response