from odoo import models, fields, api

class HrAfp(models.Model):
    _name = "hr.afp"
    _description = "AFP - Administradora de Fondos de Pensiones"

    name = fields.Char(string="Nombre", required=True)
    codigo = fields.Char(string="Código")
    rut = fields.Char(string="RUT")
    rate = fields.Float(string="Tasa AFP (%)", digits=(16, 2))
    sis = fields.Float(string="Tasa SIS (%)", digits=(16, 2))
    independiente = fields.Boolean(string="¿Aplica a independientes?", default=False)

    @api.model
    def actualizar_tasas_desde_previred(self):
        # Esta función simula la obtención de tasas desde PreviRed
        afps = self.search([])
        for afp in afps:
            afp.rate = 10.0  # tasa simulada
            afp.sis = 1.5    # tasa simulada
