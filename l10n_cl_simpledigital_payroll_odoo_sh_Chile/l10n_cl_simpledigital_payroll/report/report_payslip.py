from odoo import api, models


class PayslipReport(models.AbstractModel):
    _inherit = 'report.hr_payroll.report_payslipdetails'

    @api.model
    def _get_report_values(self, docids, data=None):
        payslips = super(PayslipReport, self)._get_report_values(docids, data)
        # Descomenta si quieres incluir más funciones personalizadas:
        # payslips.update({
        #     'get_leave': self.get_leave,
        #     'convert': self.convert,
        #     'get_payslip_lines': self.get_payslip_lines,
        # })
        return payslips

    def convert(self, amount, cur):
        return cur.amount_to_text(amount)

    def get_payslip_lines(self, payslip_lines):
        return payslip_lines.filtered(lambda l: l.appears_on_payslip)

    def get_leave(self, payslip_lines):
        return payslip_lines.filtered(lambda l: l.type == 'leaves')
