from odoo import api, fields, models, _


class HrIsapre(models.Model):
    _name = 'hr.isapre'
    _description = _('Isapres')
    _order = 'name'

    codigo = fields.Char(string='Código', required=True)
    name = fields.Char(string='Nombre', required=True)
    rut = fields.Char(string='RUT', required=True)

    _sql_constraints = [
        ('codigo_unique', 'unique(codigo)', 'El código debe ser único.'),
        ('rut_unique', 'unique(rut)', 'El RUT debe ser único.'),
    ]
