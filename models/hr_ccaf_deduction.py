from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta

class HrCcafDeduction(models.Model):
    _name = 'hr.ccaf.deduction'
    _description = 'Descuentos por CCAF (Crédito, Leasing, Seguro, etc.)'

    employee_id = fields.Many2one('hr.employee', string="Empleado", required=True)
    deduction_type = fields.Selection([
        ('credit', 'Crédito Personal'),
        ('leasing', 'Leasing / Programa Ahorro'),
        ('dental', 'Descuento Dental'),
        ('insurance', 'Seguro de Vida'),
        ('other', 'Otro'),
    ], required=True, string="Tipo de descuento")

    ccaf = fields.Selection(
        selection=[
            ('00', 'Sin CCAF'),
            ('01', 'Los Andes'),
            ('02', 'La Araucana'),
            ('03', 'Los Héroes'),
            ('06', '18 de Septiembre'),
        ], required=True, string="Caja", readonly=True,
        help="Se autocompleta con la CCAF configurada en la empresa del empleado"
    )

    total_amount = fields.Float(string="Monto total")
    installment_amount = fields.Float(string="Monto cuota mensual")
    total_installments = fields.Integer(string="N° total cuotas")
    remaining_installments = fields.Integer(
        string="Cuotas restantes",
        compute="_compute_remaining_installments",
        store=True
    )
    start_date = fields.Date(string="Fecha inicio", help="Fecha de inicio del credito o descuento")
    end_date = fields.Date(string="Fecha término", help="Fecha de término del credito o descuento")
    active = fields.Boolean(default=True)

    @api.model
    def create(self, vals):
        """Autocompletar CCAF con la información de la empresa del empleado"""
        if 'employee_id' in vals and vals['employee_id']:
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            if employee.company_id and employee.company_id.caja_compensacion:
                vals['ccaf'] = employee.company_id.caja_compensacion
            else:
                vals['ccaf'] = '00'  # Sin CCAF por defecto
        return super(HrCcafDeduction, self).create(vals)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Actualizar CCAF cuando cambia el empleado"""
        if self.employee_id and self.employee_id.company_id:
            if self.employee_id.company_id.caja_compensacion:
                self.ccaf = self.employee_id.company_id.caja_compensacion
            else:
                self.ccaf = '00'  # Sin CCAF por defecto

    # Funcion para calcular las cuotas restantes con base a la fecha actual 
    @api.depends('start_date', 'end_date', 'total_installments')
    def _compute_remaining_installments(self):
        for record in self:
            if record.start_date and record.total_installments:
                today = date.today()
                passed_months = max(0, relativedelta(today, record.start_date).months + (12 * (today.year - record.start_date.year)))
                record.remaining_installments = max(0, record.total_installments - passed_months)
                
                # Auto-desactivar si no quedan cuotas restantes
                if record.remaining_installments <= 0 and record.active:
                    record.active = False
            else:
                record.remaining_installments = 0

    # Funcion para calcular la fecha de término del descuento en relacion a las cuotas y fecha de inicio
    @api.onchange('start_date', 'total_installments')
    def _onchange_end_date(self):
        if self.start_date and self.total_installments:
            self.end_date = self.start_date + relativedelta(months=self.total_installments)

    def finalize_credit(self):
        """Método para finalizar manualmente un crédito CCAF"""
        self.ensure_one()
        self.remaining_installments = 0
        self.active = False
        return True

    def reactivate_credit(self):
        """Método para reactivar un crédito CCAF si es necesario"""
        self.ensure_one()
        if not self.active and self.remaining_installments > 0:
            self.active = True
        return True
