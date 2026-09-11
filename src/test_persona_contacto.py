"""
Tests de la persona de contacto del cliente (`clientes.persona_contacto`):
alta, edición, migración sobre una BD antigua y aparición en la ficha del
cliente del detalle de la proforma.

Uso (dentro de CT 104, con BD de prueba en /tmp):
    cd /mnt/empresa/proforma-admin/src && python3 -m pytest test_persona_contacto.py -v
"""
import base64
import os
import sqlite3
import sys

# Aislar de producción ANTES de importar db/app (leen el env al importar).
TEST_DB = '/tmp/test_persona_contacto.db'
os.environ['DB_PATH'] = TEST_DB
os.environ['PDF_DIR'] = '/tmp/test_persona_contacto_pdf'
os.environ['EXCEL_PATH'] = '/tmp/test_persona_contacto.xlsx'
os.environ['EXCEL_BACKUP_DIR'] = '/tmp/test_persona_contacto_bak'
os.environ['EXCEL_PENDING_FILE'] = '/tmp/test_persona_contacto_pendientes.json'
os.environ['EXCEL_LOCK_FILE'] = '/tmp/test_persona_contacto.lock'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import db  # noqa: E402

AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'admin:admin').decode()}


def _borrar_bd():
    for sufijo in ('', '-wal', '-shm'):
        try:
            os.remove(TEST_DB + sufijo)
        except FileNotFoundError:
            pass


@pytest.fixture(autouse=True)
def bd_limpia():
    db.DB_PATH = TEST_DB  # el módulo db se importa una vez por proceso
    _borrar_bd()
    db.init_db()
    db.set_serie_config('PRO', '{serie}-{anio}-{n}', 4)
    with db.get_db() as conn:
        conn.execute("INSERT INTO cuentas (id, nombre, predeterminada) VALUES (1, 'Principal', 1)")
    yield


@pytest.fixture()
def client():
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _cliente(nombre='Traditional Tours SLU'):
    with db.get_db() as conn:
        return conn.execute(
            "SELECT * FROM clientes WHERE nombre_agencia = ?", (nombre,)
        ).fetchone()


# ── Alta y edición ───────────────────────────────────────────────────

def test_el_alta_guarda_la_persona_de_contacto(client):
    r = client.post('/clientes/nuevo', headers=AUTH, data={
        'nombre_agencia': 'Traditional Tours SLU',
        'email': 'reservas@traditionaltours.es',
        'persona_contacto': 'Marta Ferrándiz',
        'telefono': '965000000',
    })
    assert r.status_code == 302, r.data
    cli = _cliente()
    assert cli['persona_contacto'] == 'Marta Ferrándiz'
    assert cli['email'] == 'reservas@traditionaltours.es'   # el resto sigue en su sitio
    assert cli['telefono'] == '965000000'


def test_la_edicion_actualiza_la_persona_de_contacto(client):
    client.post('/clientes/nuevo', headers=AUTH, data={
        'nombre_agencia': 'Traditional Tours SLU',
        'email': 'reservas@traditionaltours.es',
        'persona_contacto': 'Marta Ferrándiz',
    })
    cid = _cliente()['id']
    r = client.post(f'/clientes/{cid}/editar', headers=AUTH, data={
        'nombre_agencia': 'Traditional Tours SLU',
        'email': 'reservas@traditionaltours.es',
        'persona_contacto': 'Luis Beltrán',
        'telefono': '965111111',
    })
    assert r.status_code == 302, r.data
    cli = _cliente()
    assert cli['persona_contacto'] == 'Luis Beltrán'
    assert cli['telefono'] == '965111111'


def test_el_formulario_de_edicion_muestra_lo_guardado(client):
    client.post('/clientes/nuevo', headers=AUTH, data={
        'nombre_agencia': 'Traditional Tours SLU',
        'persona_contacto': 'Marta Ferrándiz',
    })
    cid = _cliente()['id']
    html = client.get(f'/clientes/{cid}/editar', headers=AUTH).get_data(as_text=True)
    assert 'name="persona_contacto"' in html
    assert 'Marta Ferrándiz' in html


def test_un_cliente_sin_persona_de_contacto_se_guarda_igual(client):
    r = client.post('/clientes/nuevo', headers=AUTH,
                    data={'nombre_agencia': 'Benidorm DMC Events SL'})
    assert r.status_code == 302, r.data
    assert _cliente('Benidorm DMC Events SL')['persona_contacto'] == ''


# ── Migración ────────────────────────────────────────────────────────

def test_la_migracion_anade_la_columna_a_una_bd_antigua():
    """BD con el schema de antes: la columna aparece y los datos se conservan."""
    _borrar_bd()
    conn = sqlite3.connect(TEST_DB)
    conn.execute("""CREATE TABLE clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_agencia TEXT NOT NULL,
        nif_cif TEXT, direccion TEXT, cp TEXT, poblacion TEXT, provincia TEXT,
        email TEXT, telefono TEXT, codigo_factusol TEXT)""")
    conn.execute("INSERT INTO clientes (nombre_agencia, email) VALUES ('Vieja SL', 'a@b.es')")
    conn.commit()
    conn.close()

    db.init_db()
    db.init_db()   # idempotente: correrla dos veces no rompe nada

    with db.get_db() as c:
        cols = [row[1] for row in c.execute("PRAGMA table_info(clientes)").fetchall()]
        assert 'persona_contacto' in cols
        fila = c.execute("SELECT * FROM clientes WHERE nombre_agencia='Vieja SL'").fetchone()
        assert fila['email'] == 'a@b.es'
        assert fila['persona_contacto'] is None


# ── Ficha del cliente en el detalle de la proforma ───────────────────

def test_el_detalle_de_la_proforma_muestra_la_persona_de_contacto(client):
    client.post('/clientes/nuevo', headers=AUTH, data={
        'nombre_agencia': 'Traditional Tours SLU',
        'email': 'reservas@traditionaltours.es',
        'persona_contacto': 'Marta Ferrándiz',
    })
    cid = _cliente()['id']
    r = client.post('/proformas/nueva', headers=AUTH, data={
        'fecha': '2026-09-11', 'cliente_id': str(cid), 'cuenta_id': '1',
        'numero_proforma': '', 'comentarios': '', 'referencia': '',
        'linea_descripcion[]': 'Visita guiada', 'linea_cantidad[]': '1',
        'linea_precio[]': '100', 'linea_iva[]': '21', 'linea_fecha[]': '',
        'linea_articulo_id[]': '',
    })
    assert r.status_code == 302, r.data
    with db.get_db() as conn:
        pid = conn.execute("SELECT id FROM proformas ORDER BY id DESC LIMIT 1").fetchone()['id']
    html = client.get(f'/proformas/{pid}', headers=AUTH).get_data(as_text=True)
    assert 'Marta Ferrándiz' in html


def test_los_campos_vacios_no_se_pintan_como_None(client):
    """Un cliente con columnas NULL (alta por `/api/clientes`, o la columna
    recién migrada) no debe mostrar el texto «None» en el formulario: si se
    guardaba así, el literal quedaba escrito en la BD."""
    client.post('/api/clientes', headers=AUTH, data={'nombre_agencia': 'Benidorm DMC Events SL'})
    cid = _cliente('Benidorm DMC Events SL')['id']
    with db.get_db() as conn:
        assert conn.execute(
            "SELECT direccion FROM clientes WHERE id = ?", (cid,)
        ).fetchone()['direccion'] is None          # la BD sí tiene NULLs
    html = client.get(f'/clientes/{cid}/editar', headers=AUTH).get_data(as_text=True)
    assert 'value="None"' not in html
