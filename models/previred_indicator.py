import logging
import requests
from bs4 import BeautifulSoup
from odoo import models, fields

_logger = logging.getLogger(__name__)

class PreviredIndicator(models.Model):
    _name = 'previred.indicator'
    _description = 'Indicadores Previsionales Previred'

    name = fields.Char(string="Nombre", required=True)
    date = fields.Date(string="Fecha")
    currency_id = fields.Many2one('res.currency', string="Moneda", default=lambda self: self.env.company.currency_id)

    uf_value_on_month = fields.Float(string="Valor UF")
    uf_value_last_month = fields.Float(string="Valor UF del Mes Anterior")

    # Campos para UTM y UTA
    utm_value = fields.Monetary(string="Valor UTM")
    uta_value = fields.Monetary(string="Valor UTA")

    # campos para Rentas Mínimas Imponibles
    trab_dependiente_independiente = fields.Monetary(string="Trab. Dependientes e Independientes")
    minor_and_major = fields.Monetary(string="Menores de 18 y Mayores de 65")
    home_working = fields.Monetary(string="Trabajadores de Casa Particular",)
    not_refund_income = fields.Monetary(string="Para fines no remuneracionales")

    # AFP
    cargo_empleador = fields.Float(string="Cargo del Empleador", digits=(5, 1))
    capital_tasa_dependiente = fields.Float(string="Capital - Tasa Dependientes", digits=(5, 2))
    capital_tasa_pagar = fields.Float(string="Capital - Tasa a Pagar", digits=(5, 2))
    capital_tasa_independiente = fields.Float(string="Capital - Tasa Independientes", digits=(5, 2))
    
    # Campos individuales para Cuprum
    cuprum_tasa_dependiente = fields.Float(string="Cuprum - Tasa Dependientes", digits=(5, 2))
    cuprum_tasa_pagar = fields.Float(string="Cuprum - Tasa a Pagar", digits=(5, 2))
    cuprum_tasa_independiente = fields.Float(string="Cuprum - Tasa Independientes", digits=(5, 2))
   
    # Campos individuales para Habitat
    habitat_tasa_dependiente = fields.Float(string="Habitat - Tasa Dependientes", digits=(5, 2))
    habitat_tasa_pagar = fields.Float(string="Habitat - Tasa a Pagar", digits=(5, 2))
    habitat_tasa_independiente = fields.Float(string="Habitat - Tasa Independientes", digits=(5, 2))
    
    # Campos individuales para PlanVital
    planvital_tasa_dependiente = fields.Float(string="PlanVital - Tasa Dependientes", digits=(5, 2))
    planvital_tasa_pagar = fields.Float(string="PlanVital - Tasa a Pagar", digits=(5, 2))
    planvital_tasa_independiente = fields.Float(string="PlanVital - Tasa Independientes", digits=(5, 2))

    # Campos individuales para ProVida
    provida_tasa_dependiente = fields.Float(string="ProVida - Tasa Dependientes", digits=(5, 2))
    provida_tasa_pagar = fields.Float(string="ProVida - Tasa a Pagar", digits=(5, 2))
    provida_tasa_independiente = fields.Float(string="ProVida - Tasa Independientes", digits=(5, 2))
    
    # Campos individuales para Modelo
    modelo_tasa_dependiente = fields.Float(string="Modelo - Tasa Dependientes", digits=(5, 2))
    modelo_tasa_pagar = fields.Float(string="Modelo - Tasa a Pagar", digits=(5, 2))
    modelo_tasa_independiente = fields.Float(string="Modelo - Tasa Independientes", digits=(5, 2))
    
    # Campos individuales para Uno
    uno_tasa_dependiente = fields.Float(string="Uno - Tasa Dependientes", digits=(5, 2))
    uno_tasa_pagar = fields.Float(string="Uno - Tasa a Pagar", digits=(5, 2))
    uno_tasa_independiente = fields.Float(string="Uno - Tasa Independientes", digits=(5, 2))

    # Tramos de Asignación Familiar
    tramo_a = fields.Monetary(string="Tramo A")
    tramo_b = fields.Monetary(string="Tramo B")
    tramo_c = fields.Monetary(string="Tramo C")

    # Tope Seguro de Cesantía
    tope_afiliados_ips = fields.Monetary(
        string="Tope Afiliados IPS",
        help="Tope de renta imponible para afiliados a IPS según Superintendencia de Pensiones"
    )

    tope_afiliados_afp = fields.Monetary(
        string="Tope Afiliados AFP",
        help="Tope de renta imponible para afiliados a AFP según Superintendencia de Pensiones"
    )
    
    tope_seguro_cesantia = fields.Monetary(
        string="Tope Seguro de Cesantía",
        help="Tope de renta imponible para el Seguro de Cesantía según Superintendencia de Pensiones"
    )

    # Tope Mensual y Anual para APV
    tope_mensual_apv = fields.Monetary(
        string="Tope Mensual (50 UF)",
    )

    tope_anual_apv = fields.Monetary(
        string="Tope Anual (600 UF)",
    )

    # Tope Anual para Depósito Convenido
    tope_anual_deposito_convenido = fields.Monetary(
        string="Tope Anual Depósito Convenido",
    )

    # Campos para Seguro de Cesantía (AFC)
    plazo_indefinido_empleador = fields.Float(
        string="Plazo Indefinido Empleador",
    )

    plazo_indefinido_trabajador = fields.Float(
        string="Plazo Indefinido Trabajador",
    )

    plazo_fijo_empleador = fields.Float(
        string="Plazo Fijo Empleador",
    )

    plazo_indefinido_empleador_more_11 = fields.Float(
        string="Plazo Indefinido Empleador +11",
    )

    trabajador_casa = fields.Float(
        string="Trabajador Casa",
    )

    # COTIZACIÓN PARA TRABAJOS PESADOS
    trabajo_pesado_empleador = fields.Float(
        string="Trabajo Pesado Empleador",
    )

    trabajo_pesado_trabajador = fields.Float(
        string="Trabajo Pesado Trabajador",
    )

    trabajo_menos_pesado_empleador = fields.Float(
        string="Trabajo Menos Pesado Empleador",
    )

    trabajo_menos_pesado_trabajador = fields.Float(
        string="Trabajo Menos Pesado Trabajador",
    )

    # DISTRIBUCIÓN DEL 7% SALUD, PARA EMPLEADORES AFILIADO A CCAF
    ccaf_empleadores_afiliados = fields.Float(
        string="CCAF Empleadores Afiliados",
    )

    fonasa_empleadores_afiliados = fields.Float(
        string="Fonasa Empleadores Afiliados",
    )

    # SEGURO SOCIAL
    expectativa_vida = fields.Float(
        string="Expectativa de Vida",
    )

    # SIS
    tasa_sis = fields.Float(
        string="Tasa SIS",
    )

    """
        Acción para scrapear los indicadores de Previred
        usando libreria BeautifulSoup
    """
    def action_scraping_previred(self):
        try:
            # Si el registro no existe, crearlo con la fecha actual
            if not self.id:
                self.name = f"Indicadores Previred {fields.Date.today()}"
                self.date = fields.Date.today()
            
            url = 'https://www.previred.com/indicadores-previsionales/'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            
            # === SCRAPING UF ===
            uf_divs = soup.find_all("div", class_="journal-content-article")
            
            uf_value_current = None
            uf_value_previous = None
            
            for uf_div in uf_divs:
                # Buscar tabla que contenga "VALOR UF"
                tables = uf_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "VALOR UF"
                    if table.find("td", string=lambda text: text and "VALOR UF" in text.upper()):
                        
                        rows = table.find_all("tr")
                        uf_data = []
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 2:
                                fecha_text = tds[0].get_text().strip()
                                valor_text = tds[1].get_text().strip()
                                
                                # Solo tomar filas que tengan fechas y valores monetarios
                                if "$" in valor_text and "2025" in fecha_text and not "VALOR UF" in fecha_text:
                                    clean_value = valor_text.replace("$", "").replace(".", "").replace(",", ".").strip()
                                    uf_data.append((fecha_text, clean_value))
                        
                        # Asignar valores: primer valor = mes actual, segundo = mes anterior
                        if len(uf_data) >= 1:
                            uf_value_current = uf_data[0][1]
                            # _logger.info(f"UF mes actual: {uf_value_current} ({uf_data[0][0]})")
                        
                        if len(uf_data) >= 2:
                            uf_value_previous = uf_data[1][1]
                            # _logger.info(f"UF mes anterior: {uf_value_previous} ({uf_data[1][0]})")
                        break
                
                if uf_value_current and uf_value_previous:
                    break
            
            # Asignar valores UF
            if uf_value_current:
                self.uf_value_on_month = float(uf_value_current)
            
            if uf_value_previous:
                self.uf_value_last_month = float(uf_value_previous)
            
            # === SCRAPING AFP ===
            afp_found = False
            afp_divs = soup.find_all("div", class_="entry-links")
            for afp_div in afp_divs: 
                tables = afp_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "AFP" y "TASA COTIZACIÓN"
                    table_text = table.get_text().upper()
                    if "TASA COTIZACIÓN AFP" in table_text and "AFP" in table_text:
                        
                        rows = table.find_all("tr")
                        afp_data = {}
                        
                        # Mapeo de nombres AFP a campos del modelo
                        afp_mapping = {
                            'capital': 'capital',
                            'cuprum': 'cuprum', 
                            'habitat': 'habitat',
                            'planvital': 'planvital',
                            'provida': 'provida',
                            'modelo': 'modelo',
                            'uno': 'uno'
                        }
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 4:
                                afp_name = tds[0].get_text().strip().lower()
                                
                                # Buscar si coincide con alguna AFP
                                for key, model_prefix in afp_mapping.items():
                                    if key in afp_name:
                                        try:
                                            # Extraer tasas (quitar % y convertir a float)
                                            tasa_dependiente = tds[1].get_text().replace("%", "").replace(",", ".").strip()
                                            tasa_cargo_empleador = tds[2].get_text().replace("%", "").replace(",", ".").strip()
                                            tasa_pagar = tds[3].get_text().replace("%", "").replace(",", ".").strip()
                                            tasa_independiente = tds[4].get_text().replace("%", "").replace(",", ".").strip()
                                            
                                            # Asignar a los campos del modelo
                                            setattr(self, f"{model_prefix}_tasa_dependiente", float(tasa_dependiente))
                                            setattr(self, f"cargo_empleador", float(tasa_cargo_empleador))
                                            setattr(self, f"{model_prefix}_tasa_pagar", float(tasa_pagar))
                                            setattr(self, f"{model_prefix}_tasa_independiente", float(tasa_independiente))
                                            
                                            afp_data[key] = {
                                                'dependiente': tasa_dependiente,
                                                'cargo_empleador': tasa_cargo_empleador,
                                                'pagar': tasa_pagar,
                                                'independiente': tasa_independiente
                                            }

                                        except (ValueError, IndexError) as e:
                                            _logger.warning(f"Error procesando AFP {key}: {e}")
                                            continue
                        
                        if afp_data:
                            afp_found = True
                        break
                if afp_found:
                    break
            
            # === SCRAPING RENTAS TOPES IMPONIBLES ===
            topes_found = False
            
            for topes_div in uf_divs:  # Reusar los divs journal-content-article
                tables = topes_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "RENTAS TOPES IMPONIBLES"
                    table_text = table.get_text().upper()
                    if "RENTAS TOPES IMPONIBLES" in table_text:
                        
                        rows = table.find_all("tr")
                        topes_data = {}
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 2:
                                descripcion = tds[0].get_text().strip()
                                valor_text = tds[1].get_text().strip()
                                
                                # Solo procesar filas que tengan valores monetarios
                                if "$" in valor_text:
                                    # Limpiar el valor monetario
                                    clean_value = valor_text.replace("$", "").replace(".", "").replace(",", ".").strip()
                                    # Remover posibles saltos de línea o etiquetas HTML
                                    clean_value = clean_value.split()[0] if clean_value.split() else "0"
                                    
                                    try:
                                        # Identificar a qué tope corresponde según la descripción
                                        if "afiliados a una afp" in descripcion.lower() or "afp" in descripcion.lower():
                                            self.tope_afiliados_afp = float(clean_value)
                                            topes_data['AFP'] = clean_value
                                            # _logger.info(f"Tope AFP: ${clean_value}")
                                        
                                        elif "afiliados al ips" in descripcion.lower() or "ex inp" in descripcion.lower():
                                            self.tope_afiliados_ips = float(clean_value)
                                            topes_data['IPS'] = clean_value
                                            # _logger.info(f"Tope IPS: ${clean_value}")
                                        
                                        elif "seguro de cesantía" in descripcion.lower() or "cesantía" in descripcion.lower():
                                            self.tope_seguro_cesantia = float(clean_value)
                                            topes_data['Cesantía'] = clean_value
                                            # _logger.info(f"Tope Cesantía: ${clean_value}")
                                    
                                    except (ValueError, IndexError) as e:
                                        _logger.warning(f"Error procesando tope '{descripcion}': {e}")
                                        continue
                        
                        if topes_data:
                            topes_found = True
                        break
                
                if topes_found:
                    break
            
            # === SCRAPING UTM y UTA ===
            utm_uta_found = False
            
            for utm_div in uf_divs: 
                tables = utm_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "UTM" y "UTA" en encabezados
                    table_text = table.get_text().upper()
                    if "UTM" in table_text and "UTA" in table_text and "VALOR" in table_text:
                        
                        rows = table.find_all("tr")
                        utm_uta_data = {}
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 3:  # Debe tener al menos 3 columnas: Valor, UTM, UTA
                                periodo = tds[0].get_text().strip()
                                utm_text = tds[1].get_text().strip()
                                uta_text = tds[2].get_text().strip()
                                
                                # Solo procesar la fila que no sea encabezado y tenga valores monetarios
                                if "$" in utm_text and "$" in uta_text and "2025" in periodo:
                                    try:
                                        # Limpiar valores UTM y UTA
                                        utm_clean = utm_text.replace("$", "").replace(".", "").replace(",", ".").strip()
                                        uta_clean = uta_text.replace("$", "").replace(".", "").replace(",", ".").strip()
                                        
                                        # Asignar a campos del modelo
                                        self.utm_value = float(utm_clean)
                                        self.uta_value = float(uta_clean)
                                        
                                        utm_uta_data['UTM'] = utm_clean
                                        utm_uta_data['UTA'] = uta_clean
                                                                                
                                    except (ValueError, IndexError) as e:
                                        _logger.warning(f"Error procesando UTM/UTA: {e}")
                                        continue
                        
                        if utm_uta_data:
                            utm_uta_found = True
                        break
                
                if utm_uta_found:
                    break
            
            # === RENTAS MÍNIMAS IMPONIBLES ===
            minimas_found = False
            
            for minimas_div in uf_divs: 
                tables = minimas_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "RENTAS MÍNIMAS IMPONIBLES"
                    table_text = table.get_text().upper()
                    if "RENTAS MÍNIMAS IMPONIBLES" in table_text:
                        
                        rows = table.find_all("tr")
                        minimas_data = {}
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 2:
                                descripcion = tds[0].get_text().strip()
                                valor_text = tds[1].get_text().strip()
                                
                                # Solo procesar filas que tengan valores monetarios
                                if "$" in valor_text:
                                    # Limpiar el valor monetario
                                    clean_value = valor_text.replace("$", "").replace(".", "").replace(",", ".").strip()
                                    # Remover posibles saltos de línea o etiquetas HTML
                                    clean_value = clean_value.split()[0] if clean_value.split() else "0"
                                    
                                    try:
                                        # Identificar a qué renta mínima corresponde según la descripción
                                        if "trab. dependientes e independientes" in descripcion.lower():
                                            self.trab_dependiente_independiente = float(clean_value)
                                            minimas_data['Dependientes'] = clean_value
                                            # _logger.info(f"Renta Mínima Dependientes: ${clean_value}")
                                        
                                        elif "menores de 18 y mayores de 65" in descripcion.lower():
                                            self.minor_and_major = float(clean_value)
                                            minimas_data['Menores/Mayores'] = clean_value
                                            # _logger.info(f"Renta Mínima Menores/Mayores: ${clean_value}")
                                        
                                        elif "trabajadores de casa particular" in descripcion.lower():
                                            self.home_working = float(clean_value)
                                            minimas_data['Casa Particular'] = clean_value
                                            # _logger.info(f"Renta Mínima Casa Particular: ${clean_value}")
                                        
                                        elif "para fines no remuneracionales" in descripcion.lower():
                                            self.not_refund_income = float(clean_value)
                                            minimas_data['No Remuneracionales'] = clean_value
                                            # _logger.info(f"Renta Mínima No Remuneracionales: ${clean_value}")
                                    
                                    except (ValueError, IndexError) as e:
                                        _logger.warning(f"Error procesando renta mínima '{descripcion}': {e}")
                                        continue
                        
                        if minimas_data:
                            minimas_found = True
                        break
                
                if minimas_found:
                    break
            
            # === SEGURO SOCIAL ===
            seguro_social_found = False
            seguro_divs = soup.find_all("div", class_="journal-content-article")

            for seguro_div in seguro_divs:
                tables = seguro_div.find_all("table")
                for table in tables:
                    table_text = table.get_text().upper()
                    if "SEGURO SOCIAL" in table_text:
                        rows = table.find_all("tr")

                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 2:
                                label = tds[0].get_text(strip=True).upper()
                                value = tds[1].get_text(strip=True)

                                if "EXPECTATIVA DE VIDA" in label and "%" in value:
                                    try:
                                        valor_float = float(value.replace("%", "").replace(",", ".").strip())
                                        self.expectativa_vida = valor_float
                                        # _logger.info(f"Expectativa de Vida: {self.expectativa_vida}%")
                                        seguro_social_found = True
                                        break
                                    except ValueError:
                                        _logger.warning(f"No se pudo convertir a float: {value}")

                if seguro_social_found:
                    break
            
            # ===  SEGURO DE INVALIDEZ Y SOBREVIVENCIA (SIS) ===
            sis_found = False

            for sis_div in seguro_divs:
                tables = sis_div.find_all("table")
                for table in tables:
                    table_text = table.get_text().upper()
                    if "SEGURO DE INVALIDEZ Y SOBREVIVENCIA (SIS)" in table_text or "SIS" in table_text:
                        _logger.info("Tabla SIS encontrada")
                        rows = table.find_all("tr")

                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 2:
                                label = tds[0].get_text(strip=True).upper()
                                value = tds[1].get_text(strip=True)

                                if "TASA SIS" in label and "%" in value:
                                    try:
                                        valor_float = float(value.replace("%", "").replace(",", ".").strip())
                                        self.tasa_sis = valor_float
                                        _logger.info(f"Tasa SIS: {self.tasa_sis}%")
                                        sis_found = True
                                        break
                                    except ValueError:
                                        _logger.warning(f"No se pudo convertir a float: {value}")

                if sis_found:
                    break


            # === SCRAPING ASIGNACIONES FAMILIARES ===
            asignaciones_found = False
            
            for asig_div in uf_divs:  # Reusar los divs journal-content-article
                tables = asig_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "ASIGNACIÓN FAMILIAR"
                    table_text = table.get_text().upper()
                    if "ASIGNACIÓN FAMILIAR" in table_text and "TRAMO" in table_text:
                        
                        rows = table.find_all("tr")
                        asignaciones_data = {}
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 3:
                                tramo = tds[0].get_text().strip()
                                monto_text = tds[1].get_text().strip()
                                
                                # Solo procesar filas que tengan valores monetarios y tramos
                                if "$" in monto_text and ("(A)" in tramo or "(B)" in tramo or "(C)" in tramo):
                                    # Limpiar el valor monetario
                                    clean_value = monto_text.replace("$", "").replace(".", "").replace(",", ".").strip()
                                    
                                    try:
                                        # Identificar tramo
                                        if "(A)" in tramo or "1" in tramo:
                                            self.tramo_a = float(clean_value)
                                            asignaciones_data['Tramo A'] = clean_value
                                            # _logger.info(f"Tramo A: ${clean_value}")
                                        
                                        elif "(B)" in tramo or "2" in tramo:
                                            self.tramo_b = float(clean_value)
                                            asignaciones_data['Tramo B'] = clean_value
                                            # _logger.info(f"Tramo B: ${clean_value}")
                                        
                                        elif "(C)" in tramo or "3" in tramo:
                                            self.tramo_c = float(clean_value)
                                            asignaciones_data['Tramo C'] = clean_value
                                            # _logger.info(f"Tramo C: ${clean_value}")
                                    
                                    except (ValueError, IndexError) as e:
                                        _logger.warning(f"Error procesando asignación familiar '{tramo}': {e}")
                                        continue
                        
                        if asignaciones_data:
                            asignaciones_found = True
                        break
                
                if asignaciones_found:
                    break
            
            # === SCRAPING TRABAJOS PESADOS ===
            pesados_found = False
            
            for pesados_div in uf_divs:  # Reusar los divs journal-content-article
                tables = pesados_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "COTIZACIÓN PARA TRABAJOS PESADOS"
                    table_text = table.get_text().upper()
                    if "COTIZACIÓN PARA TRABAJOS PESADOS" in table_text:
                        
                        rows = table.find_all("tr")
                        pesados_data = {}
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 4:
                                trabajo_tipo = tds[0].get_text().strip().lower()
                                empleador_text = tds[2].get_text().strip()
                                trabajador_text = tds[3].get_text().strip()
                                
                                # Solo procesar filas que tengan porcentajes
                                if "%" in empleador_text and "%" in trabajador_text:
                                    try:
                                        # Extraer porcentajes
                                        empleador_pct = empleador_text.replace("%", "").replace("R.I.", "").strip()
                                        trabajador_pct = trabajador_text.replace("%", "").replace("R.I.", "").strip()
                                        
                                        # Identificar tipo de trabajo
                                        if "trabajo pesado" in trabajo_tipo and "menos" not in trabajo_tipo:
                                            self.trabajo_pesado_empleador = float(empleador_pct)
                                            self.trabajo_pesado_trabajador = float(trabajador_pct)
                                            pesados_data['Trabajo Pesado'] = f"Emp: {empleador_pct}%, Trab: {trabajador_pct}%"
                                            # _logger.info(f"Trabajo Pesado - Empleador: {empleador_pct}%, Trabajador: {trabajador_pct}%")
                                        
                                        elif "trabajo menos pesado" in trabajo_tipo:
                                            self.trabajo_menos_pesado_empleador = float(empleador_pct)
                                            self.trabajo_menos_pesado_trabajador = float(trabajador_pct)
                                            pesados_data['Trabajo Menos Pesado'] = f"Emp: {empleador_pct}%, Trab: {trabajador_pct}%"
                                            # _logger.info(f"Trabajo Menos Pesado - Empleador: {empleador_pct}%, Trabajador: {trabajador_pct}%")
                                    
                                    except (ValueError, IndexError) as e:
                                        _logger.warning(f"Error procesando trabajo pesado '{trabajo_tipo}': {e}")
                                        continue
                        
                        if pesados_data:
                            pesados_found = True
                        break
                
                if pesados_found:
                    break
            
            # === SCRAPING DISTRIBUCIÓN 7% SALUD CCAF ===
            ccaf_found = False
            
            for ccaf_div in uf_divs: 
                tables = ccaf_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "DISTRIBUCIÓN DEL 7% SALUD"
                    table_text = table.get_text().upper()
                    if "DISTRIBUCIÓN DEL 7% SALUD" in table_text and "CCAF" in table_text:
                        
                        rows = table.find_all("tr")
                        ccaf_data = {}
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 2:
                                institucion = tds[0].get_text().strip().lower()
                                porcentaje_text = tds[1].get_text().strip()
                                
                                # Solo procesar filas que tengan porcentajes
                                if "%" in porcentaje_text and "r.i." in porcentaje_text.lower():
                                    try:
                                        # Extraer porcentaje
                                        porcentaje = porcentaje_text.replace("%", "").replace("R.I.", "").replace("r.i.", "").strip().replace(",", ".")
                                        
                                        # Identificar institución
                                        if "ccaf" in institucion:
                                            self.ccaf_empleadores_afiliados = float(porcentaje)
                                            ccaf_data['CCAF'] = f"{porcentaje}%"
                                            _logger.info(f"CCAF Empleadores Afiliados: {porcentaje}%")
                                        
                                        elif "fonasa" in institucion:
                                            self.fonasa_empleadores_afiliados = float(porcentaje)
                                            ccaf_data['FONASA'] = f"{porcentaje}%"
                                            _logger.info(f"FONASA Empleadores Afiliados: {porcentaje}%")
                                    
                                    except (ValueError, IndexError) as e:
                                        _logger.warning(f"Error procesando distribución 7% '{institucion}': {e}")
                                        continue
                        
                        if ccaf_data:
                            ccaf_found = True
                        break
                
                if ccaf_found:
                    break
            
            # === SCRAPING AHORRO PREVISIONAL VOLUNTARIO (APV) ===
            apv_found = False
            
            for apv_div in uf_divs:  # Reusar los divs journal-content-article
                tables = apv_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "AHORRO PREVISIONAL VOLUNTARIO"
                    table_text = table.get_text().upper()
                    if "AHORRO PREVISIONAL VOLUNTARIO" in table_text and "APV" in table_text:
                        
                        rows = table.find_all("tr")
                        apv_data = {}
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 2:
                                descripcion = tds[0].get_text().strip()
                                valor_text = tds[1].get_text().strip()
                                
                                # Solo procesar filas que tengan valores monetarios
                                if "$" in valor_text:
                                    # Limpiar el valor monetario
                                    clean_value = valor_text.replace("$", "").replace(".", "").replace(",", ".").strip()
                                    clean_value = clean_value.split()[0] if clean_value.split() else "0"
                                    
                                    try:
                                        # Identificar tope según descripción
                                        if "tope mensual" in descripcion.lower() and "50 uf" in descripcion.lower():
                                            self.tope_mensual_apv = float(clean_value)
                                            apv_data['Tope Mensual'] = clean_value
                                            _logger.info(f"APV Tope Mensual: ${clean_value}")
                                        
                                        elif "tope anual" in descripcion.lower() and "600 uf" in descripcion.lower():
                                            self.tope_anual_apv = float(clean_value)
                                            apv_data['Tope Anual'] = clean_value
                                            _logger.info(f"APV Tope Anual: ${clean_value}")
                                    
                                    except (ValueError, IndexError) as e:
                                        _logger.warning(f"Error procesando APV '{descripcion}': {e}")
                                        continue
                        
                        if apv_data:
                            apv_found = True
                        break
                
                if apv_found:
                    break
            
            # === SCRAPING DEPÓSITO CONVENIDO ===
            deposito_found = False
            
            for deposito_div in uf_divs:  # Reusar los divs journal-content-article
                tables = deposito_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "DEPÓSITO CONVENIDO"
                    table_text = table.get_text().upper()
                    if "DEPÓSITO CONVENIDO" in table_text:
                        
                        rows = table.find_all("tr")
                        deposito_data = {}
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 2:
                                descripcion = tds[0].get_text().strip()
                                valor_text = tds[1].get_text().strip()
                                
                                # Solo procesar filas que tengan valores monetarios
                                if "$" in valor_text and "tope anual" in descripcion.lower():
                                    # Limpiar el valor monetario
                                    clean_value = valor_text.replace("$", "").replace(".", "").replace(",", ".").strip()
                                    clean_value = clean_value.split()[0] if clean_value.split() else "0"
                                    
                                    try:
                                        # Asignar tope anual depósito convenido
                                        self.tope_anual_deposito_convenido = float(clean_value)
                                        deposito_data['Tope Anual'] = clean_value
                                        _logger.info(f"Depósito Convenido Tope Anual: ${clean_value}")
                                    
                                    except (ValueError, IndexError) as e:
                                        _logger.warning(f"Error procesando Depósito Convenido '{descripcion}': {e}")
                                        continue
                        
                        if deposito_data:
                            deposito_found = True
                        break
                
                if deposito_found:
                    break
            
            # === SCRAPING SEGURO DE CESANTÍA (AFC) ===
            afc_found = False
            
            for afc_div in uf_divs:  # Reusar los divs journal-content-article
                tables = afc_div.find_all("table")
                for table in tables:
                    # Verificar si esta tabla contiene "SEGURO DE CESANTÍA" y "AFC"
                    table_text = table.get_text().upper()
                    if "SEGURO DE CESANTÍA" in table_text and "AFC" in table_text and "CONTRATO" in table_text:
                        
                        rows = table.find_all("tr")
                        afc_data = {}
                        
                        for tr in rows:
                            tds = tr.find_all("td")
                            if len(tds) >= 3:
                                contrato_tipo = tds[0].get_text().strip().lower()
                                empleador_text = tds[1].get_text().strip()
                                trabajador_text = tds[2].get_text().strip()
                                
                                # Solo procesar filas que tengan porcentajes
                                if "%" in empleador_text and "r.i." in empleador_text.lower():
                                    try:
                                        # Extraer porcentajes del empleador
                                        empleador_pct = empleador_text.replace("%", "").replace("R.I.", "").replace("r.i.", "").strip().replace(",", ".")
                                        
                                        # Extraer porcentaje del trabajador (puede ser "–")
                                        trabajador_pct = "0"
                                        if "%" in trabajador_text and "–" not in trabajador_text:
                                            trabajador_pct = trabajador_text.replace("%", "").replace("R.I.", "").replace("r.i.", "").strip().replace(",", ".")
                                        
                                        # Identificar tipo de contrato
                                        if "plazo indefinido" in contrato_tipo and "11" not in contrato_tipo:
                                            self.plazo_indefinido_empleador = float(empleador_pct)
                                            self.plazo_indefinido_trabajador = float(trabajador_pct)
                                            afc_data['Plazo Indefinido'] = f"Emp: {empleador_pct}%, Trab: {trabajador_pct}%"
                                            _logger.info(f"AFC Plazo Indefinido - Empleador: {empleador_pct}%, Trabajador: {trabajador_pct}%")
                                        
                                        elif "plazo fijo" in contrato_tipo:
                                            self.plazo_fijo_empleador = float(empleador_pct)
                                            afc_data['Plazo Fijo'] = f"Emp: {empleador_pct}%"
                                            _logger.info(f"AFC Plazo Fijo - Empleador: {empleador_pct}%")
                                        
                                        elif "plazo indefinido 11" in contrato_tipo or "11 años" in contrato_tipo:
                                            self.plazo_indefinido_empleador_more_11 = float(empleador_pct)
                                            afc_data['Plazo Indefinido +11'] = f"Emp: {empleador_pct}%"
                                            _logger.info(f"AFC Plazo Indefinido +11 años - Empleador: {empleador_pct}%")
                                        
                                        elif "trabajador de casa particular" in contrato_tipo:
                                            self.trabajador_casa = float(empleador_pct)
                                            afc_data['Casa Particular'] = f"Emp: {empleador_pct}%"
                                            _logger.info(f"AFC Trabajador Casa Particular - Empleador: {empleador_pct}%")
                                    
                                    except (ValueError, IndexError) as e:
                                        _logger.warning(f"Error procesando AFC '{contrato_tipo}': {e}")
                                        continue
                        
                        if afc_data:
                            afc_found = True
                        break
                
                if afc_found:
                    break
            
            # Resultado final
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': ('Scraping Previred Exitoso'),
                    'message': 'Scraping completo',
                    'type': 'success',
                }
            }
                
        except Exception as e:
            self.name = f"ERROR: {str(e)}"
            _logger.error(f"Error en scraping Previred: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': ('Error de scraping'),
                    'message': str(e),
                    'type': 'danger',
                }
            }
    
    def cron_scraping_previred(self):
        """Método para ser llamado por el cron job mensual"""
        try:
            # Buscar si ya existe un registro para este mes
            today = fields.Date.today()
            current_month = today.replace(day=1)  # Primer día del mes actual
            existing_record = self.search([
                ('date', '>=', current_month),
                ('date', '<', current_month.replace(month=current_month.month + 1) if current_month.month < 12 else current_month.replace(year=current_month.year + 1, month=1))
            ], limit=1)
            
            if existing_record:
                # Actualizar el registro existente del mes
                _logger.info(f"Actualizando registro existente de Previred para {current_month.strftime('%B %Y')}")
                existing_record.action_scraping_previred()
                return existing_record
            else:
                # Crear nuevo registro para este mes
                _logger.info(f"Creando nuevo registro de Previred para {current_month.strftime('%B %Y')}")
                new_record = self.create({
                    'name': f"Indicadores Previred {current_month.strftime('%B %Y')}",
                    'date': today
                })
                new_record.action_scraping_previred()
                return new_record
                
        except Exception as e:
            _logger.error(f"Error en cron mensual de scraping Previred: {str(e)}")
            # Crear registro de error
            self.create({
                'name': f"ERROR: Scraping Previred {fields.Date.today().strftime('%B %Y')}",
                'date': fields.Date.today()
            })
            raise