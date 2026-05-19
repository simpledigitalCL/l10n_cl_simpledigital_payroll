def post_init_hook(env):
    """Corrige nombre, categoría y configuración de las reglas BASIC y NET."""
    structure = env['hr.payroll.structure'].search([('name', '=', 'Nómina Chile')], limit=1)
    if not structure:
        return

    category_imp = env['hr.salary.rule.category'].search([('code', '=', 'IMP')], limit=1)

    basic_rule = env['hr.salary.rule'].search([
        ('code', '=', 'BASIC'),
        ('struct_id', '=', structure.id),
    ], limit=1)
    if basic_rule and category_imp:
        basic_rule.write({
            'name': 'Sueldo Base',
            'category_id': category_imp.id,
            'appears_on_employee_cost_dashboard': True,
            'appears_on_payroll_report': True,
        })

    net_rule = env['hr.salary.rule'].search([
        ('code', '=', 'NET'),
        ('struct_id', '=', structure.id),
    ], limit=1)
    if net_rule:
        net_rule.write({
            'name': 'Sueldo Líquido',
            'appears_on_payroll_report': True,
            'amount_python_compute': "result = categories['GROSS'] + categories['habIMP'] - categories['TOTAL_DESC']",
        })
