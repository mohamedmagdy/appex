# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Employee(models.Model):
    _inherit = 'hr.employee'

    is_manager = fields.Boolean(string="Is a Manager", default=False)