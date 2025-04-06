from odoo import models, fields

class HrIsapre(models.Model):
    _name = "hr.isapre"
    _description = "Isapre - Institución de Salud Previsional"

    name = fields.Char(string="Nombre", required=True)
    codigo = fields.Char(string="Código")
    rut = fields.Char(string="RUT")
    tasa = fields.Float(string="Tasa (%)", digits=(16, 2))
    fonasa = fields.Boolean(string="¿Es Fonasa?", default=False)
