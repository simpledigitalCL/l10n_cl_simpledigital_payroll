from odoo import models, fields
from datetime import date

class HrPreviredTxtWizard(models.TransientModel):
    _name = 'hr.previred.txt.wizard'
    _description = 'Generador Archivo Previred TXT'

    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
    )
    period = fields.Date(
        string="Período",
        default=lambda self: date.today().replace(day=1),
        required=True,
        help="Elige el mes y año a exportar"
    )

    def action_generate_txt(self):
        period_dt = self.period or date.today()
        month = period_dt.strftime('%m')
        year = period_dt.strftime('%Y')
        period_str = f"{month}{year}"

        return self.env['ir.actions.act_url'].create({
            'name': 'Descargar Previred TXT',
            'url': f"/hr_payroll/previred/txt?period={period_str}&company_id={self.company_id.id}",
            'target': 'self',
        }).read()[0]
