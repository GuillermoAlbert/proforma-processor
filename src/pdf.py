import os
import jinja2
import weasyprint
from db import get_db

TEMPLATE_DIR = os.environ.get('TEMPLATE_DIR', '/mnt/empresa/proforma-admin/DOCS_ETL_PROFORMAS')
PDF_DIR = os.environ.get('PDF_DIR', '/mnt/empresa/proformas-pdf')

EMPRESA = {
    'nombre': 'Guías de Alicante',
    'nif': 'XXXXXXXXX',
    'direccion': 'Alicante',
    'cp': '03001',
    'poblacion': 'Alicante',
    'provincia': 'Alicante',
    'email': 'info@guiasdealicante.es',
    'telefono': '+34 661 639 964',
    'web': 'guiasdealicante.es',
    'iban': 'ES00 0000 0000 0000 0000 0000',
    'banco': 'Entidad bancaria',
    'condiciones_pago': '30 días desde fecha de factura',
}


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
    cliente_dict = dict(cliente) if cliente else {}

    # La cuenta seleccionada (si la hay) define el IBAN/entidad/titular del bloque
    # de pago; si no, se usan los valores por defecto de EMPRESA.
    empresa = dict(EMPRESA)
    if cuenta:
        if cuenta['iban']:
            empresa['iban'] = cuenta['iban']
        if cuenta['banco']:
            empresa['banco'] = cuenta['banco']
        empresa['titular'] = cuenta['titular'] or ''

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
        autoescape=jinja2.select_autoescape(['html'])
    )
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
