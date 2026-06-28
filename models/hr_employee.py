from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date
import re
import logging

_logger = logging.getLogger(__name__)

# Días de vacaciones legales base en Chile (Art. 67 Código del Trabajo).
LEGAL_VACATION_DAYS = 15


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

    # --- Vacaciones progresivas (Art. 68 Código del Trabajo) ---
    # Meses de cotización acreditados con empleadores ANTERIORES, ingresados a mano
    # y respaldados por el certificado de cotizaciones (AFP / Dirección del Trabajo).
    l10n_cl_prev_employer_months = fields.Integer(
        string="Meses cotizados con empleadores anteriores",
        default=0,
        tracking=True,
        groups="hr.group_hr_user",
        help="Meses de cotización acreditados con empleadores anteriores, respaldados "
             "por el certificado de cotizaciones. Se usan para el requisito de 10 años "
             "(120 meses) del Art. 68. Solo se consideran si el certificado está validado.",
    )
    l10n_cl_progressive_cert_validated = fields.Boolean(
        string="Certificado de cotizaciones validado",
        default=False,
        tracking=True,
        groups="hr.group_hr_user",
        help="Marcar cuando RR.HH. haya verificado el certificado de cotizaciones que "
             "respalda los meses con empleadores anteriores. Mientras no esté validado, "
             "esos meses no se consideran para el Art. 68.",
    )
    l10n_cl_current_employer_months = fields.Integer(
        string="Meses con el empleador actual",
        compute="_compute_progressive_vacation_days",
        groups="hr.group_hr_user",
        help="Antigüedad en meses con el empleador actual, calculada desde la fecha de "
             "inicio del contrato más antiguo del empleado.",
    )
    l10n_cl_total_contributed_months = fields.Integer(
        string="Meses cotizados (total)",
        compute="_compute_progressive_vacation_days",
        groups="hr.group_hr_user",
        help="Suma de meses con empleadores anteriores (si el certificado está validado) "
             "y meses con el empleador actual.",
    )
    l10n_cl_progressive_vacation_days = fields.Integer(
        string="Días de vacaciones progresivas (Art. 68)",
        compute="_compute_progressive_vacation_days",
        groups="hr.group_hr_user",
        help="Días adicionales de vacaciones por antigüedad. Requiere 10 años (120 meses) "
             "cotizados en total y al menos 3 años con el empleador actual; se suma 1 día "
             "por cada 3 años (36 meses) completos con el empleador actual.",
    )

    @api.depends('contract_ids.date_start', 'contract_ids.state',
                 'l10n_cl_prev_employer_months', 'l10n_cl_progressive_cert_validated')
    def _compute_progressive_vacation_days(self):
        today = date.today()
        for employee in self:
            # Antigüedad con el empleador actual: desde el contrato más antiguo.
            start_dates = employee.contract_ids.filtered('date_start').mapped('date_start')
            if start_dates:
                start = min(start_dates)
                current_months = (today.year - start.year) * 12 + (today.month - start.month)
                current_months = max(current_months, 0)
            else:
                current_months = 0

            # Los meses con empleadores anteriores solo cuentan con certificado validado.
            prev_months = (
                employee.l10n_cl_prev_employer_months
                if employee.l10n_cl_progressive_cert_validated else 0
            )
            total_months = prev_months + current_months

            # Art. 68: 10 años (120 meses) totales + 3 años (36 meses) con el empleador
            # actual dan +1 día; cada 3 años adicionales con el mismo empleador, +1 día más.
            if total_months >= 120 and current_months >= 36:
                progressive = current_months // 36
            else:
                progressive = 0

            employee.l10n_cl_current_employer_months = current_months
            employee.l10n_cl_total_contributed_months = total_months
            employee.l10n_cl_progressive_vacation_days = progressive

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
