from odoo import models


class PayslipReport(models.AbstractModel):
    _name = 'report.hr_payroll.report_payslipdetails'
    _description = 'Reporte personalizado de detalles de liquidación de sueldo'

    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.payslip'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.payslip',
            'docs': docs,
            'get_leave': self.get_leave,
            'convert': self.convert,
            'get_payslip_lines': self.get_payslip_lines,
        }

    def convert(self, amount, currency):
        return currency.amount_to_text(amount)

    def get_payslip_lines(self, payslip_lines):
        return payslip_lines.filtered(lambda l: l.appears_on_payslip)

    def get_leave(self, payslip_lines):
        return payslip_lines.filtered(lambda l: l.type == 'leaves')
