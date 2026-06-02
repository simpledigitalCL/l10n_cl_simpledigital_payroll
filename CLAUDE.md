# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Odoo 18 module for Chilean payroll (`l10n_cl_simpledigital_payroll`). Handles AFP/ISAPRE/FONASA contributions, CCAF, AFC, gratificaciones, and generates the Previred TXT file and Libro de Remuneraciones required by Chilean labor law.

## Deployment (GCP)

**Server**: `odoo-new`, zone `us-central1-c`, project `stepsconsulting`  
**Active service**: `odoo18-admin.service` (port 8068, config `/etc/odoo18-admin.conf`)  
**Module path on server**: `/opt/odoo18/custom_addons/l10n_cl_simpledigital_payroll`  
**Log file**: `/var/log/odoo18/odoo-admin.log`  
**Databases**: `odoo18-admin.conf` has **no `db_name`**, so the service hosts several DBs (e.g. `Prueba_Simple`, `SyS_Simple`, ...). Always pass `-d <DB>` explicitly. The module lives in `/opt/odoo18/custom_addons`, which is **only** in `odoo18-admin.conf`'s `addons_path` — other configs (`odoo18-sys.conf`, etc.) can't see it, so always use `-c /etc/odoo18-admin.conf` for this module regardless of which DB you target.

There are several Odoo services on the server. Always target `odoo18-admin.service` for this module. List DBs with `sudo -u postgres psql -lqt`.

### Updating a Python file

```bash
# From local repo root:
gcloud compute scp ./controllers/previred_txt.py \
    nicoruiz2003_gmail_com@odoo-new:/tmp/previred_txt.py \
    --zone=us-central1-c --project=stepsconsulting

# On server:
sudo cp /tmp/previred_txt.py /opt/odoo18/custom_addons/l10n_cl_simpledigital_payroll/controllers/previred_txt.py
sudo chown odoo:odoo /opt/odoo18/custom_addons/l10n_cl_simpledigital_payroll/controllers/previred_txt.py
sudo systemctl restart odoo18-admin.service
```

For XML/view/field changes, use upgrade instead of restart:
```bash
sudo systemctl stop odoo18-admin.service
sudo -u odoo /opt/odoo18/venv/bin/python /opt/odoo18/odoo-bin \
    -c /etc/odoo18-admin.conf -d <DB> --stop-after-init \
    -u l10n_cl_simpledigital_payroll
sudo systemctl start odoo18-admin.service
```

### ⚠️ Salary-rule changes do NOT deploy via upgrade

`data/hr_salary_rule.xml` is wrapped in `<data noupdate="1">`. The salary rules and categories are **seeded only at install time**; `-u` will NOT overwrite an existing rule's `amount_python_compute`, condition, etc. To push a rule-logic change to a running DB you must either edit the rule in the UI, or patch the field directly via `odoo-bin shell`:

```bash
# write a small script that does rule.amount_python_compute = ... ; env.cr.commit()
sudo -u odoo /opt/odoo18/venv/bin/python /opt/odoo18/odoo-bin shell \
    -c /etc/odoo18-admin.conf -d <DB> --no-http < /tmp/patch.py
```

Keep the repo XML in sync too (it's the seed for fresh installs). A rule change only affects **payslips recomputed after** the change — existing payslips keep their stored line values until recomputed.

### Testing a report render headlessly

```python
# via odoo-bin shell — catches QWeb runtime errors the upgrade won't:
ps = env['hr.payslip'].search([('line_ids','!=',False)], limit=1)
html = env['ir.qweb']._render('hr_payroll.report_payslip',
    {'docs': ps, 'o': ps, 'doc_ids': ps.ids, 'doc_model': 'hr.payslip'})
```

### Viewing logs

```bash
sudo tail -f /var/log/odoo18/odoo-admin.log | grep -E "PREVIRED|FONASA|CCAF"
```

`_logger.info` is filtered out in production — use `_logger.warning` for debug output.

## Architecture

### Key data flow: Previred TXT generation

1. User opens wizard (`wizard/hr_previred_txt_wizard.py`) and selects period
2. Wizard redirects to `/hr_payroll/previred/txt?period=MMYYYY`
3. `controllers/previred_txt.py:PreviredExportController` iterates all confirmed payslips for the period
4. For each payslip, looks up `previred.indicator` for that month to get rates (AFP, FONASA, topes imponibles, etc.)
5. Builds a semicolon-delimited line per employee following the Previred long format spec
6. Returns the file as a download

The controller has two almost-identical code blocks (one for regular lines, one for additional movement lines), each ending in a `formatted_line` f-string of all 105 campos. **Any campo change must be applied in both blocks** — grep for the `# Campo NN` comment to find both copies. Amount campos are sourced from the salary rules via `self._get_payslip_lines(payslip, ['CODE'])` (e.g. campo 101 = `AFC_T`, campo 102 = `AFC_EMPLEADOR`) to keep the logic centralized in the rules rather than recomputed here.

### Salary structure

- Single structure: **"Nómina Chile"** (`data/hr_salary_rule.xml`)
- `hooks.py:post_init_hook` patches the default BASIC and NET rules after install (renames them, and sets NET = `categories['GROSS'] + categories['habIMP'] - categories['TOTAL_DESC']`)
- `hr.employee.movement` records (bonos, comisiones, etc.) link to payslips via `hr.previred.movement` and are included in the calculation through auto-generated salary rules

**Category codes that trip people up** (these are `hr.salary.rule.category.code`, used to route/sum lines):

| Concept | Category code | Notes |
|---|---|---|
| Sueldo Base | `IMP` | BASIC rule re-categorized to `IMP` by the post_init_hook |
| Total imponible ("Sueldo imponible") | `GROSS` | Odoo default — **not** `BRUTO`. `categories['GROSS']` is the imponible base used everywhere |
| Total no imponible | `habIMP` | sum of COLA/MOV/ASIG_FAM/etc. (`NOP_IMP` lines) |
| Total descuentos | `TOTAL_DESC` | the `TOTAL_DSCTOS` rule sums the employee deduction categories |
| Sueldo Líquido | `NET` | the NET line's category is `NET`, **not** the custom `NETO`. For the net value use `payslip.net_wage` |

Employer contributions (`AFP_EMP`, `AFC_EMP`, `APV_EMP`, `AP_MUT`) are not employee-visible deductions and are excluded from the líquido. Common worked-entry codes referenced in rule logic: `WORK100` (asistencia), `LEAVECL120` (vacaciones), `LIC` (licencia médica), `LEAVE90`, `OUT`.

### Payslip PDF report

`report/report_payslip_templates.xml` inherits `hr_payroll.report_payslip` and:
- replaces `worked_days_table` (Spanish headers, removes amounts)
- replaces `payslip_lines_table` with a two-column **HABERES | DESCUENTOS** layout, computing `TOTAL HABERES` (= GROSS + habIMP) and reading `o.net_wage` for `LÍQUIDO A RECIBIR`
- empties `to_pay` and appends a signature section

Lines are routed to columns by category code; the totals reuse the existing subtotal lines so figures match the computed payslip.

### previred.indicator

Monthly record scraped from previred.com via BeautifulSoup. Contains AFP rates per institution, topes imponibles, FONASA/CCAF distribution rates, AFC rates, asignaciones familiares, APV limits, etc. Created automatically by `cron_scraping_previred` on day 1 of each month.

Key fields for FONASA calculation:
- `fonasa_empleadores_afiliados`: FONASA's share of the 7% (e.g. 2.8%)
- `ccaf_empleadores_afiliados`: CCAF's share of the 7% (e.g. 4.2%)
- Together they always sum to 7%

### CCAF logic

`res.company.caja_compensacion` stores values like `"Sin CCAF"`, `"00"`, or a CCAF code. The string `"Sin CCAF"` is truthy and not `"00"`, so conditions checking `_ccaf and _ccaf != '00'` will incorrectly treat it as an active CCAF. Always check actual behavior rather than assuming the condition is correct.

### Models overview

| File | What it does |
|------|-------------|
| `models/previred_indicator.py` | Scrapes and stores monthly previred rates |
| `models/hr_contract.py` | Adds AFP, ISAPRE/FONASA, CCAF, AFC, gratificación, APV fields |
| `models/hr_employee.py` | Adds RUT validation, commune, disability fields |
| `models/hr_employee_movement.py` | New model for bonos/descuentos linked to payslips |
| `models/hr_payslip.py` | Overrides `compute_sheet` to validate indicators and impuesto exist |
| `models/hr_leave.py` | Custom business-day calculation for Chilean holidays |
| `models/impuesto.py` | Tabla de impuesto 2da categoría |
| `controllers/previred_txt.py` | HTTP download of Previred TXT (main business logic) |
| `controllers/libro_remuneraciones.py` | HTTP download of Libro de Remuneraciones |
