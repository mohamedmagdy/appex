# -*- coding: utf-8 -*-
import random

from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.exceptions import ValidationError
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

    access_token = fields.Char(string="Access Token")

    def generate_access_token(self):
        self.access_token = ''.join(
            random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=16))
        if not bool(re.search(r'\d', self.access_token)):
            self.generate_access_token()


class Country(models.Model):
    _name = 'res.country'
    _inherit = 'res.country'

    module_ids = fields.Many2many(comodel_name="ir.module.module", relation="country_module_rel", column1="country_id",
                                  column2="module_id", string="Modules", domain=[('license', '!=', 'OEEL-1')],
                                  help="Only Community and 3rd party modules are listed. Enterprise are not listed!")


class OdooInstanceUsers(models.Model):
    _name = 'odoo.instance.users'
    _rec_name = 'name'
    _description = 'Odoo Instance Users'

    name = fields.Char(string="User Name", required=False, )
    login = fields.Char(string="Login", )
    password = fields.Char(string="Password")
    type = fields.Selection(string="Type",
                            selection=[('admin', 'Administrator'), ('manager', 'Manager'), ('client', 'Client'),
                                       ('accountant', 'Accountant')], default='accountant', )
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
    state = fields.Selection(string="State", selection=[('draft', 'New'), ('running', 'Running'), ('paused', 'Paused'),
                                                        ('deleted', 'Deleted')], required=True, default='draft',
                             tracking=True)
    port = fields.Integer(string="Port", required=False, )
    partner_id = fields.Many2one(comodel_name="res.partner", string="Client", required=True, tracking=True)
    country_id = fields.Many2one(comodel_name="res.country", string="Country", required=True, )
    instance_token = fields.Char(string="Instance Token", required=False, )
    instance_url = fields.Char(string="Instance URL", required=False, )
    instance_subdomain = fields.Char(string="Instance Domain", required=False, )
    subdomain = fields.Char(string="Subdomain", required=False, )
    db_name = fields.Char(string="DB Name", required=False, )
    creation_mode = fields.Selection(string="Creation Mode", selection=[('manual', 'Manual'), ('api', 'By API'), ],
                                     default='manual',
                                     help="Creation Mode tells how this instance was created:\n\t- API: It tells that it was created by APIs and that the instance details will be pushed to the Appex Portal.\n\t- Manual: It tells that the instance was created normally from this form view and Appex Portal will not include its data.")
    users_count = fields.Integer(string="Users Count", required=False, default=0)
    is_pushed_appex_portal = fields.Boolean(string="Is Pushed to Appex Portal", )
    user_admin_pass = fields.Char(string="Administrator Password", required=False, )
    user_ids = fields.One2many(comodel_name="odoo.instance.users", inverse_name="instance_id", string="Instance Users",
                               required=False, )

    def get_access_parameters(self):
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        odoo_instances_address = env_config_parameter.get_param('appex_instances_management.odoo_instances_address')
        username = env_config_parameter.get_param('appex_instances_management.username')

        return username, odoo_instances_address

    def create_user(self):
        time.sleep(40)
        created_user = []
        client = erppeek.Client(server='http://%s' % self.instance_url)
        client.login('admin', self.user_admin_pass, self.db_name)

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
        if not self.users_count:
            count = 0
        else:
            count = self.users_count
        for user_count in range(1, count + 1):
            password = random.randint(9999, 99999)
            username = 'accountant%s' % user_count
            name = 'Accountant %s' % user_count
            client.create('res.users', {'login': username, 'password': password, 'name': name})
            created_user.append({"name": name, "login": username, "password": password, 'type': 'accountant'})

        self.write({'user_ids': [(0, 0, user_vals) for user_vals in created_user]})
        # By default, Administrator is created already. It should be added to the returned created_user
        created_user.append(
            {'name': 'Administrator', 'login': 'admin', 'password': self.user_admin_pass, 'type': 'admin'})
        return created_user

    # TODO: Change the path for the server
    def create_odoo_instance_by_api(self, path='/home/moh/tmpfolder', version=14):
        self.create_odoo_instance(path, version)
        created_users = self.create_user()
        # created_api_user = self.create_api_user(self.instance_url, self.db_name)
        self.push_to_appex_portal(created_users)

    def push_to_appex_portal(self, created_users=None):
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        appex_response_api = env_config_parameter.get_param('appex_instances_management.appex_response_url')
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        appex_payment_token = env_config_parameter.get_param('appex_instances_management.appex_payment_token')
        if not created_users:
            created_users = self.user_ids.search_read([('instance_id', '=', self.id)],
                                                      ['name', 'login', 'password', 'type'])
        if created_users and appex_response_api:
            request_data = {"message": "Instance: %s Created successfully!" % self.name,
                            "data": {"id": self.id, "instance_id": self.instance_token, "url": f"https://{self.instance_subdomain}",
                                     "users": created_users}}
            _logger.info(appex_response_api)
            _logger.info(request_data)
            request_push_instance_data = requests.request("POST", appex_response_api,
                                                          headers={"Authorization": appex_payment_token,
                                                                   "content-type": "application/json"},
                                                          data=json.dumps(request_data))
            _logger.info(request_push_instance_data)
            _logger.info(request_push_instance_data.status_code)
            _logger.info(request_push_instance_data.content)
            if request_push_instance_data.status_code == 200:
                self.is_pushed_appex_portal = True

    def _get_subdomain(self, url):
        # Get the first name of the partner_id
        try:
            company_name = self.partner_id.name.replace(' ', '-').lower()
            instance_no = self.name.split('e')[1]
            subdomain = '%s-%s' % (company_name, instance_no)

            headers = {
                'accept': 'application/json',
                'Authorization': 'sso-key fXfiRRA4P43R_4sBj4bhjt3ngU8yD7iCyXS:K748qPEpTzgGd8FdMdc7mn',
            }
            payload = {}

            # Create a subdomain in goddady
            godaddy_api_url = 'https://api.godaddy.com/v1/domains/appexexperts.com/records'
            godaddy_check_subdomain = '%s/A/%s' % (godaddy_api_url, subdomain)
            subdomain_exist = requests.request("GET", godaddy_check_subdomain, headers=headers, data=payload)

            if json.loads(subdomain_exist.content):
                _logger.error('Subdomain already exists in GoDaddy. Please try again!')

            _logger.info("Create a new subdomain in GoDaddy")
            headers['Content-Type'] = 'application/json'
            # FIXME: Change the IP address to the server IP address
            payload = [{"data": url,"name": subdomain,"ttl": 3600,"type": "A"}]
            new_subdomain_request = requests.request("PATCH", godaddy_api_url, headers=headers, json=payload)
            _logger.info("New Subdomain Request: %s" % new_subdomain_request.content)
            if new_subdomain_request.status_code == 200:
                self.subdomain = subdomain
                instance_subdomain = "%s.appexexperts.com" % subdomain
                _logger.info("Instance Subdomain: %s" % instance_subdomain)
                return instance_subdomain
            else:
                raise _logger.error(_('Error while creating subdomain in GoDaddy. Please try again!'))
        except Exception as e:
            _logger.error(e)

    def create_odoo_instance(self, path='/home/moh/tmpfolder', version=14):
        name = self.instance_token
        unique_port = True
        while unique_port:
            port = random.randint(2000, 5999)
            unique_port = self.search([('port', '=', port)])
        try:
            username, address = self.get_access_parameters()
            # Create a separate PostgreSQL container for each Odoo instance
            subprocess.run(['ssh', '%s@%s' % (username, address), 'docker', 'service', 'create', '--name', f'{name}db',
                            '--replicas', '1', '-e', 'POSTGRES_USER=odoo', '-e', 'POSTGRES_PASSWORD=odoo', '-e',
                            'POSTGRES_DB=postgres', '--mount', 'type=volume,destination=/var/lib/postgresql/data',
                            '--network', 'my-network', 'postgres:13'])
            # Create the Odoo instance
            subprocess.run(
                ['ssh', '%s@%s' % (username, address), 'docker', 'service', 'create', '--name', f'{name}', '--replicas',
                 '1', '--publish', f'{port}:8069', '--mount', 'type=volume,destination=/var/lib/odoo', '--mount',
                 'type=volume,destination=/mnt/extra-addons', '--network', 'my-network', '-e', f'HOST={name}db',
                 'odoo:%s' % version, '-i', 'base'])
            self.port = port
            url = self.env['ir.config_parameter'].get_param('appex_instances_management.odoo_instances_address')
            base_url = url.startswith('http') and url.split('/')[-1] or url
            self.instance_url = '%s:%s' % (base_url, port)
            self.instance_subdomain = self._get_subdomain(url)
            _logger.info("Creating Nginx configuration")
            if self.instance_subdomain:
                nginx_conf = f"""server {{
 listen 80;
 listen [::]:80;
 server_name *.appexexperts.com;
 return 301 https://\$host\$request_uri;
}}

server {{
 listen 80;
 listen [::]:80;
 server_name appexexperts.com;
 return 301 https://{self.subdomain}.\$host\$request_uri;
}}

server {{
    server_name {self.subdomain}.appexexperts.com;
    return 301 https://{self.subdomain}.appexexperts.com\$request_uri;
}}

server {{
   listen 443 ssl http2;
   server_name {self.subdomain}.appexexperts.com;

   ssl_certificate /etc/ssl/appex/bundle.crt;
   ssl_certificate_key /etc/ssl/appex/appex.key;
   ssl_session_timeout 1d;
   ssl_session_cache shared:SSL:10m;
   ssl_session_tickets off;

   #ssl_dhparam /path/to/dhparam.pem;

   ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
   ssl_ciphers \'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA:ECDHE-RSA-AES256-SHA:DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA:DHE-RSA-AES256-SHA256:DHE-RSA-AES256-SHA:ECDHE-ECDSA-DES-CBC3-SHA:ECDHE-RSA-DES-CBC3-SHA:EDH-RSA-DES-CBC3-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA256:AES256-SHA256:AES128-SHA:AES256-SHA:DES-CBC3-SHA:!DSS\';
   ssl_prefer_server_ciphers on;

   add_header Strict-Transport-Security max-age=15768000;

   ssl_stapling on;
   ssl_stapling_verify on;
   ssl_trusted_certificate /etc/ssl/appex/bundle.crt;
   resolver 8.8.8.8 8.8.4.4;

   access_log /var/log/nginx/odoo.access.log;
   error_log /var/log/nginx/odoo.error.log;

   proxy_read_timeout 720s;
   proxy_connect_timeout 720s;
   proxy_send_timeout 720s;
   proxy_set_header X-Forwarded-Host \$host;
   proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
   proxy_set_header X-Forwarded-Proto \$scheme;
   proxy_set_header X-Real-IP \$remote_addr;

   location / {{
     proxy_pass    http://127.0.0.1:{self.port};
        proxy_redirect http://127.0.0.1:{self.port}/ \$scheme://\$host/;
        proxy_cookie_domain 127.0.0.1 \$host;
  }}

   location /longpolling {{
        proxy_pass http://127.0.0.1:8072;
  }}
   

   location ~* /web/static/ {{
       proxy_cache_valid 200 90m;
       proxy_buffering    on;
       expires 864000;
       proxy_pass http://127.0.0.1:{self.port};
  }}

  # gzip
  gzip_types text/css text/less text/plain text/xml application/xml application/json application/javascript;
  gzip on;
}}
"""
                # Create the Nginx configuration file and insert the configuration into it
                subprocess.run(
                    f"ssh {username}@{address} sudo touch /etc/nginx/sites-available/{self.instance_subdomain}.conf",
                    shell=True)
                subprocess.run(
                    f"ssh {username}@{address} sudo chmod o+w /etc/nginx/sites-available/{self.instance_subdomain}.conf",
                    shell=True)
                subprocess.run(
                    f'ssh {username}@{address} "echo \'{nginx_conf}\' | sudo tee /etc/nginx/sites-available/{self.instance_subdomain}.conf"',
                    shell=True, check=True)
                # Create a symbolic link to the Nginx configuration file
                subprocess.run(
                    f"ssh {username}@{address} sudo ln -s /etc/nginx/sites-available/{self.instance_subdomain}.conf /etc/nginx/sites-enabled/",
                    shell=True)
                # Restart Nginx
                subprocess.run(f"ssh {username}@{address} sudo systemctl restart nginx", shell=True)

                _logger.info("Creating Nginx configuration done!")

                self.db_name = f'{name}db'
                first_run = self.with_context(first_run=True).run_odoo_instance()
                if first_run:
                    client = erppeek.Client(server=f'http://{self.instance_url}')
                    user_admin_pass = str(random.randint(1000, 9999))
                    client.create_database(passwd='admin', database=self.db_name, user_password=user_admin_pass,
                                                       login="admin", country_code=self.country_id.code)
                    self.write({'user_admin_pass': user_admin_pass, 'user_ids': [
                                    (0, 0, {'name': 'Administrator', 'login': 'admin', 'password': user_admin_pass, 'type': 'admin'})]})
                    client.install('base')
                    # Install country-related modules
                    for module in self.country_id.module_ids:
                        client.install(module.name)
        except Exception as e:
            _logger.error(e)

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
        self.instance_token = ''.join(
            random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=16))
        if not bool(re.search(r'\d', self.instance_token)):
            self.generate_instance_token()

    @api.model
    def create(self, values):
        new_seq = self.env['ir.sequence'].next_by_code('odoo.instance.seq')
        values.update({"name": new_seq})
        res = super(OdooInstancesManagement, self).create(values)
        res.generate_instance_token()
        return res
