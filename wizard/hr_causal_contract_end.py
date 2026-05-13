from odoo import fields, models


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    causal_contract_end_id = fields.Many2one(
        'hr.causal.contract.end',
        string='Causal término de contrato',
        help='Seleccione la causal legal aplicable al término del contrato.'
    )

    def action_register_departure(self):
        res = super().action_register_departure()
        for wizard in self:
            if wizard.employee_id:
                wizard.employee_id.causal_contract_end_id = wizard.causal_contract_end_id
        return res
