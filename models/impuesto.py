import logging
import requests
from odoo import models, fields
from odoo.exceptions import UserError
from bs4 import BeautifulSoup
import locale

_logger = logging.getLogger(__name__)

class Impuesto2daCategoria(models.Model):
    _name = 'impuesto_2da_categoria'
    _description = 'Impuesto 2da Categoria del SII'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nombre', required=True)
    date = fields.Date(string="Fecha", tracking=True)
    currency_id = fields.Many2one('res.currency', string="Moneda", default=lambda self: self.env.company.currency_id)

    first_line_to = fields.Float(string='Límite Inferior', default=0.0, digits=(10, 3))

    second_line_from = fields.Float(string='Límite Superior', default=0.0, digits=(10, 3))
    second_line_to = fields.Float(string='Límite Superior', default=0.0, digits=(10, 3))
    second_line_factor = fields.Float(string='Factor', default=0.0, digits=(10, 3))
    second_line_tasa_rebaja = fields.Float(string='Tasa de Rebaja', default=0.0, digits=(10, 3))

    third_line_from = fields.Float(string='Límite Inferior', default=0.0, digits=(10, 3))
    third_line_to = fields.Float(string='Límite Superior', default=0.0, digits=(10, 3))
    third_line_factor = fields.Float(string='Factor', default=0.0, digits=(10, 3))
    third_line_tasa_rebaja = fields.Float(string='Tasa de Rebaja', default=0.0, digits=(10, 3))

    fourth_line_from = fields.Float(string='Límite Inferior', default=0.0, digits=(10, 3))
    fourth_line_to = fields.Float(string='Límite Superior', default=0.0, digits=(10, 3))
    fourth_line_factor = fields.Float(string='Factor', default=0.0, digits=(10, 3))
    fourth_line_tasa_rebaja = fields.Float(string='Tasa de Rebaja', default=0.0, digits=(10, 3))

    fifth_line_from = fields.Float(string='Límite Inferior', default=0.0, digits=(10, 3))
    fifth_line_to = fields.Float(string='Límite Superior', default=0.0, digits=(10, 3))
    fifth_line_factor = fields.Float(string='Factor', default=0.0, digits=(10, 3))
    fifth_line_tasa_rebaja = fields.Float(string='Tasa de Rebaja', default=0.0, digits=(10, 3))

    sixth_line_from = fields.Float(string='Límite Inferior', default=0.0, digits=(10, 3))
    sixth_line_to = fields.Float(string='Límite Superior', default=0.0, digits=(10, 3))
    sixth_line_factor = fields.Float(string='Factor', default=0.0, digits=(10, 3))
    sixth_line_tasa_rebaja = fields.Float(string='Tasa de Rebaja', default=0.0, digits=(10, 3))

    seventh_line_from = fields.Float(string='Límite Inferior', default=0.0, digits=(10, 3))
    seventh_line_to = fields.Float(string='Límite Superior', default=0.0, digits=(10, 3))
    seventh_line_factor = fields.Float(string='Factor', default=0.0, digits=(10, 3))
    seventh_line_tasa_rebaja = fields.Float(string='Tasa de Rebaja', default=0.0, digits=(10, 3))

    eighth_line_from = fields.Float(string='Límite Inferior', default=0.0, digits=(10, 3))
    eighth_line_factor = fields.Float(string='Factor', default=0.0, digits=(10, 3))
    eighth_line_tasa_rebaja = fields.Float(string='Tasa de Rebaja', default=0.0, digits=(10, 3))

    # ---------------------------
    # Helpers
    # ---------------------------
    def parse_currency(self, value):
        if not value or "Y MÁS" in value:
            return 0.0
        cleaned = (
            value.replace('$', '')
                 .replace('.', '')   # eliminar separador de miles
                 .replace(',', '.') # coma decimal → punto
                 .strip()
        )
        return float(cleaned)

    def get_selected_period(self, soup, url):
        """Obtiene el mes y año del período actual del SII.
        
        Args:
            soup: BeautifulSoup object con el HTML de la página
            url: URL de la página del SII
        
        Returns:
            tuple: (mes, año) donde mes es el nombre del mes en español y año es un string
        """
        mes = None
        anio = None
        
        try:
            # Obtener el año de la URL (más confiable)
            import re
            match = re.search(r'impuesto(\d{4})\.htm', url)
            if match:
                anio = match.group(1)
                _logger.info(f"Año extraído de URL: {anio}")
            
            # Buscar el mes en el texto de los botones y spans
            for element in soup.find_all(['button', 'span']):
                text = element.get_text().strip()
                if text in ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]:
                    mes = text
                    _logger.info(f"Mes encontrado: {mes}")
                    break
            
            # Si no se encontró el mes en los botones, buscar en todo el HTML
            if not mes:
                _logger.info("Buscando mes en todo el HTML...")
                for text in soup.stripped_strings:
                    if text in ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                              "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]:
                        mes = text
                        _logger.info(f"Mes encontrado en texto general: {mes}")
                        break
            
            _logger.info(f"Período final - Mes: {mes}, Año: {anio}")

        except Exception as e:
            _logger.error(f"Error en get_selected_period: {str(e)}")
            _logger.error("Traceback:", exc_info=True)

        return mes, anio

    def validate_date_with_site(self, soup, url):
        mes_nombre, anio_str = self.get_selected_period(soup, url)
        if not (mes_nombre and anio_str):
            raise UserError("No se pudo detectar el mes/año actual del sitio SII.")

        if not self.date:
            raise UserError("Debe definir una fecha en el registro antes de validar.")

        # Nombre de mes en español
        try:
            locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
        except:
            locale.setlocale(locale.LC_TIME, "es_CL.UTF-8")

        mes_modelo = self.date.strftime("%B").capitalize()
        anio_modelo = str(self.date.year)

        if mes_modelo != mes_nombre or anio_modelo != anio_str:
            raise UserError(
                f"La fecha seleccionada en el registro ({mes_modelo} {anio_modelo}) "
                f"no coincide con el periodo del sitio SII ({mes_nombre} {anio_str}). "
                "Debe seleccionar un mes/año válido."
            )

    # ---------------------------
    # Acción principal
    # ---------------------------
    def action_scraping_impuesto_2da_categoria(self):
        try:
            if not self.id:
                self.name = f"Indicadores Previred {fields.Date.today()}"
                self.date = fields.Date.today()

            url = 'https://www.sii.cl/valores_y_fechas/impuesto_2da_categoria/impuesto2026.htm'
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # Validación contra mes/año del sitio
            self.validate_date_with_site(soup, url)

            _logger.info("Iniciando scraping Impuesto 2da Categoria")

            tabla = soup.find('table', {'class': 'table'})
            if not tabla:
                raise ValueError("No se encontró la tabla de impuestos")

            filas = tabla.find_all('tr')
            seccion_mensual = False
            lineas_procesadas = 0

            for fila in filas:
                celdas = fila.find_all('td')
                
                # Si encontramos 'MENSUAL', comenzamos a procesar
                if celdas and celdas[0].get_text().strip() == 'MENSUAL':
                    seccion_mensual = True
                    # Procesar directamente esta fila (no usar continue)
                    valor_first_line_to = celdas[2].get_text().strip()
                    self.first_line_to = float(
                        valor_first_line_to.replace('$', '').replace('.', '').replace(',', '.')
                    )
                    _logger.info(f"first_line_to = {self.first_line_to}")
                    lineas_procesadas = 1
                    continue

                # Si estamos en la sección mensual y tenemos celdas
                if seccion_mensual and celdas:
                    # Segunda fila: primer tramo real
                    if lineas_procesadas == 1 and len(celdas) >= 6:
                        valor_from = celdas[1].get_text().strip()
                        valor_to = celdas[2].get_text().strip()
                        factor = celdas[3].get_text().strip()
                        rebaja = celdas[4].get_text().strip()

                        self.second_line_from = float(valor_from.replace('$', '').replace('.', '').replace(',', '.'))
                        self.second_line_to = float(valor_to.replace('$', '').replace('.', '').replace(',', '.'))
                        self.second_line_factor = float(factor.replace(',', '.'))
                        self.second_line_tasa_rebaja = float(rebaja.replace('$', '').replace('.', '').replace(',', '.'))

                        _logger.info(f"Tramo 2: {self.second_line_from} → {self.second_line_to}, factor={self.second_line_factor}, rebaja={self.second_line_tasa_rebaja}")
                        lineas_procesadas += 1

                    # Tercera fila: segundo tramo real
                    elif lineas_procesadas == 2 and len(celdas) >= 6:
                        valor_from = celdas[1].get_text().strip()
                        valor_to = celdas[2].get_text().strip()
                        factor = celdas[3].get_text().strip()
                        rebaja = celdas[4].get_text().strip()

                        self.third_line_from = float(valor_from.replace('$', '').replace('.', '').replace(',', '.'))
                        self.third_line_to = float(valor_to.replace('$', '').replace('.', '').replace(',', '.'))
                        self.third_line_factor = float(factor.replace(',', '.'))
                        self.third_line_tasa_rebaja = float(rebaja.replace('$', '').replace('.', '').replace(',', '.'))

                        _logger.info(f"Tramo 3: {self.third_line_from} → {self.third_line_to}, factor={self.third_line_factor}, rebaja={self.third_line_tasa_rebaja}")
                        lineas_procesadas += 1
                    # Cuarta fila: tercer tramo real
                    elif lineas_procesadas == 3 and len(celdas) >= 6:
                        valor_from = celdas[1].get_text().strip()
                        valor_to = celdas[2].get_text().strip()
                        factor = celdas[3].get_text().strip()
                        rebaja = celdas[4].get_text().strip()

                        self.fourth_line_from = float(valor_from.replace('$', '').replace('.', '').replace(',', '.'))
                        self.fourth_line_to = float(valor_to.replace('$', '').replace('.', '').replace(',', '.'))
                        self.fourth_line_factor = float(factor.replace(',', '.'))
                        self.fourth_line_tasa_rebaja = float(rebaja.replace('$', '').replace('.', '').replace(',', '.'))

                        _logger.info(f"Tramo 4: {self.fourth_line_from} → {self.fourth_line_to}, factor={self.fourth_line_factor}, rebaja={self.fourth_line_tasa_rebaja}")
                        lineas_procesadas += 1
                    
                    # Quinta fila: cuarto tramo real
                    elif lineas_procesadas == 4 and len(celdas) >= 6:
                        valor_from = celdas[1].get_text().strip()
                        valor_to = celdas[2].get_text().strip()
                        factor = celdas[3].get_text().strip()
                        rebaja = celdas[4].get_text().strip()

                        self.fifth_line_from = float(valor_from.replace('$', '').replace('.', '').replace(',', '.'))
                        self.fifth_line_to = float(valor_to.replace('$', '').replace('.', '').replace(',', '.'))
                        self.fifth_line_factor = float(factor.replace(',', '.'))
                        self.fifth_line_tasa_rebaja = float(rebaja.replace('$', '').replace('.', '').replace(',', '.'))

                        _logger.info(f"Tramo 5: {self.fifth_line_from} → {self.fifth_line_to}, factor={self.fifth_line_factor}, rebaja={self.fifth_line_tasa_rebaja}")
                        lineas_procesadas += 1
                    
                    # Sexta fila: quinto tramo real
                    elif lineas_procesadas == 5 and len(celdas) >= 6:
                        valor_from = celdas[1].get_text().strip()
                        valor_to = celdas[2].get_text().strip()
                        factor = celdas[3].get_text().strip()
                        rebaja = celdas[4].get_text().strip()

                        self.sixth_line_from = float(valor_from.replace('$', '').replace('.', '').replace(',', '.'))
                        self.sixth_line_to = float(valor_to.replace('$', '').replace('.', '').replace(',', '.'))
                        self.sixth_line_factor = float(factor.replace(',', '.'))
                        self.sixth_line_tasa_rebaja = float(rebaja.replace('$', '').replace('.', '').replace(',', '.'))

                        _logger.info(f"Tramo 6: {self.sixth_line_from} → {self.sixth_line_to}, factor={self.sixth_line_factor}, rebaja={self.sixth_line_tasa_rebaja}")
                        lineas_procesadas += 1

                    # Séptima fila: sexto tramo real
                    elif lineas_procesadas == 6 and len(celdas) >= 6:
                        valor_from = celdas[1].get_text().strip()
                        valor_to = celdas[2].get_text().strip()
                        factor = celdas[3].get_text().strip()
                        rebaja = celdas[4].get_text().strip()

                        self.seventh_line_from = float(valor_from.replace('$', '').replace('.', '').replace(',', '.'))
                        self.seventh_line_to = self.parse_currency(valor_to)
                        self.seventh_line_factor = float(factor.replace(',', '.'))
                        self.seventh_line_tasa_rebaja = float(rebaja.replace('$', '').replace('.', '').replace(',', '.'))

                        _logger.info(f"Tramo 7: {self.seventh_line_from} → {self.seventh_line_to}, factor={self.seventh_line_factor}, rebaja={self.seventh_line_tasa_rebaja}")
                        lineas_procesadas += 1

                    # Octava fila: tramo final (sin límite superior)
                    elif lineas_procesadas == 7 and len(celdas) >= 5:
                        valor_from = celdas[1].get_text().strip()
                        factor = celdas[3].get_text().strip()
                        rebaja = celdas[4].get_text().strip()

                        self.eighth_line_from = float(valor_from.replace('$', '').replace('.', '').replace(',', '.'))
                        self.eighth_line_factor = float(factor.replace(',', '.'))
                        self.eighth_line_tasa_rebaja = float(rebaja.replace('$', '').replace('.', '').replace(',', '.'))

                        _logger.info(f"Tramo 8: {self.eighth_line_from} → sin límite, factor={self.eighth_line_factor}, rebaja={self.eighth_line_tasa_rebaja}")
                        lineas_procesadas += 1
                        
        except Exception as e:
            _logger.error(f"Error durante el scraping: {e}")
            raise e

    def cron_scraping_impuesto_2da_categoria(self):
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
                _logger.info(f"Actualizando registro existente de Impuesto 2da Categoria para {current_month.strftime('%B %Y')}")
                existing_record.action_scraping_impuesto_2da_categoria()
                return existing_record
            else:
                # Crear nuevo registro para este mes
                _logger.info(f"Creando nuevo registro de Impuesto 2da Categoria para {current_month.strftime('%B %Y')}")
                new_record = self.create({
                    'name': f"Indicadores Impuesto 2da Categoria {current_month.strftime('%B %Y')}",
                    'date': today
                })
                new_record.cron_scraping_impuesto_2da_categoria()
                return new_record
                
        except Exception as e:
            _logger.error(f"Error en cron mensual de scraping Impuesto 2da Categoria: {str(e)}")
            # Crear registro de error
            self.create({
                'name': f"ERROR: Scraping Impuesto 2da Categoria {fields.Date.today().strftime('%B %Y')}",
                'date': fields.Date.today()
            })
            raise