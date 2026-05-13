from odoo import models, fields, api

class ResCountryCommune(models.Model):
    _name = 'res.country.commune'
    _description = 'Country Commune'
    _order = 'codigo'
    _rec_name = 'name'

    name = fields.Char(
        string='Commune Name',
        required=True,
        translate=True,
        help="Name of the commune"
    )
    
    codigo = fields.Char(
        string='Code',
        required=True,
        size=6,
        help="Official code of the commune (e.g., 2102, 4305)"
    )
    
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        required=True,
        help="Country to which this commune belongs"
    )
    
    state_id = fields.Many2one(
        'res.country.state',
        string='Region',
        required=True,
        domain="[('country_id', '=', country_id)]",
        help="Region to which this commune belongs"
    )

    _sql_constraints = [
        ('codigo_unique', 'unique(codigo)', 'The commune code must be unique!'),
        ('name_country_unique', 'unique(name, country_id)', 'The commune name must be unique per country!'),
    ]

    @api.onchange('country_id')
    def _onchange_country_id(self):
        """Clear the region when country changes"""
        if self.country_id and self.state_id:
            if self.state_id.country_id != self.country_id:
                self.state_id = False

    def name_get(self):
        """Override name_get to display code and name"""
        result = []
        for commune in self:
            name = f"[{commune.codigo}] {commune.name}"
            result.append((commune.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """Search by code or name"""
        args = args or []
        if name:
            # Search by code or name
            domain = ['|', ('codigo', operator, name), ('name', operator, name)]
            commune_ids = self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
            return self.browse(commune_ids).name_get()
        return super(ResCountryCommune, self)._name_search(name, args, operator, limit, name_get_uid)
