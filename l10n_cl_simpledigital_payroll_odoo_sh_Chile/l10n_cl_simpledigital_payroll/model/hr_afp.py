from odoo import api, fields, models, _


class HrAfp(models.Model):
    _name = 'hr.afp'
    _description = _('Fondos de Pensión')
    _order = 'name'

    codigo = fields.Char(string='Código', required=True)
    name = fields.Char(string='Nombre', required=True)
    rut = fields.Char(string='RUT', required=True)
    rate = fields.Float(string='Tasa de Cotización (%)', required=True)
    sis = fields.Float(string='Aporte SIS Empresa (%)', required=True)
    independiente = fields.Float(string='Independientes (%)', required=True)

    _sql_constraints = [
        ('codigo_unique', 'unique(codigo)', 'El código debe ser único.'),
        ('rut_unique', 'unique(rut)', 'El RUT debe ser único.'),
    ]
