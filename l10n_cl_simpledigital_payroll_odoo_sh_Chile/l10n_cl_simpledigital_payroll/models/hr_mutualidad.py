from odoo import models, fields

class HrMutual(models.Model):
    _name = 'hr.mutual'
    _description = 'Mutualidad'

    codigo = fields.Char('Código', required=True)
    name = fields.Char('Nombre', required=True)
