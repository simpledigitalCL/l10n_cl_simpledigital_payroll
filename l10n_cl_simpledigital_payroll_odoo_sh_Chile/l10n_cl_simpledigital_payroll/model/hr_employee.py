import re
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Campos de nombres
    firstname = fields.Char(string="Nombre")
    middle_name = fields.Char(string="Segundo Nombre", help='Segundo nombre del empleado')
    last_name = fields.Char(string="Apellido Paterno")
    mothers_name = fields.Char(string="Apellido Materno", help='Apellido materno del empleado')
    formated_vat = fields.Char(string='RUT Formateado', store=True, help='Muestra el RUT con puntos y guión')

    # Identificación previsional
    afp_id = fields.Many2one('hr.afp', string='AFP')
    isapre_id = fields.Many2one('hr.isapre', string='Isapre')
    apv_id = fields.Many2one('hr.apv', string='APV')
    ccaf_id = fields.Many2one('hr.ccaf', string='CCAF')
    mutual_id = fields.Many2one('hr.mutual', string='Mutualidad')
    seguro_complementario_id = fields.Many2one('hr.seguro.complementario', string='Seguro Complementario')
    tipo_empleado_id = fields.Many2one('hr.type.employee', string='Tipo de Empleado')

    # Nombre completo dinámico
    @api.model
    def _get_computed_name(self, last_name, firstname, last_name2=None, middle_name=None):
        names = []
        if firstname:
            names.append(firstname)
        if middle_name:
            names.append(middle_name)
        if last_name:
            names.append(last_name)
        if last_name2:
            names.append(last_name2)
        return " ".join(names)

    @api.onchange('firstname', 'mothers_name', 'middle_name', 'last_name')
    def get_name(self):
        if self.firstname and self.last_name:
            self.name = self._get_computed_name(
                last_name=self.last_name,
                firstname=self.firstname,
                last_name2=self.mothers_name,
                middle_name=self.middle_name,
            )

    # Formato de RUT
    @api.onchange('identification_id')
    def onchange_document(self):
        if self.identification_id:
            raw = re.sub('[^0-9Kk]', '', self.identification_id).zfill(9).upper()
            self.identification_id = '%s.%s.%s-%s' % (
                raw[0:2], raw[2:5], raw[5:8], raw[-1])

    # Validación de RUT
    def check_identification_id_cl(self, identification_id):
        if not identification_id:
            return True
        if len(identification_id) > 9:
            identification_id = identification_id.replace('-', '', 1).replace('.', '', 2)
        if len(identification_id) != 9:
            raise UserError(_('El RUT no tiene el formato correcto'))
        body, vdig = identification_id[:-1], identification_id[-1].upper()
        try:
            factors = [2, 3, 4, 5, 6, 7] * 2
            s = sum([int(d) * f for d, f in zip(body[::-1], factors)])
            res = 11 - (s % 11)
            dv = '0' if res == 11 else 'K' if res == 10 else str(res)
            if dv != vdig:
                raise UserError(_('El RUT no es válido'))
        except Exception:
            raise UserError(_('El RUT no es válido'))

    # Restricción de unicidad del RUT
    @api.constrains('identification_id')
    def _rut_unique(self):
        for record in self:
            if not record.identification_id:
                continue
            existing = self.env['hr.employee'].search([
                ('identification_id', '=', record.identification_id),
                ('id', '!=', record.id),
            ])
            if record.identification_id != "55.555.555-5" and existing:
                raise UserError(_('El RUT debe ser único'))
