import logging
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrContractInherit(models.Model):
    _inherit = 'hr.contract'

    # Salary info
    colocation = fields.Monetary(
        string='Colación',
        help='Colocation amount for the employee.',
        tracking=True
    )
    
    movility = fields.Monetary(
        string='Movilización',
        help='Movility amount for the employee.',
        tracking=True
    )

    viatico_fijo = fields.Monetary(
        string='Viático',
        help='Viático para el empleado.',
        tracking=True
    )

    has_extra_hours = fields.Boolean(
        string='¿Tiene horas extra?',
        help='Indica si el empleado tiene horas extra.',
        tracking=True
    )
    
    extra_hours = fields.Integer(
        string="Horas Extras Pactadas", 
        help="Cantidad de horas extras pactadas para el mes. "
        "El cálculo se realiza como: " 
        "((Sueldo base mensual / 30 días / 8 horas) * 1.5) * horas pactadas. "
        "Corresponde al valor hora con recargo legal del 50%."
    )

    # Gratification info
    company_has_gratification = fields.Boolean(
        string="Empresa tiene gratificación",
        compute="_compute_company_gratification",
        store=False
    )

    has_gratification = fields.Boolean(
        string='¿Tiene gratificación?',
        help='Indica si el empleado tiene derecho a gratificación.',
        tracking=True,
        required=True
    )

    income_tax_type = fields.Selection([
        ('1', 'Impuesto de Segunda Categoría'),
        ('2', 'Impuesto Único Obrero Agrícola'),
        ('3', 'Impuesto Adicional')
    ], string='Tipo de Renta', 
       default='1',
       required=True,
       help='Tipo de impuesto a la renta aplicable al trabajador',
       tracking=True)

    # Cuenta analitica
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Centro de Costos',
        required=True,
    )

    # Tipo de jornada
    work_schedule_id = fields.Selection([
        ('101', 'Ordinaria-Art. 22'),
        ('201', 'Parcial-Art. 40 bis'),
        ('301', 'Extraordinaria-Art. 30'),
        ('401', 'Especial-Art 38 inciso 5'),
        ('402', 'Especial-Art. 23'),
        ('403', 'Especial-Art. 106'),
        ('404', 'Especial-Art. 152 Ter D'),
        ('405', 'Especial-Art. 152 Ter F'),
        ('406', 'Especial-Art. 25'),
        ('407', 'Especial-Art. 25 Bis'),
        ('408', 'Especial-Art. 149'),
        ('409', 'Especial-Art. 149 Inciso 2'),
        ('410', 'Especial-Art. 152 Bis'),
        ('411', 'Especial-Art. 145-C y 145-D'),
        ('412', 'Especial-Art. 22 Inciso Final'),
        ('413', 'Especial-Art. 137, letra B, inciso 2'),
        ('414', 'Especial-Art. 27'),
        ('415', 'Especial-Art. 26'),
        ('501', 'Bisemanal-Art. 39'),
        ('601', 'Jornada Excepcional-Art. 38 Inciso Final'),
        ('701', 'Exenta-Art. 22')
    ], string='Tipo de Jornada',default='101',required=True,
        help='Código de tipo de jornada según tabla N°6 del Libro de Remuneraciones',tracking=True
    )

    # Health info
    health_institution = fields.Selection(
        [   
            ('00 - 99', 'Sin Isapre'),
            ('01 - 3', 'Banmédica'),
            ('02 - 9', 'Consalud'),
            ('03 - 12', 'Vida Tres'),
            ('04 - 4', 'Colmena'),
            ('05 - 1', 'Cruz Blanca'),
            ('07 - 102', 'Fonasa'),
            ('10 - 43', 'Nueva Masvida'),
            ('11 - 5', 'Isapre de Codelco Ltda.'),
            ('12 - 40', 'Isapre Bco. Estado'),
            ('25 - 38', 'Isapre Cruz del Norte'),
        ],
        string="Institución de Salud",
        required=True,
        help="Seleccione la institución de salud del empleado.",
        tracking=True
    )

    # Campos FONASA
    fonasa_type = fields.Selection(
        [
            ('a', 'Tramo A'),
            ('b', 'Tramo B'), 
            ('c', 'Tramo C'), 
        ],
        string="Tramo Fonasa",
        help="Seleccione el tramo Fonasa correspondiente",
        tracking=True
    )

    # Campo ISAPRE
    isapre_calc_type = fields.Selection(
        [
            ('clp', 'Plan en CLP'),
            ('uf', 'Monto en UF')],
        string="Método de cálculo Isapre",
        tracking=True
    )
    isapre_plan_monto = fields.Monetary(string="Costo mensual (CLP)", default=0)
    isapre_uf_valor = fields.Float(string="Cantidad de UF", default=0)
  
    # Pensiones
    is_retired_elderly = fields.Boolean(
        string='Pensionado',
        default=False,
        required=True,
        help='Indica si el empleado está pensionado por vejez (Campo 1109 Libro de Remuneraciones)',
        tracking=True
    )

    pension_option = fields.Selection([
        ('afp', 'Administradora de Fondos de Pensiones'),
        ('inp', 'IPS – Instituto de Previsión Social (ex-INP, ex-Cajas)'),
        ('sip', 'Sin Institución Previsional'),
    ], string="Tipo de Pensión", help="Selecciona el tipo de pensión del empleado.", tracking=True, required=True, )

    afp_option = fields.Selection([
        ('00 - 100', 'No Cotiza AFP'),
        ('03 - 13', 'AFP Cuprum'),
        ('05 - 14', 'AFP Habitat'),
        ('08 - 6', 'AFP Provida'),
        ('29 - 11', 'AFP PlanVital'),
        ('33 - 31', 'AFP Capital'),
        ('34 - 103', 'AFP Modelo'),
        ('35 - 19', 'AFP Uno'),
    ], string="AFP", help="Selecciona la AFP a la que está afiliado el empleado.", tracking=True)

    # AFC info
    afc_enrolled = fields.Boolean(
        string="AFC Empleador",
        help="Marcar si el trabajador está afecto a la cotización del Seguro de Cesantía pagada por el empleador "
            "(2,4% para contratos indefinidos o 3% para contratos a plazo fijo u obra/faena).",
        default=True
    )

    afc_enrolled_trabajador = fields.Boolean(
        string="AFC Trabajador",
        help="Marcar si el trabajador está afecto a la cotización del Seguro de Cesantía pagada por el trabajador "
            "(0,6% para contratos indefinidos, hasta completar 11 años de cotizaciones).",
        default=True
    )

    # Carga familiar info
    has_family_loads = fields.Boolean(
        string="¿Tiene cargas familiares?",
        help="Marcar si el trabajador tiene personas a su cargo."
    )

    family_simple_loads_count = fields.Integer(
        string="Cargas simples",
        help="Número de cargas familiares simples asociadas.",
        default=0
    )
    family_maternal_loads_count = fields.Integer(
        string="Cargas maternas",
        help="Número de cargas familiares maternas asociadas.",
        default=0
    )
    family_invalid_loads_count = fields.Integer(
        string="Cargas inválidas",
        help="Número de cargas familiares inválidas asociadas.",
        default=0
    )

    family_loads_segment = fields.Selection([
        ('a', 'Tramo A'),
        ('b', 'Tramo B'),
        ('c', 'Tramo C'),
    ], string="Tramo", help="Tramo de asignación familiar según ingresos.")

    contract_type_id = fields.Many2one(
        'hr.contract.type',
        string="Tipo de Contrato",
        required=True,
        help="Seleccione el tipo de contrato del empleado."
    )

    # Campos APVI /  APVC
    has_apvi = fields.Boolean(
        string="¿Tiene APVI?",
        help="Indica si el empleado tiene APVI (Ahorro Previsional Voluntario Individual).",
    )

    has_apvc = fields.Boolean(
        string="¿Tiene APVC?",
        help="Indica si el empleado tiene APVC (Ahorro Previsional Voluntario Colectivo).",
    )

    institucion_apvi_apvc = fields.Selection([
        # No Cotiza / AFP
        ('000', 'No Cotiza A.P.V.'),
        ('003', 'Cuprum'),
        ('005', 'Habitat'), 
        ('008', 'Provida'),
        ('029', 'Planvital'),
        ('033', 'Capital'),
        ('034', 'Modelo'),
        ('035', 'Uno'),
        # Compañías de Seguros de Vida
        ('100', 'ABN AMRO (CHILE) SEGUROS DE VIDA S.A.'),
        ('101', 'AGF ALLIANZ CHILE COMPAÑIA DE SEGUROS VIDA S.A'),
        ('102', 'SANTANDER SEGUROS DE VIDA S.A.'),
        ('103', 'BCI SEGUROS VIDA S.A.'),
        ('104', 'BANCHILE SEGUROS DE VIDA S.A.'),
        ('105', 'BBVA SEGUROS DE VIDA S.A.'),
        ('106', 'BICE VIDA COMPAÑIA DE SEGUROS S.A.'),
        ('107', 'CHILENA CONSOLIDADA SEGUROS DE VIDA S.A.'),
        ('108', 'CIGNA COMPAÑIA DE SEGUROS DE VIDA S.A.'),
        ('109', 'CN LIFE, COMPAÑIA DE SEGUROS DE VIDA S.A.'),
        ('110', 'COMPAÑIA DE SEGUROS DE VIDA CARDIF S.A.'),
        ('111', 'CIA DE SEG. DE VIDA CONSORCIO NACIONAL DE SEG S.A.'),
        ('113', 'COMPAÑIA DE SEGUROS DE VIDA HUELEN S.A.'),
        ('115', 'COMPAÑIA DE SEGUROS DE VIDA VITALIS S.A.'),
        ('116', 'COMPAÑIA DE SEGUROS CONFUTURO S.A.'),
        ('118', 'SEGUROS DE VIDA SURA S.A.'),
        ('121', 'METLIFE CHILE SEGUROS DE VIDA S.A.'),
        ('123', 'MAPFRE COMPAÑIA DE SEGUROS DE VIDA DE CHILE S.A.'),
        ('125', 'MUTUAL DE SEGUROS DE CHILE'),
        ('126', 'MUTUALIDAD DE CARABINEROS'),
        ('127', 'MUTUALIDAD DEL EJERCITO Y AVIACION'),
        ('128', 'OHIO NATIONAL SEGUROS DE VIDA S.A.'),
        ('129', 'PRINCIPAL COMPAÑIA DE SEGUROS DE VIDA CHILE S.A.'),
        ('130', 'RENTA NACIONAL COMPAÑIA DE SEGUROS DE VIDA S.A.'),
        ('131', 'SEGUROS DE VIDA SECURITY PREVISION S.A.'),
        ('134', 'COMPAÑIA DE SEGUROS GENERALES PENTA-SECURITY S.A.'),
        ('135', 'PENTA VIDA COMPAÑIA DE SEGUROS DE VIDA S.A.'),
        ('136', 'ACE SEGUROS S.A.'),
        # Fondos Mutuos
        ('201', 'BANDESARROLLO ADM. GENERAL DE FONDOS S.A.'),
        ('204', 'BCI ASSET MANAGEMENT ADMINISTRADORA GENERAL DE FONDOS S.A.'),
        ('205', 'BICE INVERSIONES AGF S.A.'),
        ('208', 'BTG PACTUAL CHILE S.A. ADMINISTRADORA GENERAL DE FONDOS'),
        ('214', 'PRINCIPAL ADMINISTRADORA GENERAL DE FONDOS S.A.'),
        ('215', 'SANTANDER ASSET MANAGEMENT S.A. ADM. GENERAL DE FONDOS'),
        ('217', 'SCOTIA SUDAMERICANO ADMINISTRADORA DE FONDOS MUTUOS S.A.'),
        ('218', 'ADMINISTRADORA GENERAL DE FONDOS SECURITY S.A.'),
        ('225', 'ITAU ADMINISTRADORA GENERAL DE FONDOS S.A.'),
        ('229', 'BANCO ESTADO S.A. ADMINISTRADORA GENERAL DE FONDOS'),
        ('237', 'FINTUAL ADMINISTRADORA GENERAL DE FONDOS S.A'),
        ('238', 'FOCUS AGF S.A.'),
        ('600', 'ZURICH CHILE ASSET MANAGEMENT ADMINISTRADORA GENERAL DE FONDOS S.A'),
        ('601', 'LARRAIN VIAL ADMINISTRADORA GENERAL DE FONDOS S.A.'),
        # Corredores de Bolsa
        ('213', 'LARRAIN VIAL S.A. CORREDORA DE BOLSA'),
        ('222', 'BANCHILE CORREDORES DE BOLSA S.A.'),
        ('227', 'CORREDORES DE BOLSA SURA S.A.'),
        ('228', 'BTG PACTUAL CHILE S.A. CORREDORES DE BOLSA'),
        ('231', 'SCOTIA SUD AMERICANO CORREDORES DE BOLSA S.A.'),
        ('232', 'BICE INVERSIONES CORREDORES DE BOLSA S.A.'),
        ('235', 'MBI CORREDORES DE BOLSA S.A.'),
        ('236', 'CONSORCIO CORREDORES DE BOLSA S.A.'),
        # Bancos
        ('321', 'Banco Santander Santiago'),
    ], string="Institución APVI/APVC", help="Seleccione la institución autorizada para el Ahorro Previsional Voluntario.")

    pay_format_apvi_apc = fields.Selection(
        selection=[
            ('1', 'Directa'),
            ('2', 'Indirecta'),
        ],
        string="Formato de Pago APVI/APVC",
        help="1 Directa: Se envía la información directamente a la Institución encargada de "
             "administrar los fondos. "
             "2 Indirecta: Se envía la información a la AFP del trabajador, la cual actúa como "
             "intermediaria para luego traspasar los fondos a otra Institución encargada de "
             "administrar estos fondos.",
    )

    cotizacion_apvi = fields.Monetary(
        string="Cotización APVI",
        help="Monto de la cotización para el Ahorro Previsional Voluntario Individual (APVI).",
    )

    cotizacion_apvc_trabajador = fields.Monetary(
        string="Cotización APVC Trabajador",
        help="Monto de la cotización para el Ahorro Previsional Voluntario Colectivo (APVC) - Trabajador.",
    )

    cotizacion_apvc_empleador = fields.Monetary(
        string="Cotización APVC Empleador",
        help="Monto de la cotización para el Ahorro Previsional Voluntario Colectivo (APVC) - Empleador.",
    )

    # Cuenta 2 AFP (ahorro voluntario en AFP del trabajador)
    has_cuenta2 = fields.Boolean(
        string="¿Tiene Cuenta 2 AFP?",
        help="Indica si el trabajador realiza aportes voluntarios a su Cuenta 2 en la AFP.",
    )
    cotizacion_cuenta2 = fields.Monetary(
        string="Cotización Cuenta 2 AFP",
        help="Monto mensual del aporte voluntario del trabajador a su Cuenta 2 AFP.",
    )

    # Subsidios
    has_empleo_joven = fields.Boolean(
        string="¿Tiene Subsidio Empleo Joven?",
        help="Indica si el empleado tiene acceso al subsidio de empleo joven."
    )

    # Asignacion de vacaciones al crear un empleado
    @api.model
    def create(self, vals):
        contract = super().create(vals)
        contract._generate_vacation_allocation()
        return contract
    
    # Asignacion de vacaciones al editar el date_start
    def write(self, vals):
        result = super().write(vals)
        if 'date_start' in vals:
            self._generate_vacation_allocation()
        return result
    
    # Funciona para generar la asignacion de vacaciones al crear o actualizar un contrato
    def _generate_vacation_allocation(self):
        for contract in self:
            try:
                with self.env.cr.savepoint():
                    start_date = contract.date_start
                    if not start_date:
                        logging.warning(f"Contrato {contract.id} no tiene fecha de inicio")
                        continue

                    if not contract.employee_id:
                        logging.warning(f"Contrato {contract.id} no tiene empleado asociado")
                        continue
                
                    # Calcular días trabajados
                    today = date.today()
                    months = (today.year - start_date.year) * 12 + (today.month - start_date.month)
                    
                    days = round((months / 12) * 15, 2)
                    
                    logging.info(f"Contrato {contract.id}: {months} meses, {days} días de vacaciones")
                    
                    if days <= 0:
                        logging.warning(f"Contrato {contract.id}: días calculados <= 0")
                        continue

                    # Buscar asignación existente
                    holiday_status = self.env.ref('l10n_cl_simpledigital_payroll.hr_leave_type_vacaciones_legales', raise_if_not_found=False)
                    if not holiday_status:
                        logging.error("No se encontró el tipo de vacaciones legales")
                        continue
                        
                    existing_allocation = self.env['hr.leave.allocation'].search([
                        ('employee_id', '=', contract.employee_id.id),
                        ('holiday_status_id', '=', holiday_status.id),
                        ('date_from', '<=', today),
                        ('state', 'in', ['draft', 'confirm', 'validate'])
                    ], limit=1)

                    if existing_allocation:
                        # Actualizar asignación existente
                        existing_allocation.write({
                            'number_of_days': days,
                            'date_from': start_date,  # Usar fecha de inicio del contrato
                            'name': f'Vacaciones {contract.employee_id.name}'
                        })
                        logging.info(f"Actualizada asignación existente para {contract.employee_id.name}: {days} días desde {start_date}")
                    else:
                        # Crear nueva asignación
                        allocation = self.env['hr.leave.allocation'].create({
                            'name': f'Vacaciones {contract.employee_id.name}',
                            'employee_id': contract.employee_id.id,
                            'holiday_status_id': holiday_status.id,
                            'number_of_days': days,
                            'date_from': start_date,  # Usar fecha de inicio del contrato
                        })
                        allocation.action_approve()
                        logging.info(f"Creada nueva asignación para {contract.employee_id.name}: {days} días desde {start_date}")
                    
            except Exception as e:
                logging.error(f"Error procesando contrato {contract.id}: {str(e)}")

    # Actualiza solo los días acumulados sin modificar la fecha de validez
    def _increment_vacation_allocation(self, days_increment=1.25):
        for contract in self:
            try:
                with self.env.cr.savepoint():
                    if not contract.employee_id:
                        logging.warning(f"Contrato {contract.id} no tiene empleado asociado")
                        continue

                    holiday_status = self.env.ref(
                        'l10n_cl_simpledigital_payroll.hr_leave_type_vacaciones_legales',
                        raise_if_not_found=False,
                    )
                    if not holiday_status:
                        logging.error("No se encontró el tipo de vacaciones legales")
                        continue

                    allocation = self.env['hr.leave.allocation'].search([
                        ('employee_id', '=', contract.employee_id.id),
                        ('holiday_status_id', '=', holiday_status.id),
                        ('state', 'in', ['draft', 'confirm', 'validate'])
                    ], order='date_from desc,id desc', limit=1)

                    if allocation:
                        new_days = round(allocation.number_of_days + days_increment, 2)
                        allocation.write({
                            'number_of_days': new_days,
                            'name': f'Vacaciones {contract.employee_id.name}',
                        })
                        logging.info(
                            f"Incrementada asignación para {contract.employee_id.name}: "
                            f"+{days_increment} días (total {new_days})"
                        )
                    else:
                        start_date = contract.date_start or date.today()
                        allocation = self.env['hr.leave.allocation'].create({
                            'name': f'Vacaciones {contract.employee_id.name}',
                            'employee_id': contract.employee_id.id,
                            'holiday_status_id': holiday_status.id,
                            'number_of_days': days_increment,
                            'date_from': start_date,
                        })
                        allocation.action_approve()
                        logging.info(
                            f"Creada asignación inicial para {contract.employee_id.name}: "
                            f"{days_increment} días desde {start_date}"
                        )
            except Exception as e:
                logging.error(f"Error procesando contrato {contract.id}: {str(e)}")
    
    # Método para el cron - incrementa vacaciones mensualmente
    @api.model
    def _cron_update_vacation_allocations(self):
        """Método ejecutado por cron para incrementar asignaciones de vacaciones mensualmente"""
        try:
            active_contracts = self.search([('state', '=', 'open')])
            logging.info(f"Iniciando actualización de vacaciones para {len(active_contracts)} contratos activos")
            
            for contract in active_contracts:
                logging.info(f"Procesando contrato {contract.id} - {contract.employee_id.name}")
                contract._increment_vacation_allocation()
                
            logging.info(f"Vacaciones actualizadas para {len(active_contracts)} contratos activos")
            
        except Exception as e:
            logging.error(f"Error en cron de vacaciones: {str(e)}")
            raise
    
    # Excepcion para en caso de que se seleccionen APVI y APVC al mismo tiempo
    @api.constrains('has_apvi', 'has_apvc')
    def _check_apvi_apvc_exclusive(self):
        """Validar que no se puedan seleccionar APVI y APVC al mismo tiempo"""
        for record in self:
            if record.has_apvi and record.has_apvc:
                raise ValidationError(
                    "No se puede tener APVI y APVC al mismo tiempo. "
                    "Debe seleccionar solo uno de los dos tipos de ahorro previsional voluntario."
                )
    @api.depends('company_id.gratification_enabled')
    def _compute_company_gratification(self):
        for record in self:
            record.company_has_gratification = record.company_id.gratification_enabled
            
