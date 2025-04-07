from odoo import models, fields

class HrIndicadoresPrevisionales(models.Model):
    _name = "hr.indicadores.previsionales"
    _description = "Indicadores Previsionales"
    _order = "fecha desc"

    name = fields.Char(string="Nombre", required=True)
    valor = fields.Float(string="Valor", digits="Payroll")
    fecha = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    tipo = fields.Selection([
        ('uf', 'UF'),
        ('utm', 'UTM'),
        ('tope_imponible', 'Tope Imponible'),
        ('ipc', 'IPC')
    ], string="Tipo de Indicador", required=True)
