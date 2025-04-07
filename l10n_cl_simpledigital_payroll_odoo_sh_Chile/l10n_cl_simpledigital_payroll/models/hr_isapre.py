from odoo import models, fields

class HrIsapre(models.Model):
    _name = "hr.isapre"
    _description = "Isapre - Institución de Salud Previsional"
    _order = "name"

    name = fields.Char(string="Nombre", required=True)
    codigo = fields.Char(string="Código", required=True)
    rut = fields.Char(string="RUT", required=True)
    tasa = fields.Float(string="Tasa (%)", digits="Payroll", required=True)
    fonasa = fields.Boolean(string="¿Es Fonasa?", default=False)
