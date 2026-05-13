import re
from datetime import timedelta, datetime, time
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    allocation_days_available = fields.Float(
        string='Días Disponibles en Asignación',
        readonly=True,
        help='Cantidad de días disponibles en la asignación de vacaciones correspondiente.',
        compute='_compute_allocation_days_available',
    )

    show_allocation_days_available = fields.Boolean(
        compute='_compute_show_allocation_days_available'
    )

    # Mostrar el campo allocation_days_available si el tipo de tiempo personal es "Vacaciones Legales Chile"
    @api.depends('holiday_status_id')
    def _compute_show_allocation_days_available(self):
        for record in self:
            record.show_allocation_days_available = (
                record.holiday_status_id and
                record.holiday_status_id.name == 'Vacaciones Legales Chile'
            )

    @api.depends('employee_id', 'holiday_status_id')
    def _compute_allocation_days_available(self):
        for record in self:
            available = 0.0
            if (
                record.employee_id
                and record.holiday_status_id
                and record.holiday_status_id.name == 'Vacaciones Legales Chile'
            ):
                # Suma todas las asignaciones validadas
                allocations = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('holiday_status_id', '=', record.holiday_status_id.id),
                    ('state', '=', 'validate')
                ])
                total_asignado = sum(a.number_of_days for a in allocations)

                # Suma todos los días de vacaciones YA TOMADOS y aprobados (excepto el actual si no está validado aún)
                # Nota: Los días ya están calculados según el tipo de ausencia (hábiles o calendario)
                leaves = self.env['hr.leave'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('holiday_status_id', '=', record.holiday_status_id.id),
                    ('state', '=', 'validate'),
                    ('id', '!=', record.id)  # Excluye esta misma solicitud si aún no se valida
                ])
                total_tomado = sum(l.number_of_days for l in leaves)

                available = total_asignado - total_tomado

            record.allocation_days_available = available

    def _get_public_holidays(self, start_date, end_date, employee=None):
        """
        Obtiene los días festivos definidos en resource.calendar.leaves
        para el rango de fechas especificado.
        Retorna un set de fechas (date objects) que son feriados.
        """
        # Obtener el calendario del empleado o el calendario de la compañía
        calendar = None
        if employee and employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
        elif employee and employee.company_id.resource_calendar_id:
            calendar = employee.company_id.resource_calendar_id
        else:
            # Calendario por defecto de la compañía
            calendar = self.env.company.resource_calendar_id
        
        if not calendar:
            return set()
        
        # Convertir start_date y end_date a datetime para la búsqueda
        # Asegurarnos de que sean objetos date (no datetime)
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        # Para la búsqueda en Odoo, necesitamos datetime
        search_start = datetime.combine(start_date, time.min)
        search_end = datetime.combine(end_date, time.max)
        
        # Buscar días festivos (resource.calendar.leaves) en el rango
        public_holidays = self.env['resource.calendar.leaves'].search([
            ('date_from', '<=', search_end),
            ('date_to', '>=', search_start),
            ('resource_id', '=', False),      # NO permisos de empleados
            ('holiday_id', '=', False),       # NO solicitudes HR
            ('time_type', '=', 'leave'),      # Solo leaves
            '|',
                ('calendar_id', '=', calendar.id),
                ('calendar_id', '=', False),  # feriados globales
        ])

        
        holiday_dates = set()
        for holiday in public_holidays:
            # Convertir a date si son datetime
            h_start = holiday.date_from.date() if hasattr(holiday.date_from, 'date') else holiday.date_from
            h_end = holiday.date_to.date() if hasattr(holiday.date_to, 'date') else holiday.date_to
            
            # Agregar todos los días del feriado al set
            current = h_start
            while current <= h_end:
                # Solo agregar si cae dentro del rango solicitado
                if start_date <= current <= end_date:
                    holiday_dates.add(current)
                current += timedelta(days=1)
        
        return holiday_dates

    def _calculate_business_days_excluding_holidays(self, start_date, end_date, employee=None):
        """
        Calcula días hábiles excluyendo fines de semana y días festivos.
        """
        # Obtener feriados
        public_holidays = self._get_public_holidays(start_date, end_date, employee)
        
        _logger.info(f"🔍 CALCULANDO DÍAS HÁBILES: {start_date} a {end_date}")
        _logger.info(f"   Feriados encontrados: {sorted(public_holidays) if public_holidays else 'Ninguno'}")
        
        business_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            is_weekday = current_date.weekday() < 5
            is_holiday = current_date in public_holidays
            
            # Verificar si es día hábil (lunes a viernes) y no es feriado
            if is_weekday and not is_holiday:
                business_days += 1
                _logger.info(f"   ✅ {current_date} - Día hábil (weekday={current_date.weekday()})")
            else:
                reason = "feriado" if is_holiday else f"fin de semana (weekday={current_date.weekday()})"
                _logger.info(f"   ❌ {current_date} - Excluido ({reason})")
            
            current_date += timedelta(days=1)
        
        _logger.info(f"   📊 TOTAL DÍAS HÁBILES: {business_days}")
        return business_days

    @api.depends('date_from', 'date_to', 'employee_id', 'number_of_days')
    def _compute_duration_display(self):
        """
        Sobreescribe el método nativo para mostrar la duración en días hábiles
        calculados por este módulo (number_of_days ya refleja el cálculo correcto).
        """
        for leave in self:
            if leave.number_of_days:
                business_days = int(leave.number_of_days)
                if business_days == 1:
                    leave.duration_display = '1 día'
                else:
                    leave.duration_display = f'{business_days} días'
            else:
                leave.duration_display = '0 días'

    def _calculate_business_days(self, start_date, end_date):
        """Método auxiliar para calcular días hábiles entre dos fechas"""
        business_days = 0
        current_date = start_date
        while current_date <= end_date:
            # weekday() devuelve 0=lunes, 6=domingo
            if current_date.weekday() < 5:  # 0-4 son lunes a viernes
                business_days += 1
            current_date += timedelta(days=1)
        return business_days

    @api.depends('date_from', 'date_to', 'holiday_status_id.include_business_days', 'employee_id')
    def _compute_duration(self):
        """Calcular duración según si incluye días hábiles o todos los días calendario."""
        for leave in self:
            if leave.date_from and leave.date_to:
                start = leave.date_from.date() if hasattr(leave.date_from, 'date') else leave.date_from
                end = leave.date_to.date() if hasattr(leave.date_to, 'date') else leave.date_to
                
                # Verificar si debe contar solo días hábiles
                if leave.holiday_status_id and leave.holiday_status_id.include_business_days:
                    # Contar solo días hábiles excluyendo fines de semana Y feriados
                    leave.number_of_days = leave._calculate_business_days_excluding_holidays(
                        start, end, leave.employee_id
                    )
                else:
                    # Contar todos los días calendario (incluyendo fines de semana)
                    leave.number_of_days = (end - start).days + 1
                
                leave.number_of_hours = leave.number_of_days * 24
            else:
                leave.number_of_days = 0
                leave.number_of_hours = 0

    @api.model
    def create(self, vals):
        if vals.get("date_to"):
            dt = fields.Datetime.to_datetime(vals["date_to"])
            vals["date_to"] = datetime.combine(dt.date(), time(23, 59, 59))
        return super().create(vals)

    def write(self, vals):
        if vals.get("date_to"):
            dt = fields.Datetime.to_datetime(vals["date_to"])
            vals["date_to"] = datetime.combine(dt.date(), time(23, 59, 59))
        return super().write(vals)

class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    include_business_days = fields.Boolean(
        string='Incluir Días Hábiles',
        help='Indica si este tipo de ausencia es solo para dias hábiles.',
        default=False,
    )

