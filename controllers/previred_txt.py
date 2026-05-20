import calendar
import logging
import csv
import io
from calendar import monthrange
from odoo import http
from odoo.http import request
from datetime import datetime, date

_logger = logging.getLogger(__name__)

# https://www.previred.com/wp-content/uploads/2025/07/FormatoLargoFijoPorPosicion-Reforma-1.pdf
class PreviredExportController(http.Controller):    
    
    def _get_real_worked_days_from_payslip(self, payslip):
        """
        Retorna los días trabajados reales desde hr.payslip.worked_days,
        sumando únicamente asistencia + vacaciones.
        Si no existe línea de asistencia y sobran días hasta completar 30,
        se agrega la diferencia como días trabajados.
        """
        if not payslip:
            return 0
    
        total_days = 0
        vac_days = 0
        asistencia_days = 0
    
        for line in payslip.worked_days_line_ids:
            code = line.work_entry_type_id.code or ""
            if code == "WORK100":
                asistencia_days += line.number_of_days or 0
            elif code == "LEAVECL120":
                vac_days += line.number_of_days or 0
    
        total_days = asistencia_days + vac_days
    
        # Forzar a que nunca supere 30
        if total_days > 30:
            total_days = 30
    
        # Si no hay asistencia registrada y faltan días para completar 30,
        # se asume que los días restantes fueron trabajados.
        if total_days < 30:
            total_days += (30 - (vac_days + asistencia_days + self._get_absent_days(payslip)))
    
        return int(total_days)
    
    def _get_absent_days(self, payslip):
        """Cuenta días de licencias/faltas (que no son trabajados)."""
        absent = 0
        for line in payslip.worked_days_line_ids:
            code = line.work_entry_type_id.code or ""
            if code in ["LIC", "FALT","OUT", "LEAVE90"]:
                absent += line.number_of_days or 0
        return absent

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

    def _calculate_license_days(self, payslip):
        """Cuenta días de licencias de la nomina"""
        try:
            license_days = 0
            for line in payslip.worked_days_line_ids:
                code = line.work_entry_type_id.code or ""
                if code in ["LIC"]:
                    license_days += line.number_of_days or 0

            # Limitar a un máximo de 30 días
            license_days = min(license_days, 30)
            return int(license_days)
        except Exception as e:
            _logger.error(f"Error calculando días de licencia para empleado {payslip.employee_id.id}: {str(e)}")
            return 0

    def _calculate_previred_taxable_income(self, employee, contract, period_start, period_end, pension_regime, previred_indicator=None, tope_type='pension', payslip = None):
        """
            Calcular renta imponible específica para Previred incluyendo:
            - Renta base (sueldo o horas trabajadas)
            - Movimientos imponibles del empleado
            - Aplicación de topes según régimen previsional
            - Ajuste proporcional por días trabajados
            
            Args:
                tope_type (str): Tipo de tope a aplicar
                    - 'pension': Aplica tope según régimen previsional (AFP/INP)
                    - 'cesantia': Aplica tope de seguro de cesantía
                    - 'none': No aplica ningún tope
        """
        try:
            # Obtener indicador Previred si no se proporciona
            if previred_indicator is None:
                previred_indicator = request.env['previred.indicator'].sudo().search([
                    ('date', '<=', period_end)
                ], order='date desc', limit=1)
            
            payslip = request.env['hr.payslip'].sudo().search([
                ('employee_id', '=', employee.id),
                ('date_from', '>=', period_start),
                ('date_from', '<=', period_end),
            ], limit=1, order='id desc')

            base_wage = None
            if payslip:
                basic_line = payslip.line_ids.filtered(lambda l: l.code == 'GROSS')
                if basic_line:
                    base_wage = basic_line[0].amount

                # Si no se encontró línea BASICO, usar contract.wage
                base_wage = (base_wage if base_wage is not None else (contract.wage or 0.0))

            renta_imponible_calculada = int(base_wage)

            # APLICAR TOPE SEGÚN EL TIPO ESPECIFICADO
            if previred_indicator and tope_type != 'none':
                if tope_type == 'cesantia':
                    # Aplicar tope de seguro de cesantía
                    if previred_indicator.tope_seguro_cesantia:
                        tope_aplicable = int(previred_indicator.tope_seguro_cesantia)
                        renta_imponible_calculada = min(renta_imponible_calculada, tope_aplicable)
                elif tope_type == 'pension' or tope_type == 'afp':
                    # Aplicar tope según régimen previsional (lógica original)
                    if pension_regime == 'AFP' and previred_indicator.tope_afiliados_afp:
                        tope_aplicable = int(previred_indicator.tope_afiliados_afp)
                        renta_imponible_calculada = min(renta_imponible_calculada, tope_aplicable)
                    elif pension_regime == 'INP' and previred_indicator.tope_afiliados_ips:
                        tope_aplicable = int(previred_indicator.tope_afiliados_ips) 
                        renta_imponible_calculada = min(renta_imponible_calculada, tope_aplicable)

            return renta_imponible_calculada
            
        except Exception as e:
            _logger.error(f"Error calculando renta imponible Previred para empleado {employee.id}: {str(e)}")
            return 0

    def _calculate_additional_health_contribution_previred(self, employee, contract, period_dt, dias_trabajados, previred_indicator=None):
        """
            Calcular cotización adicional de salud para Campo 81 en contexto Previred
            Adaptada para trabajar con los parámetros disponibles en previred_txt
        """
        try:
            if not contract:
                _logger.warning(f"No hay contrato para empleado {employee.id}")
                return 0

            health_institution = contract.health_institution or ''
            health_code = health_institution.split(' - ')[0] if ' - ' in health_institution else health_institution
            
            # Solo calcular para Isapres (no FONASA '07' ni Sin Isapre '00')
            if health_code in ['07', '00']:
                return 0

            # Obtener indicador Previred si no se proporciona
            if previred_indicator is None:
                previred_indicator = request.env['previred.indicator'].sudo().search([
                    ('date', '<=', period_dt.date())
                ], order='date desc', limit=1)

            if not previred_indicator:
                _logger.warning(f"No se encontró indicador Previred válido para {period_dt}")
                return 0

            # Calcular cotización legal obligatoria (7%) usando la función existente
            # Necesitamos calcular la renta imponible para obtener el 7%
            year = period_dt.year
            month = period_dt.month
            from calendar import monthrange
            _, dias_mes = monthrange(year, month)
            
            period_start = period_dt.replace(day=1).date()
            period_end = period_dt.replace(day=dias_mes).date()
            
            # Calcular renta imponible para Isapres (usa tope AFP)
            renta_imponible_isapre = self._calculate_previred_taxable_income(
                employee, contract, period_start, period_end,
                dias_trabajados, dias_mes, 'AFP', previred_indicator
            )
            
            # Calcular 7% obligatorio
            cotizacion_legal_7 = int(renta_imponible_isapre * 0.07)

            # Cálculo según tipo de plan
            calc_type = contract.isapre_calc_type or ''
            valor_plan_pactado_en_pesos = 0

            if calc_type == 'uf':
                if not contract.isapre_uf_valor:
                    _logger.warning(f"Contrato sin valor UF definido para plan de salud: empleado {employee.id}")
                    return 0
                uf_value = previred_indicator.uf_value_on_month or 0
                if not uf_value:
                    _logger.warning(f"Valor UF no disponible para {period_dt}")
                    return 0
                valor_plan_pactado_en_pesos = contract.isapre_uf_valor * uf_value

            elif calc_type == 'clp':
                if not contract.isapre_plan_monto:
                    _logger.warning(f"Contrato sin valor CLP definido para plan de salud: empleado {employee.id}")
                    return 0
                valor_plan_pactado_en_pesos = contract.isapre_plan_monto

            else:
                _logger.info(f"Tipo de cálculo no reconocido: {calc_type}")
                return 0

            # Calcular adicional
            adicional = valor_plan_pactado_en_pesos - cotizacion_legal_7
            if adicional > 0:
                return int(round(adicional))
            else:
                return 0  # Hay excedente o el plan es menor al 7%

        except Exception as e:
            _logger.error(f"Error calculando cotización adicional salud para empleado {employee.id}: {str(e)}")
            return 0

    def _calculate_renta_imponible_last_month(self, employee, contract, period_dt):
        """
        Calcula la renta imponible para el campo RIMA (Previred):
        - Busca la última liquidación anterior a period_dt con 30 días trabajados
        - Usa el código de regla salarial "GROSS" como renta imponible
        """
        try:
            rima = 0
            # Traer todas las nóminas anteriores a la fecha del período
            payslips = request.env["hr.payslip"].search([
                ("employee_id", "=", employee.id),
                ("contract_id", "=", contract.id),
                ("date_to", "<", period_dt),
                ("state", "in", ["done", "paid", "verify"]),
            ], order="date_to desc")

            # Buscar nómina con 30 dias trabajados
            for payslip in payslips:
                worked_days = self._get_real_worked_days_from_payslip(payslip)
                if worked_days == 30:
                    rima = self._get_payslip_lines(payslip, rule_codes="GROSS")
                    break

            return rima

        except Exception as e:
            _logger.error(
                f"Error calculando renta imponible mes válido para empleado {employee.id}: {str(e)}"
            )
            return 0

    @http.route('/hr_payroll/previred/txt', auth='user')
    def download_previred_txt(self, period=None, company_id=None, **kw):
        if period:
            try:
                period_dt = datetime.strptime(period, '%m%Y')
            except Exception:
                period_dt = datetime.now()
        else:
            period_dt = datetime.now()
        period_str = period_dt.strftime('%m%Y')
        
        # Obtener días del mes correspondiente
        year = period_dt.year
        month = period_dt.month
        period_str = period_dt.strftime('%m%Y')

        start_of_month = date(year, month, 1)

        # Calcular el último día del mes
        if month == 12:
            end_of_month = date(year + 1, 1, 1)
        else:
            end_of_month = date(year, month + 1, 1)
            
        _, dias_mes = calendar.monthrange(year, month)

        # Obtener solo contratos activos
        period_start = period_dt.replace(day=1).date()
        period_end = period_dt.replace(day=dias_mes).date()

        domain = [
            ('date_from', '>=', period_start),
            ('date_from', '<=', period_end),
            ('state', 'in', ['verify', 'done', 'paid']),
        ]

        if company_id:
            domain.append(('company_id', '=', int(company_id)))

        payslips = request.env['hr.payslip'].sudo().search(domain, order='employee_id')

        lines = []
        for payslip in payslips:
            employee = payslip.employee_id
            contract = payslip.contract_id or employee.contract_id

            # Buscar liquidación de sueldo del empleado para el período
            payslip = request.env['hr.payslip'].sudo().search([
                ('employee_id', '=', employee.id),
                ('date_from', '>=', period_start),
                ('date_from', '<=', period_end),
            ], limit=1)

            # Helper para extraer código de institución de salud para Previred TXT (primera parte)
            def get_health_institution_code():
                health_institution = contract.health_institution or ''
                if ' - ' in health_institution:
                    return health_institution.split(' - ')[0]
                return health_institution
            
            health_code = get_health_institution_code()

            # Indicador previred
            previred_indicator = request.env['previred.indicator'].sudo().search([
                ('date', '>=', start_of_month),
                ('date', '<', end_of_month)
            ], order='date desc', limit=1)

            # Campo 1 - RUT Trabajador 
            raw_rut = employee.identification_id or ''

            # Campo 2 - DV Trabajador
            if raw_rut:
                clean_rut = raw_rut.replace('.', '').replace('-', '')
                if len(clean_rut) >= 2:
                    rut_number = clean_rut[:-1]
                    verification_digit = clean_rut[-1]
                else:
                    rut_number = "0"
                    verification_digit = "0"
            else:
                rut_number = "0"
                verification_digit = "0"

            # Campo 3,4 y 5 - Apellido Paterno | Apellido Materno | Nombre
            employee_name = employee.name or ''
            import unicodedata
            def normalize_name_part(s):
                if not s:
                    return ''
                # Eliminar tildes y pasar a mayúsculas
                s = unicodedata.normalize('NFKD', s)
                s = ''.join(c for c in s if not unicodedata.combining(c))
                return s.upper()

            name_parts = employee_name.strip().split()
            first_name = normalize_name_part(name_parts[0]) if len(name_parts) > 0 else ''
            paternal_surname = normalize_name_part(name_parts[1]) if len(name_parts) > 1 else ''
            maternal_surname = normalize_name_part(name_parts[2]) if len(name_parts) > 2 else ''

            # Campo 6 - Genero
            gender = employee.gender or ''
            previred_gender = 'M' if gender == 'male' else ('F' if gender == 'female' else 'M')
            
            # Campo 7 - País
            country = employee.country_id
            nationality = '0' if country and country.code == 'CL' else '1'

            # Campo 8 - Tipo de Pago
            payment_type = '01'

            # Campo 9 - Periodo (Desde)
            period_from = period_str

            # Campo 10 - Periodo (Hasta)
            period_to = period_str

            # Campo 11 - Regimen previsonal
            pension_option = contract.pension_option or ''
            if pension_option.lower() == 'afp':
                pension_regime = 'AFP'
            elif pension_option.lower() == 'inp':
                pension_regime = 'INP'
            elif pension_option.lower() == 'sip':
                pension_regime = 'SIP'
            else:
                pension_regime = 'AFP'

            # Campo 12 — Tipo de Trabajador
            worker_type = '0'
            # Tipo 2: Pensionado mayor de 65 años sin cotización AFP
            if  contract.is_retired_elderly:
                worker_type = '2'
            elif employee.birthday:
                today = period_dt.date()
                age = today.year - employee.birthday.year - ((today.month, today.day) < (employee.birthday.month, employee.birthday.day))
                if age > 65:
                    worker_type = '3'

            # Campo 13 - Dias trabajados            
            dias_trabajados = self._get_real_worked_days_from_payslip(payslip)

            # Calcular renta imponible
            def renta_imponible(tope_type):
                return self._calculate_previred_taxable_income(
                    employee, contract, period_start, period_end, pension_regime, previred_indicator, tope_type=tope_type, payslip=payslip
                )

            # Campo 14 — Tipo de Línea 
            # "0" = Línea principal (siempre con movimiento "0")
            # "1" = Línea adicional (donde van los movimientos reales)
            tipo_linea = "0"  # Línea principal siempre es "0"

            # Campo 15 - Código Movimiento de Personal / Campo 16 — Fecha Desde / Campo 17 - Fecha Hasta
            movimiento_personal = "0"
            fecha_desde = ""
            fecha_hasta = ""

            # Campo 18 — Tramo Asignación Familiar
            if contract.has_family_loads and contract.family_loads_segment:
                # Si tiene cargas y segmento definido, usar el segmento
                segment = contract.family_loads_segment.upper()
                if segment in ['A', 'B', 'C']:
                    tramo_asignacion_familiar = segment
                else:
                    tramo_asignacion_familiar = "D"
            elif contract.has_family_loads:
                # Si tiene cargas pero no segmento, calcular por renta (requiere implementación adicional)
                # Por ahora asignar A como default
                tramo_asignacion_familiar = "A"
            else:
                # Si no tiene cargas familiares, siempre es D
                tramo_asignacion_familiar = "D"

            # Campos 19, 20, 21 — Cantidad de cargas familiares
            cargas_simples = str(contract.family_simple_loads_count or 0)
            cargas_maternales = str(contract.family_maternal_loads_count or 0)
            cargas_invalidas = str(contract.family_invalid_loads_count or 0)

            # Campo 22 — Monto en $ Asignación Familiar
            asignacion_familiar = "0"
            if contract.has_family_loads and tramo_asignacion_familiar in ['A', 'B', 'C']:
                # Obtener el indicador previred más reciente para valores de cargas
                previred_indicator = request.env['previred.indicator'].sudo().search([
                    ('date', '<=', period_dt.date())
                ], order='date desc', limit=1)
                
                if previred_indicator:
                    # Obtener valor de carga según tramo
                    if tramo_asignacion_familiar == 'A':
                        valor_carga = previred_indicator.tramo_a or 0
                    elif tramo_asignacion_familiar == 'B':
                        valor_carga = previred_indicator.tramo_b or 0
                    elif tramo_asignacion_familiar == 'C':
                        valor_carga = previred_indicator.tramo_c or 0
                    else:
                        valor_carga = 0
                    
                    if valor_carga > 0:
                        # Calcular cargas totales: CT = cargas simples + 2 × cargas inválidas + cargas maternales
                        cargas_totales = (
                            int(cargas_simples) + 
                            (2 * int(cargas_invalidas)) + 
                            int(cargas_maternales)
                        )
                        
                        # Asignación Familiar = VC × CT
                        if cargas_totales > 0:
                            asignacion_familiar_amount = int(valor_carga * cargas_totales)
                            asignacion_familiar = str(asignacion_familiar_amount)

            # Campo 23 — Monto en $ Asignación Familiar Retroactiva
            asignacion_familiar_retroactiva = ""

            # Campo 24 — Monto en $ del reintegro de cargas familiares
            reintegro_cargas_familiares = ""

            # Campo 25 — Subsidio empleo joven (N por defecto)
            subsidio_empleo_joven = "N"

            # Campo 26 — Tipo de AFP
            afp_option = contract.afp_option or ''
            # Extraer solo la primera parte del código (antes del guión)
            afp_code = afp_option.split(' - ')[0] if ' - ' in afp_option else afp_option
            if afp_code in ['03', '05', '08', '29', '33', '34', '35']:
                tipo_afp = afp_code
            else:
                tipo_afp = "00"  

            # Campo 27 — Renta Imponible AFP
            if contract.pension_option in ['inp', 'sip']:
                renta_imponible_afp = 0
            else:
                renta_imponible_afp = round(int(min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope_afiliados_afp or 0)))

            # Campo 28 — Cotización AFP
            cotizacion_afp = self._get_payslip_lines(payslip, rule_codes=['AFP', 'AFP_EMP']) or "0"

            # Campo 29 — Cotización Seguro de Invalidez y Sobrevivencia (SIS)
            cotizacion_sis = self._get_payslip_lines(payslip, rule_codes=['SIS']) or ""
            
            # Campo 30 — Cuenta de Ahorro Voluntario AFP (vacío por defecto)
            ahorro_voluntario_afp = ""

            # Campo 31 — Renta Imponible Sustitutiva AFP (vacío por defecto)
            renta_imponible_sustitutiva = ""

            # Campo 32 — Tasa Pactada Sustitutiva (vacío por defecto)
            tasa_pactada_sustitutiva = ""

            # Campo 33 — Aporte Indemnización Sustitutiva (vacío por defecto)
            aporte_indemnizacion_sustitutiva = ""

            # Campo 34 — Número de Períodos Sustitutivos (vacío por defecto)
            num_periodos_sustitutivos = ""

            # Campo 35 — Período Desde Sustitutivo (vacío por defecto)
            periodo_desde_sustitutivo = ""

            # Campo 36 — Período Hasta Sustitutivo (vacío por defecto)
            periodo_hasta_sustitutivo = ""

            # Campo 37 — Puesto de Trabajo Pesado (vacío por defecto)
            puesto_trabajo_pesado = ""

            # Campo 38 — Porcentaje Cotización Trabajo Pesado (vacío por defecto)
            porcentaje_trabajo_pesado = ""

            # Campo 39 — Cotización Trabajo Pesado (vacío por defecto)
            cotizacion_trabajo_pesado = ""

            # TODO LINEA EXTRA CUANDO TIENE APVI / APVC
            # Campo 40 — Código de la Institución APVI
            if contract.has_apvi:
                codigo_institucion_apvi = contract.institucion_apvi_apvc or ""
            else:
                codigo_institucion_apvi = ""

            # Campo 41 — Número de Contrato APVI (vacío por defecto)
            numero_contrato_apvi = ""

            # Campo 42 — Forma de Pago APVI
            if contract.has_apvi:
                forma_pago_apvi = contract.pay_format_apvi_apc or ""
            else:
                forma_pago_apvi = ""

            # Campo 43 — Cotización APVI
            if contract.has_apvi:
                monto_apvi = int(contract.cotizacion_apvi or 0)
                cotizacion_apvi = f"{monto_apvi:08d}" if monto_apvi > 0 else ""
            else:
                cotizacion_apvi = ""

            # Campo 44 — Cotización Depósitos Convenidos (vacío por defecto)
            cotizacion_depositos_convenidos = ""

            # Campo 45 — Código Institución Autorizada APVC (vacío por defecto)
            if contract.has_apvc:
                codigo_institucion_apvc = contract.institucion_apvi_apvc or ""
            else:                           
                codigo_institucion_apvc = ""

            # Campo 46 — Número de Contrato APVC (vacío por defecto)
            numero_contrato_apvc = ""

            # Campo 47 — Forma de Pago APVC (vacío por defecto)
            if contract.has_apvc:
                forma_pago_apvc = contract.pay_format_apvi_apc or ""
            else:
                forma_pago_apvc = ""

            # Campo 48 — Cotización Trabajador APVC (vacío por defecto)|
            if contract.has_apvc:
                monto_apvc_trabajador = int(contract.cotizacion_apvc_trabajador or 0)
                cotizacion_trabajador_apvc = f"{monto_apvc_trabajador:08d}" if monto_apvc_trabajador > 0 else ""
            else:
                cotizacion_trabajador_apvc = ""

            # Campo 49 — Cotización Empleador APVC (vacío por defecto)
            if contract.has_apvc:
                monto_apvc_empleador = int(contract.cotizacion_apvc_empleador or 0)
                cotizacion_empleador_apvc = f"{monto_apvc_empleador:08d}" if monto_apvc_empleador > 0 else ""
            else:
                cotizacion_empleador_apvc = ""

            # Campo 50 — RUT Afiliado Voluntario (vacío por defecto)
            rut_afiliado_voluntario = ""

            # Campo 51 — DV Afiliado Voluntario (vacío por defecto)
            dv_afiliado_voluntario = ""

            # Campo 52 — Apellido Paterno Afiliado Voluntario (vacío por defecto)
            apellido_paterno_afiliado_voluntario = ""

            # Campo 53 — Apellido Materno Afiliado Voluntario (vacío por defecto)
            apellido_materno_afiliado_voluntario = ""

            # Campo 54 — Nombres Afiliado Voluntario (vacío por defecto)
            nombres_afiliado_voluntario = ""

            # Campo 55 — Código Movimiento de Personal Afiliado Voluntario (vacío por defecto)
            codigo_movimiento_afiliado_voluntario = "00"

            # Campo 56 — Fecha desde Afiliado Voluntario (vacío por defecto)
            fecha_desde_afiliado_voluntario = ""

            # Campo 57 — Fecha hasta Afiliado Voluntario (vacío por defecto)
            fecha_hasta_afiliado_voluntario = ""

            # Campo 58 — Código de la AFP Afiliado Voluntario (vacío por defecto)
            codigo_afp_afiliado_voluntario = ""

            # Campo 59 — Monto Capitalización Voluntaria (vacío por defecto)
            monto_capitalizacion_voluntaria = ""

            # Campo 60 — Monto Ahorro Voluntario (vacío por defecto)
            monto_ahorro_voluntario = ""

            # Campo 61 — Número de períodos de cotización (vacío por defecto)
            numero_periodos_cotizacion = ""

            # Campo 62 — Código EX-Caja Régimen (vacío por defecto)
            codigo_ex_caja_regimen = ""

            # Campo 63 — Tasa Cotización Ex-Caja Previsión (vacío por defecto)
            tasa_cotizacion_ex_caja_prevision = ""

            # Campo 64 — Renta Imponible Fonasa
            if health_code == '07':
                renta_imponible_ips = min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope_afiliados_afp or 0)
            else:
                renta_imponible_ips = ""

            # Campo 65 — Cotización Obligatoria IPS (vacío por defecto)
            cotizacion_obligatoria_ips = ""

            # Campo 66 — Renta Imponible Desahucio (vacío por defecto)
            renta_imponible_desahucio = ""

            # Campo 67 — Código Ex-Caja Régimen Desahucio (vacío por defecto)
            codigo_ex_caja_regimen_desahucio = ""

            # Campo 68 — Tasa Cotización Desahucio Ex-Cajas de Previsión (vacío por defecto)
            tasa_cotizacion_desahucio_ex_cajas = ""

            # Campo 69 — Cotización Desahucio (vacío por defecto)
            cotizacion_desahucio = ""

            # Campo 70 — Cotización Fonasa
            if health_code == '07':
                tasa_fonasa = (previred_indicator.fonasa_empleadores_afiliados + previred_indicator.ccaf_empleadores_afiliados) / 100
                cotizacion_fonasa = min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope_afiliados_afp or 0) * tasa_fonasa
                cotizacion_fonasa = int(round(cotizacion_fonasa))
            else:
                cotizacion_fonasa = ""

            # Campo 71 — Cotización Acc. Trabajo (ISL) (vacío por defecto)
            cotizacion_acc_trabajo_isl = ""

            # Campo 72 — Bonificación Ley 15.386 (vacío por defecto)
            bonificacion_ley_15386 = ""

            # Campo 73 — Descuento por cargas familiares de IPS (ex INP) (vacío por defecto)
            descuento_cargas_familiares_ips = ""

            # Campo 74 — Bonos Gobierno (vacío por defecto)
            bonos_gobierno = ""

            # Campo 75 — Código Institución de Salud
            codigo_institucion_salud = health_code

            # Campo 76 — Número del FUN (vacio por defecto)
            numero_fun = "00000000"

            # Campo 77 — Renta Imponible Isapre - impo_isapre
            if health_code == '07':
                # Si está en Fonasa, usar 8 ceros
                renta_imponible_isapre = "00000000"
            elif health_code and health_code != '07':
                renta_imponible_isapre = round(int(min(self._get_payslip_lines(payslip, rule_codes=['GROSS']), previred_indicator.tope_afiliados_afp or 0)))
            else:
                renta_imponible_isapre = ""

            # Campo 78 — Moneda del plan pactado Isapre
            if health_code == '07':
                # Fonasa siempre es 1
                moneda_plan_isapre = "1"
            elif health_code and health_code != '07':
                # Isapre: si el tipo de cálculo es UF es 2, sino es 1
                if contract.isapre_calc_type == 'uf':
                    moneda_plan_isapre = "2"
                else:
                    moneda_plan_isapre = "1"
            else:
                moneda_plan_isapre = ""

            # Campo 79 — Cotización Pactada - cot_pactada
            if health_code == '07':
                # Fonasa siempre 8 ceros
                cotizacion_pactada = "00000000"
            elif health_code and health_code != '07':
                # Isapre: usar monto según tipo de cálculo
                if contract.isapre_calc_type == 'clp':
                    # Plan en CLP - usar isapre_plan_monto
                    monto_clp = int(contract.isapre_plan_monto or 0)
                    cotizacion_pactada = f"{monto_clp:08d}" 
                elif contract.isapre_calc_type == 'uf':
                    # Monto en UF - usar isapre_uf_valor con formato de UF
                    uf_valor = contract.isapre_uf_valor or 0
                    # Formato UF con 4 decimales, rellenando con ceros
                    cotizacion_pactada = f"{uf_valor:08.4f}".replace('.', ',')
                else:
                    # Porcentaje u otro tipo - por defecto 8 ceros
                    cotizacion_pactada = "00000000"
            else:
                cotizacion_pactada = ""

            # Campo 80 — Cotización obligatoria (7% de la renta imponible) - cot_obli_isa
            if health_code == '07':
                # Fonasa siempre 8 ceros
                cotizacion_obligatoria = "00000000"
            elif health_code and health_code != '07':
                cotizacion_obligatoria = self._get_payslip_lines(payslip, ['SALUD']) or ""
            else:
                cotizacion_obligatoria = ""

            # Campo 81 — Cotización Adicional Voluntaria
            if health_code == '07':
                # Fonasa siempre 8 ceros
                cotizacion_salud_adicional = "00000000"
            elif health_code and health_code != '07':
                cotizacion_salud_adicional = self._get_payslip_lines(payslip, ['ISAPRE_EXTRA']) or ""
            else:
                cotizacion_salud_adicional = ""

            # Campo 82 — Monto Garantía Explícita de Salud GES (uso futuro)
            monto_ges = "00000000"  

            # Campo 83 — Código CCAF
            company = contract.employee_id.company_id
            codigo_ccaf = company.caja_compensacion or ""

            # Campo 84 — Renta Imponible CCAF
            if codigo_ccaf and codigo_ccaf != '00' and health_code == "07":
                # Solo si la empresa tiene CCAF (no es '00' - Sin CCAF)
                if int(dias_trabajados) > 0:
                    renta_imponible_ccaf = min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope_afiliados_afp or 0)
                else:
                    renta_imponible_ccaf = "00000000"
            else:
                renta_imponible_ccaf = ""

            # Campo 85 — Cotización CCAF
            ccaf_credits = employee.ccaf_deduction_ids.filtered(
                lambda c: c.active and c.remaining_installments > 0 and c.deduction_type == 'credit'
            )
            if ccaf_credits:
                # Sumar todas las cuotas mensuales de créditos activos
                total_installment = sum(ccaf_credits.mapped('installment_amount'))
                creditos_personales_ccaf = f"{int(total_installment):08d}"
            else:
                creditos_personales_ccaf = ""

            # Campo 86 — Descuento Dental CCAF
            # TODO APLICAR PARA CAJA LOS HEROES
            codigo_ex_caja_regimen_ips = ""

            # Campo 87 — Descuentos por Leasing
            ccaf_leasing = employee.ccaf_deduction_ids.filtered(
                lambda c: c.active and c.deduction_type == 'leasing'
            )
            if ccaf_leasing:
                # Sumar todas las cuotas mensuales de leasing activos
                total_leasing = sum(ccaf_leasing.mapped('total_amount'))
                descuentos_ccaf_leasing = f"{int(total_leasing):08d}"  
            else:
                descuentos_ccaf_leasing = ""

            # Campo 88 — Descuentos por seguro de vida
            ccaf_insurance = employee.ccaf_deduction_ids.filtered(
                lambda c: c.active and c.deduction_type == 'insurance'
            )
            if ccaf_insurance:
                    # Sumar todas las cuotas mensuales de seguros activos
                    total_insurance = sum(ccaf_insurance.mapped('total_amount'))
                    renta_imponible_ips_ex_caja = f"{int(total_insurance):08d}"  
            else:
                renta_imponible_ips_ex_caja = ""
       
            # Campo 89 — Otros descuentos CCAF
            cotizacion_ips_ex_caja = ""

            # Campo 90 — Cotización a CCAF de no afiliados a Isapres
            if health_code == '07':
                # Calcular cotización CCAF para trabajadores de Fonasa según si la empresa tiene CCAF
                if int(dias_trabajados) > 0 and renta_imponible_ips != "0":
                    renta_imponible_int = int(renta_imponible_ips)
                    
                    # Verificar si la empresa está afiliada a CCAF
                    company = contract.employee_id.company_id
                    codigo_ccaf = company.caja_compensacion or ""
                    
                    if codigo_ccaf and codigo_ccaf != '00':
                        if previred_indicator.ccaf_empleadores_afiliados:
                            # Usar porcentaje específico para empleadores afiliados a CCAF
                            porcentaje_ccaf = previred_indicator.ccaf_empleadores_afiliados / 100.0
                            cotizacion_ccaf_fonasa = int(renta_imponible_int * porcentaje_ccaf)
                        else:
                            # Fallback: usar 5.2% si no hay indicador
                            cotizacion_ccaf_fonasa = int(renta_imponible_int * 0.052) 
                        
                        codigo_accidente_trabajo_isl = f"{cotizacion_ccaf_fonasa:08d}"  
                    else:
                        # Empleador NO afiliado a CCAF: no hay cotización CCAF
                        codigo_accidente_trabajo_isl = "00000000"
                else:
                    codigo_accidente_trabajo_isl = "00000000"
            else:
                # Si no está en Fonasa, campo vacío
                codigo_accidente_trabajo_isl = ""

            # Campo 91 — Tasa Accidente del Trabajo (ISL) (vacío por defecto)
            tasa_accidente_trabajo_isl = ""

            # Campo 92 — Renta Imponible Mes Anterior a la Licencia (RIMA) - CO
            renta_imponible_licencia = "0"
            
            if hasattr(payslip, 'previred_movement_ids'):
                employee_movements = payslip.previred_movement_ids
                for movement in employee_movements:
                    if movement.code in ["3", "6"]:
                        try:
                            renta_imponible_licencia = self._calculate_renta_imponible_last_month(employee, contract, period_dt)
                        except ValueError as e:
                            _logger.warning(e)
                        break  # si basta con el primero que cumpla


            # Campo 93 — Tipo de Jornada - Jornada Completa o Jornada Parcial (Part-time) 
            if contract.resource_calendar_id.full_time_required_hours >= 30:
                tipo_jornada = "1"
            else:
                tipo_jornada = "0"

            # Campo 94 — Cotización Expectativa de Vida - Monto en $ de cotización aporte empleador - CQ - Seguro de social
            if afp_code != "00" and contract.pension_option == "afp": 
                expectativa_vida = previred_indicator.expectativa_vida / 100
                renta_imponible_valor = renta_imponible('afp')
                tiene_licencia = False
                
                if hasattr(payslip, 'previred_movement_ids'):
                    employee_movements = payslip.previred_movement_ids
                    for movement in employee_movements:
                        if movement.code in ["3", "6"]:
                            tiene_licencia = True
                            break
                
                if tiene_licencia:
                    dias_licencia = self._calculate_license_days(payslip)

                    # Si tiene licencia del mes completo usa el completo del RIMA (Renta Imponible Mes Anterior)
                    if dias_licencia >= 30:
                        cotizacion_expectativa_vida = round(float(renta_imponible_licencia) * expectativa_vida)
                    else:
                        # Si no es mes completo, usa la suma de lo trabajado + RIMA proporcional
                        rima_proporcional = round((float(renta_imponible_licencia) / 30) * dias_licencia)   
                        print( "RIMA Proporcional:", rima_proporcional )     
                        cotizacion_expectativa_vida = round((renta_imponible_valor + rima_proporcional) * expectativa_vida)
                else:
                    cotizacion_expectativa_vida = round(renta_imponible_valor * expectativa_vida)
            else:
                cotizacion_expectativa_vida = "0"

            # Campo 95 — Cotización Rentabilidad Protegida - campo a utilizar a partir de agosto 2026
            cotizacion_rentabilidad_protegida = ""

            # Campo 96 — Código Mutualidad - CS
            company = contract.employee_id.company_id
            if company.has_mutual and company.mutual:
                codigo_mutualidad = company.mutual
            else:
                codigo_mutualidad = "00"  

            # Campo 97 – Renta Imponible Mutual
            if codigo_mutualidad != "00":
                dias_licencia = self._calculate_license_days(payslip)
                if dias_licencia >= 30:
                    renta_imponible_mutual = self._calculate_renta_imponible_last_month(employee, contract, period_dt)
                else:
                    renta_imponible_mutual = int(min(self._get_payslip_lines(payslip, rule_codes=['GROSS']), previred_indicator.tope_afiliados_afp) or 0)
            else:
                renta_imponible_mutual = ""
            
            # Campo 98 – Cotización por Accidente del Trabajo (MUTUAL)
            if codigo_mutualidad != "00":
                cotizacion_accidente_trabajo_mutual = self._get_payslip_lines(payslip, ['APORTE_MUTUAL']) or 0
            else:
                cotizacion_accidente_trabajo_mutual = ""

            # Campo 99 — Sucursal para pago Mutual 
            campo_adicional_99 = ""

            # Campo 100 — Renta Imponible Seguro Cesantía
            if hasattr(contract, 'afc_enrolled') and contract.afc_enrolled:
                # Solo si el trabajador está afiliado al Seguro de Cesantía
                tiene_licencia = False
                if hasattr(payslip, 'previred_movement_ids'):
                    employee_movements = payslip.previred_movement_ids
                    for movement in employee_movements:
                        if movement.code in ["3", "6"]:
                            tiene_licencia = True
                            break
                
                if tiene_licencia:
                    renta_imponible_seguro_cesantia = self._calculate_renta_imponible_last_month(employee, contract, period_dt)
                
                else:
                    # Sin licencia: usar renta imponible normal
                    renta_imponible_seguro_cesantia = renta_imponible('cesantia')
                
                renta_imponible_seguro_cesantia = str(renta_imponible_seguro_cesantia)
              
            else:
                # Si no está afiliado al seguro de cesantía, campo vacío
                renta_imponible_seguro_cesantia = ""

            # Campo 101 — Aporte Trabajador Seguro Cesantía
            aporte_trabajador_cesantia = ""
            # Permitir cálculo si afc_enrolled o afc_enrolled_trabajado es True
            if contract.afc_enrolled_trabajador and renta_imponible_seguro_cesantia and renta_imponible_seguro_cesantia != "00000000":
                renta_cesantia_int = int(renta_imponible_seguro_cesantia)
                # Verificar tipo de contrato
                contract_type = contract.contract_type_id.name.lower() if contract.contract_type_id else ""
                if 'permanent' in contract_type or 'indefinido' in contract_type:
                    # Contrato indefinido: 0,6% trabajador
                    aporte_trabajador = round(renta_cesantia_int * 0.006)
                    aporte_trabajador_cesantia = f"{aporte_trabajador:08d}"
                else:
                    # Contrato plazo fijo: 0% trabajador
                    aporte_trabajador_cesantia = "00000000"

            # Campo 102 — Aporte Empleador Seguro Cesantía - CY
            """
                Contrato indefinido: plazo_indefinido_empleador - Usar contract_type_id 'Contrato Indefinido'
                Contrato plazo fijo: plazo_fijo_empleador - Usar contract_type_id 'Contrato Plazo Fijo'
                Contra indefinido y +11 años: plazo_indefinido_more_11 - Usar contract_type_id 'Contrato Indefinido' y afc_enrolled_trabajador False
            """
            aporte_empleador_cesantia = self._get_payslip_lines(payslip, ['AFC_EMPLEADOR']) or ""

            # Campo 103 — Rut Pagadora Subsidio - CZ
            HEALTH_RUT_MAPPING = {
                "01": "96572800-7",
                "02": "96856780-2",
                "03": "96502530-8",
                "04": "76296619-0",
                "05": "96501450-0",
                "07": "61603000-0",
                "10": "96504160-5",
                "11": "76334370-7",
                "12": "71235700-2",
                "25": "79906120-1",
                "28": "96936100-0",
            }
            MUTUAL_RUT_MAPPING = {
                "01": "70360100-6",
                "02": "70285100-9",
                "03": "70015580-3",
                "00": "61533000-0",
            }
            rut_pagadora_subsidio = "00000000000"
            if movimiento_personal == "3":
                rut_completo = HEALTH_RUT_MAPPING.get(str(health_code).zfill(2), "00000000000")
            elif movimiento_personal == "6":
                rut_completo = MUTUAL_RUT_MAPPING.get(str(codigo_mutualidad).zfill(2), "00000000000")
            else:
                rut_completo = "00000000000"

            # campos 103 y 104 - DA
            if '-' in rut_completo:
                rut_pagadora_subsidio, dv_pagadora_subsidio = rut_completo.split('-')
            else:
                rut_pagadora_subsidio = rut_completo
                dv_pagadora_subsidio = ""

            # Si hay fecha de término de contrato igual al fin de periodo, forzar DV a "0" (mantener lógica previa)
            if contract.date_end:
                if contract.date_end == period_end:
                    dv_pagadora_subsidio = "0"

            # Campo 105 — Centro de Costos, Sucursal, Agencia - DB
            centro_costos = ""
            if contract.analytic_account_id and contract.analytic_account_id.code:
                centro_costos = str(contract.analytic_account_id.code)[:20]  # Máximo 20 caracteres

            # ==================== LOGGING DE DEBUG ====================
            # Logger consolidado al final para debugging de campos críticos
            _logger.warning(f"PREVIRED - {first_name} {paternal_surname} {maternal_surname}")
            _logger.warning(f":COTIZACION FONASA: {cotizacion_fonasa}")
            _logger.warning(f"COTIZACION CCFA: {codigo_accidente_trabajo_isl}")
            # ==================== FIN LOGGING DEBUG ====================

            # Generar línea principal (siempre se genera)
            formatted_line = f"{rut_number};{verification_digit};{paternal_surname};{maternal_surname};{first_name};{previred_gender};{nationality};{payment_type};{period_from};{period_to};{pension_regime};{worker_type};{dias_trabajados};{tipo_linea};{movimiento_personal};{fecha_desde};{fecha_hasta};{tramo_asignacion_familiar};{cargas_simples};{cargas_maternales};{cargas_invalidas};{asignacion_familiar};{asignacion_familiar_retroactiva};{reintegro_cargas_familiares};{subsidio_empleo_joven};{tipo_afp};{renta_imponible_afp};{cotizacion_afp};{cotizacion_sis};{ahorro_voluntario_afp};{renta_imponible_sustitutiva};{tasa_pactada_sustitutiva};{aporte_indemnizacion_sustitutiva};{num_periodos_sustitutivos};{periodo_desde_sustitutivo};{periodo_hasta_sustitutivo};{puesto_trabajo_pesado};{porcentaje_trabajo_pesado};{cotizacion_trabajo_pesado};{codigo_institucion_apvi};{numero_contrato_apvi};{forma_pago_apvi};{cotizacion_apvi};{cotizacion_depositos_convenidos};{codigo_institucion_apvc};{numero_contrato_apvc};{forma_pago_apvc};{cotizacion_trabajador_apvc};{cotizacion_empleador_apvc};{rut_afiliado_voluntario};{dv_afiliado_voluntario};{apellido_paterno_afiliado_voluntario};{apellido_materno_afiliado_voluntario};{nombres_afiliado_voluntario};{codigo_movimiento_afiliado_voluntario};{fecha_desde_afiliado_voluntario};{fecha_hasta_afiliado_voluntario};{codigo_afp_afiliado_voluntario};{monto_capitalizacion_voluntaria};{monto_ahorro_voluntario};{numero_periodos_cotizacion};{codigo_ex_caja_regimen};{tasa_cotizacion_ex_caja_prevision};{renta_imponible_ips};{cotizacion_obligatoria_ips};{renta_imponible_desahucio};{codigo_ex_caja_regimen_desahucio};{tasa_cotizacion_desahucio_ex_cajas};{cotizacion_desahucio};{cotizacion_fonasa};{cotizacion_acc_trabajo_isl};{bonificacion_ley_15386};{descuento_cargas_familiares_ips};{bonos_gobierno};{codigo_institucion_salud};{numero_fun};{renta_imponible_isapre};{moneda_plan_isapre};{cotizacion_pactada};{cotizacion_obligatoria};{cotizacion_salud_adicional};{monto_ges};{codigo_ccaf};{renta_imponible_ccaf};{creditos_personales_ccaf};{codigo_ex_caja_regimen_ips};{descuentos_ccaf_leasing};{renta_imponible_ips_ex_caja};{cotizacion_ips_ex_caja};{codigo_accidente_trabajo_isl};{tasa_accidente_trabajo_isl};{renta_imponible_licencia};{tipo_jornada};{cotizacion_expectativa_vida};{cotizacion_rentabilidad_protegida};{codigo_mutualidad};{renta_imponible_mutual};{cotizacion_accidente_trabajo_mutual};{campo_adicional_99};{renta_imponible_seguro_cesantia};{aporte_trabajador_cesantia};{aporte_empleador_cesantia};{rut_pagadora_subsidio};{dv_pagadora_subsidio};{centro_costos}"
            lines.append(formatted_line)

            # Obtener y procesar los movimientos de personal adicionales
            if hasattr(payslip, 'previred_movement_ids') and payslip.previred_movement_ids:
                employee_movements = payslip.previred_movement_ids
                for movement in employee_movements:
                    movimiento_personal = movement.code or "00"
                    fecha_desde = movement.date_from.strftime('%d-%m-%Y') if movement.date_from else ""
                    fecha_hasta = movement.date_to.strftime('%d-%m-%Y') if movement.date_to else ""
                    tipo_linea = movement.tipo_linea or "1" 

                    aditional_line = f"{rut_number};{verification_digit};{paternal_surname};{maternal_surname};{first_name};{previred_gender};{nationality};{payment_type};{period_from};{period_to};{pension_regime};{worker_type};{''};{tipo_linea};{movimiento_personal};{fecha_desde};{fecha_hasta};{tramo_asignacion_familiar};{cargas_simples};{cargas_maternales};{cargas_invalidas};{asignacion_familiar};{asignacion_familiar_retroactiva};{reintegro_cargas_familiares};{subsidio_empleo_joven};{''};{''};{''};{''};{''};{''};{tasa_pactada_sustitutiva};{aporte_indemnizacion_sustitutiva};{num_periodos_sustitutivos};{periodo_desde_sustitutivo};{periodo_hasta_sustitutivo};{puesto_trabajo_pesado};{porcentaje_trabajo_pesado};{cotizacion_trabajo_pesado};{codigo_institucion_apvi};{numero_contrato_apvi};{forma_pago_apvi};{''};{cotizacion_depositos_convenidos};{codigo_institucion_apvc};{numero_contrato_apvc};{forma_pago_apvc};{cotizacion_trabajador_apvc};{''};{rut_afiliado_voluntario};{dv_afiliado_voluntario};{''};{''};{nombres_afiliado_voluntario};{codigo_movimiento_afiliado_voluntario};{fecha_desde_afiliado_voluntario};{fecha_hasta_afiliado_voluntario};{codigo_afp_afiliado_voluntario};{monto_capitalizacion_voluntaria};{monto_ahorro_voluntario};{numero_periodos_cotizacion};{codigo_ex_caja_regimen};{''};{''};{cotizacion_obligatoria_ips};{renta_imponible_desahucio};{codigo_ex_caja_regimen_desahucio};{tasa_cotizacion_desahucio_ex_cajas};{cotizacion_desahucio};{''};{cotizacion_acc_trabajo_isl};{bonificacion_ley_15386};{descuento_cargas_familiares_ips};{bonos_gobierno};{codigo_institucion_salud};{numero_fun};{renta_imponible_isapre};{moneda_plan_isapre};{cotizacion_pactada};{cotizacion_obligatoria};{cotizacion_salud_adicional};{monto_ges};{codigo_ccaf};{''};{creditos_personales_ccaf};{codigo_ex_caja_regimen_ips};{descuentos_ccaf_leasing};{''};{cotizacion_ips_ex_caja};{''};{''};{''};{tipo_jornada};{''};{cotizacion_rentabilidad_protegida};{''};{''};{''};{''};{''};{''};{''};{rut_pagadora_subsidio};{dv_pagadora_subsidio};{centro_costos}"
                    lines.append(aditional_line)
                    # _logger.info(f"Línea adicional por movimiento de personal {movimiento_personal} para {first_name} {paternal_surname} {maternal_surname}")
                    
        # Generar contenido TXT con formato Windows (CR+LF)
        txt_content = '\r\n'.join(lines)

        return request.make_response(
            txt_content,
            headers=[
                ('Content-Type', 'text/plain'),
                ('Content-Disposition', f'attachment; filename="previred_{period_str}.txt"')
            ]
        )

    @http.route('/hr_payroll/previred/csv', auth='user')
    def download_previred_csv(self, period=None, company_id=None, **kw):
        """
        Genera un archivo CSV con los mismos datos del TXT de Previred.
        Los encabezados son números del 1 al 105 para facilitar la visualización.
        """
        if period:
            try:
                period_dt = datetime.strptime(period, '%m%Y')
            except Exception:
                period_dt = datetime.now()
        else:
            period_dt = datetime.now()
        period_str = period_dt.strftime('%m%Y')
        
        # Obtener días del mes correspondiente
        year = period_dt.year
        month = period_dt.month
        period_str = period_dt.strftime('%m%Y')

        start_of_month = date(year, month, 1)

        # Calcular el último día del mes
        if month == 12:
            end_of_month = date(year + 1, 1, 1)
        else:
            end_of_month = date(year, month + 1, 1)
            
        _, dias_mes = calendar.monthrange(year, month)

        # Obtener solo contratos activos
        period_start = period_dt.replace(day=1).date()
        period_end = period_dt.replace(day=dias_mes).date()

        domain = [
            ('date_from', '>=', period_start),
            ('date_from', '<=', period_end),
            ('state', 'in', ['verify', 'done', 'paid']),
        ]

        if company_id:
            domain.append(('company_id', '=', int(company_id)))

        payslips = request.env['hr.payslip'].sudo().search(domain, order='employee_id')

        # Crear el buffer CSV
        output = io.StringIO()
        csv_writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Escribir encabezados (números del 1 al 105)
        headers = [str(i) for i in range(1, 106)]
        csv_writer.writerow(headers)

        for payslip in payslips:
            employee = payslip.employee_id
            contract = payslip.contract_id or employee.contract_id

            # Buscar liquidación de sueldo del empleado para el período
            payslip = request.env['hr.payslip'].sudo().search([
                ('employee_id', '=', employee.id),
                ('date_from', '>=', period_start),
                ('date_from', '<=', period_end),
            ], limit=1)

            # Helper para extraer código de institución de salud para Previred TXT (primera parte)
            def get_health_institution_code():
                health_institution = contract.health_institution or ''
                if ' - ' in health_institution:
                    return health_institution.split(' - ')[0]
                return health_institution
            
            health_code = get_health_institution_code()

            # Indicador previred
            previred_indicator = request.env['previred.indicator'].sudo().search([
                ('date', '>=', start_of_month),
                ('date', '<', end_of_month)
            ], order='date desc', limit=1)

            # Campo 1 - RUT Trabajador 
            raw_rut = employee.identification_id or ''

            # Campo 2 - DV Trabajador
            if raw_rut:
                clean_rut = raw_rut.replace('.', '').replace('-', '')
                if len(clean_rut) >= 2:
                    rut_number = clean_rut[:-1]
                    verification_digit = clean_rut[-1]
                else:
                    rut_number = "0"
                    verification_digit = "0"
            else:
                rut_number = "0"
                verification_digit = "0"

            # Campo 3,4 y 5 - Apellido Paterno | Apellido Materno | Nombre
            employee_name = employee.name or ''
            import unicodedata
            def normalize_name_part(s):
                if not s:
                    return ''
                # Eliminar tildes y pasar a mayúsculas
                s = unicodedata.normalize('NFKD', s)
                s = ''.join(c for c in s if not unicodedata.combining(c))
                return s.upper()

            name_parts = employee_name.strip().split()
            first_name = normalize_name_part(name_parts[0]) if len(name_parts) > 0 else ''
            paternal_surname = normalize_name_part(name_parts[1]) if len(name_parts) > 1 else ''
            maternal_surname = normalize_name_part(name_parts[2]) if len(name_parts) > 2 else ''

            # Campo 6 - Genero
            gender = employee.gender or ''
            previred_gender = 'M' if gender == 'male' else ('F' if gender == 'female' else 'M')
            
            # Campo 7 - País
            country = employee.country_id
            nationality = '0' if country and country.code == 'CL' else '1'

            # Campo 8 - Tipo de Pago
            payment_type = '01'

            # Campo 9 - Periodo (Desde)
            period_from = period_str

            # Campo 10 - Periodo (Hasta)
            period_to = period_str

            # Campo 11 - Regimen previsonal
            pension_option = contract.pension_option or ''
            if pension_option.lower() == 'afp':
                pension_regime = 'AFP'
            elif pension_option.lower() == 'inp':
                pension_regime = 'INP'
            elif pension_option.lower() == 'sip':
                pension_regime = 'SIP'
            else:
                pension_regime = 'AFP'

            # Campo 12 — Tipo de Trabajador
            worker_type = '0'
            # Tipo 2: Pensionado mayor de 65 años sin cotización AFP
            if  contract.is_retired_elderly:
                worker_type = '2'
            elif employee.birthday:
                today = period_dt.date()
                age = today.year - employee.birthday.year - ((today.month, today.day) < (employee.birthday.month, employee.birthday.day))
                if age > 65:
                    worker_type = '3'

            # Campo 13 - Dias trabajados            
            dias_trabajados = self._get_real_worked_days_from_payslip(payslip)

            # Calcular renta imponible
            def renta_imponible(tope_type):
                return self._calculate_previred_taxable_income(
                    employee, contract, period_start, period_end, pension_regime, previred_indicator, tope_type=tope_type, payslip=payslip
                )

            # Campo 14 — Tipo de Línea 
            # "0" = Línea principal (siempre con movimiento "0")
            # "1" = Línea adicional (donde van los movimientos reales)
            tipo_linea = "0"  # Línea principal siempre es "0"

            # Campo 15 - Código Movimiento de Personal / Campo 16 — Fecha Desde / Campo 17 - Fecha Hasta
            movimiento_personal = "0"
            fecha_desde = ""
            fecha_hasta = ""

            # Campo 18 — Tramo Asignación Familiar
            if contract.has_family_loads and contract.family_loads_segment:
                # Si tiene cargas y segmento definido, usar el segmento
                segment = contract.family_loads_segment.upper()
                if segment in ['A', 'B', 'C']:
                    tramo_asignacion_familiar = segment
                else:
                    tramo_asignacion_familiar = "D"
            elif contract.has_family_loads:
                # Si tiene cargas pero no segmento, calcular por renta (requiere implementación adicional)
                # Por ahora asignar A como default
                tramo_asignacion_familiar = "A"
            else:
                # Si no tiene cargas familiares, siempre es D
                tramo_asignacion_familiar = "D"

            # Campos 19, 20, 21 — Cantidad de cargas familiares
            cargas_simples = str(contract.family_simple_loads_count or 0)
            cargas_maternales = str(contract.family_maternal_loads_count or 0)
            cargas_invalidas = str(contract.family_invalid_loads_count or 0)

            # Campo 22 — Monto en $ Asignación Familiar
            asignacion_familiar = "0"
            if contract.has_family_loads and tramo_asignacion_familiar in ['A', 'B', 'C']:
                # Obtener el indicador previred más reciente para valores de cargas
                previred_indicator = request.env['previred.indicator'].sudo().search([
                    ('date', '<=', period_dt.date())
                ], order='date desc', limit=1)
                
                if previred_indicator:
                    # Obtener valor de carga según tramo
                    if tramo_asignacion_familiar == 'A':
                        valor_carga = previred_indicator.tramo_a or 0
                    elif tramo_asignacion_familiar == 'B':
                        valor_carga = previred_indicator.tramo_b or 0
                    elif tramo_asignacion_familiar == 'C':
                        valor_carga = previred_indicator.tramo_c or 0
                    else:
                        valor_carga = 0
                    
                    if valor_carga > 0:
                        # Calcular cargas totales: CT = cargas simples + 2 × cargas inválidas + cargas maternales
                        cargas_totales = (
                            int(cargas_simples) + 
                            (2 * int(cargas_invalidas)) + 
                            int(cargas_maternales)
                        )
                        
                        # Asignación Familiar = VC × CT
                        if cargas_totales > 0:
                            asignacion_familiar_amount = int(valor_carga * cargas_totales)
                            asignacion_familiar = str(asignacion_familiar_amount)

            # Campo 23 — Monto en $ Asignación Familiar Retroactiva
            asignacion_familiar_retroactiva = ""

            # Campo 24 — Monto en $ del reintegro de cargas familiares
            reintegro_cargas_familiares = ""

            # Campo 25 — Subsidio empleo joven (N por defecto)
            subsidio_empleo_joven = "N"

            # Campo 26 — Tipo de AFP
            afp_option = contract.afp_option or ''
            # Extraer solo la primera parte del código (antes del guión)
            afp_code = afp_option.split(' - ')[0] if ' - ' in afp_option else afp_option
            if afp_code in ['03', '05', '08', '29', '33', '34', '35']:
                tipo_afp = afp_code
            else:
                tipo_afp = "00"  

            # Campo 27 — Renta Imponible AFP
            if contract.pension_option in ['inp', 'sip']:
                renta_imponible_afp = 0
            else:
                renta_imponible_afp = round(int(min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope_afiliados_afp or 0)))

            # Campo 28 — Cotización AFP
            cotizacion_afp = self._get_payslip_lines(payslip, rule_codes=['AFP', 'AFP_EMP']) or "0"

            # Campo 29 — Cotización Seguro de Invalidez y Sobrevivencia (SIS)
            cotizacion_sis = self._get_payslip_lines(payslip, rule_codes=['SIS']) or ""
            
            # Campo 30 — Cuenta de Ahorro Voluntario AFP (vacío por defecto)
            ahorro_voluntario_afp = ""

            # Campo 31 — Renta Imponible Sustitutiva AFP (vacío por defecto)
            renta_imponible_sustitutiva = ""

            # Campo 32 — Tasa Pactada Sustitutiva (vacío por defecto)
            tasa_pactada_sustitutiva = ""

            # Campo 33 — Aporte Indemnización Sustitutiva (vacío por defecto)
            aporte_indemnizacion_sustitutiva = ""

            # Campo 34 — Número de Períodos Sustitutivos (vacío por defecto)
            num_periodos_sustitutivos = ""

            # Campo 35 — Período Desde Sustitutivo (vacío por defecto)
            periodo_desde_sustitutivo = ""

            # Campo 36 — Período Hasta Sustitutivo (vacío por defecto)
            periodo_hasta_sustitutivo = ""

            # Campo 37 — Puesto de Trabajo Pesado (vacío por defecto)
            puesto_trabajo_pesado = ""

            # Campo 38 — Porcentaje Cotización Trabajo Pesado (vacío por defecto)
            porcentaje_trabajo_pesado = ""

            # Campo 39 — Cotización Trabajo Pesado (vacío por defecto)
            cotizacion_trabajo_pesado = ""

            # TODO LINEA EXTRA CUANDO TIENE APVI / APVC
            # Campo 40 — Código de la Institución APVI
            if contract.has_apvi:
                codigo_institucion_apvi = contract.institucion_apvi_apvc or ""
            else:
                codigo_institucion_apvi = ""

            # Campo 41 — Número de Contrato APVI (vacío por defecto)
            numero_contrato_apvi = ""

            # Campo 42 — Forma de Pago APVI
            if contract.has_apvi:
                forma_pago_apvi = contract.pay_format_apvi_apc or ""
            else:
                forma_pago_apvi = ""

            # Campo 43 — Cotización APVI
            if contract.has_apvi:
                monto_apvi = int(contract.cotizacion_apvi or 0)
                cotizacion_apvi = f"{monto_apvi:08d}" if monto_apvi > 0 else ""
            else:
                cotizacion_apvi = ""

            # Campo 44 — Cotización Depósitos Convenidos (vacío por defecto)
            cotizacion_depositos_convenidos = ""

            # Campo 45 — Código Institución Autorizada APVC (vacío por defecto)
            if contract.has_apvc:
                codigo_institucion_apvc = contract.institucion_apvi_apvc or ""
            else:                           
                codigo_institucion_apvc = ""

            # Campo 46 — Número de Contrato APVC (vacío por defecto)
            numero_contrato_apvc = ""

            # Campo 47 — Forma de Pago APVC (vacío por defecto)
            if contract.has_apvc:
                forma_pago_apvc = contract.pay_format_apvi_apc or ""
            else:
                forma_pago_apvc = ""

            # Campo 48 — Cotización Trabajador APVC (vacío por defecto)|
            if contract.has_apvc:
                monto_apvc_trabajador = int(contract.cotizacion_apvc_trabajador or 0)
                cotizacion_trabajador_apvc = f"{monto_apvc_trabajador:08d}" if monto_apvc_trabajador > 0 else ""
            else:
                cotizacion_trabajador_apvc = ""

            # Campo 49 — Cotización Empleador APVC (vacío por defecto)
            if contract.has_apvc:
                monto_apvc_empleador = int(contract.cotizacion_apvc_empleador or 0)
                cotizacion_empleador_apvc = f"{monto_apvc_empleador:08d}" if monto_apvc_empleador > 0 else ""
            else:
                cotizacion_empleador_apvc = ""

            # Campo 50 — RUT Afiliado Voluntario (vacío por defecto)
            rut_afiliado_voluntario = ""

            # Campo 51 — DV Afiliado Voluntario (vacío por defecto)
            dv_afiliado_voluntario = ""

            # Campo 52 — Apellido Paterno Afiliado Voluntario (vacío por defecto)
            apellido_paterno_afiliado_voluntario = ""

            # Campo 53 — Apellido Materno Afiliado Voluntario (vacío por defecto)
            apellido_materno_afiliado_voluntario = ""

            # Campo 54 — Nombres Afiliado Voluntario (vacío por defecto)
            nombres_afiliado_voluntario = ""

            # Campo 55 — Código Movimiento de Personal Afiliado Voluntario (vacío por defecto)
            codigo_movimiento_afiliado_voluntario = "00"

            # Campo 56 — Fecha desde Afiliado Voluntario (vacío por defecto)
            fecha_desde_afiliado_voluntario = ""

            # Campo 57 — Fecha hasta Afiliado Voluntario (vacío por defecto)
            fecha_hasta_afiliado_voluntario = ""

            # Campo 58 — Código de la AFP Afiliado Voluntario (vacío por defecto)
            codigo_afp_afiliado_voluntario = ""

            # Campo 59 — Monto Capitalización Voluntaria (vacío por defecto)
            monto_capitalizacion_voluntaria = ""

            # Campo 60 — Monto Ahorro Voluntario (vacío por defecto)
            monto_ahorro_voluntario = ""

            # Campo 61 — Número de períodos de cotización (vacío por defecto)
            numero_periodos_cotizacion = ""

            # Campo 62 — Código EX-Caja Régimen (vacío por defecto)
            codigo_ex_caja_regimen = ""

            # Campo 63 — Tasa Cotización Ex-Caja Previsión (vacío por defecto)
            tasa_cotizacion_ex_caja_prevision = ""

            # Campo 64 — Renta Imponible Fonasa
            if health_code == '07':
                renta_imponible_ips = min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope_afiliados_afp or 0)
            else:
                renta_imponible_ips = ""

            # Campo 65 — Cotización Obligatoria IPS (vacío por defecto)
            cotizacion_obligatoria_ips = ""

            # Campo 66 — Renta Imponible Desahucio (vacío por defecto)
            renta_imponible_desahucio = ""

            # Campo 67 — Código Ex-Caja Régimen Desahucio (vacío por defecto)
            codigo_ex_caja_regimen_desahucio = ""

            # Campo 68 — Tasa Cotización Desahucio Ex-Cajas de Previsión (vacío por defecto)
            tasa_cotizacion_desahucio_ex_cajas = ""

            # Campo 69 — Cotización Desahucio (vacío por defecto)
            cotizacion_desahucio = ""

            # Campo 70 — Cotización Fonasa
            if health_code == '07':
                tasa_fonasa = (previred_indicator.fonasa_empleadores_afiliados + previred_indicator.ccaf_empleadores_afiliados) / 100
                cotizacion_fonasa = min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope_afiliados_afp or 0) * tasa_fonasa
                cotizacion_fonasa = int(round(cotizacion_fonasa))
            else:
                cotizacion_fonasa = ""

            # Campo 71 — Cotización Acc. Trabajo (ISL) (vacío por defecto)
            cotizacion_acc_trabajo_isl = ""

            # Campo 72 — Bonificación Ley 15.386 (vacío por defecto)
            bonificacion_ley_15386 = ""

            # Campo 73 — Descuento por cargas familiares de IPS (ex INP) (vacío por defecto)
            descuento_cargas_familiares_ips = ""

            # Campo 74 — Bonos Gobierno (vacío por defecto)
            bonos_gobierno = ""

            # Campo 75 — Código Institución de Salud
            codigo_institucion_salud = health_code

            # Campo 76 — Número del FUN (vacio por defecto)
            numero_fun = "00000000"

            # Campo 77 — Renta Imponible Isapre - impo_isapre
            if health_code == '07':
                # Si está en Fonasa, usar 8 ceros
                renta_imponible_isapre = "00000000"
            elif health_code and health_code != '07':
                renta_imponible_isapre = round(int(min(self._get_payslip_lines(payslip, rule_codes=['GROSS']), previred_indicator.tope_afiliados_afp or 0)))
            else:
                renta_imponible_isapre = ""

            # Campo 78 — Moneda del plan pactado Isapre
            if health_code == '07':
                # Fonasa siempre es 1
                moneda_plan_isapre = "1"
            elif health_code and health_code != '07':
                # Isapre: si el tipo de cálculo es UF es 2, sino es 1
                if contract.isapre_calc_type == 'uf':
                    moneda_plan_isapre = "2"
                else:
                    moneda_plan_isapre = "1"
            else:
                moneda_plan_isapre = ""

            # Campo 79 — Cotización Pactada - cot_pactada
            if health_code == '07':
                # Fonasa siempre 8 ceros
                cotizacion_pactada = "00000000"
            elif health_code and health_code != '07':
                # Isapre: usar monto según tipo de cálculo
                if contract.isapre_calc_type == 'clp':
                    # Plan en CLP - usar isapre_plan_monto
                    monto_clp = int(contract.isapre_plan_monto or 0)
                    cotizacion_pactada = f"{monto_clp:08d}" 
                elif contract.isapre_calc_type == 'uf':
                    # Monto en UF - usar isapre_uf_valor con formato de UF
                    uf_valor = contract.isapre_uf_valor or 0
                    # Formato UF con 4 decimales, rellenando con ceros
                    cotizacion_pactada = f"{uf_valor:08.4f}".replace('.', ',')
                else:
                    # Porcentaje u otro tipo - por defecto 8 ceros
                    cotizacion_pactada = "00000000"
            else:
                cotizacion_pactada = ""

            # Campo 80 — Cotización obligatoria (7% de la renta imponible) - cot_obli_isa
            if health_code == '07':
                # Fonasa siempre 8 ceros
                cotizacion_obligatoria = "00000000"
            elif health_code and health_code != '07':
                cotizacion_obligatoria = self._get_payslip_lines(payslip, ['SALUD']) or ""
            else:
                cotizacion_obligatoria = ""

            # Campo 81 — Cotización Adicional Voluntaria
            if health_code == '07':
                # Fonasa siempre 8 ceros
                cotizacion_salud_adicional = "00000000"
            elif health_code and health_code != '07':
                cotizacion_salud_adicional = self._get_payslip_lines(payslip, ['ISAPRE_EXTRA']) or ""
            else:
                cotizacion_salud_adicional = ""

            # Campo 82 — Monto Garantía Explícita de Salud GES (uso futuro)
            monto_ges = "00000000"  

            # Campo 83 — Código CCAF
            company = contract.employee_id.company_id
            codigo_ccaf = company.caja_compensacion or ""

            # Campo 84 — Renta Imponible CCAF
            if codigo_ccaf and codigo_ccaf != '00' and health_code == "07":
                # Solo si la empresa tiene CCAF (no es '00' - Sin CCAF)
                if int(dias_trabajados) > 0:
                    renta_imponible_ccaf = min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope_afiliados_afp or 0)
                else:
                    renta_imponible_ccaf = "00000000"
            else:
                renta_imponible_ccaf = ""

            # Campo 85 — Cotización CCAF
            ccaf_credits = employee.ccaf_deduction_ids.filtered(
                lambda c: c.active and c.remaining_installments > 0 and c.deduction_type == 'credit'
            )
            if ccaf_credits:
                # Sumar todas las cuotas mensuales de créditos activos
                total_installment = sum(ccaf_credits.mapped('installment_amount'))
                creditos_personales_ccaf = f"{int(total_installment):08d}"
            else:
                creditos_personales_ccaf = ""

            # Campo 86 — Descuento Dental CCAF
            # TODO APLICAR PARA CAJA LOS HEROES
            codigo_ex_caja_regimen_ips = ""

            # Campo 87 — Descuentos por Leasing
            ccaf_leasing = employee.ccaf_deduction_ids.filtered(
                lambda c: c.active and c.deduction_type == 'leasing'
            )
            if ccaf_leasing:
                # Sumar todas las cuotas mensuales de leasing activos
                total_leasing = sum(ccaf_leasing.mapped('total_amount'))
                descuentos_ccaf_leasing = f"{int(total_leasing):08d}"  
            else:
                descuentos_ccaf_leasing = ""

            # Campo 88 — Descuentos por seguro de vida
            ccaf_insurance = employee.ccaf_deduction_ids.filtered(
                lambda c: c.active and c.deduction_type == 'insurance'
            )
            if ccaf_insurance:
                    # Sumar todas las cuotas mensuales de seguros activos
                    total_insurance = sum(ccaf_insurance.mapped('total_amount'))
                    renta_imponible_ips_ex_caja = f"{int(total_insurance):08d}"  
            else:
                renta_imponible_ips_ex_caja = ""
       
            # Campo 89 — Otros descuentos CCAF
            cotizacion_ips_ex_caja = ""

            # Campo 90 — Cotización a CCAF de no afiliados a Isapres
            if health_code == '07':
                # Calcular cotización CCAF para trabajadores de Fonasa según si la empresa tiene CCAF
                if int(dias_trabajados) > 0 and renta_imponible_ips != "0":
                    renta_imponible_int = int(renta_imponible_ips)
                    
                    # Verificar si la empresa está afiliada a CCAF
                    company = contract.employee_id.company_id
                    codigo_ccaf = company.caja_compensacion or ""
                    
                    if codigo_ccaf and codigo_ccaf != '00':
                        if previred_indicator.ccaf_empleadores_afiliados:
                            # Usar porcentaje específico para empleadores afiliados a CCAF
                            porcentaje_ccaf = previred_indicator.ccaf_empleadores_afiliados / 100.0
                            cotizacion_ccaf_fonasa = int(renta_imponible_int * porcentaje_ccaf)
                        else:
                            # Fallback: usar 5.2% si no hay indicador
                            cotizacion_ccaf_fonasa = int(renta_imponible_int * 0.052) 
                        
                        codigo_accidente_trabajo_isl = f"{cotizacion_ccaf_fonasa:08d}"  
                    else:
                        # Empleador NO afiliado a CCAF: no hay cotización CCAF
                        codigo_accidente_trabajo_isl = "00000000"
                else:
                    codigo_accidente_trabajo_isl = "00000000"
            else:
                # Si no está en Fonasa, campo vacío
                codigo_accidente_trabajo_isl = ""

            # Campo 91 — Tasa Accidente del Trabajo (ISL) (vacío por defecto)
            tasa_accidente_trabajo_isl = ""

            # Campo 92 — Renta Imponible Mes Anterior a la Licencia (RIMA) - CO
            renta_imponible_licencia = "0"
            
            if hasattr(payslip, 'previred_movement_ids'):
                employee_movements = payslip.previred_movement_ids
                for movement in employee_movements:
                    if movement.code in ["3", "6"]:
                        try:
                            renta_imponible_licencia = self._calculate_renta_imponible_last_month(employee, contract, period_dt)
                        except ValueError as e:
                            _logger.warning(e)
                        break  # si basta con el primero que cumpla


            # Campo 93 — Tipo de Jornada - Jornada Completa o Jornada Parcial (Part-time) 
            if contract.resource_calendar_id.full_time_required_hours >= 30:
                tipo_jornada = "1"
            else:
                tipo_jornada = "0"

            # Campo 94 — Cotización Expectativa de Vida - Monto en $ de cotización aporte empleador - CQ - Seguro de social
            if afp_code != "00" and contract.pension_option == "afp": 
                expectativa_vida = previred_indicator.expectativa_vida / 100
                renta_imponible_valor = renta_imponible('afp')
                tiene_licencia = False
                
                if hasattr(payslip, 'previred_movement_ids'):
                    employee_movements = payslip.previred_movement_ids
                    for movement in employee_movements:
                        if movement.code in ["3", "6"]:
                            tiene_licencia = True
                            break
                
                if tiene_licencia:
                    dias_licencia = self._calculate_license_days(payslip)

                    # Si tiene licencia del mes completo usa el completo del RIMA (Renta Imponible Mes Anterior)
                    if dias_licencia >= 30:
                        cotizacion_expectativa_vida = round(float(renta_imponible_licencia) * expectativa_vida)
                    else:
                        # Si no es mes completo, usa la suma de lo trabajado + RIMA proporcional
                        rima_proporcional = round((float(renta_imponible_licencia) / 30) * dias_licencia)   
                        print( "RIMA Proporcional:", rima_proporcional )     
                        cotizacion_expectativa_vida = round((renta_imponible_valor + rima_proporcional) * expectativa_vida)
                else:
                    cotizacion_expectativa_vida = round(renta_imponible_valor * expectativa_vida)
            else:
                cotizacion_expectativa_vida = "0"

            # Campo 95 — Cotización Rentabilidad Protegida - campo a utilizar a partir de agosto 2026
            cotizacion_rentabilidad_protegida = ""

            # Campo 96 — Código Mutualidad - CS
            company = contract.employee_id.company_id
            if company.has_mutual and company.mutual:
                codigo_mutualidad = company.mutual
            else:
                codigo_mutualidad = "00"  

            # Campo 97 – Renta Imponible Mutual
            if codigo_mutualidad != "00":
                dias_licencia = self._calculate_license_days(payslip)
                if dias_licencia >= 30:
                    renta_imponible_mutual = self._calculate_renta_imponible_last_month(employee, contract, period_dt)
                else:
                    renta_imponible_mutual = int(min(self._get_payslip_lines(payslip, rule_codes=['GROSS']), previred_indicator.tope_afiliados_afp) or 0)
            else:
                renta_imponible_mutual = ""
            
            # Campo 98 – Cotización por Accidente del Trabajo (MUTUAL)
            if codigo_mutualidad != "00":
                cotizacion_accidente_trabajo_mutual = self._get_payslip_lines(payslip, ['APORTE_MUTUAL']) or 0
            else:
                cotizacion_accidente_trabajo_mutual = ""

            # Campo 99 — Sucursal para pago Mutual 
            campo_adicional_99 = ""

            # Campo 100 — Renta Imponible Seguro Cesantía
            if hasattr(contract, 'afc_enrolled') and contract.afc_enrolled:
                # Solo si el trabajador está afiliado al Seguro de Cesantía
                tiene_licencia = False
                if hasattr(payslip, 'previred_movement_ids'):
                    employee_movements = payslip.previred_movement_ids
                    for movement in employee_movements:
                        if movement.code in ["3", "6"]:
                            tiene_licencia = True
                            break
                
                if tiene_licencia:
                    renta_imponible_seguro_cesantia = self._calculate_renta_imponible_last_month(employee, contract, period_dt)
                
                else:
                    # Sin licencia: usar renta imponible normal
                    renta_imponible_seguro_cesantia = renta_imponible('cesantia')
                
                renta_imponible_seguro_cesantia = str(renta_imponible_seguro_cesantia)
              
            else:
                # Si no está afiliado al seguro de cesantía, campo vacío
                renta_imponible_seguro_cesantia = ""

            # Campo 101 — Aporte Trabajador Seguro Cesantía
            aporte_trabajador_cesantia = ""
            # Permitir cálculo si afc_enrolled o afc_enrolled_trabajado es True
            if contract.afc_enrolled_trabajador and renta_imponible_seguro_cesantia and renta_imponible_seguro_cesantia != "00000000":
                renta_cesantia_int = int(renta_imponible_seguro_cesantia)
                # Verificar tipo de contrato
                contract_type = contract.contract_type_id.name.lower() if contract.contract_type_id else ""
                if 'permanent' in contract_type or 'indefinido' in contract_type:
                    # Contrato indefinido: 0,6% trabajador
                    aporte_trabajador = round(renta_cesantia_int * 0.006)
                    aporte_trabajador_cesantia = f"{aporte_trabajador:08d}"
                else:
                    # Contrato plazo fijo: 0% trabajador
                    aporte_trabajador_cesantia = "00000000"

            # Campo 102 — Aporte Empleador Seguro Cesantía - CY
            """
                Contrato indefinido: plazo_indefinido_empleador - Usar contract_type_id 'Contrato Indefinido'
                Contrato plazo fijo: plazo_fijo_empleador - Usar contract_type_id 'Contrato Plazo Fijo'
                Contra indefinido y +11 años: plazo_indefinido_more_11 - Usar contract_type_id 'Contrato Indefinido' y afc_enrolled_trabajador False
            """
            aporte_empleador_cesantia = self._get_payslip_lines(payslip, ['AFC_EMPLEADOR']) or ""

            # Campo 103 — Rut Pagadora Subsidio - CZ
            HEALTH_RUT_MAPPING = {
                "01": "96572800-7",
                "02": "96856780-2",
                "03": "96502530-8",
                "04": "76296619-0",
                "05": "96501450-0",
                "07": "61603000-0",
                "10": "96504160-5",
                "11": "76334370-7",
                "12": "71235700-2",
                "25": "79906120-1",
                "28": "96936100-0",
            }
            MUTUAL_RUT_MAPPING = {
                "01": "70360100-6",
                "02": "70285100-9",
                "03": "70015580-3",
                "00": "61533000-0",
            }
            rut_pagadora_subsidio = "00000000000"
            if movimiento_personal == "3":
                rut_completo = HEALTH_RUT_MAPPING.get(str(health_code).zfill(2), "00000000000")
            elif movimiento_personal == "6":
                rut_completo = MUTUAL_RUT_MAPPING.get(str(codigo_mutualidad).zfill(2), "00000000000")
            else:
                rut_completo = "00000000000"

            # campos 103 y 104 - DA
            if '-' in rut_completo:
                rut_pagadora_subsidio, dv_pagadora_subsidio = rut_completo.split('-')
            else:
                rut_pagadora_subsidio = rut_completo
                dv_pagadora_subsidio = ""

            # Si hay fecha de término de contrato igual al fin de periodo, forzar DV a "0" (mantener lógica previa)
            if contract.date_end:
                if contract.date_end == period_end:
                    dv_pagadora_subsidio = "0"

            # Campo 105 — Centro de Costos, Sucursal, Agencia - DB
            centro_costos = ""
            if contract.analytic_account_id and contract.analytic_account_id.code:
                centro_costos = str(contract.analytic_account_id.code)[:20]  # Máximo 20 caracteres

            # Crear fila con los 105 campos
            row = [
                rut_number, verification_digit, paternal_surname, maternal_surname, first_name,
                previred_gender, nationality, payment_type, period_from, period_to,
                pension_regime, worker_type, dias_trabajados, tipo_linea, movimiento_personal,
                fecha_desde, fecha_hasta, tramo_asignacion_familiar, cargas_simples, cargas_maternales,
                cargas_invalidas, asignacion_familiar, asignacion_familiar_retroactiva, reintegro_cargas_familiares, subsidio_empleo_joven,
                tipo_afp, renta_imponible_afp, cotizacion_afp, cotizacion_sis, ahorro_voluntario_afp,
                renta_imponible_sustitutiva, tasa_pactada_sustitutiva, aporte_indemnizacion_sustitutiva, num_periodos_sustitutivos, periodo_desde_sustitutivo,
                periodo_hasta_sustitutivo, puesto_trabajo_pesado, porcentaje_trabajo_pesado, cotizacion_trabajo_pesado, codigo_institucion_apvi,
                numero_contrato_apvi, forma_pago_apvi, cotizacion_apvi, cotizacion_depositos_convenidos, codigo_institucion_apvc,
                numero_contrato_apvc, forma_pago_apvc, cotizacion_trabajador_apvc, cotizacion_empleador_apvc, rut_afiliado_voluntario,
                dv_afiliado_voluntario, apellido_paterno_afiliado_voluntario, apellido_materno_afiliado_voluntario, nombres_afiliado_voluntario, codigo_movimiento_afiliado_voluntario,
                fecha_desde_afiliado_voluntario, fecha_hasta_afiliado_voluntario, codigo_afp_afiliado_voluntario, monto_capitalizacion_voluntaria, monto_ahorro_voluntario,
                numero_periodos_cotizacion, codigo_ex_caja_regimen, tasa_cotizacion_ex_caja_prevision, renta_imponible_ips, cotizacion_obligatoria_ips,
                renta_imponible_desahucio, codigo_ex_caja_regimen_desahucio, tasa_cotizacion_desahucio_ex_cajas, cotizacion_desahucio, cotizacion_fonasa,
                cotizacion_acc_trabajo_isl, bonificacion_ley_15386, descuento_cargas_familiares_ips, bonos_gobierno, codigo_institucion_salud,
                numero_fun, renta_imponible_isapre, moneda_plan_isapre, cotizacion_pactada, cotizacion_obligatoria,
                cotizacion_salud_adicional, monto_ges, codigo_ccaf, renta_imponible_ccaf, creditos_personales_ccaf,
                codigo_ex_caja_regimen_ips, descuentos_ccaf_leasing, renta_imponible_ips_ex_caja, cotizacion_ips_ex_caja, codigo_accidente_trabajo_isl,
                tasa_accidente_trabajo_isl, renta_imponible_licencia, tipo_jornada, cotizacion_expectativa_vida, cotizacion_rentabilidad_protegida,
                codigo_mutualidad, renta_imponible_mutual, cotizacion_accidente_trabajo_mutual, campo_adicional_99, renta_imponible_seguro_cesantia,
                aporte_trabajador_cesantia, aporte_empleador_cesantia, rut_pagadora_subsidio, dv_pagadora_subsidio, centro_costos
            ]
            csv_writer.writerow(row)

            # Obtener y procesar los movimientos de personal adicionales
            if hasattr(payslip, 'previred_movement_ids') and payslip.previred_movement_ids:
                employee_movements = payslip.previred_movement_ids
                for movement in employee_movements:
                    movimiento_personal = movement.code or "00"
                    fecha_desde = movement.date_from.strftime('%d-%m-%Y') if movement.date_from else ""
                    fecha_hasta = movement.date_to.strftime('%d-%m-%Y') if movement.date_to else ""
                    tipo_linea = movement.tipo_linea or "1" 

                    additional_row = [
                        rut_number, verification_digit, paternal_surname, maternal_surname, first_name,
                        previred_gender, nationality, payment_type, period_from, period_to,
                        pension_regime, worker_type, "", tipo_linea, movimiento_personal,
                        fecha_desde, fecha_hasta, tramo_asignacion_familiar, cargas_simples, cargas_maternales,
                        cargas_invalidas, asignacion_familiar, asignacion_familiar_retroactiva, reintegro_cargas_familiares, subsidio_empleo_joven,
                        "", "", "", "", "",
                        "", tasa_pactada_sustitutiva, aporte_indemnizacion_sustitutiva, num_periodos_sustitutivos, periodo_desde_sustitutivo,
                        periodo_hasta_sustitutivo, puesto_trabajo_pesado, porcentaje_trabajo_pesado, cotizacion_trabajo_pesado, codigo_institucion_apvi,
                        numero_contrato_apvi, forma_pago_apvi, "", cotizacion_depositos_convenidos, codigo_institucion_apvc,
                        numero_contrato_apvc, forma_pago_apvc, cotizacion_trabajador_apvc, "", rut_afiliado_voluntario,
                        dv_afiliado_voluntario, "", "", nombres_afiliado_voluntario, codigo_movimiento_afiliado_voluntario,
                        fecha_desde_afiliado_voluntario, fecha_hasta_afiliado_voluntario, codigo_afp_afiliado_voluntario, monto_capitalizacion_voluntaria, monto_ahorro_voluntario,
                        numero_periodos_cotizacion, codigo_ex_caja_regimen, "", "", cotizacion_obligatoria_ips,
                        renta_imponible_desahucio, codigo_ex_caja_regimen_desahucio, tasa_cotizacion_desahucio_ex_cajas, cotizacion_desahucio, "",
                        cotizacion_acc_trabajo_isl, bonificacion_ley_15386, descuento_cargas_familiares_ips, bonos_gobierno, codigo_institucion_salud,
                        numero_fun, renta_imponible_isapre, moneda_plan_isapre, cotizacion_pactada, cotizacion_obligatoria,
                        cotizacion_salud_adicional, monto_ges, codigo_ccaf, "", creditos_personales_ccaf,
                        codigo_ex_caja_regimen_ips, descuentos_ccaf_leasing, "", cotizacion_ips_ex_caja, "",
                        "", "", tipo_jornada, "", cotizacion_rentabilidad_protegida,
                        "", "", "", "", "",
                        "", "", rut_pagadora_subsidio, dv_pagadora_subsidio, centro_costos
                    ]
                    csv_writer.writerow(additional_row)

        # Obtener el contenido CSV
        csv_content = output.getvalue()
        output.close()

        return request.make_response(
            csv_content,
            headers=[
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', f'attachment; filename="previred_{period_str}.csv"')
            ]
        )

