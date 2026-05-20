from odoo import models, fields, api
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import base64

class HrLibroRemuneracionesWizard(models.TransientModel):
    _name = 'hr.libro.remuneraciones.wizard'
    _description = 'Wizard para exportar Libro de Remuneraciones CSV'

    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string='Fecha Desde',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1)
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=lambda self: fields.Date.today()
    )

    # Campos adicionales específicos para el libro de remuneraciones
    include_header = fields.Boolean(
        string='Incluir Encabezados',
        default=True,
        help='Incluir encabezados de columnas en el CSV'
    )
    
    @api.onchange('date_from')
    def _onchange_date_from(self):
        """Cuando cambia la fecha desde, ajustar la fecha hasta al último día del mes"""
        if self.date_from:
            # Calcular el último día del mes usando relativedelta (más confiable)
            last_day_of_month = self.date_from + relativedelta(day=31)
            self.date_to = last_day_of_month

    def action_generate_csv(self):
        """Generar y descargar el archivo CSV del Libro de Remuneraciones"""
        # Validaciones
        if self.date_from > self.date_to:
            raise models.ValidationError('La fecha desde no puede ser mayor que la fecha hasta')

        # Generar el CSV usando el controlador
        url = f'/libro_remuneraciones/csv?date_from={self.date_from}&date_to={self.date_to}&include_header={self.include_header}&company_id={self.company_id.id}'
        
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_preview(self):
        """Vista previa de los datos que se incluirán en el CSV"""
        payslips = self._get_payslips()
        
        if not payslips:
            raise models.ValidationError('No se encontraron liquidaciones para el período seleccionado')
        
        return {
            'name': 'Vista Previa - Libro de Remuneraciones',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payslips.ids)],
            'context': {
                'search_default_group_by_employee': 1,
            },
            'target': 'new',
        }

    def _get_payslips(self):
        """Obtener las liquidaciones del período seleccionado"""
        domain = [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['done', 'paid'])
        ]
        return self.env['hr.payslip'].search(domain)
