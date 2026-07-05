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


def generar_pdf(proforma_id):
    os.makedirs(PDF_DIR, exist_ok=True)

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
        empresa['titular'] = cuenta['titular'] or ''

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
    html_rendered = template.render(
        proforma=proforma_dict,
        cliente=cliente_dict,
        empresa=empresa,
    )

    pdf_path = os.path.join(PDF_DIR, f"{proforma_dict['numero_proforma']}.pdf")
    weasyprint.HTML(string=html_rendered, base_url=TEMPLATE_DIR).write_pdf(pdf_path)

    with get_db() as conn:
        conn.execute(
            "UPDATE proformas SET ruta_pdf = ? WHERE id = ?",
            (pdf_path, proforma_id)
        )

    return pdf_path
