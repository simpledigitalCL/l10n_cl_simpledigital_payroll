from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)
class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    identification_id = fields.Char(
        string='Identification No', 
        groups="hr.group_hr_user", 
        tracking=True,
        help="Identification number of the employee, usually the RUT in Chilean context."
    )

    # Campos Region y Comuna    
    hr_commune = fields.Many2one(
        'res.country.commune',
        string='Comuna',
        domain="[('country_id', '=', country_id), ('state_id', '=', private_state_id)]",
        help="Commune where the employee resides.",
        required=True,
        groups="hr.group_hr_user"
    )

    has_disability = fields.Boolean(
        string='¿Tiene invalidez?',
        default=False,
        help='Indica si el empleado tiene algún tipo de invalidez o discapacidad',
        tracking=True,
        groups="hr.group_hr_user"
    )

    # Campos computados para visibilidad de páginas 
    ccaf_deduction_ids = fields.One2many(
        'hr.ccaf.deduction',
        'employee_id',
        string='Descuentos CCAF'
    )
    company_has_ccaf = fields.Boolean(
        string="Empresa tiene CCAF",
        compute="_compute_company_ccaf_mutual",
        store=False,
        help="Campo computado para determinar si la empresa tiene CCAF configurada"
    )

    causal_contract_end_id = fields.Many2one(
        'hr.causal.contract.end',
        string='Causal término de contrato',
        help='Última causal legal registrada para la salida del empleado.',
        groups="hr.group_hr_user"
    )

    payslip_count = fields.Integer(
        string='Número de Liquidaciones',
        compute='_compute_payslip_count',
        help='Número de liquidaciones asociadas a este empleado',
        groups="hr.group_hr_user"
    )

    can_view_payslips = fields.Boolean(
        string='Puede ver liquidaciones',
        compute='_compute_can_view_payslips',
        help='Determina si el usuario actual puede ver las liquidaciones de este empleado'
    )

    @api.depends('company_id', 'company_id.caja_compensacion')
    def _compute_company_ccaf_mutual(self):
        for record in self:
            # Verificar si la empresa tiene CCAF configurada
            record.company_has_ccaf = (
                record.company_id and 
                record.company_id.caja_compensacion and 
                record.company_id.caja_compensacion != '00'
            )

    def _compute_payslip_count(self):
        """Calcula el número de liquidaciones del empleado"""
        for employee in self:
            employee.payslip_count = self.env['hr.payslip'].search_count([
                ('employee_id', '=', employee.id)
            ])

    def _compute_can_view_payslips(self):
        """Determina si el usuario actual puede ver las liquidaciones de este empleado"""
        for employee in self:
            # El usuario puede ver si es su propio empleado o si es manager de payroll
            is_own_employee = employee.user_id.id == self.env.uid
            is_payroll_manager = self.env.user.has_group('hr_payroll.group_hr_payroll_manager')
            employee.can_view_payslips = is_own_employee or is_payroll_manager

    @api.onchange('country_id')
    def _onchange_country_id(self):
        """Limpiar la comuna cuando se cambie el país"""
        if self.country_id and self.private_state_id:
            # Si la región actual no pertenece al nuevo país, limpiarla
            if self.private_state_id.country_id != self.country_id:
                self.private_state_id = False
                self.hr_commune = False
        elif self.country_id:
            # Si no hay región previa, limpiar la comuna por si acaso
            self.hr_commune = False

    @api.onchange('private_state_id')
    def _onchange_private_state_id(self):
        """Limpiar la comuna cuando se cambie la región"""
        if self.private_state_id and self.hr_commune:
            # Si la comuna actual no pertenece a la nueva región, limpiarla
            if self.hr_commune.state_id != self.private_state_id:
                self.hr_commune = False
        elif not self.private_state_id:
            # Si se quita la región, limpiar la comuna
            self.hr_commune = False

    """
        Funcion para formatar input en formato de RUT chileno. Cuando se escribe 123456789K
        se transforma a 12.345.678-K
    """
    @api.onchange('identification_id')
    def _onchange_identification_id(self):
        if self.identification_id:
            # Eliminar puntos y guión
            rut = re.sub(r'[\.\-]', '', self.identification_id)
            if len(rut) > 1:
                cuerpo = rut[:-1]
                dv = rut[-1]
                if cuerpo.isdigit():
                    # Formatear: puntos cada 3 y guión antes del dígito verificador
                    cuerpo_formateado = "{:,}".format(int(cuerpo)).replace(",", ".")
                    self.identification_id = f"{cuerpo_formateado}-{dv}"
                else:
                    self.identification_id = ''
                    return {
                        'warning': {
                            'title': "RUT inválido",
                            'message': "El cuerpo del RUT debe contener solo números."
                        }
                    }

    """
        Función para validar el RUT chileno ingresado.
        Se asegura de que el RUT sea válido antes de guardar el registro.
    """
    @api.constrains('identification_id')
    def _check_rut(self):
        for record in self:
            if record.identification_id and not self._validate_rut(record.identification_id):
                raise ValidationError("El RUT ingresado no es válido.")

    """
        Función para validar el RUT chileno.
    """
    def _validate_rut(self, rut):
        # Eliminar puntos y guión
        rut = re.sub(r'[\.\-]', '', rut)
        if not rut[:-1].isdigit():
            return False
        cuerpo = rut[:-1]
        dv = rut[-1].upper()
        suma = 0
        multiplo = 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplo
            multiplo += 1
            if multiplo > 7:
                multiplo = 2
        res = 11 - (suma % 11)
        if res == 11:
            dv_esperado = '0'
        elif res == 10:
            dv_esperado = 'K'
        else:
            dv_esperado = str(res)
        return dv == dv_esperado
    
    def _cron_update_ccaf_credits(self):
        """Cron job para actualizar los créditos de la CCAF descontando la cantidad de cuotas"""
        employees = self.search([('ccaf_deduction_ids', '!=', False)])
        updated_count = 0
        deactivated_count = 0
        
        for emp in employees:
            for deduction in emp.ccaf_deduction_ids:
                # Solo procesar deducciones activas con cuotas restantes
                if deduction.active and deduction.remaining_installments > 0:
                    deduction.remaining_installments -= 1
                    updated_count += 1
                    
                    # Si las cuotas llegan a 0, desactivar el crédito
                    if deduction.remaining_installments <= 0:
                        deduction.active = False
                        deactivated_count += 1
        
        _logger.info(f"Cron CCAF ejecutado: {updated_count} cuotas descontadas, {deactivated_count} créditos finalizados")
        
        return {
            'updated': updated_count,
            'deactivated': deactivated_count
        }

    def action_view_payslips(self):
        """Acción para ver las liquidaciones del empleado"""
        self.ensure_one()
        return {
            'name': 'Liquidaciones',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('hr_payroll.view_hr_payslip_tree').id, 'list'),
                (self.env.ref('hr_payroll.view_hr_payslip_form').id, 'form')
            ],
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
            },
        }
