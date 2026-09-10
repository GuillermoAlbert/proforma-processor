import json
import os
import jinja2
import weasyprint
from db import get_db, get_empresa_config, get_serie_config

TEMPLATE_DIR = os.environ.get('TEMPLATE_DIR', '/mnt/empresa/proforma-admin/DOCS_ETL_PROFORMAS')
PDF_DIR = os.environ.get('PDF_DIR', '/mnt/empresa/proformas-pdf')


def _numero_corto(proforma):
    """Forma corta del número para el PDF: PREFIJO-AA-NNNN.

    Usa el contador secuencial y el año de la fecha de la proforma, ignorando
    la parte descriptiva (agencia/mes) del numero_proforma. Si falta el
    secuencial, intenta deducirlo de los tres primeros segmentos del número
    largo; si no, devuelve el número largo tal cual."""
    cfg = get_serie_config()
    n = proforma.get('numero_secuencial')
    fecha = proforma.get('fecha') or ''
    aa = ''
    try:
        aa = fecha.split('-')[0][-2:]
    except (AttributeError, IndexError):
        aa = ''
    if n is not None and aa:
        return f"{cfg['prefijo']}-{aa}-{str(n).zfill(cfg['digitos'])}"
    # Fallback: primeros tres segmentos del número largo (PREFIJO-AA-NNNN)
    partes = (proforma.get('numero_proforma') or '').split('-')
    if len(partes) >= 3:
        return '-'.join(partes[:3])
    return proforma.get('numero_proforma') or ''


# ── Ajuste automático a una hoja ──────────────────────────────────────────────
# Una proforma con varias líneas, suplidos y comentarios se desbordaba a una
# segunda página con el bloque de datos de pago solo (medido en la 26-054:
# faltaban ~90 px de 1069,6 px útiles). En vez de apretar la plantilla para
# todas, se renderiza normal y SOLO si sale a más de una página se reintenta
# con peldaños de compactación progresiva. El 90 % de las proformas (1 línea,
# 3 líneas sin suplidos) no se toca en absoluto.
#
# La tabla es de espaciado vertical: (selector, propiedad, base, mínimo, unidad).
# Nunca cambia contenido, anchos ni colores.
_ESPACIADO = [
    ('.page', 'padding-top', 11, 6, 'mm'),
    ('.page', 'padding-bottom', 6, 0, 'mm'),
    ('.doc-header', 'padding-top', 14, 9, 'px'),
    ('.doc-header', 'padding-bottom', 14, 9, 'px'),
    ('.doc-header', 'margin-bottom', 10, 5, 'px'),
    # las dos columnas de facturación se compactan a la vez para que «Emisor» y
    # «Facturar a» sigan alineados
    ('.billing-client-box', 'padding-top', 14, 9, 'px'),
    ('.billing-client-box', 'padding-bottom', 14, 9, 'px'),
    ('.billing-wrap > .billing-col:first-child', 'padding-top', 14, 9, 'px'),
    ('.billing-wrap', 'margin-bottom', 18, 8, 'px'),
    ('table.rates thead th', 'padding-top', 7, 4, 'px'),
    ('table.rates thead th', 'padding-bottom', 7, 4, 'px'),
    ('table.rates tbody td', 'padding-top', 6, 3, 'px'),
    ('table.rates tbody td', 'padding-bottom', 6, 3, 'px'),
    ('.totals-area', 'margin-top', 10, 4, 'px'),
    ('.totals-area', 'margin-bottom', 16, 6, 'px'),
    ('.totals-box table td', 'padding-top', 6, 3, 'px'),
    ('.totals-box table td', 'padding-bottom', 6, 3, 'px'),
    ('.totals-box .row-total td', 'padding-top', 11, 6, 'px'),
    ('.totals-box .row-total td', 'padding-bottom', 11, 6, 'px'),
    ('.highlight', 'padding-top', 10, 5, 'px'),
    ('.highlight', 'padding-bottom', 10, 5, 'px'),
    ('.highlight', 'margin-bottom', 20, 8, 'px'),
    ('.payment-box', 'padding-top', 13, 8, 'px'),
    ('.payment-box', 'padding-bottom', 13, 8, 'px'),
    ('.payment-box', 'margin-bottom', 12, 5, 'px'),
    ('.legal', 'padding-top', 7, 3, 'px'),
    ('.legal', 'padding-bottom', 7, 3, 'px'),
]

# Último recurso del peldaño 3: bajar la tipografía un pelo (pt base de cada regla).
_TIPOGRAFIA = {
    'body': 11, 'table.rates': 9.5, '.billing-col': 9.5, '.hl-content': 10.5,
    '.totals-box table td': 10, '.pago-value': 10.5, '.party-name': 12.5,
}

# (factor de espaciado, factor de tipografía). 1.0 = como está la plantilla.
# Medido: peldaño 1 arregla la 26-054; el 2, hasta 4 líneas; el 3, hasta 5.
_PELDANOS = ((0.30, 1.0), (0.0, 1.0), (0.0, 0.94))

_hojas_cache = {}


def _hoja_compacta(factor, factor_tipo):
    """CSS de un peldaño de compactación, como weasyprint.CSS ya parseado."""
    if (factor, factor_tipo) in _hojas_cache:
        return _hojas_cache[(factor, factor_tipo)]
    # !important obligatorio: WeasyPrint mete las hojas de stylesheets= ANTES
    # del <style> del documento, así que a igualdad de especificidad perdería
    # siempre la cascada y la compactación no haría nada (comprobado en v69).
    reglas = [
        f"{sel}{{{prop}:{minimo + (base - minimo) * factor:.2f}{unidad} !important}}"
        for sel, prop, base, minimo, unidad in _ESPACIADO
    ]
    if factor_tipo < 1.0:
        reglas += [f"{sel}{{font-size:{pt * factor_tipo:.2f}pt !important}}"
                   for sel, pt in _TIPOGRAFIA.items()]
    hoja = weasyprint.CSS(string=''.join(reglas))
    _hojas_cache[(factor, factor_tipo)] = hoja
    return hoja


def _render_ajustado(html_rendered):
    """Renderiza el HTML y, si ocupa más de una página, reintenta compactando.

    Devuelve el Document con menos páginas. Si ningún peldaño baja a una sola
    página, se queda con el render base (aireado): compactar sin conseguir
    ahorrar una hoja solo empeora el documento.
    """
    documento = weasyprint.HTML(string=html_rendered, base_url=TEMPLATE_DIR)
    base = documento.render()
    if len(base.pages) <= 1:
        return base
    for factor, factor_tipo in _PELDANOS:
        intento = documento.render(stylesheets=[_hoja_compacta(factor, factor_tipo)])
        if len(intento.pages) <= 1:
            return intento
    return base


def _cargar_datos(proforma_id):
    """Lee de la BD todo lo que necesita la plantilla. Devuelve
    (proforma_dict, cliente_dict, empresa)."""
    with get_db() as conn:
        proforma = conn.execute(
            "SELECT * FROM proformas WHERE id = ?", (proforma_id,)
        ).fetchone()
        if proforma is None:
            raise ValueError(f"Proforma {proforma_id} no encontrada")

        cliente = conn.execute(
            "SELECT * FROM clientes WHERE id = ?", (proforma['cliente_id'],)
        ).fetchone()

        cuenta = None
        if proforma['cuenta_id']:
            cuenta = conn.execute(
                "SELECT * FROM cuentas WHERE id = ?", (proforma['cuenta_id'],)
            ).fetchone()

        lineas = conn.execute(
            "SELECT * FROM proforma_lineas WHERE proforma_id = ? ORDER BY id",
            (proforma_id,)
        ).fetchall()

    proforma_dict = dict(proforma)
    proforma_dict['lineas'] = [dict(l) for l in lineas]

    # Número corto para el PDF (cabecera y pie): solo PREFIJO-AA-NNNN, sin la
    # parte descriptiva (agencia/mes) que sí lleva numero_proforma en la UI/Excel.
    proforma_dict['numero_corto'] = _numero_corto(proforma_dict)

    raw = proforma_dict.get('suplidos_detalle')
    if raw:
        try:
            proforma_dict['suplidos_items'] = json.loads(raw)
        except (ValueError, TypeError):
            proforma_dict['suplidos_items'] = []
    elif proforma_dict.get('suplidos', 0):
        proforma_dict['suplidos_items'] = [{'desc': '', 'importe': proforma_dict['suplidos']}]
    else:
        proforma_dict['suplidos_items'] = []
    cliente_dict = dict(cliente) if cliente else {}

    # La cuenta seleccionada (si la hay) define el IBAN/entidad/titular del bloque
    # de pago; si no, se usan los valores de empresa (DB o defaults).
    empresa = get_empresa_config()
    if cuenta:
        if cuenta['iban']:
            empresa['iban'] = cuenta['iban']
        if cuenta['banco']:
            empresa['banco'] = cuenta['banco']
        if cuenta['bic']:
            empresa['bic'] = cuenta['bic']
        empresa['titular'] = cuenta['titular'] or ''

    return proforma_dict, cliente_dict, empresa


def generar_pdf(proforma_id):
    """PDF definitivo: sin marca de agua, escrito en PDF_DIR y cacheado en
    proformas.ruta_pdf. Devuelve la ruta."""
    os.makedirs(PDF_DIR, exist_ok=True)
    proforma_dict, cliente_dict, empresa = _cargar_datos(proforma_id)

    html_rendered = render_proforma_html(proforma_dict, cliente_dict, empresa)

    pdf_path = os.path.join(PDF_DIR, f"{proforma_dict['numero_proforma']}.pdf")
    _render_ajustado(html_rendered).write_pdf(pdf_path)

    with get_db() as conn:
        conn.execute(
            "UPDATE proformas SET ruta_pdf = ? WHERE id = ?",
            (pdf_path, proforma_id)
        )

    return pdf_path


def generar_pdf_preview(proforma_id):
    """Vista previa de un borrador: con marca de agua y EN MEMORIA.

    No escribe en disco ni toca ruta_pdf a propósito — un borrador no debe
    dejar detrás un PDF cacheado que luego se sirva como si fuera definitivo,
    y así tampoco quedan ficheros huérfanos en el NAS.

    Devuelve (bytes del PDF, nombre de fichero sugerido).
    """
    proforma_dict, cliente_dict, empresa = _cargar_datos(proforma_id)

    html_rendered = render_proforma_html(
        proforma_dict, cliente_dict, empresa, borrador_preview=True
    )

    return (_render_ajustado(html_rendered).write_pdf(),
            f"{proforma_dict['numero_proforma']}-BORRADOR.pdf")


def render_proforma_html(proforma_dict, cliente_dict, empresa, borrador_preview=False):
    """Renderiza la plantilla Jinja2 de la proforma y devuelve el HTML.

    borrador_preview=True añade la marca de agua «BORRADOR · SIN VALIDEZ».
    Depende de cómo se pida el PDF, no de proforma.estado: el estado interno
    no se imprime nunca."""
    def _fecha_es(value):
        """Convierte YYYY-MM-DD a DD/MM/YYYY para el PDF."""
        if not value:
            return ''
        try:
            y, m, d = value.split('-')
            return f"{d}/{m}/{y}"
        except (ValueError, AttributeError):
            return value or ''

    def _iban_format(value):
        """Formatea un IBAN en grupos de 4 caracteres: ES91 2100 0418 ..."""
        if not value:
            return ''
        clean = value.replace(' ', '').upper()
        return ' '.join(clean[i:i+4] for i in range(0, len(clean), 4))

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
        autoescape=jinja2.select_autoescape(['html'])
    )
    env.filters['fecha_es'] = _fecha_es
    env.filters['iban_format'] = _iban_format
    template = env.get_template('plantilla-proforma.html')
    return template.render(
        proforma=proforma_dict,
        cliente=cliente_dict,
        empresa=empresa,
        borrador_preview=borrador_preview,
    )
