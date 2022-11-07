from odoo import fields, models, SUPERUSER_ID, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    appex_payment_token = fields.Char(string="Staff Payment Token", required=False, )
    appex_payment_url = fields.Char(string="Staff Payment URL", required=False, )
    billing_product_id = fields.Many2one(comodel_name="product.product", string="Billing Product", required=False, )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        res.update(
            appex_payment_token=env_config_parameter.get_param('accounting_integration.appex_payment_token'),
            appex_payment_url=env_config_parameter.get_param('accounting_integration.appex_payment_url'),
            billing_product_id=int(env_config_parameter.get_param('accounting_integration.billing_product_id')),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()

        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        appex_payment_token = self.appex_payment_token and self.appex_payment_token or False
        appex_payment_url = self.appex_payment_url and self.appex_payment_url or False
        billing_product_id = self.billing_product_id and self.billing_product_id or False
        print(self.billing_product_id)

        env_config_parameter.set_param('accounting_integration.appex_payment_token', appex_payment_token)
        env_config_parameter.set_param('accounting_integration.appex_payment_url', appex_payment_url)
        env_config_parameter.set_param('accounting_integration.billing_product_id', billing_product_id.id)
