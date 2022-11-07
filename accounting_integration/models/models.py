# -*- coding: utf-8 -*-

from odoo import models, fields, api, SUPERUSER_ID
import requests
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import json


class StaffPayment(models.Model):
    _name = 'staff.payment'
    _rec_name = 'name'
    _description = 'Staff Payment'

    @api.model
    def _selection_target_model(self):
        return [(model.model, model.name)
                for model in self.env['ir.model'].sudo().search(
                [('model', 'in', ['account.payment', 'account.move'])])]

    generated_record_ref = fields.Reference(string='Generated Record', selection='_selection_target_model')
    name = fields.Char(string="Payment ID", required=False, )
    beneficiary_name = fields.Char(string="Beneficiary Name", required=False, )
    partner_id = fields.Many2one(comodel_name="res.partner", string="Beneficiary", required=False, )
    entity_type = fields.Selection(string="Entity Type", selection=[('Corporate', 'Corporate'), ('Individual', 'Individual'), ], required=False, )
    beneficiary_type = fields.Selection(string="Beneficiary Type", selection=[('Consultant', 'Consultant'), ('Partner', 'Partner'), ], required=False, )
    currency_id = fields.Many2one(comodel_name="res.currency", string="Currency", required=False, )
    amount = fields.Monetary(string="Amount", currency_field="currency_id", required=False, )
    description = fields.Char(string="Description", required=False, )
    iban = fields.Char(string="IBAN", required=False, )

    def _generate_accounting_records(self):
        """
        This method will determine if the staff payment should be created as a Vendor Bill or a Vendor Receipt
        :return:
        """
        # all_staff_payments = self.search([('generated_record_ref', '=', False)])
        env_bills = self.env['account.move'].with_context(default_move_type='in_invoice')
        env_receipts = self.env['account.payment'].with_context({'default_payment_type': 'outbound', 'default_partner_type': 'supplier'})
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        billing_product_id = int(env_config_parameter.get_param('accounting_integration.billing_product_id'))
        bills_vals = {}
        receipts_vals = {}
        for staff_payment in self:
            partner_id = staff_payment.partner_id or False
            if staff_payment.beneficiary_type == 'Consultant':
                receipts_vals.update({'partner_id': partner_id and partner_id.id or False, 'amount': staff_payment.amount,
                                      'currency_id': staff_payment.currency_id.id, 'ref': staff_payment.description})
                created_receipts = env_receipts.create(receipts_vals)
                if created_receipts:
                    staff_payment.generated_record_ref = 'account.payment,%s' % created_receipts.id
            elif staff_payment.beneficiary_type == 'Partner':
                bills_vals.update({'partner_id': partner_id and partner_id.id or False, 'currency_id': staff_payment.currency_id.id,
                                   "invoice_line_ids": [(0, 0, {"product_id": billing_product_id, 'currency_id': staff_payment.currency_id.id,
                                               "price_unit": staff_payment.amount,
                                           },
                                       ),]
                                   })
                created_bills = env_bills.create(bills_vals)
                if created_bills:
                    staff_payment.generated_record_ref = 'account.move,%s' % created_bills.id
            else:
                pass
        # if bills_vals:
        #     env_bills.create(bills_vals)
        # if receipts_vals:
        #     env_receipts.create(receipts_vals)



    def _filter_date_from(self):
        """
        This method returns the preserved 'last_date_to' so that it can be used in the new request as "FromDateTime"
        :return:
        """
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        last_date_to = env_config_parameter.get_param('accounting_integration.last_date_to')
        return last_date_to or '1900-01-01'

    def _filter_date_to(self):
        return fields.Date.context_today(self).strftime(DEFAULT_SERVER_DATE_FORMAT)

    def get_staff_payment(self):
        env_config_parameter = self.env['ir.config_parameter'].with_user(SUPERUSER_ID)
        appex_payment_token = env_config_parameter.get_param('accounting_integration.appex_payment_token')
        appex_payment_url = env_config_parameter.get_param('accounting_integration.appex_payment_url')
        FromDateTime = self._filter_date_from()
        ToDateTime = self._filter_date_to()

        url = "%s?FromDateTime=%s&ToDateTime=%s&Status=issued" % (appex_payment_url, FromDateTime, ToDateTime)
        payload = {}
        headers = {'Authorization': appex_payment_token}

        response = requests.request("GET", url, headers=headers, data=payload)
        if response.status_code == 200:
            env_currency = self.env['res.currency']
            env_partner = self.env['res.partner']
            json_response = json.loads(response.content)
            if json_response:
                for payment in json_response:
                    currency_id = env_currency.search([('name', '=', payment.get('Currency'))], limit=1).id
                    exist_staff_payment = self.search([('name', '=', payment.get('PaymentId'))])
                    if payment.get('BeneficiaryName'):
                        exist_partner_id = env_partner.search([('name', '=', payment.get('BeneficiaryName'))], limit=1)
                        if not exist_partner_id:
                            company_type = payment.get('EntityType') == 'Corporate' and 'company' or 'person'
                            partner_id = env_partner.create({'name': payment.get('BeneficiaryName'), 'company_type': company_type})
                        else:
                            partner_id = exist_partner_id
                    staff_payment_vals = {}
                    if not exist_staff_payment:
                        staff_payment_vals.update({'partner_id': payment.get('BeneficiaryName') and partner_id.id or False,
                                                   'name': payment.get('PaymentId'),
                                                   'entity_type': payment.get('EntityType'),
                                                   'beneficiary_type': payment.get('BeneficiaryType'),
                                                   'amount': payment.get('Amount'), 'iban': payment.get('IBAN'),
                                                   'description': payment.get('Description'), 'currency_id': currency_id})
                        created_staff_payments = self.create(staff_payment_vals)
                if created_staff_payments:
                    # If success response, Set the 'last_date_to' to today's date
                    env_config_parameter.set_param('accounting_integration.last_date_to', ToDateTime)
