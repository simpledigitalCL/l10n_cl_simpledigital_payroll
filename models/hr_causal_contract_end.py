from odoo import models, fields


class HrCausalContractEnd(models.Model):
    _name = 'hr.causal.contract.end'
    _description = 'Causal de término de contrato'

    name = fields.Char(required=True, string='Glosa')
    code = fields.Char(required=True, string='Código')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('hr_causal_contract_end_code_uniq', 'unique (code)', 'El código de causal debe ser único.'),
    ]
