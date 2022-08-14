# -*- coding: utf-8 -*-
import random

from odoo import models, fields, api
import subprocess
import erppeek
import string
import re
import time


class Users(models.Model):
    _name = 'res.users'
    _inherit = 'res.users'

    # reset_password_code = fields.Char(string="Reset Password Code", )
    access_token = fields.Char(string="Access Token")

    def generate_access_token(self):
        self.access_token = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=16))
        if not bool(re.search(r'\d', self.access_token)):
            self.generate_access_token()


class Country(models.Model):
    _name = 'res.country'
    _inherit = 'res.country'

    module_ids = fields.Many2many(comodel_name="ir.module.module", relation="country_module_rel", column1="country_id", column2="module_id", string="Modules", domain=[('license', '!=', 'OEEL-1')], help="Only Community and 3rd party modules are listed. Enterprise are not listed!")


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
    master_password = fields.Char(string="Master Password", required=False, )

    def generate_master_password(self):
        self.master_password = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=16))
        if not bool(re.search(r'\d', self.master_password)):
            self.generate_master_password()

    #TODO: Change the path for the server
    def create_odoo_instance(self,path='/home/moh/tmpfolder',version=15):
        name = self.partner_id.name.lower().replace(" ", "_")
        unique_port = True
        while unique_port:
            port = random.randint(8000, 9001)
            unique_port = self.search([('port', '=', port)])
        try:
            subprocess.run(['docker', 'create', '-e','POSTGRES_USER=odoo','-e','POSTGRES_PASSWORD=odoo','-e','POSTGRES_DB=postgres',f'--name',f'{name}db','postgres:13'])
            subprocess.run(['docker', 'create','-v',f'{path}:/mnt/extra-addons','-p',f'{port}:8069','--name',f'{name}','--link',f'{name}db:db','-t',f'odoo:{version}'])
            self.port = port
            base_url =self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if base_url.count(':') == 2:
                base_url = base_url[:-5]
            self.instance_url = '%s:%s' %(base_url, port)
            self.db_name = self.name
            self.master_password = self.generate_master_password()
            first_run = self.with_context(first_run=True).run_odoo_instance()
            time.sleep(20)
            if first_run:
                client = erppeek.Client(server=self.instance_url)
                client.create_database('admin', self.db_name)
                client.install('base')
                # Install country-related modules
                for module in self.country_id.module_ids:
                    client.install(module.name)

        except Exception as e:
            print(e)
            pass
        #FIXME: if created successfully run to create DB and install default configuration per country. Then, stop using pause_odoo_instance()

    def run_odoo_instance(self):
        name = self.partner_id.name.lower().replace(" ", "_")
        subprocess.Popen(['docker', 'start', f'{name}db'])
        subprocess.Popen(['docker', 'start', f'{name}'])
        self.state = 'running'
        if self._context.get('first_run'):
            return True

    def pause_odoo_instance(self):
        name = self.partner_id.name.lower().replace(" ", "_")
        subprocess.Popen(['docker', 'stop', f'{name}'])
        subprocess.Popen(['docker', 'stop', f'{name}db'])
        self.state = 'paused'

    def restart_odoo_instance(self):
        name = self.partner_id.name.lower().replace(" ", "_")
        subprocess.Popen(['docker', 'restart', f'{name}'])
        subprocess.Popen(['docker', 'restart', f'{name}db'])
        self.state = 'running'

    def delete_odoo_instance(self):
        self.pause_odoo_instance()
        name = self.partner_id.name.lower().replace(" ", "_")
        subprocess.Popen(['docker', 'rm', f'{name}'])
        subprocess.Popen(['docker', 'rm', f'{name}db'])
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
