{
    "name": "Nómina Chilena Simpledigital",
    "version": "18.0.1.0.0",
    "category": "Localization/Chile",
    "summary": "Módulo de nómina chilena desarrollado por Simpledigital.cl",
    "description": """
Módulo de Nómina para Chile desarrollado por Simpledigital.cl

Características principales:
- Remuneraciones completas según legislación chilena.
- Cálculo automático de AFP, Isapres, APV, CCAF, Mutual.
- Exportación a Previred.
- Libros de remuneraciones y reportes personalizados.
- Gestión de asistencia, vacaciones y licencias médicas.
    """,
    "author": "Simpledigital.cl",
    "website": "https://simpledigital.cl",
    "contributors": [
        "Claudio Poblete <contacto@simpledigital.cl>",
    ],
    "license": "AGPL-3",
"depends": [
    "hr",
    "hr_contract",
    "hr_work_entry",
    "hr_holidays",
    "hr_payroll",
    "hr_payroll_account", 
    "hr_payroll_holidays",      
    "account",
    "l10n_cl"
],
    "external_dependencies": {
        "python": [
            "requests",
            "bs4"
        ]
    },
    "data": [
        "security/ir.model.access.csv",

        "views/menu_root.xml",
        "views/hr_afp_view.xml",
        "views/hr_isapre_view.xml",
        "views/hr_indicadores_previsionales_view.xml",
        "views/hr_apv_view.xml",
        "views/hr_ccaf_view.xml",
        "views/hr_type_employee_view.xml",
        "views/hr_seguro_complementario_view.xml",
        "views/hr_mutual_view.xml",

        "views/hr_contract_view.xml",
        "views/hr_employee.xml",
        "views/hr_contribution_register_view.xml",

        "views/hr_payslip_view.xml",
        "views/hr_payslip_run_view.xml",
        "views/hr_salary_rule_view.xml",
        "views/hr_holiday_views.xml",
        "views/hr_salary_books.xml",

        "views/wizard_export_csv_previred_view.xml",
        "views/account_centralized_export.xml",

        "views/report_payslip.xml",
        "views/report_hrsalarybymonth.xml",

        "data/account_journal.xml",
        "data/hr_centros_costos.xml",
        "data/hr_contract_type.xml",
        "data/hr_salary_rule_category.xml",
        "data/l10n_cl_hr_afp.xml",
        "data/l10n_cl_hr_apv.xml",
        "data/l10n_cl_hr_ccaf.xml",
        "data/l10n_cl_hr_indicadores.xml",
        "data/l10n_cl_hr_isapre.xml",
        "data/l10n_cl_hr_mutual.xml",
        "data/hr_type_employee.xml",
        "data/l10n_cl_hr_payroll_data.xml",
        "data/partner.xml",
        "data/resource_calendar_attendance.xml"
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "price": 150.00,
    "currency": "USD"
}
