from odoo import models, fields, api, _

class HrAfp(models.Model):
    _name = "hr.afp"
    _description = "AFP - Administradora de Fondos de Pensiones"
    _order = "name"

    name = fields.Char(string="Nombre", required=True)
    codigo = fields.Char(string="Código", required=True)
    rut = fields.Char(string="RUT", required=True)
    rate = fields.Float(string="Tasa AFP (%)", digits="Payroll", required=True)
    sis = fields.Float(string="Tasa SIS (%)", digits="Payroll", required=True)
    independiente = fields.Boolean(string="¿Aplica a independientes?", default=False)

    @api.model
    def actualizar_tasas_desde_previred(self):
        """Método simulado para actualizar tasas. Idealmente se conecta a PreviRed."""
        for afp in self.search([]):
            afp.write({
                'rate': 10.0,  # Valor simulado
                'sis': 1.5     # Valor simulado
            })
