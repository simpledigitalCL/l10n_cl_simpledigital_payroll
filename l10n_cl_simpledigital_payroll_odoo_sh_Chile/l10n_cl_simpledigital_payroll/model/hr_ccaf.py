from odoo import api, fields, models, _


class HrCcaf(models.Model):
    _name = 'hr.ccaf'
    _description = _('Caja de Compensación (CCAF)')
    _order = 'name'

    codigo = fields.Char(string='Código', required=True)
    name = fields.Char(string='Nombre', required=True)

    _sql_constraints = [
        ('codigo_unique', 'unique(codigo)', 'El código debe ser único.'),
        ('name_unique', 'unique(name)', 'El nombre debe ser único.'),
    ]
