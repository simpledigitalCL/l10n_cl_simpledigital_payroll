from odoo import api, fields, models, _


class HrSeguroComplementario(models.Model):
    _name = 'hr.seguro.complementario'
    _description = _('Seguro Complementario de Salud')
    _order = 'name'

    codigo = fields.Char(string='Código', required=True)
    name = fields.Char(string='Nombre', required=True)

    _sql_constraints = [
        ('codigo_unique', 'unique(codigo)', 'El código debe ser único.'),
        ('name_unique', 'unique(name)', 'El nombre debe ser único.'),
    ]
