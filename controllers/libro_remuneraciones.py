import csv
import io
from datetime import datetime, date
from odoo import http
from odoo.http import request, Response
import logging

_logger = logging.getLogger(__name__)

# https://static-content.api.dirtrab.cl/dt-docs/lre/lre_suplemento.pdf
class LibroRemuneracionesController(http.Controller):

    @http.route('/libro_remuneraciones/csv', type='http', auth='user', methods=['GET'])
    def export_libro_remuneraciones_csv(self, date_from, date_to, include_header='True', company_id=None, **kwargs):
        """
        Endpoint para exportar el Libro de Remuneraciones en formato CSV
        """
        try:
            # Convertir parámetros
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            include_header = include_header.lower() == 'true'

            # Usar la empresa indicada por parámetro; si no, la empresa de sesión
            if company_id:
                company = request.env['res.company'].sudo().browse(int(company_id))
                if not company.exists():
                    return request.make_response('Empresa no encontrada', headers={'Content-Type': 'text/plain'})
            else:
                company = request.env.company
            if not company:
                return request.make_response('No se pudo determinar la empresa actual', headers={'Content-Type': 'text/plain'})

            # Obtener liquidaciones del período
            payslips = self._get_payslips(date_from, date_to, company.id)
            
            if not payslips:
                return request.make_response('No se encontraron liquidaciones para el período seleccionado', 
                                           headers={'Content-Type': 'text/plain'})

            # Generar CSV (sin formato de moneda, usar formato estándar)
            csv_content = self._generate_csv_content(payslips, include_header)
            
            # Log del contenido CSV para debugging
            # _logger.info(f"=== LIBRO DE REMUNERACIONES CSV ===")
            # _logger.info(f"Período: {date_from} - {date_to}")
            # _logger.info(f"CSV Content:\n{csv_content}")
            # _logger.info(f"=== FIN LIBRO DE REMUNERACIONES CSV ===")
            
            # Preparar nombre del archivo
            filename = f"libro_remuneraciones_{company.name}_{date_from.strftime('%Y%m')}.csv"
            filename = filename.replace(' ', '_').replace('/', '_')

            # Codificar el contenido a ANSI (Windows-1252/cp1252)
            # Usar 'replace' para reemplazar caracteres no compatibles
            csv_content_ansi = csv_content.encode('cp1252', errors='replace')

            # Configurar headers para descarga con ANSI
            headers = [
                ('Content-Type', 'text/csv; charset=windows-1252'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', len(csv_content_ansi)),
                ('Cache-Control', 'no-cache'),
                ('Pragma', 'no-cache'),
            ]

            return request.make_response(csv_content_ansi, headers=headers)

        except Exception as e:
            return request.make_response(f'Error: {str(e)}', headers={'Content-Type': 'text/plain'})

    def _get_payslips(self, date_from, date_to, company_id):
        """Obtener liquidaciones del período"""
        domain = [
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('company_id', '=', company_id),
            ('state', 'in', ['done', 'paid'])
        ]
        return request.env['hr.payslip'].sudo().search(domain, order='employee_id, date_from')

    def _get_payslip_lines(self, payslip, rule_codes=None):
        """
        Obtener líneas de liquidaciones filtradas por código(s) de regla salarial.
        :param payslip: objeto hr.payslip
        :param rule_codes: Lista de códigos de regla salarial (ej: ["COLA", "MOV"])
        :return: Suma total de las líneas que coinciden con los códigos
        """
        try:
            # Obtener líneas directamente del payslip
            if not payslip or not hasattr(payslip, 'line_ids'):
                return 0

            lines = payslip.line_ids

            # Filtrar por códigos si se especifican
            if rule_codes:
                if isinstance(rule_codes, str):
                    rule_codes = [rule_codes]
                lines = lines.filtered(lambda l: l.code in rule_codes)

            # Sumar los totales
            return int(sum(line.total for line in lines))

        except Exception as e:
            _logger.error(f"Error al obtener líneas de nómina: {str(e)}")
            return 0

    def _get_termination_causal(self, employee_id, date_from, date_to):
        """Obtener la causal de término registrada en el empleado"""
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if employee.exists() and employee.causal_contract_end_id:
            return employee.causal_contract_end_id.code
        return 

    def _get_days_by_work_entry_code(self, payslip, work_entry_code):
        """
        Función genérica para obtener días desde hr.payslip.worked_days por código.
        
        :param payslip: objeto hr.payslip
        :param work_entry_code: código del tipo de entrada de trabajo (ej: "WORK100", "LEAVECL120", "LIC")
        :return: número de días como entero
        """
        if not payslip or not work_entry_code:
            return 0
    
        # Buscar la línea con el código especificado
        for line in payslip.worked_days_line_ids:
            code = line.work_entry_type_id.code or ""
            if code == work_entry_code:
                # Retornar el valor exacto de number_of_days
                return int(line.number_of_days or 0)
    
        # Si no se encuentra el código, retornar 0
        return 0
    
    def _get_real_worked_days_from_payslip(self, payslip):
        """Retorna los días trabajados Previred desde la liquidación."""
        return payslip._dias_trabajados_previred() if payslip else 0
    
    def _get_absent_days(self, payslip):
        """Cuenta días de licencias/faltas (que no son trabajados)."""
        absent = 0
        for line in payslip.worked_days_line_ids:
            code = line.work_entry_type_id.code or ""
            if code in ["LIC", "FALT","OUT", "LEAVE90"]:
                absent += line.number_of_days or 0
        return absent

    def _calculate_sick_leave_days(self, payslip):
        """
        Calcular días de licencia médica en el mes.
        Utiliza el código LIC del work_entry_type.
        """
        return self._get_days_by_work_entry_code(payslip, "LIC") 

    def _calculate_vacation_days(self, payslip):
        """
        Calcular días de vacaciones en el mes.
        Utiliza el código LEAVECL120 del work_entry_type.
        """
        return self._get_days_by_work_entry_code(payslip, "LEAVECL120")

    def _get_movement_rule_codes(self, name_keywords):
        """
        Devuelve los códigos de regla salarial (MOV_<id>) de los tipos de movimiento
        cuyo nombre contiene alguno de los keywords dados.

        Cada hr.employee.movement.type auto-genera una regla salarial MOV_<id> que ya
        suma sus montos en la liquidación (ver models/hr_employee_movement.py). Esto
        permite que el LRE sume esas líneas de regla -en lugar de releer los movimientos
        en crudo- junto con la regla base correspondiente.
        """
        try:
            if not name_keywords:
                return []
            domain = ['|'] * (len(name_keywords) - 1)
            for kw in name_keywords:
                domain.append(('name', 'ilike', kw))
            types = request.env['hr.employee.movement.type'].sudo().search(domain)
            return [t.salary_rule_id.code for t in types if t.salary_rule_id and t.salary_rule_id.code]
        except Exception as e:
            _logger.error(f"Error obteniendo códigos de regla de movimiento {name_keywords}: {str(e)}")
            return []

    def _calculate_overtime_salary(self, payslip, contract):
        """
        Campo 41 (2102 Sobresueldo): suma de las líneas de regla salarial de horas extras.

        Fuente única = reglas salariales ya presentes en la liquidación:
          - HE            -> horas extras pactadas del contrato
          - MOV_<id>      -> tipos de movimiento de horas extras no pactadas

        Se leen las líneas de la liquidación (no se recalcula), por lo que el monto coincide
        exactamente con lo computado en el líquido y refleja cualquier ajuste a la regla.
        """
        codes = ["HE"] + self._get_movement_rule_codes(['horas extras', 'extra'])
        return int(self._get_payslip_lines(payslip, codes) or 0)

    def _calculate_commissions(self, payslip):
        """
            - Calcular comisiones para el campo 42 (2103 Comisiones):
            - Buscar los tipo de movimientos que tengan comision_ok como True
            - Se deben sumar todos los tipo de movimientos que tenga comision_ok como True
        """
        try:
            employee = payslip.employee_id
            from_date = payslip.date_from
            to_date = payslip.date_to
            
            # Buscar los movimientos que tengan el tipo de movimiento comision_ok como True
            lines = request.env['hr.employee.movement.line'].sudo().search([
                ('employee_id', '=', employee.id),
                ('movement_id.date', '>=', from_date),
                ('movement_id.date', '<=', to_date),
                ('movement_type_id.comision_ok', '=', True),
            ])  
   
            total_commissions = 0.0
            
            for line in lines:
                total_commissions += line.amount or 0.0
            
            return int(total_commissions)
                
        except Exception as e:
            return 0

    def _calculate_aguinaldo(self, payslip):
        """
            Calcular aguinaldo para el campo 49 (2110 Aguinaldo):
            - Busca movimientos del empleado que contengan el tipo de movimiento como aguinaldo_ok en True
        """
        try:
            employee = payslip.employee_id
            from_date = payslip.date_from
            to_date = payslip.date_to

            # Buscar líneas de movimientos que contengan "aguinaldo_ok" en el tipo de movimiento
            lines = request.env['hr.employee.movement.line'].sudo().search([
                ('employee_id', '=', employee.id),
                ('movement_id.date', '>=', from_date),
                ('movement_id.date', '<=', to_date),
                ('movement_type_id.aguinaldo_ok', '=', True),
            ])
            
            total_aguinaldo = 0.0
            
            for line in lines:
                total_aguinaldo += line.amount or 0.0
            
            return int(total_aguinaldo)
                
        except Exception as e:
            return 0  

    def _calculate_bonuses(self, payslip):
        """
        Calcular bonos para el campo 50 (2111 Bonos u otras remuneraciones fijas mensuales):
        - Busca movimientos del empleado que bono_ok en el tipo de movimiento para el período de la liquidación
        """
        try:
            employee = payslip.employee_id
            from_date = payslip.date_from
            to_date = payslip.date_to
            
            # Buscar líneas de movimientos que contengan bono_ok en el tipo de movimiento
            lines = request.env['hr.employee.movement.line'].sudo().search([
                ('employee_id', '=', employee.id),
                ('movement_id.date', '>=', from_date),
                ('movement_id.date', '<=', to_date),
                ('movement_type_id.bono_ok', '=', True),
            ])
            
            total_bonuses = 0.0
            
            for line in lines:
                total_bonuses += line.amount or 0.0
            
            return int(total_bonuses)
                
        except Exception as e:
            return 0  

    def _calculate_viaticos(self, payslip):
        """
        Campo 71 (2303 Viáticos total mensual): suma de las líneas de regla salarial de viáticos.

        Fuente única = reglas salariales ya presentes en la liquidación:
          - VIATICO_FIJO  -> viático fijo del contrato
          - MOV_<id>      -> tipos de movimiento de viáticos

        Se leen las líneas de la liquidación (no se recalcula), evitando doble conteo con las
        reglas MOV_<id> que ya suman los movimientos en el líquido.
        """
        codes = ["VIATICO_FIJO"] + self._get_movement_rule_codes(['viatico'])
        return int(self._get_payslip_lines(payslip, codes) or 0)

    def _get_previred_indicator_value(self, payslip, field_name):
        """Return a field from previred.indicator for the payslip month."""
        try:
            if not payslip or not field_name:
                return 0

            year = payslip.date_from.year
            month = payslip.date_from.month
            period_start = date(year, month, 1)
            if month < 12:
                next_month = date(year, month + 1, 1)
            else:
                next_month = date(year + 1, 1, 1)

            indicator = request.env['previred.indicator'].sudo().search([
                ('date', '>=', period_start),
                ('date', '<', next_month)
            ], order='date desc', limit=1)

            if indicator and hasattr(indicator, field_name):
                return getattr(indicator, field_name) or 0

            return 0

        except Exception as e:
            _logger.error(f"Error obteniendo {field_name} desde indicadores Previred: {str(e)}")
            return 0

    def _calculate_aporte_empleador_apvc(self, payslip, total_haberes_imponibles_tributables):
        """
            Calcula el aporte APVC del empleador. Campo 4157
            Suma: aporte_contractual + EXP_VIDA + AFP_EMP
        """
        contract = getattr(payslip, 'contract_id', None)
        
        # Aporte contractual del empleador
        aporte_contractual = int(getattr(contract, 'cotizacion_apvc_empleador', 0) or 0)
        
        # Seguro de vida (EXP_VIDA)
        exp_vida = int(self._get_payslip_lines(payslip, ["EXP_VIDA"]) or 0)
        
        # Aporte AFP del empleador (AFP_EMP)
        afp_emp = int(self._get_payslip_lines(payslip, ["AFP_EMP"]) or 0)

        _logger.info(
            f"Aporte contractual: {aporte_contractual}, Exp. Vida: {exp_vida}, AFP_EMP: {afp_emp}"
        )
        return aporte_contractual + exp_vida + afp_emp

    def _get_gratification_limit_from_previred(self, payslip):
        """
            Obtener el tope de gratificación desde los indicadores Previred (IMM * 4.75)
        """
        try:
            # Buscar el indicador Previred por mes y año
            year = payslip.date_from.year
            month = payslip.date_from.month
            previred_indicator = request.env['previred.indicator'].sudo().search([
                ('date', '>=', date(year, month, 1)),
                ('date', '<', date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1))
            ], order='date desc', limit=1)
            
            if previred_indicator and hasattr(previred_indicator, 'trab_dependiente_independiente'):
                imm = previred_indicator.trab_dependiente_independiente or 0
                tope = imm * 4.75 / 12
                return tope
            else:
                _logger.warning(f"No se encontró indicador Previred válido para {month}/{year}")
                return 0
                
        except Exception as e:
            _logger.error(f"Error obteniendo tope de gratificación desde Previred: {str(e)}")
            return 0

    def _generate_csv_content(self, payslips, include_header):
        """Generar el contenido del CSV con codificación ANSI"""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        # Escribir encabezados si se solicita
        if include_header:
            headers = self._get_csv_headers()
            writer.writerow(headers)

        # Escribir datos de cada liquidación
        for payslip in payslips:
            row_data = self._get_payslip_row_data(payslip)
            writer.writerow(row_data)

        # Asegurar que el contenido esté en ANSI
        csv_content = output.getvalue()
        output.close()
        
        return csv_content
        
    def _get_ccaf_credit_deduction(self, payslip):
        """
            Campo 3110 - Crédito social CCAF
            Fuente: reglas salariales CCAF_CREDITO (crédito social) + CCAF_SEG_VIDA (seguro de vida).
            La regla salarial es la única fuente de verdad; así un ajuste en la regla se refleja
            automáticamente en el LRE y en el TXT de Previred.
        """
        return int(round(self._get_payslip_lines(payslip, ["CCAF_CREDITO", "CCAF_SEG_VIDA"]) or 0))

    def _get_ccaf_credit_saving (self, payslip):
        """
            Campo 119 - 3182 Crédito cooperativas de ahorro
            Fuente: regla salarial CCAF_AHORRO (programa de ahorro / leasing).
        """
        return int(round(self._get_payslip_lines(payslip, ["CCAF_AHORRO"]) or 0))

    def _get_ccaf_credit_others(self, payslip):
        """
            Campo 3183 - Otros créditos CCAF
            Fuente: regla salarial CCAF_OTROS.
        """
        return int(round(self._get_payslip_lines(payslip, ["CCAF_OTROS"]) or 0))

    def _get_descuentos_anticipos_prestamos(self, payslip):
        """
            Calculo campo 125 - 3188 Descuentos por anticipos y préstamos
            Usar el modelo hr.employee.movement buscando los que tienes hr.employee.movement.type "Anticipo" o "Préstamos"
            Filtrar por mes y año del payslip
        """
        try:
            employee = payslip.employee_id
            from_date = payslip.date_from
            to_date = payslip.date_to
            
            # Buscar líneas de movimientos que contengan "anticipo" o "préstamo" en el tipo de movimiento
            lines = request.env['hr.employee.movement.line'].sudo().search([
                ('employee_id', '=', employee.id),
                ('movement_id.date', '>=', from_date),
                ('movement_id.date', '<=', to_date),
                '|',
                ('movement_type_id.name', 'ilike', 'anticipo'),
                ('movement_type_id.name', 'ilike', 'préstamo'),
            ])
            
            total_descuentos = 0.0
            
            for line in lines:
                total_descuentos += line.amount or 0.0
            
            return int(total_descuentos)
                
        except Exception as e:
            _logger.error(f"Error calculando descuentos por anticipos y préstamos para payslip {payslip.id}: {str(e)}")
            return 0
              
    def _calculate_otros_descuentos_movimientos(self, payslip):
        """
            Función para calcular otros descuentos desde los hr.employee.movement
            - Filtrar por los hr.employee.movement.type que tengan el otros_descuentos_ok como True
            - Filtrar por el date correspondiente 
        """
        try:
            employee = payslip.employee_id
            from_date = payslip.date_from
            to_date = payslip.date_to
            
            # Buscar líneas de movimientos que contengan otros_descuentos_ok como True
            lines = request.env['hr.employee.movement.line'].sudo().search([
                ('employee_id', '=', employee.id),
                ('movement_id.date', '>=', from_date),
                ('movement_id.date', '<=', to_date),
                ('movement_type_id.otros_descuentos_ok', '=', True),
            ])

            total_otros_descuentos_movimientos = 0.0

            for line in lines:
                total_otros_descuentos_movimientos += line.amount or 0.0

            return int(total_otros_descuentos_movimientos)

        except Exception as e:
            return 0  

    def _get_csv_headers(self):
        """Definir encabezados del CSV"""
        return [
            'Rut trabajador(1101)',
            'Fecha inicio contrato(1102)',
            'Fecha término de contrato(1103)',
            'Causal término de contrato(1104)',
            'Región prestación de servicios(1105)',
            'Comuna prestación de servicios(1106)',
            'Tipo impuesto a la renta(1170)',
            'Técnico extranjero exención cot. previsionales(1146)',
            'Código tipo de jornada(1107)',
            'Persona con Discapacidad - Pensionado por Invalidez(1108)',
            'Pensionado por vejez(1109)',
            'AFP(1141)',
            'IPS (ExINP)(1142)',
            'FONASA - ISAPRE(1143)',
            'AFC(1151)',
            'CCAF(1110)',
            'Org. administrador ley 16.744(1152)',
            'Nro cargas familiares legales autorizadas(1111)',
            'Nro de cargas familiares maternales(1112)',
            'Nro de cargas familiares invalidez(1113)',
            'Tramo asignación familiar(1114)',
            'Rut org sindical 1(1171)',
            'Rut org sindical 2(1172)',
            'Rut org sindical 3(1173)',
            'Rut org sindical 4(1174)',
            'Rut org sindical 5(1175)',
            'Rut org sindical 6(1176)',
            'Rut org sindical 7(1177)',
            'Rut org sindical 8(1178)',
            'Rut org sindical 9(1179)',
            'Rut org sindical 10(1180)',
            'Nro días trabajados en el mes(1115)',
            'Nro días de licencia médica en el mes(1116)',
            'Nro días de vacaciones en el mes(1117)',
            'Subsidio trabajador joven(1118)',
            'Puesto Trabajo Pesado(1154)',
            'APVI(1155)',
            'APVC(1157)',
            'Indemnización a todo evento(1131)',
            'Tasa indemnización a todo evento(1132)',
            'Sueldo(2101)',
            'Sobresueldo(2102)',
            'Comisiones(2103)',
            'Semana corrida(2104)',
            'Participación(2105)',
            'Gratificación(2106)',
            'Recargo 30% día domingo(2107)',
            'Remun. variable pagada en vacaciones(2108)',
            'Remun. variable pagada en clausura(2109)',
            'Aguinaldo(2110)',
            'Bonos u otras remun. fijas mensuales(2111)',
            'Tratos(2112)',
            'Bonos u otras remun. variables mensuales o superiores a un mes(2113)',
            'Ejercicio opción no pactada en contrato(2114)',
            'Beneficios en especie constitutivos de remun(2115)',
            'Remuneraciones bimestrales(2116)',
            'Remuneraciones trimestrales(2117)',
            'Remuneraciones cuatrimestral(2118)',
            'Remuneraciones semestrales(2119)',
            'Remuneraciones anuales(2120)',
            'Participación anual(2121)',
            'Gratificación anual(2122)',
            'Otras remuneraciones superiores a un mes(2123)',
            'Pago por horas de trabajo sindical(2124)',
            'Sueldo empresarial (2161)',
            'Subsidio por incapacidad laboral por licencia médica(2201)',
            'Beca de estudio(2202)',
            'Gratificaciones de zona(2203)',
            'Otros ingresos no constitutivos de renta(2204)',
            'Colación(2301)',
            'Movilización(2302)',
            'Viáticos(2303)',
            'Asignación de pérdida de caja(2304)',
            'Asignación de desgaste herramienta(2305)',
            'Asignación familiar legal(2311)',
            'Gastos por causa del trabajo(2306)',
            'Gastos por cambio de residencia(2307)',
            'Sala cuna(2308)',
            'Asignación trabajo a distancia o teletrabajo(2309)',
            'Depósito convenido hasta UF 900(2347)',
            'Alojamiento por razones de trabajo(2310)',
            'Asignación de traslación(2312)',
            'Indemnización por feriado legal(2313)',
            'Indemnización años de servicio(2314)',
            'Indemnización sustitutiva del aviso previo(2315)',
            'Indemnización fuero maternal(2316)',
            'Pago indemnización a todo evento(2331)',
            'Indemnizaciones voluntarias tributables(2417)',
            'Indemnizaciones contractuales tributables(2418)',
            'Cotización obligatoria previsional (AFP o IPS)(3141)',
            'Cotización obligatoria salud 7%(3143)',
            'Cotización voluntaria para salud(3144)',
            'Cotización AFC - trabajador(3151)',
            'Cotizaciones técnico extranjero para seguridad social fuera de Chile(3146)',
            'Descuento depósito convenido hasta UF 900 anual(3147)',
            'Cotización APVi Mod A(3155)',
            'Cotización APVi Mod B hasta UF50(3156)',
            'Cotización APVc Mod A(3157)',
            'Cotización APVc Mod B hasta UF50(3158)',
            'Impuesto retenido por remuneraciones(3161)',
            'Impuesto retenido por indemnizaciones(3162)',
            'Mayor retención de impuestos solicitada por el trabajador(3163)',
            'Impuesto retenido por reliquidación remun. devengadas otros períodos(3164)',
            'Diferencia impuesto reliquidación remun. devengadas en este período(3165)',
            'Retención préstamo clase media 2020 (Ley 21.252) (3166)',
            'Rebaja zona extrema DL 889 (3167)',
            'Cuota sindical 1(3171)',
            'Cuota sindical 2(3172)',
            'Cuota sindical 3(3173)',
            'Cuota sindical 4(3174)',
            'Cuota sindical 5(3175)',
            'Cuota sindical 6(3176)',
            'Cuota sindical 7(3177)',
            'Cuota sindical 8(3178)',
            'Cuota sindical 9(3179)',
            'Cuota sindical 10(3180)',
            'Crédito social CCAF(3110)',
            'Cuota vivienda o educación(3181)',
            'Crédito cooperativas de ahorro(3182)',
            'Otros descuentos autorizados y solicitados por el trabajador(3183)',
            'Cotización adicional trabajo pesado - trabajador(3154)',
            'Donaciones culturales y de reconstrucción(3184)',
            'Otros descuentos(3185)',
            'Pensiones de alimentos(3186)',
            'Descuento mujer casada(3187)',
            'Descuentos por anticipos y préstamos(3188)',
            'AFC - Aporte empleador(4151)',
            'Aporte empleador seguro accidentes del trabajo y Ley SANNA(4152)',
            'Aporte empleador indemnización a todo evento(4131)',
            'Aporte adicional trabajo pesado - empleador(4154)',
            'Aporte empleador seguro invalidez y sobrevivencia(4155)',
            'APVC - Aporte Empleador(4157)',
            'Total haberes(5201)',
            'Total haberes imponibles y tributables(5210)',
            'Total haberes imponibles no tributables(5220)',
            'Total haberes no imponibles y no tributables(5230)',
            'Total haberes no imponibles y tributables(5240)',
            'Total descuentos(5301)',
            'Total descuentos impuestos a las remuneraciones(5361)',
            'Total descuentos impuestos por indemnizaciones(5362)',
            'Total descuentos por cotizaciones del trabajador(5341)',
            'Total otros descuentos(5302)',
            'Total aportes empleador(5410)',
            'Total líquido(5501)',
            'Total indemnizaciones(5502)',
            'Total indemnizaciones tributables(5564)',
            'Total indemnizaciones no tributables(5565)'
        ]

    def _get_payslip_row_data(self, payslip):
        """Obtener datos de una fila para una liquidación"""
        employee = payslip.employee_id
        contract = payslip.contract_id
        
        # Campo 1 - 1101 Rut trabajador - INT - OBLIGATORIO
        rut = employee.identification_id
        # Quitar puntos del RUT, mantener solo el guión
        if rut:
            rut = rut.replace('.', '')

        # Campo 2  - 1102 Fecha inicio contrato - DATE - OBLIGATORIO
        date_start = contract.date_start if contract else '0'

        # Campo 3 - 1103 Fecha de término de contrato - DATE - OPCIONAL
        date_end = contract.date_end if contract else ''

        # Campo 4 - 1104 Causal de término del contrato - Tinyint - OPCIONAL
        termination_causal = self._get_termination_causal(
            employee.id, 
            payslip.date_from, 
            payslip.date_to
        ) 
        
        # Campo 5 - 1105 Región de prestación de los servicios - tinyint - OBLIGATORIO
        region_code = ''
        if employee.private_state_id:
            # Extraer el código de la región (ej: "01" de "base.state_cl_01")
            raw_region_code = employee.private_state_id.code or ''
            # Convertir a string sin ceros a la izquierda para cumplir formato DT
            region_code = raw_region_code.lstrip('0') or '0'

        # Campo 6 - 1106 Comuna de prestación de los servicios - Tinyint - OBLIGATORIO
        commune_code = ''
        if employee.hr_commune:
            commune_code = employee.hr_commune.codigo or ''

        # Campo 7 - 1170 Tipo de impuesto a la renta - Tinyint - OBLIGATORIO
        income_tax_type = contract.income_tax_type if contract else '1'

        # Campo 8 - 1146 Técnico extranjero exención de cotizaciones previsionales (ley 18.156) - tinyint - OBLIGATORIO
        country = employee.country_id
        nationality = '0' if country and country.code == 'CL' else '1'

        # Campo 9 - 1107 Código tipo de jornada - tinyint - OBLIGATORIO
        work_schedule_code = contract.work_schedule_id if contract else '101'

        # Campo 10 - 1108 Persona con discapacidad/pensionado por invalidez - tinyint - OBLIGATORIO
        disability_code = '1' if employee.has_disability else '0'

        # Campo 11 - 1109 Pensionado por vejez - tinyint - OBLIGATORIO
        retired_elderly_code = '1' if contract.is_retired_elderly else '0'

        # Campo 12 - 1141 AFP - tinyint - OBLIGATORIO
        afp_option = contract.afp_option if contract else ''
        if afp_option and ' - ' in afp_option:
            afp_code_libro = afp_option.split(' - ')[1]
        else:
            afp_code_libro = '100'  # Default: No Cotiza AFP

        # Campo 13 - 1142 IPS (ExINP) - tinyint - OBLIGATORIO
        ips_code_libro = '0'  

        # Campo 14 - 1143 FONASA / ISAPRE - tinyint - OBLIGATORIO
        health_institution = contract.health_institution if contract else ''
        # Extraer la segunda parte del código (después del guión) para Libro de Remuneraciones
        if health_institution and ' - ' in health_institution:
            health_code_libro = health_institution.split(' - ')[1]
        else:
            health_code_libro = '99'  # Default: Sin Isapre

        # Campo 15 - 1151 AFC - tinyint - OBLIGATORIO
        afc_enrolled = contract.afc_enrolled if contract else False
        afc_code_libro = '1' if afc_enrolled else '0'

        # Campo 16 - 1110 CCAF - tinyint - OBLIGATORIO
        company = employee.company_id
        caja_compensacion = company.caja_compensacion if company else '00'
        ccaf_code_libro = '1' if caja_compensacion and caja_compensacion != '00' else '0'

        # Campo 17 - 1152 Org. administrador ley 16.744 - tinyint - OBLIGATORIO
        mutual = company.mutual if company else '00'
        if mutual and mutual != '00':
            mutual_code_libro = mutual.lstrip('0') or '0'  
        else:
            mutual_code_libro = '0'  

        # Campo 18 - 1111 Número cargas familiares legales autorizadas - int - OPCIONAL
        family_simple_loads = str(contract.family_simple_loads_count or 0) if contract else '0'

        # Campo 19 - 1112 Número de cargas familiares maternales - int - OPCIONAL
        family_maternal_loads = str(contract.family_maternal_loads_count or 0) if contract else '0'

        # Campo 20 - 1113 Número de cargas familiares invalidez - int - OPCIONAL
        family_invalid_loads = str(contract.family_invalid_loads_count or 0) if contract else '0'

        # Campo 21 - 1114 Tramo asignación familiar - tinyint - OPCIONAL
        family_segment = ''
        if not contract.has_family_loads:
            family_segment = 'S'
        else:
            if contract.family_loads_segment:
                # Convertir a mayúscula: 'a' -> 'A', 'b' -> 'B', 'c' -> 'C'
                family_segment = contract.family_loads_segment.upper()

        # Campo 22 - 1171 Rut organización sindical 1 Int 10 OPCIONAL - int - OPCIONAL
        sindical_1 = ''

        # Campo 23 - 1172 Rut organización sindical 2 Int 10 OPCIONAL - int - OPCIONAL
        sindical_2 = ''

        # Campo 24 - 1173 Rut organización sindical 3 Int 10 OPCIONAL - int - OPCIONAL
        sindical_3 = ''

        # Campo 25 - 1174 Rut organización sindical 4 Int 10 OPCIONAL - int - OPCIONAL
        sindical_4 = ''

        # Campo 26 - 1175 Rut organización sindical 5 Int 10 OPCIONAL - int - OPCIONAL
        sindical_5 = ''

        # Campo 27 - 1176 Rut organización sindical 6 Int 10 OPCIONAL - int - OPCIONAL
        sindical_6 = ''

        # Campo 28 - 1177 Rut organización sindical 7 Int 10 OPCIONAL - int - OPCIONAL
        sindical_7 = ''

        # Campo 29 - 1178 Rut organización sindical 8 Int 10 OPCIONAL - int - OPCIONAL
        sindical_8 = ''

        # Campo 30 - 1179 Rut organización sindical 9 Int 10 OPCIONAL - int - OPCIONAL
        sindical_9 = ''

        # Campo 31 - 1180 Rut organización sindical 10 Int 10 OPCIONAL - int - OPCIONAL
        sindical_10 = ''

        # Campo 32 - 1115 Número días trabajados en el mes - Int - OBLIGATORIO
        worked_days = self._get_real_worked_days_from_payslip(payslip)

        # Campo 33 - 1116 Número días de licencia médica en el mes - Int - OPCIONAL
        sick_leave_days = self._calculate_sick_leave_days(payslip)

        # Campo 34 - 1117 Número días de vacaciones en el mes - Int - OPCIONAL
        vacation_days = self._calculate_vacation_days(payslip)

        # Campo 35 - 1118 Subsidio trabajador joven - int - OBLIGATORIO
        has_empleo_joven = contract.has_empleo_joven if contract else False
        subsidio_empleo_joven = '1' if has_empleo_joven else '0'

        # Campo 36 - 1154 Puesto trabajo pesado - int - OPCIONAL
        trabajo_pesado = '0'  

        # Campo 37 - 1155 Ahorro previsional voluntario individual (APVI) - int - OBLIGATORIO
        apvi_enrolled = '1' if contract and contract.has_apvi else '0'

        # Campo 38 - 1157 Ahorro previsional voluntario colectivo (APVC) - int - OBLIGATORIO
        apvc_enrolled = '1' if contract and contract.has_apvc else '0'

        # Campo 38 - 1131 Indemnización a todo evento (Art. 164) -  int - OBLIGATORIO
        indemnizacion_todo_evento = '0'  

        # Campo 39 - 1132 Tasa indemnización a todo evento (Art. 164) - float - OPCIONAL
        tasa_indemnizacion_todo_evento = '4.11'  

        # Campo 40 - 2101 Sueldo - int - OBLIGATORIO
        sueldo = self._get_payslip_lines(payslip, ["BASIC"]) or 0

        # Campo 41 - 2102 Sobresueldo (Horas extras pactadas)
        sobresueldo = self._calculate_overtime_salary(payslip, contract)

        # Campo 42 - 2103 Comisiones (mensual) - int - OPCIONAL
        comisiones = self._calculate_commissions(payslip)

        # Campo 43 - 2104 Semana corrida mensual (Art. 45) - int - OPCIONAL
        semana_corrida_mensual = self._get_payslip_lines(payslip, ['MOV_8']) or 0 

        # Campos 44 - 2105 Participación (mensual) - int - OPCIONAL
        participacion = '0'

        # Campo 45 - 2106 Gratificación (mensual) - int - OPCIONAL
        gratificacion = self._get_payslip_lines(payslip, ['GRAT47','GRAT50']) or 0

        # Campo 46 - 2107 Recargo 30% día domingo (Art. 38)  - int - OPCIONAL
        recargo_dia_domingo = 0 

        # Campo 47 - 2108 Remuneración variable pagada en vacaciones (Art. 71) - int - OPCIONAL
        remuneracion_variable_vacaciones = 0 

        # Campo 48 - 2109 Remuneración variable pagada en clausura (Art. 38 DFL 2) - int - OPCIONAL
        remuneracion_variable_clausura = 0

        # Campo 49 - 2110 Aguinaldo - INT - opcional
        aguinaldo = self._calculate_aguinaldo(payslip)

        # Campo 50 - 2111 Bonos u otras remuneraciones fijas mensuales -  int - opcional
        bonos_fijos = 0

        # Campo 51 - 2112 Tratos (mensual) Int 8 OPCIONAL
        tratos = 0

        # Campo 52 - 2113 Bonos u otras remuneraciones variables mensuales o superiores a un mes Int 8 OPCIONAL
        bonos = self._calculate_bonuses(payslip)

        # Campo 53 - 2114 Ejercicio opción no pactada en contrato (Art. 17 N°8 LIR) Int 8 OPCIONAL
        ejercicio_opcion = 0

        # Campo 54 - 2115 Beneficios en especie constitutivos de remuneración Int 8 OPCIONAL
        beneficios_especie = 0

        # Campo 55 - 2116 Asignaciones familiares retroactivas Int 8 OPCIONAL
        asignaciones_familiares_retroactivas = 0

        # Campo 56 - 2117 Remuneraciones trimestrales (devengo en tres meses) Int 8 OPCIONAL
        remuneraciones_trimestrales = 0

        # Campo 57 - 2118 Remuneraciones cuatrimestral (devengo en cuatro meses) Int 8 OPCIONAL
        remuneraciones_cuatrimestral = 0

        # Campo 58 - 2119 Remuneraciones semestrales (devengo en seis meses) Int 8 OPCIONAL
        remuneraciones_semestrales = 0

        # Campo 59 - 2120 Remuneraciones anuales (devengo en doce meses) Int 8 OPCIONAL
        remuneraciones_anuales = 0

        # Campo 60 - 2121 Participación anual (devengo en doce meses) Int 8 OPCIONAL
        participacion_anual = 0

        # Campo 61 - 2122 Gratificación anual (devengo en doce meses) Int 8 OPCIONAL
        gratificacion_anual = 0

        # Campo 62 - 2123 Otras remuneraciones superiores a un mes Int 8 OPCIONAL
        otras_remuneraciones_superiores = 0

        # Campo 63 - 2124 Pago por horas de trabajo sindical Int 8 OPCIONAL
        pago_horas_trabajo_sindical = 0

        # Campo 64 - 2161 Sueldo empresarial Int 8 OPCIONAL
        sueldo_empresarial = 0

        # Campo 65 - 2201 Subsidio por incapacidad laboral por licencia médica - total mensual Int 8 OPCIONAL
        # Fuente: regla salarial SUBSIDIO (monto que paga la institución de salud por licencia).
        subsidio_incapacidad_laboral = self._get_payslip_lines(payslip, ["SUBSIDIO"]) or 0

        # Campo 66 - 2202 Beca de estudio (Art. 17 N°18 LIR) Int 8 OPCIONAL
        beca_estudio = 0

        # Campo 67 - 2203 Gratificaciones de zona (Art. 17 N°27) Int 8 OPCIONAL
        gratificaciones_zona = 0

        # Campo 68 - 2204 Otros ingresos no constitutivos de renta (Art. 17 N°29 LIR) Int 8 OPCIONAL
        otros_ingresos_no_constitutivos = 0 

        # Campo 69 - 2301 Colación total mensual (Art. 41) Int 8 OPCIONAL
        colacion_total_mensual = self._get_payslip_lines(payslip, ["COLA"])

        # Campo 70 - 2302 Movilización total mensual (Art. 41) Int 8 OPCIONAL - BS
        movilizacion_total_mensual = self._get_payslip_lines(payslip, ["MOV", "MOV_15"])

        # Campo 71 - 2303 Viáticos total mensual (Art. 41) Int 8 OPCIONAL
        viaticos_total_mensual = self._calculate_viaticos(payslip)
        
        # Campo 72 - 2304 Asignación de pérdida de caja total mensual (Art. 41) Int 8 OPCIONAL
        asignacion_perdida_caja = 0

        # Campo 73 - 2305 Asignación de desgaste herramienta total mensual (Art. 41) Int 8 OPCIONAL
        asignacion_desgaste_herramienta = 0

        # Campo 74 - 2311 Asignación familiar legal total mensual (Art. 41) Int 8 OPCIONAL
        asignacion_familiar_legal = self._get_payslip_lines(payslip, ["ASIG_FAM"]) or 0

        # Campo 75 - 2306 Gastos por causa del trabajo (Art. 41) Int 8 OPCIONAL
        gastos_causa_trabajo = 0

        # Campo 76 - 2307 Gastos por cambio de residencia (Art. 53) Int 8 OPCIONAL
        gastos_cambio_residencia = 0

        # Campo 77 - 2308 Sala cuna (Art. 203) Int 8 OPCIONAL
        sala_cuna = 0

        # Campo 78 - 2309 Asignación trabajo a distancia o teletrabajo Int 8 OPCIONAL
        asignacion_trabajo_distancia = 0

        # Campo 79 - 2347 Depósito convenido hasta UF 900 Int 8 OPCIONAL
        deposito_convenido = 0

        # Campo 80 - 2310 Alojamiento por razones de trabajo (Art. 17 N°14 LIR) Int 8 OPCIONAL
        alojamiento_razones_trabajo = 0

        # Campo 81 - 2312 Asignación de traslación (Art. 17 N°15 LIR) Int 8 OPCIONAL
        asignacion_traslacion = 0

        # Campo 82 - 2313 Indemnización por feriado legal Int 8 OPCIONAL
        indemnizacion_feriado_legal = self._get_payslip_lines(payslip, ["MOV_20"]) or 0

        # Campo 83 - 2314 Indemnización años de servicio Int 8 OPCIONAL
        indemnizacion_anos_servicio = self._get_payslip_lines(payslip, ["MOV_21"]) or 0

        # Campo 84 - 2315 Indemnización sustitutiva del aviso previo Int 8 OPCIONAL
        indemnizacion_sustitutiva_aviso = self._get_payslip_lines(payslip, ["MOV_22"]) or 0

        # Campo 85 - 2316 Indemnización fuero maternal (Art. 163 bis) Int 8 OPCIONAL
        indemnizacion_fuero_maternal = 0

        # Campo 86 - 2331 Indemnización a todo evento (Art. 164) Int 8 OPCIONAL
        indemnizacion_todo_evento_campo86 = 0

        # Campo 87 - 2417 Indemnizaciones voluntarias tributables Int 8 OPCIONAL
        indemnizaciones_voluntarias_tributables = self._get_payslip_lines(payslip, ["MOV_23"]) or 0

        # Campo 88 - 2418 Indemnizaciones contractuales tributables Int 8 OPCIONAL
        indemnizaciones_contractuales_tributables = self._get_payslip_lines(payslip, ["MOV_24"]) or 0

        # Campo 89 - 3141 Cotización obligatoria previsional (AFP o IPS) 
        cotizacion_previsional_obligatoria = self._get_payslip_lines(payslip, ["AFP", "IPS"]) or 0
        
        # Campo 90 - 3143 Cotización obligatoria salud 7% Int 8 OBLIGATORIO
        cotizacion_salud_obligatoria = self._get_payslip_lines(payslip, ["SALUD"]) or 0

        # Campo 91 - 3144 Cotización voluntaria para salud
        cotizacion_salud_adicional = self._get_payslip_lines(payslip, ["ISAPRE_EXTRA"]) or 0

        # Campo 92 - 3151 Cotización AFC - trabajador
        cotizacion_afc_trabajador = self._get_payslip_lines(payslip, ["AFC_T"]) or 0

        # Campo 93 - 3146 Cotizaciones técnico extranjero para seguridad social fuera de Chile  - Vacio por defecto - Int 
        cotizacion_tecnico_extranjero = 0

        # Campo 94 - 3147 Descuento depósito convenido hasta UF 900 anual  - Vacio por defecto - Int 
        descuento_deposito_convenido = 0

        # Campo 95 - 3155 Cotización ahorro previsional voluntario individual modalidad A Int - Opcional
        if contract.has_apvi:
            cotizacion_apvi_modalidad_a = int(contract.cotizacion_apvi)
        else:
            cotizacion_apvi_modalidad_a = 0

        # Campo 96 - 3156 Cotización ahorro previsional voluntario individual modalidad B hasta UF 50 Int  - Opcional - Vacio por defecto
        cotizacion_apvi_modalidad_b = 0

        # Campo 97 - 3157 Cotización ahorro previsional voluntario colectivo modalidad A Int - Opcional
        if contract.has_apvc:
            cotizacion_apvc_modalidad_a = int(contract.cotizacion_apvc_trabajador)
        else:
            cotizacion_apvc_modalidad_a = 0

        # Campo 98 - 3158 Cotización ahorro previsional voluntario colectivo modalidad B hasta UF 50 Int - Opcional
        if contract.has_apvc:
            cotizacion_apvc_modalidad_b = int(contract.cotizacion_apvc_empleador)
        else:
            cotizacion_apvc_modalidad_b = 0

        # Campo 99 - 3161 Impuesto retenido por remuneraciones - Int - Obligatorio
        impuesto_retenido_remuneraciones = self._get_payslip_lines(payslip, ["IMP_RETENIDO"]) or 0

        # Campo 100 - 3162 Impuesto retenido por indemnizaciones Int 8 OPCIONAL - Vacio por defecto
        impuesto_retenido_indemnizaciones = 0

        # Campo 101 - 3163 Mayor retención de impuestos solicitada por el trabajador Int 8 OPCIONAL - Vacio por defecto
        mayor_retencion_impuestos = 0

        # Campo 102 - 3164 Impuesto retenido por reliquidación remuneraciones devengadas en otros períodos Int 8 OPCIONAL - Vacio por defecto
        impuesto_retenido_reliquidacion = 0

        # Campo 103 - 3165 Diferencia de impuesto por reliquidación remuneraciones devengadas en este período Int 8 OPCIONAL - Vacio por defecto
        impuesto_retenido_diferencia = 0

        # Campo 104 - 3166 Retención préstamo clase media 2020 (Ley 21.252) Int 8 OPCIONAL - Vacio por defecto
        retencion_prestamo_clase_media = 0

        # Campo 105 - 3167 Rebaja zona extrema DL 889 Int 8 OPCIONAL - Vacio por defecto
        rebaja_zona_extrema = 0

        # Campo 106 - 3171 Cuota sindical 1 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_1 = 0

        # Campo 107 - 3172 Cuota sindical 2 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_2 = 0

        # Campo 108 - 3173 Cuota sindical 3 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_3 = 0

        # Campo 109 - 3174 Cuota sindical 4 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_4 = 0

        # Campo 110 - 3175 Cuota sindical 5 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_5 = 0

        # Campo 111 - 3176 Cuota sindical 6 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_6 = 0

        # Campo 112 - 3177 Cuota sindical 7 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_7 = 0

        # Campo 113 - 3178 Cuota sindical 8 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_8 = 0

        # Campo 114 - 3179 Cuota sindical 9 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_9 = 0

        # Campo 115 - 3180 Cuota sindical 10 Int 8 OPCIONAL - Vacio por defecto
        cuota_sindical_10 = 0   

        # Campo 116 - 3110 Crédito social CCAF Int 8 OPCIONAL
        ccaf_credit = self._get_ccaf_credit_deduction(payslip)

        # Campo 118 - 3181 Cuota vivienda o educación (Art. 58) Int 8 OPCIONAL - Vacio por defecto
        cuota_vivienda_educacion = 0

        # Campo 119 - 3182 Crédito cooperativas de ahorro (Art 54. Ley Coop.) Int 8 OPCIONAL 
        ccaf_credit_saving = self._get_ccaf_credit_saving(payslip)

        # Campo 120 - 3183 Otros descuentos autorizados y solicitados por el trabajador Int 8 OPCIONAL
        # Incluye otros créditos CCAF + Cuenta 2 AFP (ahorro voluntario del trabajador)
        ccaf_credit_others = int(self._get_ccaf_credit_others(payslip) or 0)
        cuenta2_afp = self._get_payslip_lines(payslip, ["CUENTA2"]) or 0
        ccaf_credit_others = ccaf_credit_others + int(cuenta2_afp)

        # Campo 121 - 3154 Cotización adicional trabajo pesado - trabajador Int 8 OPCIONAL - Vacio por defecto
        cotizacion_adicional_trabajo_pesado = 0

        # Campo 122 - 3184 Donaciones culturales y de reconstrucción Int 8 OPCIONAL - Vacio por defecto
        donaciones_culturales_reconstruccion = 0

        # Campo 122 - 3185 Otros descuentos (Art. 58) Int 8 OPCIONAL - Vacio por defecto
        otros_descuentos_art58 = 0

        # Campo 123 - 3186 Pensiones de alimentos Int 8 OPCIONAL - Vacio por defecto
        pensiones_alimentos = 0

        # Campo 124 - 3187 Descuento mujer casada (Art. 59) Int 8 OPCIONAL - Vacio por defecto
        descuento_mujer_casada = 0

        # Campo 125 - 3188 Descuentos por anticipos y préstamos Int 8 OPCIONAL
        descuentos_anticipos_prestamos = self._get_descuentos_anticipos_prestamos(payslip)

        # Campo 126 - 4151 Aporte AFC - empleador Int 8 OPCIONAL
        aporte_afc_empleador = self._get_payslip_lines(payslip, ["AFC_EMPLEADOR"]) or 0

        # Campo 127 - 4152 Aporte empleador seguro accidentes del trabajo y Ley SANNA (Ley 16.744) Int 8 OBLIGATORIO
        aporte_empleador_seguro_accidentes = self._get_payslip_lines(payslip, ["APORTE_MUTUAL"]) or 0

        # Campo 128 - 4131 Aporte empleador indemnización a todo evento (Art. 164) Int 8 OPCIONAL - Vacio por defecto
        aporte_empleador_indemnizacion_todo_evento = 0

        # Campo 129 - 4154 Aporte adicional trabajo pesado - empleador Int 8 OPCIONAL - Vacio por defecto
        aporte_adicional_trabajo_pesado = 0

        # Campo 130 - 4155 Aporte empleador seguro invalidez y sobrevivencia Int 8 OBLIGATORIO
        """
            Corresponde a la suma de los aportes del empleador al seguro de invalidez y sobrevivencia (SIS) y al seguro de renta protegida (RENT_PROT).
            ** Estos campos estan agregados aqui porque todavia LRE no tiene un campo espefico para alojarlos**
        """
        aporte_empleador_seguro_invalidez = (
            (self._get_payslip_lines(payslip, ["SIS"]) or 0) +
            (self._get_payslip_lines(payslip, ["RENT_PROT"]) or 0)
        )

        # Campo 133 - 5210 Total haberes imponibles y tributables Int 8 OBLIGATORIO
        """
            Debe sumarse: Sueldo, Sobresueldo, Comisiones, Semana corrida mensual (2104), Participación (mensual), Gratificación, 
            Recargo 30% día domingo, Remuneración variable pagada en vacaciones , Remuneración variable pagada en clausura,
            Aguinaldos (2110), Tratos (mensual), Bonos, Ejercicio opción no pactada en contrato, Beneficios en especie constitutivos de remuneración ,
            Remuneraciones bimestrales, Remuneraciones trimestrales , Remuneraciones semestrales , Remuneraciones anuales,
            Participación anual , Gratificación anual , Otras remuneraciones superiores a un mes, 
            Pago por horas de trabajo sindical , Sueldo empresarial, 
            
            Viatico, Movilizacion, Colacion, 
        """
        total_haberes_imponibles_tributables = 0
        try:
            total_haberes_imponibles_tributables = (
                int(float(sueldo or 0)) +
                int(float(sobresueldo or 0)) +
                int(float(comisiones or 0)) +
                int(float(semana_corrida_mensual or 0)) +
                int(float(participacion or 0)) +
                int(float(gratificacion or 0)) +
                int(float(recargo_dia_domingo or 0)) +
                int(float(remuneracion_variable_vacaciones or 0)) +
                int(float(remuneracion_variable_clausura or 0)) +
                int(float(aguinaldo or 0)) +
                int(float(bonos_fijos or 0)) +
                int(float(tratos or 0)) +
                int(float(bonos or 0)) 
            )
            total_haberes_imponibles_tributables = int(total_haberes_imponibles_tributables)
        except Exception:
            total_haberes_imponibles_tributables = 0

        # Campo 131 - 4157 Aporte empleador ahorro previsional voluntario colectivo Int 8 OPCIONAL + Seguro Social
        aporte_empleador_apvc = self._calculate_aporte_empleador_apvc(payslip, total_haberes_imponibles_tributables)

        # Campo 134 - 5220 Total haberes imponibles no tributables Int 8 OBLIGATORIO - Vacio por defecto
        """
            Corresponde a la suma de todos los campos 22xx
            (2201, 2202, 2203, 2204)
        """
        total_haberes_imponibles_no_tributables = 0

        # Campo 135 - 5230 Total haberes no imponibles y no tributables Int 8 OBLIGATORIO 
        """
            Corresponde a la sumatoria de los valores de todos los campos 23xx
            Debe sumarse: 2301, 2302, 2303, 2304, 2305, 2311, 2306, 2307,
            2308, 2309, 2347, 2310, 2312, 2313, 2314, 2315, 2316, 2331
        """
        total_haberes_no_imponibles_no_tributables = 0
        try:
            total_haberes_no_imponibles_no_tributables = (
                int(float(movilizacion_total_mensual or 0)) +
                int(float(colacion_total_mensual or 0)) +
                int(float(viaticos_total_mensual or 0)) +
                int(float(asignacion_familiar_legal or 0))
            )
            total_haberes_no_imponibles_no_tributables = int(total_haberes_no_imponibles_no_tributables)
        except Exception:
            total_haberes_no_imponibles_no_tributables = 0

        # Campo 136 - 5240 Total haberes no imponibles y tributables Int 8 OBLIGATORIO - Vacio por defecto
        total_haberes_no_imponibles_tributables = 0

        # Campo 137 - 5301 Total descuentos Int 8 OBLIGATORIO
        # TODO REGLA
        """
            Debe sumarse: 3141, 3143, 3151, 3161, 3110, 3144, 3155, 3156, 3157, 3158, 3182, 3183, 3188
        """
        total_descuentos = 0
        try:
            total_descuentos = (
                self._get_payslip_lines(payslip, ["TOTAL_DSCTOS"]) or 0
            )
            total_descuentos = int(total_descuentos)
        except Exception:
            total_descuentos = 0

        # Campo 138 - 5361 Total descuentos impuestos a las remuneraciones Int 8 OBLIGATORIO
        total_descuentos_impuestos_remuneraciones = 0
        try:
            total_descuentos_impuestos_remuneraciones = (
                int(float(impuesto_retenido_remuneraciones or 0))
            )
            total_descuentos_impuestos_remuneraciones = int(total_descuentos_impuestos_remuneraciones)
        except Exception:
            total_descuentos_impuestos_remuneraciones = 0

        # Campo 139 - 5362 Total descuentos impuestos por indemnizaciones Int 8 OPCIONAL - Vacio por defecto
        total_descuentos_impuestos_indemnizaciones = 0

        # Campo 140 - 5341 Total descuentos por cotizaciones del trabajador Int 8 OBLIGATORIO
        total_descuentos_cotizaciones_trabajador = 0
        """
            Sumar: 3141, 3143, 3144, 3151, 3155, 3156, 3157, 3158,
        """
        try:
            total_descuentos_cotizaciones_trabajador = (
                int(float(cotizacion_previsional_obligatoria or 0)) +
                int(float(cotizacion_salud_obligatoria or 0)) +
                int(float(cotizacion_salud_adicional or 0)) +
                int(float(cotizacion_afc_trabajador or 0)) +
                int(float(cotizacion_apvi_modalidad_a or 0)) +
                int(float(cotizacion_apvi_modalidad_b or 0)) +
                int(float(cotizacion_apvc_modalidad_a or 0)) +
                int(float(cotizacion_apvc_modalidad_b or 0))
            )
            total_descuentos_cotizaciones_trabajador = int(total_descuentos_cotizaciones_trabajador)
            # _logger.info(
            #     f"Total descuentos cotizaciones trabajador: {total_descuentos_cotizaciones_trabajador}"
            # )
        except Exception:
            total_descuentos_cotizaciones_trabajador = 0

        # Campo 140 - 5302 Total otros descuentos Int 8 OBLIGATORIO
        """
            5301 - (5361 + 5362 + 5341)
        """
        total_otros_descuentos = 0
        try:
            total_otros_descuentos = (
                int(float(total_descuentos or 0)) -(
                int(float(total_descuentos_impuestos_remuneraciones or 0)) +
                int(float(total_descuentos_impuestos_indemnizaciones or 0)) +
                int(float(total_descuentos_cotizaciones_trabajador or 0)))
            )
            # Asegurar que el valor nunca sea negativo
            total_otros_descuentos = max(0, int(total_otros_descuentos))
        except Exception:
            total_otros_descuentos = 0

        # Campo 141 - 5410 Total aportes empleador Int 8 OBLIGATORIO
        """
            Sumar: 4151, 4152, 4131, 4154, 4155, 4157
        """
        total_aportes_empleador = 0
        try:
            total_aportes_empleador = (
                int(float(aporte_afc_empleador or 0)) +
                int(float(aporte_empleador_seguro_accidentes or 0)) +
                int(float(aporte_empleador_indemnizacion_todo_evento or 0)) +
                int(float(aporte_adicional_trabajo_pesado or 0)) +
                int(float(aporte_empleador_seguro_invalidez or 0)) +
                int(float(aporte_empleador_apvc or 0))
            )
            total_aportes_empleador = int(round(total_aportes_empleador))
        except Exception:
            total_aportes_empleador = 0

        # Campo 143 - 5502 Total indemnizaciones Int 8 OPCIONAL - Vacio por defecto - Suma de: 2313, 2314, 2315, 2316, 2331, 2417, 2418
        total_indemnizaciones = 0
        try:
            total_indemnizaciones = (
                int(float(indemnizacion_sustitutiva_aviso or 0)) +
                int(float(indemnizacion_anos_servicio or 0)) +
                int(float(indemnizacion_feriado_legal or 0)) +
                int(float(indemnizacion_fuero_maternal or 0)) +
                int(float(indemnizacion_todo_evento_campo86 or 0)) +
                int(float(indemnizaciones_voluntarias_tributables or 0)) +
                int(float(indemnizaciones_contractuales_tributables or 0))
            )
            total_indemnizaciones = int(total_indemnizaciones)
        except Exception:
            total_indemnizaciones = 0

        # Campo 144 - 5564 Total indemnizaciones tributables Int 8 OBLIGATORIO - Vacio por defecto - Suma de: 2417 y 2418
        total_indemnizaciones_tributables = 0
        try:
            total_indemnizaciones_tributables = (
                int(float(indemnizaciones_voluntarias_tributables or 0)) +
                int(float(indemnizaciones_contractuales_tributables or 0))
            )
            total_indemnizaciones_tributables = int(total_indemnizaciones_tributables)
        except Exception:
            total_indemnizaciones_tributables = 0

        # Campo 145 - 5565 total indemnizaciones no tributables Int 8 OPCIONAL - Vacio por defecto - Suma de: 2313, 2314, 2315, 2316, 2331
        total_indemnizaciones_no_tributables = 0
        try:
            total_indemnizaciones_no_tributables = (
                int(float(indemnizacion_sustitutiva_aviso or 0)) +
                int(float(indemnizacion_anos_servicio or 0)) +
                int(float(indemnizacion_feriado_legal or 0)) +
                int(float(indemnizacion_fuero_maternal or 0)) +
                int(float(indemnizacion_todo_evento_campo86 or 0))
            )
            total_indemnizaciones_no_tributables = int(total_indemnizaciones_no_tributables)
        except Exception:
            total_indemnizaciones_no_tributables = 0

        # Campo 132 - 5201 Total haberes Int 8 OBLIGATORIO
        """
            Debe sumarse: 5210, 5220, 5230 y 5240
        """
        total_haberes = 0
        try:
            total_haberes = (
                total_haberes_imponibles_tributables +
                total_haberes_imponibles_no_tributables +
                total_haberes_no_imponibles_no_tributables +
                total_haberes_no_imponibles_tributables
            )
            total_haberes = int(total_haberes)
        except Exception:
            total_haberes = 0

        # Campo 142 - 5501 Total líquido Int 8 OBLIGATORIO
        """
            Calculo: 5201 - 5301
        """
        total_liquido = 0
        try:
            total_liquido = (
                int(float(total_haberes or 0)) -
                int(float(total_descuentos or 0))
            )
            total_liquido = int(total_liquido)
        except Exception:
            total_liquido = 0

        return [
            rut,
            date_start.strftime('%d/%m/%Y') if date_start else '',
            date_end.strftime('%Y-%m-%d') if date_end else '',
            termination_causal,
            region_code,
            commune_code,
            income_tax_type,
            nationality,
            work_schedule_code,
            disability_code,
            retired_elderly_code,
            afp_code_libro,
            ips_code_libro,
            health_code_libro,
            afc_code_libro,
            ccaf_code_libro,
            mutual_code_libro,
            family_simple_loads,
            family_maternal_loads,
            family_invalid_loads,
            family_segment,
            sindical_1,
            sindical_2,
            sindical_3,
            sindical_4,
            sindical_5,
            sindical_6,
            sindical_7,
            sindical_8,
            sindical_9,
            sindical_10,
            worked_days,
            sick_leave_days,
            vacation_days,
            subsidio_empleo_joven,
            apvi_enrolled,
            apvc_enrolled,
            trabajo_pesado,
            indemnizacion_todo_evento,
            tasa_indemnizacion_todo_evento,
            sueldo,
            sobresueldo,
            comisiones,
            semana_corrida_mensual,
            participacion,
            gratificacion,
            recargo_dia_domingo,
            remuneracion_variable_vacaciones,
            remuneracion_variable_clausura,
            aguinaldo,
            bonos_fijos,
            tratos,
            bonos,
            ejercicio_opcion,
            beneficios_especie,
            asignaciones_familiares_retroactivas,
            remuneraciones_trimestrales,
            remuneraciones_cuatrimestral,
            remuneraciones_semestrales,
            remuneraciones_anuales,
            participacion_anual,
            gratificacion_anual,
            otras_remuneraciones_superiores,
            pago_horas_trabajo_sindical,
            sueldo_empresarial,
            subsidio_incapacidad_laboral,
            beca_estudio,
            gratificaciones_zona,
            otros_ingresos_no_constitutivos,
            colacion_total_mensual,
            movilizacion_total_mensual,
            viaticos_total_mensual,
            asignacion_perdida_caja,
            asignacion_desgaste_herramienta,
            asignacion_familiar_legal,
            gastos_causa_trabajo,
            gastos_cambio_residencia,
            sala_cuna,
            asignacion_trabajo_distancia,
            deposito_convenido,
            alojamiento_razones_trabajo,
            asignacion_traslacion,
            indemnizacion_feriado_legal,
            indemnizacion_anos_servicio,
            indemnizacion_sustitutiva_aviso,
            indemnizacion_fuero_maternal,
            indemnizacion_todo_evento_campo86,
            indemnizaciones_voluntarias_tributables,
            indemnizaciones_contractuales_tributables,
            cotizacion_previsional_obligatoria,
            cotizacion_salud_obligatoria,
            cotizacion_salud_adicional,
            cotizacion_afc_trabajador,
            cotizacion_tecnico_extranjero,
            descuento_deposito_convenido,
            cotizacion_apvi_modalidad_a,
            cotizacion_apvi_modalidad_b,
            cotizacion_apvc_modalidad_a,
            cotizacion_apvc_modalidad_b,
            impuesto_retenido_remuneraciones,
            impuesto_retenido_indemnizaciones,
            mayor_retencion_impuestos,
            impuesto_retenido_reliquidacion,
            impuesto_retenido_diferencia,
            retencion_prestamo_clase_media,
            rebaja_zona_extrema,
            cuota_sindical_1,
            cuota_sindical_2,
            cuota_sindical_3,   
            cuota_sindical_4,
            cuota_sindical_5,
            cuota_sindical_6,
            cuota_sindical_7,
            cuota_sindical_8,
            cuota_sindical_9,
            cuota_sindical_10,
            ccaf_credit,
            cuota_vivienda_educacion,
            ccaf_credit_saving,
            ccaf_credit_others,
            cotizacion_adicional_trabajo_pesado,
            donaciones_culturales_reconstruccion,
            otros_descuentos_art58,
            pensiones_alimentos,
            descuento_mujer_casada,
            descuentos_anticipos_prestamos,
            aporte_afc_empleador,
            aporte_empleador_seguro_accidentes,
            aporte_empleador_indemnizacion_todo_evento,
            aporte_adicional_trabajo_pesado,
            aporte_empleador_seguro_invalidez,
            aporte_empleador_apvc,
            total_haberes,
            total_haberes_imponibles_tributables,
            total_haberes_imponibles_no_tributables,
            total_haberes_no_imponibles_no_tributables,
            total_haberes_no_imponibles_tributables,
            total_descuentos,
            total_descuentos_impuestos_remuneraciones,
            total_descuentos_impuestos_indemnizaciones,
            total_descuentos_cotizaciones_trabajador,
            total_otros_descuentos,
            total_aportes_empleador,
            total_liquido,
            total_indemnizaciones,
            total_indemnizaciones_tributables,
            total_indemnizaciones_no_tributables
        ]
