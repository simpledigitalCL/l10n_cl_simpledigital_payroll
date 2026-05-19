# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Odoo 18 module for Chilean payroll (`l10n_cl_simpledigital_payroll`). Handles AFP/ISAPRE/FONASA contributions, CCAF, AFC, gratificaciones, and generates the Previred TXT file and Libro de Remuneraciones required by Chilean labor law.

## Deployment (GCP)

**Server**: `odoo-new`, zone `us-central1-c`, project `stepsconsulting`  
**Active service**: `odoo18-admin.service` (port 8068, config `/etc/odoo18-admin.conf`)  
**Module path on server**: `/opt/odoo18/custom_addons/l10n_cl_simpledigital_payroll`  
**Log file**: `/var/log/odoo18/odoo-admin.log`  
**Database**: `Prueba_Simple`

There are 6 Odoo services on the server (`odoo18`, `odoo18-sys`, `odoo18-admin`, `odoo18-dev`, `odoo18-everfruit`, `odoo-delete-param`). Always target `odoo18-admin.service`.

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
    -c /etc/odoo18-admin.conf -d Prueba_Simple --stop-after-init \
    -u l10n_cl_simpledigital_payroll
sudo systemctl start odoo18-admin.service
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

The controller has two almost-identical code blocks (one for regular lines, one for additional movement lines). Changes to campo calculations must be applied in both places (~line 657 and ~line 1435).

### Salary structure

- Single structure: **"Nómina Chile"** (`data/hr_salary_rule.xml`)
- `hooks.py:post_init_hook` patches the default BASIC and NET rules after install
- `hr.employee.movement` records (bonos, comisiones, etc.) link to payslips via `hr.previred.movement` and are included in the calculation through auto-generated salary rules

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
