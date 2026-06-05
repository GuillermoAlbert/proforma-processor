"""
Genera dos PDFs de prueba directamente desde la plantilla, sin BD.
Uso:  python test_pdf_gen.py
Salida: /tmp/test_proforma_corta.pdf  y  /tmp/test_proforma_larga.pdf
"""
import os
import jinja2
import weasyprint

TEMPLATE_DIR = os.environ.get('TEMPLATE_DIR', '/mnt/empresa/proforma-admin/DOCS_ETL_PROFORMAS')
OUT_DIR = '/tmp'

EMPRESA = {
    'nombre': 'Guías de Alicante',
    'nif': 'XXXXXXXXX',
    'direccion': 'Calle Ejemplo 1',
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

CLIENTE = {
    'nombre_agencia': 'Agencia de Viajes Test S.L.',
    'nif_cif': 'B12345678',
    'direccion': 'Calle Mayor 42',
    'cp': '28001',
    'poblacion': 'Madrid',
    'provincia': 'Madrid',
    'email': 'test@agencia.es',
    'telefono': '+34 910 000 000',
}

def lineas(n):
    return [
        {
            'descripcion': f'Servicio de guía turístico — jornada {i+1} (ciudad histórica)',
            'cantidad': 1,
            'precio': 150.00 + i * 10,
            'porcentaje_iva': 21,
            'importe': (150.00 + i * 10) * 1.21,
        }
        for i in range(n)
    ]

def proforma_data(numero, n_lineas, comentarios=''):
    ls = lineas(n_lineas)
    base = sum(l['cantidad'] * l['precio'] for l in ls)
    iva_total = sum(l['cantidad'] * l['precio'] * l['porcentaje_iva'] / 100 for l in ls)
    suplidos = 0.0
    return {
        'numero_proforma': numero,
        'fecha': '2026-06-05',
        'estado': 'borrador',
        'base': base,
        'iva_total': iva_total,
        'suplidos': suplidos,
        'total': base + iva_total,
        'total_suplidos': base + iva_total + suplidos,
        'comentarios': comentarios,
        'lineas': ls,
    }

def generar(numero, n_lineas, comentarios=''):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
        autoescape=jinja2.select_autoescape(['html'])
    )
    template = env.get_template('plantilla-proforma.html')
    html = template.render(
        proforma=proforma_data(numero, n_lineas, comentarios),
        cliente=CLIENTE,
        empresa=EMPRESA,
    )
    out = os.path.join(OUT_DIR, f'{numero}.pdf')
    weasyprint.HTML(string=html, base_url=TEMPLATE_DIR).write_pdf(out)
    print(f'Generado: {out}')

if __name__ == '__main__':
    generar('TEST-CORTA-5lin',  5)
    generar('TEST-LARGA-12lin', 12)
    generar('TEST-COMENTARIO',  6, 'Este es un comentario de prueba con varias líneas de texto para ver cómo se adapta el bloque de descripción del servicio en el documento final.')
    print('Listo. Abre los PDFs en /tmp/ para verificar.')
