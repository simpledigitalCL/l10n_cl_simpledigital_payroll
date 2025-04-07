from odoo import api, fields, models, _


class HrApv(models.Model):
    _name = 'hr.apv'
    _description = _('Institución Autorizada APV/APVC - Compañías de Seguros de Vida')
    _order = 'name'

    codigo = fields.Char(string='Código', required=True)
    name = fields.Char(string='Nombre', required=True)

    _sql_constraints = [
        ('codigo_unique', 'unique(codigo)', 'El código debe ser único.'),
        ('name_unique', 'unique(name)', 'El nombre debe ser único.'),
    ]
