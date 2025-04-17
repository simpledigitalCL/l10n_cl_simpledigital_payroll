#Modificado el 17/04/2025 para usar el parámetro states a través del método _valid_field_parameter para mayor flexibilidad y control acorde a ODOO 18.
from odoo import api, fields, models, tools, _

class hr_payslip_run(models.Model):
    _inherit = 'hr.payslip.run'
    _description = 'Payslip Run'

    # 1. Primero definimos el método para aceptar parámetros personalizados
    @api.model
    def _valid_field_parameter(self, field, name):
        """Permitir el parámetro 'states' para cualquier campo"""
        if name == 'states':
            return True
        return super()._valid_field_parameter(field, name)

    # 2. Campo indicadores_id modificado
    indicadores_id = fields.Many2one(
        'hr.indicadores',
        string='Indicadores',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help="Indicadores Previred para esta ejecución de nóminas"
    )

    # 3. Campo movimientos_personal mejorado
    movimientos_personal = fields.Selection(
        selection=[
            ('0', 'Sin Movimiento en el Mes'),
            ('1', 'Contratación a plazo indefinido'),
            ('2', 'Retiro'),
            ('3', 'Subsidios (L Médicas)'),
            ('4', 'Permiso Sin Goce de Sueldos'),
            ('5', 'Incorporación en el Lugar de Trabajo'),
            ('6', 'Accidentes del Trabajo'),
            ('7', 'Contratación a plazo fijo'),
            ('8', 'Cambio Contrato plazo fijo a plazo indefinido'),
            ('11', 'Otros Movimientos (Ausentismos)'),
            ('12', 'Reliquidación, Premio, Bono')
        ],
        string='Movimientos de Personal',
        default="0",
        help="Tipo de movimiento de personal asociado a esta ejecución"
    )