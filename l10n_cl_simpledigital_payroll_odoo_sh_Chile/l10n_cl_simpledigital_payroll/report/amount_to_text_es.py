# -------------------------------------------------------------
# SPANISH - Amount to Text Conversion
# -------------------------------------------------------------

from odoo.tools.translate import _

units_29 = (
    'CERO', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS',
    'SIETE', 'OCHO', 'NUEVE', 'DIEZ', 'ONCE', 'DOCE',
    'TRECE', 'CATORCE', 'QUINCE', 'DIECISÉIS', 'DIECISIETE', 'DIECIOCHO',
    'DIECINUEVE', 'VEINTE', 'VEINTIÚN', 'VEINTIDÓS', 'VEINTITRÉS', 'VEINTICUATRO',
    'VEINTICINCO', 'VEINTISÉIS', 'VEINTISIETE', 'VEINTIOCHO', 'VEINTINUEVE'
)

tens = (
    'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA', 'CIEN'
)

denom = (
    '', 'MIL', 'MILLÓN', 'MIL MILLONES', 'BILLÓN', 'MIL BILLONES', 'TRILLÓN', 'MIL TRILLONES',
    'CUATRILLÓN', 'MIL CUATRILLONES', 'QUINTILLÓN', 'MIL QUINTILLONES', 'SEXTILLÓN',
    'MIL SEXTILLONES', 'SEPTILLÓN', 'MIL SEPTILLONES', 'OCTILLÓN', 'MIL OCTILLONES',
    'NONILLÓN', 'MIL NONILLONES', 'DECILLÓN', 'MIL DECILLONES'
)

denom_plural = (
    '', 'MIL', 'MILLONES', 'MIL MILLONES', 'BILLONES', 'MIL BILLONES', 'TRILLONES', 'MIL TRILLONES',
    'CUATRILLONES', 'MIL CUATRILLONES', 'QUINTILLONES', 'MIL QUINTILLONES', 'SEXTILLONES',
    'MIL SEXTILLONES', 'SEPTILLONES', 'MIL SEPTILLONES', 'OCTILLONES', 'MIL OCTILLONES',
    'NONILLONES', 'MIL NONILLONES', 'DECILLONES', 'MIL DECILLONES'
)

def _convert_nn(val):
    if val < 30:
        return units_29[val]
    for (dcap, dval) in ((k, 30 + (10 * v)) for (v, k) in enumerate(tens)):
        if dval + 10 > val:
            if val % 10:
                return dcap + ' Y ' + units_29[val % 10]
            return dcap
    return ''  # por seguridad

def _convert_nnn(val):
    word = ''
    mod, quotient = val % 100, val // 100
    if quotient > 0:
        if quotient == 1:
            word = 'CIEN' if mod == 0 else 'CIENTO'
        elif quotient == 5:
            word = 'QUINIENTOS'
        elif quotient == 9:
            word = 'NOVECIENTOS'
        else:
            word = units_29[quotient] + 'CIENTOS'
        if mod > 0:
            word += ' '
    if mod > 0:
        word += _convert_nn(mod)
    return word

def spanish_number(val):
    if val < 100:
        return _convert_nn(val)
    if val < 1000:
        return _convert_nnn(val)
    
    for (didx, dval) in ((v - 1, 1000 ** v) for v in range(len(denom))):
        if dval > val:
            mod = 1000 ** didx
            l = val // mod
            r = val - (l * mod)

            if l == 1:
                ret = denom[didx] if didx == 1 else _convert_nnn(l) + ' ' + denom[didx]
            else:
                ret = _convert_nnn(l) + ' ' + denom_plural[didx]

            if r > 0:
                ret += ' ' + spanish_number(r)
            return ret
    return ''

def amount_to_text_es(number, currency='EUROS'):
    try:
        number = float(number)
    except ValueError:
        return "VALOR INVÁLIDO"

    number = '%.2f' % number
    units_name = currency.upper()
    int_part, dec_part = number.split('.')
    start_word = spanish_number(int(int_part))
    end_word = spanish_number(int(dec_part))
    cents_number = int(dec_part)
    cents_name = 'CÉNTIMOS' if cents_number != 1 else 'CÉNTIMO'

    final_result = start_word + ' ' + units_name
    if int(int_part) != 1:
        final_result += 'S'

    if cents_number > 0:
        final_result += ' CON ' + end_word + ' ' + cents_name

    return final_result

# -------------------------------------------------------------
# Generic functions
# -------------------------------------------------------------
_translate_funcs = {'es': amount_to_text_es}

def amount_to_text(nbr, lang='es', currency='euros'):
    """
    Converts a number to its textual representation.
    """
    if lang not in _translate_funcs:
        print("WARNING: no translation function found for lang: '%s'" % lang)
        lang = 'es'
    return _translate_funcs[lang](abs(float(nbr)), currency)

