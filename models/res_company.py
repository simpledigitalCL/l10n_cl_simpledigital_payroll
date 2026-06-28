import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
class ResCompany(models.Model):
    _inherit = 'res.company'

    gratification_enabled = fields.Boolean(
        string='Habilitar Gratificación',
        default=False,
        help="Active esta opción si la empresa debe pagar gratificación"
    )

    gratification_type = fields.Selection([
        ('47', 'Art. 47 - Gratificación proporcional anual'),
        ('50', 'Art. 50 - Gratificación proporcional mensual'),
    ], string='Tipo de Gratificación Legal', default='47', help="Seleccione el tipo de gratificación que la empresa aplica según la legislación chilena.")
    
    
    gratification_percentage = fields.Float(
        string='Porcentaje de Gratificación (%)',
        default=30.0,
        help="Porcentaje de gratificación a aplicar"
    )
    
    gratification_base = fields.Selection([
        ('basic', 'Sueldo Base'),
    ], string='Base de Cálculo', default='basic',
        help="Base sobre la cual se calcula la gratificación")
    
    gratification_period = fields.Selection([
        ('monthly', 'Mensual'),
        ('biannual', 'Semestral'),
        ('annual', 'Anual'),
    ], string='Período de Gratificación', default='biannual',
        help="Frecuencia de pago de la gratificación")
    
    gratification_payment_date = fields.Date(
        string='Fecha de Pago',
        help="Fecha programada para el pago de gratificación"
    )
        
    # Campo para ganancia neta anual
    annual_net_profit = fields.Monetary(
        string='Ganancia Neta Anual',
        help="Ganancia neta anual para cálculo de gratificación",
        currency_field='currency_id'
    )

    # Campos instituciones relacionadas
    caja_compensacion = fields.Selection(
        string="Caja de Compensación",
        help="Selecciona la caja de compensación asociada a este indicador.",
        selection=[
            ('00', 'Sin CCAF'),
            ('01', 'Los Andes'),
            ('02', 'La Araucana'),
            ('03', 'Los Héroes'),
            ('06', '18 de Septiembre'),
        ],
        default='00'
    )

    has_mutual = fields.Boolean(
        string="Tiene Mutual",
        help="Indica si la empresa tiene una institución de seguridad social asociada."
    )

    mutual = fields.Selection(
        string="Mutual de Seguridad",
        help="Selecciona la mutual de seguridad asociada a esta empresa.",
        selection=[
            ('00', 'Sin Mutual - ISL'),
            ('01', 'Asociación Chilena de Seguridad (ACHS)'),
            ('02', 'Mutual de Seguridad CCHC'),
            ('03', 'Instituto de Seguridad del Trabajo I.S.T.'),
        ]
    )

    rate_base = fields.Float(
        string = "Tasa Base",
        readonly=True,
        default=0.93,
        help=(
            "Porcentaje de cotización obligatoria para accidentes del trabajo y enfermedades profesionales "
            "(Ley 16.744), aplicado sobre la renta imponible de cada trabajador afiliado a Mutual. "
            "Esta tasa base es fijada por la ley y puede ser modificada por cambios normativos. "
            "Revise periódicamente la normativa vigente, ya que ajustes futuros deben ser reflejados en este campo para mantener el cumplimiento legal."
        )
    )

    rate_additional = fields.Float(
        default=0.0,
        string="Tasa Adicional",
        help=(
            "Porcentaje adicional de cotización para accidentes del trabajo y enfermedades profesionales, "
            "aplicado sobre la renta imponible de cada trabajador afiliado a Mutual. "
            "Este porcentaje se suma a la tasa base de la mutual y se calcula sobre la renta imponible del trabajador. "
            "Ejemplo: si se ingresa 0.5, se aplicará un 0.5% adicional a la cotización mutual estándar. "
        )
    )
    
    # Método para obtener ganancia neta desde contabilidad
    def get_annual_net_profit_from_accounting(self, year=None):
        _logger.info("=== INICIANDO get_annual_net_profit_from_accounting ===")
        if not year:
            year = fields.Date.today().year
    
        # Fechas para el período anual
        date_from = f'{year}-01-01'
        date_to = f'{year}-12-31'
    
        def sum_accounts(domain, label):
            moves = self.env['account.move.line'].search([
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('company_id', '=', self.id),
                ('move_id.state', '=', 'posted')
            ] + domain)
            total = sum(moves.mapped(lambda m: m.credit - m.debit))
            _logger.info(f"{label}: {total}")
            return total
    
        # Suma por tipo de cuenta (usa los mismos criterios del reporte)
        rev = sum_accounts([('account_id.account_type', '=', 'income')], "REV (Ingresos)")
        cos = sum_accounts([('account_id.account_type', '=', 'expense_direct_cost')], "COS (Costos)")
        exp = sum_accounts([('account_id.account_type', '=', 'expense')], "EXP (Gastos)")
        oexp = sum_accounts([('account_id.account_type', '=', 'expense_other')], "OEXP (Otros gastos)")
        grp = rev + cos
    
        # Mismo cálculo que tu reporte
        net_profit = grp + exp
        _logger.info(f"Ganancia neta calculada (método reporte): {net_profit}")
    
        return net_profit

    
    def action_get_annual_net_profit(self):
        """
        Acción del botón para obtener ganancia neta desde contabilidad
        """
        _logger.info(f"=== INICIANDO action_get_annual_net_profit ===")
        _logger.info(f"Empresa: {self.name} (ID: {self.id})")
        
        for record in self:
            try:
                # Obtener el año actual
                current_year = fields.Date.today().year
                _logger.info(f"Año actual: {current_year}")
                
                # Intentar obtener desde contabilidad
                _logger.info("Llamando a get_annual_net_profit_from_accounting...")
                net_profit = record.get_annual_net_profit_from_accounting(current_year)
                _logger.info(f"Resultado obtenido: ${net_profit:,.0f}")
                
                if net_profit > 0:
                    record.annual_net_profit = net_profit
                    _logger.info(f"Campo annual_net_profit actualizado: ${net_profit:,.0f}")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Éxito',
                            'message': f'Ganancia neta obtenida: ${net_profit:,.0f}',
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    _logger.warning("No se pudo obtener ganancia neta válida")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Información',
                            'message': 'No se pudo obtener la ganancia neta desde contabilidad. Configure el valor manualmente.',
                            'type': 'warning',
                            'sticky': False,
                        }
                    }
                    
            except Exception as e:
                _logger.error(f"Error en action_get_annual_net_profit: {str(e)}")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'Error al obtener ganancia neta: {str(e)}',
                        'type': 'danger',
                        'sticky': False,
                    }
                }
