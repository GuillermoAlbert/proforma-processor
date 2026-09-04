"""
Tests del número de proforma cuando el formato de serie depende del cliente o
de la fecha (`{agencia}`, `{mes_corto}`…).

El asistente de CT108 puede crear borradores sin cliente: el número nace con el
hueco de la agencia vacío (`PROFORMA-26-050--sep_26`) y debe rellenarse solo al
asignar el cliente en el panel, sin consumir un número nuevo.

Uso (dentro de CT 104, con BD de prueba en /tmp):
    cd /mnt/empresa/proforma-admin/src && python3 -m pytest test_numeracion_agencia.py -v
"""
import base64
import os
import sys

# Aislar de producción ANTES de importar db/app (leen el env al importar).
TEST_DB = '/tmp/test_numeracion_agencia.db'
os.environ['DB_PATH'] = TEST_DB
os.environ['PDF_DIR'] = '/tmp/test_numeracion_agencia_pdf'
os.environ['EXCEL_PATH'] = '/tmp/test_numeracion_agencia.xlsx'
os.environ['EXCEL_BACKUP_DIR'] = '/tmp/test_numeracion_agencia_bak'
os.environ['EXCEL_PENDING_FILE'] = '/tmp/test_numeracion_agencia_pendientes.json'
os.environ['EXCEL_LOCK_FILE'] = '/tmp/test_numeracion_agencia.lock'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import db  # noqa: E402

AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'admin:admin').decode()}
FORMATO_CON_AGENCIA = '{serie}-{aa}-{n}-{agencia}-{mes_corto}_{aa}'


@pytest.fixture(autouse=True)
def bd_limpia():
    db.DB_PATH = TEST_DB  # el módulo db se importa una vez por proceso
    for sufijo in ('', '-wal', '-shm'):
        try:
            os.remove(TEST_DB + sufijo)
        except FileNotFoundError:
            pass
    db.init_db()
    db.set_serie_config('PROFORMA', FORMATO_CON_AGENCIA, 3)
    with db.get_db() as conn:
        conn.execute("INSERT INTO clientes (id, nombre_agencia) VALUES (1, 'Traditional Tours SLU')")
        conn.execute("INSERT INTO clientes (id, nombre_agencia) VALUES (2, 'Benidorm DMC Events SL')")
    yield


@pytest.fixture()
def client():
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _borrador_sin_cliente(client, fecha='2026-09-10'):
    """Crea un borrador por la vía del asistente (CT108), sin cliente."""
    r = client.post('/api/proformas/borrador', headers=AUTH,
                    json={'fecha_servicio': fecha, 'concepto': 'Visita guiada', 'importe': 200})
    assert r.status_code == 201, r.data
    return r.get_json()['id']


def _proforma(pid):
    with db.get_db() as conn:
        return conn.execute("SELECT * FROM proformas WHERE id=?", (pid,)).fetchone()


def _guardar_edicion(client, pid, **extra):
    datos = {
        'fecha': '2026-09-10', 'cliente_id': '1', 'cuenta_id': '', 'comentarios': '',
        'referencia': '', 'linea_descripcion[]': 'Visita guiada', 'linea_cantidad[]': '1',
        'linea_precio[]': '200', 'linea_iva[]': '21', 'linea_fecha[]': '2026-09-10',
        'linea_articulo_id[]': '',
    }
    datos.setdefault('numero_proforma', _proforma(pid)['numero_proforma'])
    datos.update(extra)
    return client.post('/proformas/%d/editar' % pid, headers=AUTH, data=datos)


# ── Cómo nace el número ──────────────────────────────────────────────

def test_sin_cliente_el_hueco_de_agencia_queda_vacio(client):
    numero = _proforma(_borrador_sin_cliente(client))['numero_proforma']
    assert numero == 'PROFORMA-26-001--sep_26'


def test_con_cliente_el_numero_lleva_la_agencia(client):
    r = client.post('/api/proformas/borrador', headers=AUTH, json={
        'fecha_servicio': '2026-09-10', 'concepto': 'Visita guiada', 'cliente_id': 1})
    numero = _proforma(r.get_json()['id'])['numero_proforma']
    assert numero == 'PROFORMA-26-001-TRADITIONAL-TOURS-sep_26'


# ── Previsualización (/api/peek-numero) ──────────────────────────────

def test_peek_con_proforma_id_usa_su_secuencial(client):
    pid = _borrador_sin_cliente(client)
    r = client.get('/api/peek-numero?fecha=2026-09-10&cliente_id=1&proforma_id=%d' % pid,
                   headers=AUTH)
    assert r.get_json()['numero'] == 'PROFORMA-26-001-TRADITIONAL-TOURS-sep_26'


def test_peek_sin_proforma_id_devuelve_el_siguiente(client):
    _borrador_sin_cliente(client)
    r = client.get('/api/peek-numero?fecha=2026-09-10&cliente_id=1', headers=AUTH)
    assert r.get_json()['numero'] == 'PROFORMA-26-002-TRADITIONAL-TOURS-sep_26'


def test_peek_con_proforma_id_inexistente_no_revienta(client):
    r = client.get('/api/peek-numero?fecha=2026-09-10&proforma_id=999', headers=AUTH)
    assert r.status_code == 200
    assert r.get_json()['numero'] == 'PROFORMA-26-001--sep_26'


# ── Renumerado al guardar la edición ─────────────────────────────────

def test_asignar_cliente_rellena_la_agencia(client):
    pid = _borrador_sin_cliente(client)
    _guardar_edicion(client, pid, cliente_id='1')
    assert _proforma(pid)['numero_proforma'] == 'PROFORMA-26-001-TRADITIONAL-TOURS-sep_26'


def test_renumerar_no_consume_un_numero_nuevo(client):
    pid = _borrador_sin_cliente(client)
    secuencial = _proforma(pid)['numero_secuencial']
    _guardar_edicion(client, pid, cliente_id='1')
    assert _proforma(pid)['numero_secuencial'] == secuencial
    r = client.get('/api/peek-numero?fecha=2026-09-10&cliente_id=1', headers=AUTH)
    assert r.get_json()['numero'].startswith('PROFORMA-26-002-')


def test_cambiar_la_fecha_actualiza_el_mes(client):
    pid = _borrador_sin_cliente(client)
    _guardar_edicion(client, pid, cliente_id='1', fecha='2026-10-05',
                     **{'linea_fecha[]': '2026-10-05'})
    assert _proforma(pid)['numero_proforma'] == 'PROFORMA-26-001-TRADITIONAL-TOURS-oct_26'


def test_cambiar_de_cliente_cambia_la_agencia(client):
    pid = _borrador_sin_cliente(client)
    _guardar_edicion(client, pid, cliente_id='1')
    _guardar_edicion(client, pid, cliente_id='2')
    assert _proforma(pid)['numero_proforma'] == 'PROFORMA-26-001-BENIDORM-DMC-EVENTS-sep_26'


def test_numero_escrito_a_mano_se_respeta(client):
    pid = _borrador_sin_cliente(client)
    _guardar_edicion(client, pid, cliente_id='1', numero_proforma='MANUAL-0001')
    assert _proforma(pid)['numero_proforma'] == 'MANUAL-0001'


def test_una_proforma_enviada_no_se_renumera(client):
    pid = _borrador_sin_cliente(client)
    with db.get_db() as conn:
        conn.execute("UPDATE proformas SET estado='enviada' WHERE id=?", (pid,))
    _guardar_edicion(client, pid, cliente_id='1')
    assert _proforma(pid)['numero_proforma'] == 'PROFORMA-26-001--sep_26'


def test_si_el_numero_reconstruido_ya_existe_se_conserva_el_actual(client):
    pid = _borrador_sin_cliente(client)
    with db.get_db() as conn:
        conn.execute(
            """INSERT INTO proformas (numero_proforma, fecha, estado, numero_secuencial)
               VALUES ('PROFORMA-26-001-TRADITIONAL-TOURS-sep_26', '2026-09-10', 'enviada', 99)"""
        )
    _guardar_edicion(client, pid, cliente_id='1')
    assert _proforma(pid)['numero_proforma'] == 'PROFORMA-26-001--sep_26'


def test_formato_sin_agencia_no_cambia_el_numero(client):
    db.set_serie_config('PROFORMA', '{serie}-{anio}-{n}', 3)
    pid = _borrador_sin_cliente(client)
    numero = _proforma(pid)['numero_proforma']
    _guardar_edicion(client, pid, cliente_id='1')
    assert _proforma(pid)['numero_proforma'] == numero == 'PROFORMA-2026-001'


# ── Formulario de alta ───────────────────────────────────────────────

def test_el_numero_no_es_editable_si_la_serie_usa_la_agencia(client):
    html = client.get('/proformas/nueva', headers=AUTH).get_data(as_text=True)
    campo = html.split('id="numero_proforma"')[1].split('>')[0]
    assert 'readonly' in campo


def test_el_numero_es_editable_si_la_serie_no_usa_la_agencia(client):
    db.set_serie_config('PROFORMA', '{serie}-{anio}-{n}', 3)
    html = client.get('/proformas/nueva', headers=AUTH).get_data(as_text=True)
    campo = html.split('id="numero_proforma"')[1].split('>')[0]
    assert 'readonly' not in campo
