from odoo import models, fields

class HrCcaf(models.Model):
    _name = 'hr.ccaf'
    _description = 'Caja de Compensación'

    codigo = fields.Char('Código', required=True)
    name = fields.Char('Nombre', required=True)
