from odoo import models, fields
from datetime import date

class HrPreviredTxtWizard(models.TransientModel):
    _name = 'hr.previred.txt.wizard'
    _description = 'Generador Archivo Previred TXT'

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

        # Reutiliza tu lógica, pero recibe el periodo
        return self.env['ir.actions.act_url'].create({
            'name': 'Descargar Previred TXT',
            'url': f"/hr_payroll/previred/txt?period={period_str}",
            'target': 'self',
        }).read()[0]

    """" Boton generar el archivo de previred en formato csv para visualizar mejor """
    # def action_generate_csv(self):
    #     period_dt = self.period or date.today()
    #     month = period_dt.strftime('%m')
    #     year = period_dt.strftime('%Y')
    #     period_str = f"{month}{year}"

    #     # Genera el archivo CSV
    #     return self.env['ir.actions.act_url'].create({
    #         'name': 'Descargar Previred CSV',
    #         'url': f"/hr_payroll/previred/csv?period={period_str}",
    #         'target': 'self',
    #     }).read()[0]
