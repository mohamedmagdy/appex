from odoo import fields, models, SUPERUSER_ID, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    appex_response_url = fields.Char(string="Appex Portal Response URL", required=False, )
    odoo_instances_address = fields.Char(string="Instances Server",  required=False, )
    username = fields.Char(string="Server Username",  required=False, )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        res.update(
            appex_response_url=env_config_parameter.get_param('appex_instances_management.appex_response_url'),
            odoo_instances_address=env_config_parameter.get_param('appex_instances_management.odoo_instances_address'),
            username=env_config_parameter.get_param('appex_instances_management.username'),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()

        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        appex_response_url = self.appex_response_url and self.appex_response_url or False
        odoo_instances_address = self.odoo_instances_address and self.odoo_instances_address or False
        username = self.username and self.username or False

        env_config_parameter.set_param('appex_instances_management.appex_response_url', appex_response_url)
        env_config_parameter.set_param('appex_instances_management.odoo_instances_address', odoo_instances_address)
        env_config_parameter.set_param('appex_instances_management.username', username)
