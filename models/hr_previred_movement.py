from odoo import models, fields, api

class HrPreviredMovement(models.Model):
    _name = 'hr.previred.movement'
    _description = 'Movimientos de Personal para Previred'

    employee_id = fields.Many2one(
        'hr.employee', 
        required=True, 
        string="Empleado",
        default=lambda self: self._get_default_employee()
    )
    payslip_id = fields.Many2one('hr.payslip', string="Liquidación")
    code = fields.Selection([
        ('1', 'Contratación a plazo indefinido'),
        ('2', 'Retiro'),
        ('3', 'Subsidios'),
        ('4', 'Permiso sin goce'),
        ('5', 'Incorporación lugar de trabajo'),
        ('6', 'Accidente del trabajo'),
        ('7', 'Plazo fijo'),
        ('8', 'Cambio a indefinido'),
        ('11', 'Otros Ausentismos'),
        ('12', 'Reliquidación, bono'),
        ('13', 'Suspensión acto autoridad'),
        ('14', 'Suspensión por pacto'),
        ('15', 'Reducción de jornada'),
    ], string="Código", required=True)
    date_from = fields.Date(string="Desde", required=False)
    date_to = fields.Date(string="Hasta", required=False)
    tipo_linea = fields.Selection([
        ('01', 'Línea adicional de movimiento (01)'),
        ('02', 'Segundo Contrato o Pagos Adicionales (02)'),
        ('03', 'Movimiento de Personal Afiliado Voluntario (03)'),
        
    ], default='01', readonly=False)
    
    @api.onchange('payslip_id')
    def _onchange_payslip_id(self):
        """Autocompletar employee_id cuando se selecciona un payslip_id"""
        if self.payslip_id and self.payslip_id.employee_id:
            self.employee_id = self.payslip_id.employee_id
    
    def _get_default_employee(self):
        """Obtener empleado por defecto desde el contexto del payslip"""
        # Si se está creando desde un payslip, usar el empleado del payslip
        if self.env.context.get('default_payslip_id'):
            payslip = self.env['hr.payslip'].browse(self.env.context.get('default_payslip_id'))
            return payslip.employee_id.id if payslip.employee_id else False
        return False
