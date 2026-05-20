from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class HrEmployeeMovement(models.Model):
    _name = 'hr.employee.movement'
    _description = 'Movimientos de Empleado'
    _order = 'date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Referencia', required=True, default='Nuevo')
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company
    )
    movement_type_id = fields.Many2one(
        'hr.employee.movement.type',
        string='Tipo de Movimiento',
        required=True,
        domain="[('active', '=', True)]"
    )
    date = fields.Date(string='Fecha', required=True, default=fields.Date.today)
    movement_line_ids = fields.One2many(
        'hr.employee.movement.line', 'movement_id',
        string='Líneas de Movimiento'
    )
    total_amount = fields.Monetary(
        string='Total', 
        compute='_compute_total_amount', 
        store=True,
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )
    earn_type = fields.Selection(
        related='movement_type_id.earn_type',
        string='Tipo de Ingreso',
        readonly=True,
        store=True
    )

    def _auto_init(self):
        super()._auto_init()
        self._cr.execute("""
            UPDATE hr_employee_movement
            SET company_id = 1
            WHERE company_id IS NULL
        """)

    @api.depends('movement_line_ids.amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.movement_line_ids.mapped('amount'))

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nuevo') == 'Nuevo':
            movement_type = self.env['hr.employee.movement.type'].browse(vals.get('movement_type_id'))
            vals['name'] = f"Asignación {movement_type.name}" if movement_type else 'Asignación'
        return super().create(vals)

    @api.onchange('movement_type_id')
    def _onchange_movement_type_id(self):
        if self.movement_type_id:
            self.name = f"Asignación {self.movement_type_id.name}"


class HrEmployeeMovementLine(models.Model):
    _name = 'hr.employee.movement.line'
    _description = 'Línea de Movimiento de Empleado'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Secuencia', default=10)
    movement_id = fields.Many2one(
        'hr.employee.movement', 
        string='Movimiento', 
        required=True, 
        ondelete='cascade'
    )
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True,)
    movement_type_id = fields.Many2one(
        related='movement_id.movement_type_id', 
        string='Tipo de Movimiento', store=True, readonly=True
    )
    name = fields.Char(string='Descripción', required=True)

    amount = fields.Monetary(
        string='Monto', 
        required=True, 
        store = True,
        compute='_compute_amount',
        inverse='_inverse_amount',
        help='Monto asociado al movimiento. En caso de ser horas, se calculará el automaticamente con el calculo del sueldo * 0,0079545',
    )
    hours = fields.Float(
        string='Horas', 
        default=0.0, 
        help='Cantidad de horas asociadas al movimiento horas extras no pactadas'
    )
    is_amount_readonly = fields.Boolean(
        string='Amount Readonly', 
        compute='_compute_amount_readonly',
        help='Determina si el campo amount debe ser readonly'
    )

    account_move_id = fields.Many2one(
        'account.move',
        string='Asiento Contable',
        help='Asiento contable asociado filtrado por journal de Salarios'
    )
    hr_event_type_id = fields.Many2one(
        'hr.employee.hr.event.type',
        string='Tipo de Evento RRHH',
        help='Tipo de evento de recursos humanos asociado a este movimiento'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            movement = self.env['hr.employee.movement'].browse(vals.get('movement_id'))
            vals['name'] = movement.movement_type_id.name or 'Movimiento'
        return super().create(vals)

    @api.onchange('movement_type_id')
    def _onchange_movement_type_id(self):
        if self.movement_type_id:
            self.name = self.movement_type_id.name

    # Funcion para calcular el monto basado en las horas
    @api.depends('hours', 'employee_id.contract_id.wage', 'employee_id.contract_id.hourly_wage', 'movement_type_id')
    def _compute_amount(self):
        for rec in self:
            if rec.movement_type_id and rec.hours and rec.hours > 0:
                contract = rec.employee_id.contract_id
                if contract and getattr(contract, 'hourly_wage', 0) and contract.hourly_wage > 0:
                    rec.amount = contract.hourly_wage * 1.5 * rec.hours
                elif contract and getattr(contract, 'wage', 0) and contract.wage > 0:
                    rec.amount = (contract.wage * 0.0079545) * rec.hours
                else:
                    rec.amount = 0.0
            else:
                # Si no hay horas, mantenemos el valor actual (permitir edición manual)
                rec.amount = rec.amount or 0.0
    
    def _inverse_amount(self):
        for rec in self:
            # Si hay horas, forzamos el cálculo y evitamos que el usuario sobrescriba manualmente
            if rec.movement_type_id and rec.hours and rec.hours > 0:
                contract = rec.employee_id.contract_id
                if contract and getattr(contract, 'hourly_wage', 0) and contract.hourly_wage > 0:
                    rec.amount = contract.hourly_wage * 1.5 * rec.hours
                elif contract and getattr(contract, 'wage', 0) and contract.wage > 0:
                    rec.amount = (contract.wage * 0.0079545) * rec.hours
                else:
                    rec.amount = 0.0

    @api.depends('hours')
    def _compute_amount_readonly(self):
        """Determina si el campo amount debe ser readonly basado en hours"""
        for record in self:
            record.is_amount_readonly = record.hours > 0



class HrEmployeeMovementType(models.Model):
    _name = 'hr.employee.movement.type'
    _description = 'Tipo de Movimiento de Empleado'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nombre del Tipo', required=True, help="Nombre del Movimiento (Ej: Comisión de Venta)")
    active = fields.Boolean(string='Activo', default=True, )
    earn_type = fields.Selection([
        ('imponible', 'Imponible'),
        ('no_imponible', 'No Imponible'),
        ('others', 'Otros descuentos')
    ], string='Tipo de Ingreso', required=True, 
    help="Determinar si el tipo es imponible o no. En caso de ser imponible se suma a la cantidad de la nomina", tracking=True
    )

    # Booleans
    bono_ok = fields.Boolean(
        string = "Movimiento Bono",
        help="Opción para marcar el tipo de movimiento como bono. Esto permite que en LRE tome este movimiento",
        tracking=True
    )

    comision_ok = fields.Boolean(
        string = "Movimiento Comisión",
        help="Opción para marcar el tipo de movimiento como comisión. Esto permite que en LRE tome este movimiento",
        tracking=True
    )

    aguinaldo_ok = fields.Boolean(
        string = "Movimiento Aguinlado",
        help="Opción para marcar el tipo de movimiento como aguinaldo. Esto permite que en LRE tome este movimiento",
        tracking=True
    )

    movilizacion_ok = fields.Boolean(
        string = "Movimiento Movilización",
        help="Opción para marcar el tipo de movimiento como movilización. Esto permite que en LRE tome este movimiento",
        tracking=True
    )

    otros_descuentos_ok = fields.Boolean(
        string = "Otros Descuentos",
        help="Opción para marcar el tipo de movimiento como Otros Descuentos. Esto permite que en LRE tome este movimiento en los descuentos totales",
        tracking=True
    )
    
    asiento_contable_debito = fields.Many2one(
        'account.account',
        string='Cuenta de Débito',
        help='Cuenta contable de débito asociada al tipo de movimiento',
        tracking=True
    )
    asiento_contable_credito = fields.Many2one(
        'account.account',
        string='Cuenta de Crédito',
        help='Cuenta contable de crédito asociada al tipo de movimiento',
        tracking=True
    )
    sequence = fields.Selection(
        [(str(i), str(i)) for i in range(10, 200, 10)],
        string='Secuencia',
        default='10',
        help='Secuencia para el orden en las reglas salariales',
        tracking=True,
        required=True
    )


    hr_event_line_ids = fields.One2many(
        'hr.employee.hr.event.type',
        'movement_id',
        string='Eventos RRHH'
    )

    salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        string='Regla Salarial Generada',
    )
    contract_id = fields.Many2one('hr.contract', string="Contrato")

    def _auto_init(self):
        super()._auto_init()
        rules = self.env['hr.salary.rule'].search([
            ('code', 'like', 'MOV_%'),
            ('condition_python', 'not like', 'company_id'),
        ])
        for rule in rules:
            try:
                mid = int(rule.code.split('_')[1])
            except (IndexError, ValueError):
                continue
            rule.write({
                'condition_python': f"""
employee = contract.employee_id
from_date = payslip.date_from
to_date = payslip.date_to

lines = payslip.env['hr.employee.movement.line'].search([
    ('employee_id', '=', employee.id),
    ('movement_type_id', '=', {mid}),
    ('movement_id.date', '>=', from_date),
    ('movement_id.date', '<=', to_date),
    ('movement_id.company_id', '=', payslip.company_id.id),
])

result = bool(lines)
""",
                'amount_python_compute': f"""
result = 0.0
employee = contract.employee_id
from_date = payslip.date_from
to_date = payslip.date_to

lines = payslip.env['hr.employee.movement.line'].search([
    ('employee_id', '=', employee.id),
    ('movement_type_id', '=', {mid}),
    ('movement_id.date', '>=', from_date),
    ('movement_id.date', '<=', to_date),
    ('movement_id.company_id', '=', payslip.company_id.id),
])

if lines:
    result = sum(lines.mapped('amount'))
""",
            })

    @api.model
    def create(self, vals):
        movement_type = super().create(vals)

        struct = self.env['hr.payroll.structure'].search([('name', '=', 'Nómina Chile')], limit=1)
        if not struct:
            raise ValueError("No se encontró la estructura 'Nómina Chile'")

        # Mapeo de earn_type a código de categoría
        code_map = {
            'imponible': 'IMP',
            'no_imponible': 'NOP_IMP',
            'others': 'others'
        }
        
        # Obtener la categoría correcta por código
        category_code = code_map.get(movement_type.earn_type, 'NOP_IMP')
        category = self.env['hr.salary.rule.category'].search([
            ('code', '=', category_code)
        ], limit=1)
        
        if not category:
            # Fallback: buscar categoría "No Imponible" por defecto
            category = self.env['hr.salary.rule.category'].search([
                ('code', '=', 'NOP_IMP')
            ], limit=1)
            if not category:
                raise ValueError(f"No se encontró ninguna categoría de regla salarial con código {category_code}")

        # Crear la regla salarial a partir del movimiento
        salary_rule = self.env['hr.salary.rule'].create({
            'name': f"{movement_type.name}",
            'code': f"MOV_{movement_type.id}",
            'category_id': category.id,
            'struct_id': struct.id,
            'sequence': int(movement_type.sequence) if movement_type.sequence else 10,
            'condition_select': 'python',
            'condition_python': f"""
employee = contract.employee_id
from_date = payslip.date_from
to_date = payslip.date_to

lines = payslip.env['hr.employee.movement.line'].search([
    ('employee_id', '=', employee.id),
    ('movement_type_id', '=', {movement_type.id}),
    ('movement_id.date', '>=', from_date),
    ('movement_id.date', '<=', to_date),
    ('movement_id.company_id', '=', payslip.company_id.id),
])

result = bool(lines)
""",
            'amount_select': 'code',
            'amount_python_compute': f"""
result = 0.0
employee = contract.employee_id
from_date = payslip.date_from
to_date = payslip.date_to

lines = payslip.env['hr.employee.movement.line'].search([
    ('employee_id', '=', employee.id),
    ('movement_type_id', '=', {movement_type.id}),
    ('movement_id.date', '>=', from_date),
    ('movement_id.date', '<=', to_date),
    ('movement_id.company_id', '=', payslip.company_id.id),
])

if lines:
    result = sum(lines.mapped('amount'))
""",
            'appears_on_payslip': True,
            'active': True,
            'account_debit': movement_type.asiento_contable_debito.id if movement_type.asiento_contable_debito else False,
            'account_credit': movement_type.asiento_contable_credito.id if movement_type.asiento_contable_credito else False,
        })

        movement_type.salary_rule_id = salary_rule.id
        return movement_type

    def write(self, vals):
        res = super().write(vals)
    
        # Verificar si se cambió algún campo que afecte la regla salarial
        if any(field in vals for field in ['name', 'earn_type', 'code', 'asiento_contable_debito', 'asiento_contable_credito']):
            
            for record in self:
                # Si no tiene regla salarial, intentar encontrarla o crearla
                if not record.salary_rule_id:
                    # Buscar si existe una regla con el código del movimiento
                    existing_rule = self.env['hr.salary.rule'].search([
                        ('code', '=', f'MOV_{record.id}')
                    ], limit=1)
                    
                    if existing_rule:
                        # Asignar la regla encontrada
                        record.salary_rule_id = existing_rule.id
                        # _logger.info(f"Regla salarial encontrada y asignada a movimiento {record.name}: {existing_rule.name}")
                    else:
                        # Crear nueva regla salarial
                        # _logger.info(f"Creando nueva regla salarial para movimiento {record.name}")
                        record._create_salary_rule()
                
                if record.salary_rule_id:
                    # Valores a actualizar en la regla salarial
                    rule_vals = {}
                    
                    # Actualizar nombre si cambió
                    if 'name' in vals:
                        rule_vals['name'] = record.name
                    
                    # Actualizar categoría si cambió earn_type
                    if 'earn_type' in vals:
                        # Mapeo de earn_type a código de categoría
                        code_map = {
                            'imponible': 'IMP',
                            'no_imponible': 'NOP_IMP', 
                            'others': 'others'
                        }
                        
                        if record.earn_type in code_map:
                            category_code = code_map[record.earn_type]
                            # Buscar categoría por código
                            category = self.env['hr.salary.rule.category'].search([
                                ('code', '=', category_code)
                            ], limit=1)
                            
                            if category:
                                rule_vals['category_id'] = category.id
                                # _logger.info(f"Actualizando category_id de regla {record.salary_rule_id.name} a categoría {category.name} (código: {category_code})")
                            else:
                                # _logger.error(f"No se encontró categoría con código {category_code}")
                                pass
                        else:
                            # _logger.warning(f"earn_type '{record.earn_type}' no está mapeado")
                            pass
                    
                    # Actualizar cuentas contables si cambiaron
                    if 'asiento_contable_debito' in vals:
                        rule_vals['account_debit'] = vals['asiento_contable_debito'] or False
                    if 'asiento_contable_credito' in vals:
                        rule_vals['account_credit'] = vals['asiento_contable_credito'] or False
                    
                    # Aplicar los cambios si hay algo que actualizar
                    if rule_vals:
                        # _logger.info(f"Actualizando regla salarial {record.salary_rule_id.name} con valores: {rule_vals}")
                        record.salary_rule_id.write(rule_vals)
                        # _logger.info(f"Regla salarial actualizada exitosamente")
                else:
                    # _logger.error(f"No se pudo crear o encontrar regla salarial para movimiento {record.name}")
                    pass
    
        return res
    
    def _create_salary_rule(self):
        """Método auxiliar para crear una regla salarial"""
        struct = self.env['hr.payroll.structure'].search([('name', '=', 'Nómina Chile')], limit=1)
        if not struct:
            # _logger.error("No se encontró la estructura 'Nómina Chile'")
            return False

        # Mapeo de earn_type a código de categoría
        code_map = {
            'imponible': 'IMP',
            'no_imponible': 'NOP_IMP',
            'others': 'others'
        }
        
        # Obtener la categoría correcta por código
        category_code = code_map.get(self.earn_type, 'NOP_IMP')
        category = self.env['hr.salary.rule.category'].search([
            ('code', '=', category_code)
        ], limit=1)
        
        if not category:
            # Fallback: buscar categoría "No Imponible" por defecto
            category = self.env['hr.salary.rule.category'].search([
                ('code', '=', 'NOP_IMP')
            ], limit=1)
            if not category:
                # _logger.error(f"No se encontró ninguna categoría de regla salarial con código {category_code}")
                return False

        # Crear la regla salarial
        salary_rule = self.env['hr.salary.rule'].create({
            'name': f"{self.name}",
            'code': f"MOV_{self.id}",
            'category_id': category.id,
            'struct_id': struct.id,
            'sequence': int(self.sequence) if self.sequence else 10,
            'condition_select': 'python',
            'condition_python': f"""
employee = contract.employee_id
from_date = payslip.date_from
to_date = payslip.date_to

lines = payslip.env['hr.employee.movement.line'].search([
    ('employee_id', '=', employee.id),
    ('movement_type_id', '=', {self.id}),
    ('movement_id.date', '>=', from_date),
    ('movement_id.date', '<=', to_date),
    ('movement_id.company_id', '=', payslip.company_id.id),
])

result = bool(lines)
""",
            'amount_select': 'code',
            'amount_python_compute': f"""
result = 0.0
employee = contract.employee_id
from_date = payslip.date_from
to_date = payslip.date_to

lines = payslip.env['hr.employee.movement.line'].search([
    ('employee_id', '=', employee.id),
    ('movement_type_id', '=', {self.id}),
    ('movement_id.date', '>=', from_date),
    ('movement_id.date', '<=', to_date),
    ('movement_id.company_id', '=', payslip.company_id.id),
])

if lines:
    result = sum(lines.mapped('amount'))
""",
            'appears_on_payslip': True,
            'active': True,
            'account_debit': self.asiento_contable_debito.id if self.asiento_contable_debito else False,
            'account_credit': self.asiento_contable_credito.id if self.asiento_contable_credito else False,
        })

        self.salary_rule_id = salary_rule.id
        # _logger.info(f"Regla salarial creada exitosamente: {salary_rule.name}")
        return True
    
    def reconnect_salary_rules(self):
        """Método para reconectar reglas salariales existentes que puedan estar desvinculadas"""
        for record in self:
            if not record.salary_rule_id:
                # Buscar regla por código
                existing_rule = self.env['hr.salary.rule'].search([
                    ('code', '=', f'MOV_{record.id}')
                ], limit=1)
                
                if existing_rule:
                    record.salary_rule_id = existing_rule.id
                    # _logger.info(f"Regla salarial reconectada: {record.name} -> {existing_rule.name}")
                else:
                    # Buscar regla por nombre similar
                    existing_rule = self.env['hr.salary.rule'].search([
                        ('name', 'ilike', record.name)
                    ], limit=1)
                    
                    if existing_rule:
                        record.salary_rule_id = existing_rule.id
                        # _logger.info(f"Regla salarial reconectada por nombre: {record.name} -> {existing_rule.name}")
                    else:
                        # _logger.warning(f"No se encontró regla salarial para reconectar con {record.name}")
                        pass
        
        return True

class HrEmployeeHrEventType(models.Model):
    _name = 'hr.employee.hr.event.type'
    _description = 'Tipo de Evento de RRHH'

    name = fields.Char(string='Nombre del Evento', required=True)
    code = fields.Char(string='Código', required=False)
    movement_id = fields.Many2one(
        'hr.employee.movement.type',
        string='Tipo de Movimiento',
        required=False,
        ondelete='cascade'
    )
