from datetime import timedelta, datetime, time as dt_time
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    previred_movement_ids = fields.One2many(
        'hr.previred.movement',
        'payslip_id',
        string="Movimientos Previred"
    )

    overtime_hours = fields.Float(
        string='Horas Extras No Pactadas',
        compute='_compute_overtime_hours',
        help='Total de horas extras no pactadas del empleado en el período de la nómina'
    )

    def compute_sheet(self):
        # Llamamos primero al compute original
        res = super().compute_sheet()

        for payslip in self.filtered(lambda p: p.state in ['draft', 'verify']):
            if payslip.struct_id.name == "Nómina Chile":
                date_from = payslip.date_from
                date_to = payslip.date_to

                # Validar Impuesto de Segunda Categoría
                impuesto = self.env['impuesto_2da_categoria'].search([
                    ('date', '>=', date_from),
                    ('date', '<=', date_to)
                ], limit=1)

                # Validar Indicadores Previred
                previred_movs = self.env['previred.indicator'].search([
                    ('date', '>=', date_from),
                    ('date', '<=', date_to)
                ], limit=1)

                if not impuesto:
                    raise UserError(_(
                        "No se encontró información de Impuesto de Segunda Categoría para el período de la nómina (%s - %s). Por favor, regístrela antes de continuar.") % (
                        date_from, date_to))

                if not previred_movs:
                    raise UserError(_(
                        "No se encontraron movimientos en Previred para el período de la nómina (%s - %s). Asegúrate de ingresarlos antes de procesar.") % (
                        date_from, date_to))

                # Los días OUT y asistencia ya se calculan correctamente en _get_worked_day_lines_values
                pass

        return res

    def action_payslip_done(self):
        res = super().action_payslip_done()
        for slip in self:
            if slip.move_id:
                for move_line in slip.move_id.line_ids:
                    pline = slip.line_ids.filtered(
                        lambda l: l.salary_rule_id.account_debit.id == move_line.account_id.id or
                                  l.salary_rule_id.account_credit.id == move_line.account_id.id
                    )
                    if pline:
                        move_line.name = pline[0].name  # aquí se actualiza la etiqueta
        return res

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_overtime_hours(self):
        """
        Calcula el total de horas extras no pactadas del empleado en el período de la nómina.
        Busca todos los movimientos de empleado (hr.employee.movement.line) que:
        - Pertenezcan al empleado de la nómina
        - Tengan fecha dentro del período de la nómina
        - Tengan horas registradas (campo hours > 0)
        """
        for payslip in self:
            total_hours = 0.0
            
            if payslip.employee_id and payslip.date_from and payslip.date_to:
                # Buscar todas las líneas de movimientos con horas en el período
                movement_lines = self.env['hr.employee.movement.line'].search([
                    ('employee_id', '=', payslip.employee_id.id),
                    ('movement_id.date', '>=', payslip.date_from),
                    ('movement_id.date', '<=', payslip.date_to),
                    ('hours', '>', 0),
                ])
                
                # Sumar todas las horas
                total_hours = sum(movement_lines.mapped('hours'))
            
            payslip.overtime_hours = total_hours
        
    # ================================================
    # Reemplazo de _get_worked_day_lines_values
    # ================================================
    #
    # Este método sobrescribe el cálculo de líneas de días trabajados (hr.payslip.worked_days)
    # para Licencia Médica y Faltas con el fin de:
    #
    # Recalcular el número de días (`number_of_days`) usando los días calendario reales
    #     registrados en los objetos hr.leave.
    #
    # Por defecto, Odoo genera hr.work.entry considerando el calendario laboral,
    #     lo que excluye fines de semana y feriados. Esto hacía que, por ejemplo,
    #     una licencia médica de 30 días se reflejara como 21 días en la nómina. Ademas en Chile un mes laboral equivale a
    #     30 días calendario, por lo que se deben considerar todos los días del mes para el cálculo de la nómina.
    #
    # Con esta modificación, buscamos todos los hr.leave validados que se crucen
    #     con el período del recibo de sueldo y que correspondan al mismo tipo de entrada
    #     (`work_entry_type_id`) de la línea, y sumamos los días calendario de forma inclusiva.
    #
    # Solo se modifica el campo `number_of_days`, dejando `number_of_hours` e `importe` tal como lo calcula Odoo.
    #
    # Resultado: La nómina refleja el total de días calendario de ausencia, incluyendo fines de semana.
    #
    def _get_worked_day_lines_values(self, domain=None):
        lines = super()._get_worked_day_lines_values(domain)
    
        slip_start = fields.Datetime.to_datetime(self.date_from)
        slip_end = datetime.combine(self.date_to, dt_time(23, 59, 59))
    
        if self.struct_id.name == "Nómina Chile":
            out_days = 0
            if self.contract_id and self.contract_id.date_start:
                contract_start = self.contract_id.date_start
                if contract_start > self.date_from:
                    out_days = (contract_start - self.date_from).days
                    # _logger.info(f"DEBUG OUT DAYS - Contract start: {contract_start}, OUT days: {out_days}")
    
            # Calcular días totales considerando fin de contrato
            total_days_in_period = 30
            if self.contract_id and self.contract_id.date_end:
                contract_end = self.contract_id.date_end
                # Si el contrato termina dentro del período de la nómina
                if self.date_from <= contract_end <= self.date_to:
                    # Calcular días trabajados desde inicio del período hasta fin de contrato
                    days_worked = (contract_end - max(self.date_from, self.contract_id.date_start)).days + 1
                    total_days_in_period = days_worked
                    # _logger.info(f"DEBUG CONTRACT END - Contract ends: {contract_end}, Days in period: {total_days_in_period}")

    
            # --- Calcular ausencias ---
            lic_falt_days = 0
            vac_days = 0
            for line in lines:
                we_type = self.env['hr.work.entry.type'].browse(line.get('work_entry_type_id'))
                if we_type and we_type.is_leave:
                    # Poner los code de hr.work.entry.type según configuración local para buscar esos tipos de ausencias
                    if we_type.code in ['LIC', 'LEAVECL130']:
                        # Recalcular licencias como días CALENDARIO (incluyendo fines de semana)
                        # Las licencias médicas incluyen reposo total, por lo que se cuentan todos los días
                        leaves = self.env['hr.leave'].search([
                            ('employee_id', '=', self.employee_id.id),
                            ('state', '=', 'validate'),
                            ('holiday_status_id.work_entry_type_id', '=', we_type.id),
                            ('date_from', '<=', slip_end),
                            ('date_to', '>=', slip_start),
                        ])
                        total_days = 0
                        for lv in leaves:
                            lv_start = fields.Datetime.to_datetime(lv.date_from)
                            lv_end = fields.Datetime.to_datetime(lv.date_to)
                            start = max(lv_start, slip_start)
                            end = min(lv_end, slip_end)
                            if start <= end:
                                # Días calendario (incluyendo fines de semana)
                                total_days += (end.date() - start.date()).days + 1
                        if total_days:
                            line['number_of_days'] = float(min(total_days, total_days_in_period))
                            line['number_of_hours'] = float(min(total_days, total_days_in_period)) * 8
                            lic_falt_days += total_days
    
                    elif we_type.code == 'FALT':
                        # Recalcular faltas como días HÁBILES (excluyendo fines de semana y feriados)
                        leaves = self.env['hr.leave'].search([
                            ('employee_id', '=', self.employee_id.id),
                            ('state', '=', 'validate'),
                            ('holiday_status_id.work_entry_type_id', '=', we_type.id),
                            ('date_from', '<=', slip_end),
                            ('date_to', '>=', slip_start),
                        ])
                        total_days = 0
                        for lv in leaves:
                            lv_start = fields.Datetime.to_datetime(lv.date_from)
                            lv_end = fields.Datetime.to_datetime(lv.date_to)
                            start = max(lv_start, slip_start)
                            end = min(lv_end, slip_end)
                            if start <= end:
                                # Calcular días hábiles excluyendo fines de semana y feriados
                                business_days = lv._calculate_business_days_excluding_holidays(
                                    start.date(), end.date(), self.employee_id
                                )
                                total_days += business_days
                        if total_days:
                            line['number_of_days'] = float(min(total_days, total_days_in_period))
                            line['number_of_hours'] = float(min(total_days, total_days_in_period)) * 8
                            lic_falt_days += total_days
    
                    elif we_type.code == 'LEAVECL120':
                        # Recalcular vacaciones usando días hábiles (excluyendo fines de semana y feriados)
                        leaves = self.env['hr.leave'].search([
                            ('employee_id', '=', self.employee_id.id),
                            ('state', '=', 'validate'),
                            ('holiday_status_id.work_entry_type_id', '=', we_type.id),
                            ('date_from', '<=', slip_end),
                            ('date_to', '>=', slip_start),
                        ])
                        total_days = 0
                        for lv in leaves:
                            lv_start = fields.Datetime.to_datetime(lv.date_from)
                            lv_end = fields.Datetime.to_datetime(lv.date_to)
                            start = max(lv_start, slip_start)
                            end = min(lv_end, slip_end)
                            if start <= end:
                                # Calcular días hábiles excluyendo fines de semana y feriados
                                business_days = lv._calculate_business_days_excluding_holidays(
                                    start.date(), end.date(), self.employee_id
                                )
                                total_days += business_days
                        if total_days:
                            line['number_of_days'] = float(min(total_days, total_days_in_period))
                            line['number_of_hours'] = float(min(total_days, total_days_in_period)) * 8
                            vac_days += total_days
    
            # --- Ajuste por diferencia entre días calendario y norma chilena de 30 días ---
            # En meses con menos de 30 días (ej: febrero con 28), si el empleado estuvo
            # ausente todos los días reales, los días extra hasta 30 se asignan a la ausencia.
            actual_calendar_days = (self.date_to - self.date_from).days + 1
            extra_days = total_days_in_period - actual_calendar_days
            if extra_days > 0 and (lic_falt_days + vac_days + out_days) >= actual_calendar_days:
                for line in lines:
                    we_type = self.env['hr.work.entry.type'].browse(line.get('work_entry_type_id'))
                    if we_type and we_type.is_leave and line.get('number_of_days', 0) > 0:
                        current = line['number_of_days']
                        new_days = min(current + extra_days, total_days_in_period)
                        added = new_days - current
                        line['number_of_days'] = float(new_days)
                        line['number_of_hours'] = float(new_days) * 8
                        if we_type.code in ['LIC', 'LEAVECL130', 'FALT']:
                            lic_falt_days += added
                        elif we_type.code == 'LEAVECL120':
                            vac_days += added
                        break

            # --- Calcular asistencia ---
            asistencia_dias = total_days_in_period - lic_falt_days - vac_days - out_days
            if asistencia_dias < 0:
                asistencia_dias = 0
    
            # Buscar línea WORK100
            work100_line = next((l for l in lines if self.env['hr.work.entry.type'].browse(l.get('work_entry_type_id')).code == 'WORK100'), None)
            if work100_line:
                work100_line['number_of_days'] = asistencia_dias
                work100_line['amount'] = (self.contract_id.wage / 30.0) * asistencia_dias
                work100_line['number_of_hours'] = asistencia_dias * 8
            else:
                # Crear la línea si no existe
                work_type = self.env['hr.work.entry.type'].search([('code', '=', 'WORK100')], limit=1)
                if work_type and asistencia_dias > 0:
                    lines.append({
                        'sequence': 1,
                        'work_entry_type_id': work_type.id,
                        'number_of_days': asistencia_dias,
                        'number_of_hours': asistencia_dias * 8,
                        'amount': (self.contract_id.wage / 30.0) * asistencia_dias,
                    })
    
            # --- Corregir línea OUT ---
            for line in lines:
                we_type = self.env['hr.work.entry.type'].browse(line.get('work_entry_type_id'))
                if we_type and we_type.code == 'OUT':
                    line['number_of_days'] = float(min(out_days, total_days_in_period))
                    line['number_of_hours'] = float(out_days * 8)
                    line['amount'] = 0.0
    
        else:
            # Lógica estándar Odoo
            for line in lines:
                we_type = self.env['hr.work.entry.type'].browse(line.get('work_entry_type_id'))
                if not we_type or not we_type.is_leave:
                    continue
    
                leaves = self.env['hr.leave'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('state', '=', 'validate'),
                    ('holiday_status_id.work_entry_type_id', '=', we_type.id),
                    ('date_from', '<=', slip_end),
                    ('date_to', '>=', slip_start),
                ])
    
                total_days = 0
                for lv in leaves:
                    lv_start = fields.Datetime.to_datetime(lv.date_from)
                    lv_end = fields.Datetime.to_datetime(lv.date_to)
                    start = max(lv_start, slip_start)
                    end = min(lv_end, slip_end)
                    if start <= end:
                        total_days += (end.date() - start.date()).days + 1
    
                if total_days:
                    line['number_of_days'] = float(min(total_days, 30))
    
        return lines



class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.model
    def create(self, vals):
        result = super().create(vals)
        
        # Ajustar días OUT para estructura chilena
        if result.payslip_id and result.payslip_id.struct_id.name == "Nómina Chile":
            work_entry_type = result.work_entry_type_id
            if work_entry_type and work_entry_type.code == 'OUT':
                payslip = result.payslip_id
                if payslip.contract_id and payslip.contract_id.date_start:
                    contract_start = payslip.contract_id.date_start
                    if contract_start > payslip.date_from:
                        correct_out_days = (contract_start - payslip.date_from).days
                        result.number_of_days = float(correct_out_days)
                        result.number_of_hours = float(correct_out_days * 8)
                        
                        # _logger.info(f"DEBUG CREATE WORKED_DAYS - Corrected OUT days from {vals.get('number_of_days')} to {correct_out_days}")
        
        return result

    def write(self, vals):
        result = super().write(vals)
        
        # Ajustar días OUT para estructura chilena al modificar
        for record in self:
            if record.payslip_id and record.payslip_id.struct_id.name == "Nómina Chile":
                work_entry_type = record.work_entry_type_id
                if work_entry_type and work_entry_type.code == 'OUT':
                    payslip = record.payslip_id
                    if payslip.contract_id and payslip.contract_id.date_start:
                        contract_start = payslip.contract_id.date_start
                        if contract_start > payslip.date_from:
                            correct_out_days = (contract_start - payslip.date_from).days
                            if 'number_of_days' in vals and vals['number_of_days'] != correct_out_days:
                                record.number_of_days = float(correct_out_days)
                                record.number_of_hours = float(correct_out_days * 8)

                                # _logger.info(f"DEBUG WRITE WORKED_DAYS - Corrected OUT days to {correct_out_days}")
        
        return result


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    code = fields.Char(related="salary_rule_id.code", store=True, readonly=True,
                       help="The code of salary rules can be used as reference in computation of other rules. "
                       "In that case, it is case sensitive.")

    """ Funcion para que las lineas de Salud y AFP tengan el nombre de la institucion correspondiente """
    def _update_institution_names(self):
        """Actualiza el nombre de las líneas de Salud y AFP con la institución correspondiente"""
        for line in self:
            if not line.salary_rule_id or not line.slip_id.contract_id:
                continue

            contract = line.slip_id.contract_id
            rule_name = line.salary_rule_id.name
            new_name = None

            # Actualizar nombre para Salud (FONASA / ISAPRE)
            if rule_name == 'Salud (FONASA / ISAPRE)':
                selection = dict(
                    contract._fields['health_institution'].selection
                )
                institution_label = selection.get(contract.health_institution)

                tipo = (
                    'FONASA'
                    if contract.health_institution == '07 - 102'
                    else 'ISAPRE'
                )

                new_name = f"Salud ({tipo}) - {institution_label}"
            
            # Actualizar nombre para AFP
            elif rule_name == 'AFP':
                if contract.afp_option and contract.afp_option != '00 - 100':
                    selection = dict(
                        contract._fields['afp_option'].selection
                    )
                    afp_label = selection.get(contract.afp_option)
                    
                    new_name = f"AFP - {afp_label}"
            
            if new_name and new_name != line.name:
                self.env.cr.execute(
                    "UPDATE hr_payslip_line SET name = %s WHERE id = %s",
                    (new_name, line.id)
                )
                line.invalidate_recordset(['name'])
    
    def create(self, vals_list):
        """Forzamos que el name de la línea sea siempre el de la regla"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]  

        for vals in vals_list:
            if vals.get("salary_rule_id"):
                rule = self.env["hr.salary.rule"].browse(vals["salary_rule_id"])
                if rule:
                    vals["name"] = rule.name

        lines = super().create(vals_list)
        lines._update_institution_names()
        return lines

    def write(self, vals):
        if self.env.context.get('skip_update_institution_names'):
            return super().write(vals)
        
        res = super().write(vals)
        
        if 'name' not in vals:
            self.with_context(skip_update_institution_names=True)._update_institution_names()
        
        return res