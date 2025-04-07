from odoo import models, fields

class HrTypeEmployee(models.Model):
    _name = 'hr.type.employee'
    _description = 'Tipo de Empleado'

    id_type = fields.Char('Código', required=True)
    name = fields.Char('Nombre', required=True)
