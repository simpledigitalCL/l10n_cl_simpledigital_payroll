# l10n_cl_simpledigital_payroll

Módulo de nómina chilena para Odoo 18, desarrollado por Simpledigital.cl.

## Información técnica

| Campo | Valor |
|---|---|
| Versión | 18.0.1.0.0 |
| Licencia | AGPL-3 |
| Autor | Simpledigital.cl |
| Dependencias | `base`, `hr`, `hr_payroll`, `hr_work_entry`, `mail`, `hr_payroll_account` |

## Características

- Gestión de contratos chilenos: AFP, ISAPRE/FONASA, APV/APVC, CCAF, Mutual y AFC
- Cálculo automático de descuentos previsionales, gratificaciones y días trabajados
- Indicadores previsionales con scraping automático mensual desde Previred
- Exportación de archivos Previred (.txt) y Libro de Remuneraciones
- Liquidaciones de sueldo con estructura de nómina chilena
- Tipos de movimiento (bonos, comisiones, viáticos, etc.) con generación automática de reglas salariales
- Asignación automática de vacaciones legales (acumulación mensual via cron)
- Validación de RUT chileno
- Reporte PDF de liquidación de sueldo
- Causales de término de contrato según legislación chilena

## Despliegue en Odoo.sh

1. Clona este repositorio en una rama `18.0`
2. Conecta el repositorio a [odoo.sh](https://www.odoo.sh)
3. Una vez desplegado, ve a **Aplicaciones > Actualizar lista**
4. Busca **"Nómina Chilena Simpledigital"** e instala

## Configuración inicial

Sigue estos pasos en orden después de instalar el módulo.

### 1. Empresa

Ve a **Configuración > Empresa** y completa la pestaña de nómina chilena:

- **Gratificación**: activar si la empresa paga gratificación legal, seleccionar artículo (Art. 47 anual o Art. 50 mensual) y porcentaje
- **CCAF**: seleccionar la caja de compensación (Los Andes, La Araucana, Los Héroes, 18 de Septiembre o Sin CCAF)
- **Mutual de seguridad**: activar si la empresa está adherida a una mutual (ACHS, Mutual CCHC, IST), e ingresar la tasa base (0,93% por defecto) y la tasa adicional si corresponde

### 2. Indicadores previsionales

Ve a **Nómina > Indicadores Previsionales** y crea un registro para el mes en curso:

1. Haz clic en **Nuevo**
2. Ingresa nombre y fecha
3. Presiona el botón **Scrapear Previred** para cargar automáticamente los valores desde previred.com

Los valores que se cargan incluyen: UF, UTM/UTA, tasas AFP por institución, topes imponibles, asignaciones familiares, AFC y APV.

El cron job `cron_scraping_previred` se ejecuta automáticamente el primer día de cada mes para crear o actualizar el indicador del mes. Verifica que el cron esté activo en **Configuración > Técnico > Acciones programadas**.

### 3. Empleados

En la ficha de cada empleado completa:

- **RUT**: campo "Número de identificación" (validación de RUT chileno incluida)
- **Región y comuna** de residencia (ambos campos obligatorios)
- **¿Tiene invalidez?**: si corresponde
- **Descuentos CCAF**: si la empresa tiene CCAF y el empleado tiene descuentos asociados, agrégalos en la pestaña CCAF

### 4. Contratos

En **Nómina > Contratos** o desde la ficha del empleado, configura:

**Previsión**
- Tipo de pensión: AFP, IPS o Sin institución previsional
- AFP a la que está afiliado
- ¿Es pensionado por vejez?

**Salud**
- Institución de salud: FONASA (con tramo A/B/C) o ISAPRE (con monto en CLP o UF)

**Remuneración**
- Colación, movilización y viático fijo (montos fijos mensuales no imponibles)
- ¿Tiene horas extra pactadas? y cantidad de horas
- ¿Tiene gratificación? (hereda la configuración de empresa pero puede desactivarse por contrato)

**Seguro de cesantía (AFC)**
- AFC Empleador: activo si el contrato es indefinido o a plazo fijo con cotización empleador
- AFC Trabajador: activo para contratos indefinidos con cotización trabajador

**Cargas familiares**
- Activar si el empleado tiene cargas y completar número de cargas simples, maternas e inválidas, y tramo

**Otros**
- Tipo de contrato (definido, indefinido, obra o faena, etc.)
- Tipo de jornada (ordinaria Art. 22, parcial Art. 40 bis, etc.)
- Centro de costos (cuenta analítica, campo obligatorio)
- Tipo de renta: Impuesto 2da Categoría, Único Obrero Agrícola o Adicional
- APV/APVC si corresponde: institución, monto de cotización y formato de pago

Al guardar el contrato se asignan automáticamente los días de vacaciones legales según antigüedad.

### 5. Tipos de movimiento

Ve a **Nómina > Tipos de Movimiento**. El módulo ya crea los tipos básicos al instalarse (Bonificaciones, Aguinaldo, Comisiones, Viático, Anticipo, Préstamos, Horas extra no pactadas, Indemnización).

Al crear un nuevo tipo de movimiento, el sistema genera automáticamente una regla salarial asociada en la estructura **Nómina Chile** con la categoría correspondiente:

| Tipo de ingreso | Categoría de regla |
|---|---|
| Imponible | IMP |
| No imponible | NOP_IMP |
| Otros descuentos | others |

Si la empresa tiene `hr_payroll_account` instalado, puedes asignar cuentas contables de débito y crédito al tipo de movimiento para su contabilización automática.

### 6. Generación de liquidaciones

1. Ve a **Nómina > Liquidaciones** y crea un lote
2. Agrega los empleados y el período
3. Calcula la nómina

Los movimientos de empleados (bonos, comisiones, etc.) registrados para el período se incluyen automáticamente en la liquidación según las reglas salariales generadas.
