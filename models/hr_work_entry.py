from odoo import models, fields, api
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta

class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    duration = fields.Float(string="Duración (horas)", readonly=False, help="Duración manual en horas")
    date_stop = fields.Datetime(string='Hasta', readonly=False)
    months_hours = fields.Float(string="Horas del mes", help="Horas trabajadas en el mes")

    @api.depends('date_stop', 'date_start')
    def _compute_duration(self):
        for entry in self:
            if entry.date_start and entry.date_stop:
                duration = (entry.date_stop - entry.date_start).total_seconds() / 3600
                entry.duration = round(duration, 2)

    @api.depends('date_start', 'duration')
    def _compute_date_stop(self):
        for entry in self:
            if entry.date_start and entry.duration:
                entry.date_stop = entry.date_start + timedelta(hours=entry.duration)

    def action_generate_monthly_entries(self):
        """Generar entradas de trabajo para todo el mes basado en months_hours"""
        for record in self:
            if not record.months_hours or record.months_hours <= 0:
                continue

            if not record.date_start:
                continue

            # Obtener el mes de la fecha de inicio
            start_date = record.date_start.date()
            month_start = start_date.replace(day=1)
            month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)

            # Calcular días laborales del mes (lunes a viernes)
            working_days = []
            current_date = month_start
            while current_date <= month_end:
                # 0=lunes, 6=domingo - días laborales son 0-4 (lunes a viernes)
                if current_date.weekday() < 5:
                    working_days.append(current_date)
                current_date += timedelta(days=1)

            if not working_days:
                continue

            # Calcular horas por día (permitir jornadas más largas para compensar no trabajar fines de semana)
            total_working_days = len(working_days)
            hours_per_day = record.months_hours / total_working_days

            # Horario estándar: 9:00 AM - permitir hasta 12 horas por día si es necesario
            start_hour = 9
            
            # Validar que no exceda las 12 horas por día (jornada máxima razonable)
            max_hours_per_day = 12
            if hours_per_day > max_hours_per_day:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error: Demasiadas horas',
                        'message': f'No se puede distribuir {record.months_hours} horas en {total_working_days} días laborales. Esto requeriría {hours_per_day:.2f} horas por día (máximo permitido: {max_hours_per_day} horas).',
                        'type': 'danger',
                        'sticky': True,
                    }
                }
            
            # Eliminar entradas existentes del empleado para este mes (excepto la actual si es del mes)
            domain_delete = [
                ('employee_id', '=', record.employee_id.id),
                ('date_start', '>=', datetime.combine(month_start, datetime.min.time())),
                ('date_start', '<=', datetime.combine(month_end, datetime.max.time())),
                ('work_entry_type_id', '=', self.env.ref('hr_work_entry.work_entry_type_attendance').id),
                ('id', '!=', record.id)
            ]
            existing_entries = self.env['hr.work.entry'].search(domain_delete)
            existing_entries.unlink()

            # Crear nuevas entradas para cada día laboral
            entries_to_create = []
            for work_date in working_days:
                # Saltar si es el día de la entrada actual
                if work_date == start_date:
                    # Actualizar la entrada actual
                    record.write({
                        'date_start': datetime.combine(work_date, datetime.min.time().replace(hour=start_hour)),
                        'date_stop': datetime.combine(work_date, datetime.min.time().replace(hour=start_hour)) + timedelta(hours=hours_per_day),
                        'duration': hours_per_day,
                    })
                    continue

                start_datetime = datetime.combine(work_date, datetime.min.time().replace(hour=start_hour))
                end_datetime = start_datetime + timedelta(hours=hours_per_day)
                
                entry_vals = {
                    'name': f'{record.employee_id.name}: {work_date.strftime("%d/%m/%Y")}',
                    'employee_id': record.employee_id.id,
                    'date_start': start_datetime,
                    'date_stop': end_datetime,
                    'duration': hours_per_day,
                    'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
                    'state': 'draft',
                    'company_id': record.employee_id.company_id.id,
                }
                entries_to_create.append(entry_vals)

            # Crear todas las entradas
            created_entries = self.env['hr.work.entry'].create(entries_to_create)
            
            # Calcular hora de salida para mostrar en el mensaje
            end_hour = start_hour + hours_per_day
            end_hour_int = int(end_hour)
            end_minutes = int((end_hour - end_hour_int) * 60)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Entradas del mes generadas',
                    'message': f'Se crearon {len(created_entries)} entradas adicionales + 1 actualizada = {total_working_days} días laborales.\nHorario: 9:00 AM - {end_hour_int:02d}:{end_minutes:02d} PM ({hours_per_day:.2f} horas/día)\nTotal mensual: {record.months_hours} horas',
                    'type': 'success',
                    'sticky': True,
                }
            }

    @api.model
    def create(self, vals):
        """Override create para auto-generar entradas si tiene months_hours"""
        record = super().create(vals)
        
        # Si se crea con months_hours, generar automáticamente
        if record.months_hours and record.months_hours > 0:
            record.action_generate_monthly_entries()
        
        return record
