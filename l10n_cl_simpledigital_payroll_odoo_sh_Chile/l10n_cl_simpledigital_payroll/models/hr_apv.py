from odoo import models, fields

class HrApv(models.Model):
    _name = 'hr.apv'
    _description = 'Institución Autorizada APV - APVC : Cías Seguros de Vida'

    codigo = fields.Char('Código', required=True)
    name = fields.Char('Nombre', required=True)
