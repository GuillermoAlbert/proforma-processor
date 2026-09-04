"""
Tests del modo de visualización de la dirección de la empresa en el PDF
(`empresa.direccion_modo`: completa / poblacion / oculta).

Uso (dentro de CT 104, con BD y PDFs de prueba en /tmp):
    cd /mnt/empresa/proforma-admin/src && python3 -m pytest test_direccion_modo.py -v
"""
import base64
import os
import sys

# Aislar de producción ANTES de importar db/app (leen el env al importar).
TEST_DB = '/tmp/test_direccion_modo.db'
os.environ['DB_PATH'] = TEST_DB
os.environ['PDF_DIR'] = '/tmp/test_direccion_modo_pdf'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import db  # noqa: E402
import pdf  # noqa: E402
import test_pdf_gen  # noqa: E402


@pytest.fixture(autouse=True)
def bd_limpia():
    db.DB_PATH = TEST_DB  # el módulo db se importa una vez por proceso
    for sufijo in ('', '-wal', '-shm'):
        try:
            os.remove(TEST_DB + sufijo)
        except FileNotFoundError:
            pass
    db.init_db()
    yield


def _set_config(clave, valor):
    with db.get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config (clave, valor) VALUES (?, ?)",
            (clave, valor),
        )


def _get_config(clave):
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT valor FROM config WHERE clave = ?", (clave,)
        ).fetchone()
    return row[0] if row else None


# ── Config y migración ──────────────────────────────────────────────

def test_default_es_completa():
    empresa = db.get_empresa_config()
    assert empresa['direccion_modo'] == 'completa'
    assert 'mostrar_direccion' not in empresa


def test_migracion_mostrar_direccion_0_pasa_a_oculta():
    _set_config('empresa.mostrar_direccion', '0')
    db.init_db()
    assert db.get_empresa_config()['direccion_modo'] == 'oculta'
    assert _get_config('empresa.mostrar_direccion') is None


def test_migracion_mostrar_direccion_1_pasa_a_completa():
    _set_config('empresa.mostrar_direccion', '1')
    db.init_db()
    assert db.get_empresa_config()['direccion_modo'] == 'completa'
    assert _get_config('empresa.mostrar_direccion') is None


def test_migracion_no_pisa_un_modo_ya_elegido():
    _set_config('empresa.mostrar_direccion', '0')
    _set_config('empresa.direccion_modo', 'poblacion')
    db.init_db()
    assert db.get_empresa_config()['direccion_modo'] == 'poblacion'
    assert _get_config('empresa.mostrar_direccion') is None


# ── Render de la plantilla del PDF ──────────────────────────────────

EMPRESA_TEST = {
    'nombre': 'Empresa Test S.L.',
    'nif': 'B00000000',
    'direccion': 'Calle Falsa, 123',
    'cp': '03530',
    'poblacion': 'La Nucia',
    'provincia': 'Alicante',
    'email': 'test@test.es',
    'telefono': '+34 600 000 000',
    'web': 'test.es',
    'iban': 'ES0000000000000000000000',
    'banco': 'Banco Test',
    'condiciones_pago': 'Al contado',
    'tagline': 'Tagline test',
    'aviso_legal': 'Aviso test',
}


def _render(modo):
    empresa = dict(EMPRESA_TEST, direccion_modo=modo)
    return pdf.render_proforma_html(
        test_pdf_gen.proforma_data('TEST-26-0001', 2),
        test_pdf_gen.CLIENTE,
        empresa,
    )


def test_render_completa_lleva_calle_y_poblacion():
    html = _render('completa')
    assert 'Calle Falsa, 123' in html
    assert '03530 La Nucia (Alicante)' in html


def test_render_poblacion_lleva_solo_cp_y_poblacion():
    html = _render('poblacion')
    assert 'Calle Falsa, 123' not in html
    assert '03530 La Nucia (Alicante)' in html


def test_render_oculta_no_lleva_direccion():
    html = _render('oculta')
    assert 'Calle Falsa, 123' not in html
    assert '03530 La Nucia' not in html


# ── Formulario del panel (Config → Empresa) ─────────────────────────

AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'admin:admin').decode()}


@pytest.fixture()
def client():
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _form_base(**extra):
    campos = {k: '' for k in (
        'nombre', 'nif', 'direccion', 'cp', 'poblacion', 'provincia',
        'email', 'telefono', 'web', 'condiciones_pago', 'tagline', 'aviso_legal',
    )}
    campos.update(extra)
    return campos


def test_form_guarda_el_modo(client):
    r = client.post('/config/empresa', headers=AUTH,
                    data=_form_base(direccion_modo='poblacion'))
    assert r.status_code == 302
    assert db.get_empresa_config()['direccion_modo'] == 'poblacion'


def test_form_valor_invalido_revierte_a_completa(client):
    r = client.post('/config/empresa', headers=AUTH,
                    data=_form_base(direccion_modo='loquesea'))
    assert r.status_code == 302
    assert db.get_empresa_config()['direccion_modo'] == 'completa'


def test_form_muestra_el_selector(client):
    _set_config('empresa.direccion_modo', 'poblacion')
    r = client.get('/config/empresa', headers=AUTH)
    html = r.get_data(as_text=True)
    assert 'name="direccion_modo"' in html
    assert 'value="poblacion" selected' in html
