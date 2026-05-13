from odoo import api, fields, models

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    payslip_count = fields.Integer(
        string='Número de Liquidaciones',
        compute='_compute_payslip_count',
        help='Número de liquidaciones asociadas a este empleado'
    )

    can_view_payslips = fields.Boolean(
        string='Puede ver liquidaciones',
        compute='_compute_can_view_payslips',
        help='Determina si el usuario actual puede ver las liquidaciones de este empleado'
    )

    def _compute_payslip_count(self):
        """Calcula el número de liquidaciones del empleado"""
        for employee in self:
            employee.payslip_count = self.env['hr.payslip'].search_count([
                ('employee_id', '=', employee.id)
            ])

    def _compute_can_view_payslips(self):
        """Determina si el usuario actual puede ver las liquidaciones de este empleado"""
        for employee in self:
            # El usuario puede ver si es su propio empleado o si es manager de payroll
            is_own_employee = employee.user_id.id == self.env.uid
            is_payroll_manager = self.env.user.has_group('hr_payroll.group_hr_payroll_manager')
            employee.can_view_payslips = is_own_employee or is_payroll_manager
     
    def action_view_payslips(self):
        """Acción para ver las liquidaciones del empleado"""
        self.ensure_one()
        return {
            'name': 'Liquidaciones',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('hr_payroll.view_hr_payslip_tree').id, 'list'),
                (self.env.ref('hr_payroll.view_hr_payslip_form').id, 'form')
            ],
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
            },
        }