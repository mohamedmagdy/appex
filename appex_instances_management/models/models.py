# -*- coding: utf-8 -*-
import random

from odoo import models, fields, api, SUPERUSER_ID
import subprocess
import erppeek
import string
import re
import time
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class Users(models.Model):
    _name = 'res.users'
    _inherit = 'res.users'

    # reset_password_code = fields.Char(string="Reset Password Code", )
    access_token = fields.Char(string="Access Token")

    def generate_access_token(self):
        self.access_token = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=16))
        if not bool(re.search(r'\d', self.access_token)):
            self.generate_access_token()


# class Company(models.Model):
#     _name = 'res.company'
#     _inherit = 'res.company'
#
#     appex_response_url = fields.Char(string="Appex Portal Response URL", required=False, )


class Country(models.Model):
    _name = 'res.country'
    _inherit = 'res.country'

    module_ids = fields.Many2many(comodel_name="ir.module.module", relation="country_module_rel", column1="country_id", column2="module_id", string="Modules", domain=[('license', '!=', 'OEEL-1')], help="Only Community and 3rd party modules are listed. Enterprise are not listed!")


class OdooInstanceUsers(models.Model):
    _name = 'odoo.instance.users'
    _rec_name = 'name'
    _description = 'Odoo Instance Users'

    name = fields.Char(string="User Name", required=False, )
    login = fields.Char(string="Login", )
    password = fields.Char(string="Password")
    type = fields.Selection(string="Type", selection=[('admin', 'Administrator'), ('manager', 'Manager'), ('client', 'Client'), ('accountant', 'Accountant')], default='accountant', )
    instance_id = fields.Many2one(comodel_name="odoo.instances.management", string="Instance", required=True, )


class OdooInstancesManagement(models.Model):
    _name = 'odoo.instances.management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'id DESC'
    _description = 'Odoo Instances Management'

    name = fields.Char(string="Instance ID", required=True, default="New")
    active = fields.Boolean(default=True)
    creation_date = fields.Datetime(string="Creation Date", required=True, default=fields.Datetime.now)
    state = fields.Selection(string="State", selection=[('draft', 'New'), ('running', 'Running'), ('paused', 'Paused'), ('deleted', 'Deleted')], required=True, default='draft', tracking=True)
    port = fields.Integer(string="Port", required=False, )
    partner_id = fields.Many2one(comodel_name="res.partner", string="Client", required=True, tracking=True)
    country_id = fields.Many2one(comodel_name="res.country", string="Country", required=True, )
    instance_token = fields.Char(string="Instance Token", required=False, )
    instance_url = fields.Char(string="Instance URL", required=False, )
    db_name = fields.Char(string="DB Name", required=False, )
    creation_mode = fields.Selection(string="Creation Mode", selection=[('manual', 'Manual'), ('api', 'By API'), ], default='manual', help="Creation Mode tells how this instance was created:\n\t- API: It tells that it was created by APIs and that the instance details will be pushed to the Appex Portal.\n\t- Manual: It tells that the instance was created normally from this form view and Appex Portal will not include its data.")
    users_count = fields.Integer(string="Users Count", required=False, default=0)
    is_pushed_appex_portal = fields.Boolean(string="Is Pushed to Appex Portal", )
    user_admin_pass = fields.Char(string="Administrator Password", required=False, )
    user_ids = fields.One2many(comodel_name="odoo.instance.users", inverse_name="instance_id", string="Instance Users", required=False, )

    def get_access_parameters(self):
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        odoo_instances_address = env_config_parameter.get_param('appex_instances_management.odoo_instances_address')
        username = env_config_parameter.get_param('appex_instances_management.username')

        return username, odoo_instances_address

    def create_user(self, instance_url, db_name, count):
        time.sleep(40)
        created_user = []
        client = erppeek.Client(server='http://%s' % self.instance_url)
        client.login('admin', self.user_admin_pass, db_name)

        # Create a client account
        password = random.randint(9999, 99999)
        username = 'client'
        name = 'Client'
        client.create('res.users', {'login': username, 'password': password, 'name': name})
        created_user.append({"name": name, "login": username, "password": password, 'type': 'client'})

        # Create a manager account
        password = random.randint(9999, 99999)
        username = 'manager'
        name = 'Manager'
        client.create('res.users', {'login': username, 'password': password, 'name': name})
        created_user.append({"name": name, "login": username, "password": password, 'type': 'manager'})

        # Create Accountant Users using the number of users requested
        for user_count in range(1, count+1):
            password = random.randint(9999, 99999)
            username = 'accountant%s' % user_count
            name = 'Accountant %s' % user_count
            client.create('res.users', {'login': username, 'password': password, 'name': name})
            created_user.append({"name": name, "login": username, "password": password, 'type': 'accountant'})

        self.write({'user_ids': [(0, 0, user_vals) for user_vals in created_user]})
        # By default, Administrator is created already. It should be added to the returned created_user
        created_user.append({'name': 'Administrator', 'login': 'admin', 'password': self.user_admin_pass, 'type': 'admin'})
        return created_user

    # def create_api_user(self, instance_url, db_name):
    #     time.sleep(20)
    #     client = erppeek.Client(server=instance_url)
    #     client.login('admin', 'admin', db_name)
    #     api_password = random.randint(9999, 99999)
    #     client.create('res.users', {'login': "api_user", 'password': api_password, 'name': "API User"})
    #     return {"name": "API User", "login": "api_user", "password": api_password, 'type': 'api'}

    #TODO: Change the path for the server
    def create_odoo_instance_by_api(self, path='/home/moh/tmpfolder', version=14):
        self.create_odoo_instance(path, version)
        created_users = self.create_user(self.instance_url, self.db_name, self.users_count)
        # created_api_user = self.create_api_user(self.instance_url, self.db_name)
        self.push_to_appex_portal(created_users)

    def push_to_appex_portal(self, created_users=None):
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        appex_response_api = env_config_parameter.get_param('appex_instances_management.appex_response_url')
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        appex_payment_token = env_config_parameter.get_param('appex_instances_management.appex_payment_token')
        if not created_users:
            created_users = self.user_ids.search_read([('instance_id', '=', self.id)], ['name', 'login', 'password', 'type'])
        if created_users and appex_response_api:
            request_data = {"message": "Instance: %s Created successfully!" % self.name,
                            "data": {"id": self.id, "instance_id": self.instance_token, "url": self.instance_url,
                                     "users": created_users}}
            _logger.info(appex_response_api)
            _logger.info(request_data)
            request_push_instance_data = requests.request("POST", appex_response_api, headers={"Authorization": appex_payment_token,"content-type": "application/json"},
                                                       data=json.dumps(request_data))
            _logger.info(request_push_instance_data)
            _logger.info(request_push_instance_data.status_code)
            _logger.info(request_push_instance_data.content)
            if request_push_instance_data.status_code == 200:
                self.is_pushed_appex_portal = True

    #TODO: Change the path for the server
    def create_odoo_instance(self,path='/home/moh/tmpfolder', version=14):
        name = self.instance_token
        unique_port = True
        while unique_port:
            port = random.randint(2000, 5999)
            unique_port = self.search([('port', '=', port)])
        try:
            username, address = self.get_access_parameters()
            subprocess.run(['ssh', '%s@%s' % (username, address), 'docker', 'create', '-e','POSTGRES_USER=odoo','-e','POSTGRES_PASSWORD=odoo','-e','POSTGRES_DB=postgres',f'--name',f'{name}db','postgres:13'])
            subprocess.run(['ssh', '%s@%s' % (username, address), 'docker', 'create', '-v', f'{path}:/mnt/extra-addons', '-p',f'{port}:8069','--name',f'{name}','--link',f'{name}db:db','-t',f'odoo:{version}'])
            self.port = port
            url = self.env['ir.config_parameter'].get_param('appex_instances_management.odoo_instances_address')
            base_url = url.startswith('http') and url.split('/')[-1] or url
            self.instance_url = '%s:%s' % (base_url, port)
            self.db_name = self.instance_token
            first_run = self.with_context(first_run=True).run_odoo_instance()
            self.env.cr.commit()
            time.sleep(20)
            if first_run:
                client = erppeek.Client(server='http://%s' % self.instance_url)
                user_admin_pass = str(random.randint(1000, 9999))
                client.create_database(passwd='admin', database=self.db_name, user_password=user_admin_pass, login="admin", country_code=self.country_id.code)
                self.write({'user_admin_pass': user_admin_pass, 'user_ids': [(0, 0, {'name': 'Administrator', 'login': 'admin', 'password': user_admin_pass, 'type': 'admin'})]})
                client.install('base')
                # Install country-related modules
                for module in self.country_id.module_ids:
                    client.install(module.name)

        except Exception as e:
            #FIXME: Handle exceptions and show in the log
            # print(e)
            pass

    def run_odoo_instance(self):
        name = self.instance_token
        username, address = self.get_access_parameters()
        subprocess.Popen(['ssh', '%s@%s' % (username, address), 'docker', 'start', f'{name}db'])
        subprocess.Popen(['ssh', '%s@%s' % (username, address), 'docker', 'start', f'{name}'])
        self.state = 'running'
        if self._context.get('first_run'):
            return True

    def pause_odoo_instance(self):
        name = self.instance_token
        username, address = self.get_access_parameters()
        subprocess.Popen(['ssh', '%s@%s' % (username, address), 'docker', 'stop', f'{name}'])
        subprocess.Popen(['ssh', '%s@%s' % (username, address), 'docker', 'stop', f'{name}db'])
        self.state = 'paused'

    def restart_odoo_instance(self):
        name = self.instance_token
        username, address = self.get_access_parameters()
        subprocess.Popen(['ssh', '%s@%s' % (username, address), 'docker', 'restart', f'{name}'])
        subprocess.Popen(['ssh', '%s@%s' % (username, address), 'docker', 'restart', f'{name}db'])
        self.state = 'running'

    def delete_odoo_instance(self):
        self.pause_odoo_instance()
        # TODO: Perform long-term backup before proceeding with deleting procedures
        name = self.instance_token
        username, address = self.get_access_parameters()
        subprocess.Popen(['ssh', '%s@%s' % (username, address), 'docker', 'rm', f'{name}'])
        subprocess.Popen(['ssh', '%s@%s' % (username, address), 'docker', 'rm', f'{name}db'])
        self.state = 'deleted'

    def generate_instance_token(self):
        self.instance_token = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=16))
        if not bool(re.search(r'\d', self.instance_token)):
            self.generate_instance_token()

    @api.model
    def create(self, values):
        new_seq = self.env['ir.sequence'].next_by_code('odoo.instance.seq')
        values.update({"name": new_seq})
        res = super(OdooInstancesManagement, self).create(values)
        res.generate_instance_token()
        return res
