from odoo import models, fields

class HrSeguroComplementario(models.Model):
    _name = 'hr.seguro.complementario'
    _description = 'Seguro Complementario'

    codigo = fields.Char('Código', required=True)
    name = fields.Char('Nombre', required=True)
