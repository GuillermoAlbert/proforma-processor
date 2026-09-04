"""
Tests del duplicado de proformas, de los filtros del listado y de las
comprobaciones de duplicados del catálogo (clientes y guías).

Uso (dentro de CT 104, con BD de prueba en /tmp):
    cd /mnt/empresa/proforma-admin/src && python3 -m pytest test_duplicar_y_filtros.py -v
"""
import base64
import os
import sys

# Aislar de producción ANTES de importar db/app (leen el env al importar).
TEST_DB = '/tmp/test_duplicar_y_filtros.db'
os.environ['DB_PATH'] = TEST_DB
os.environ['PDF_DIR'] = '/tmp/test_duplicar_y_filtros_pdf'
os.environ['EXCEL_PATH'] = '/tmp/test_duplicar_y_filtros.xlsx'
os.environ['EXCEL_BACKUP_DIR'] = '/tmp/test_duplicar_y_filtros_bak'
os.environ['EXCEL_PENDING_FILE'] = '/tmp/test_duplicar_y_filtros_pendientes.json'
os.environ['EXCEL_LOCK_FILE'] = '/tmp/test_duplicar_y_filtros.lock'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import db  # noqa: E402

AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'admin:admin').decode()}


@pytest.fixture(autouse=True)
def bd_limpia():
    db.DB_PATH = TEST_DB  # el módulo db se importa una vez por proceso
    for sufijo in ('', '-wal', '-shm'):
        try:
            os.remove(TEST_DB + sufijo)
        except FileNotFoundError:
            pass
    db.init_db()
    db.set_serie_config('PRO', '{serie}-{anio}-{n}', 4)
    with db.get_db() as conn:
        conn.execute("INSERT INTO clientes (id, nombre_agencia) VALUES (1, 'Traditional Tours SLU')")
        conn.execute("INSERT INTO clientes (id, nombre_agencia) VALUES (2, 'Benidorm DMC Events SL')")
        conn.execute("INSERT INTO guias (id, nombre) VALUES (1, 'Juan Pérez')")
        conn.execute("INSERT INTO cuentas (id, nombre, predeterminada) VALUES (1, 'Principal', 1)")
    yield


@pytest.fixture()
def client():
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _crear(client, cliente_id='1', **extra):
    datos = {
        'fecha': '2026-09-10', 'cliente_id': cliente_id, 'cuenta_id': '1',
        'numero_proforma': '', 'comentarios': 'Grupo de Roma', 'referencia': 'OF-9',
        'guia_ids[]': '1',
        'linea_descripcion[]': 'Visita guiada', 'linea_cantidad[]': '2',
        'linea_precio[]': '100', 'linea_iva[]': '21', 'linea_fecha[]': '2026-09-10',
        'linea_articulo_id[]': '',
        'suplido_desc[]': 'Entradas', 'suplido_cantidad[]': '2',
        'suplido_precio[]': '15', 'suplido_importe[]': '30',
    }
    datos.update(extra)
    r = client.post('/proformas/nueva', headers=AUTH, data=datos)
    assert r.status_code == 302, r.data
    return _ultima()


def _ultima():
    with db.get_db() as conn:
        return conn.execute("SELECT * FROM proformas ORDER BY id DESC LIMIT 1").fetchone()


def _lineas(pid):
    with db.get_db() as conn:
        return conn.execute(
            "SELECT * FROM proforma_lineas WHERE proforma_id=? ORDER BY id", (pid,)
        ).fetchall()


# ── Duplicar ─────────────────────────────────────────────────────────

def test_duplicar_copia_los_datos_y_deja_un_borrador(client):
    origen = _crear(client)
    r = client.post('/proformas/%d/duplicar' % origen['id'], headers=AUTH)
    assert r.status_code == 302
    copia = _ultima()
    assert copia['id'] != origen['id']
    assert copia['estado'] == 'borrador'
    assert copia['cliente_id'] == origen['cliente_id']
    assert copia['cuenta_id'] == origen['cuenta_id']
    assert copia['comentarios'] == origen['comentarios']
    assert copia['referencia'] == origen['referencia']
    assert copia['total_suplidos'] == origen['total_suplidos']


def test_duplicar_copia_lineas_guias_y_suplidos(client):
    origen = _crear(client)
    client.post('/proformas/%d/duplicar' % origen['id'], headers=AUTH)
    copia = _ultima()
    assert [l['descripcion'] for l in _lineas(copia['id'])] == ['Visita guiada']
    assert _lineas(copia['id'])[0]['importe'] == _lineas(origen['id'])[0]['importe']
    assert copia['suplidos'] == origen['suplidos']
    with db.get_db() as conn:
        guias = conn.execute(
            "SELECT guia_id FROM proforma_guias WHERE proforma_id=?", (copia['id'],)
        ).fetchall()
    assert [g['guia_id'] for g in guias] == [1]


def test_duplicar_no_arrastra_las_fechas_de_servicio(client):
    origen = _crear(client)
    client.post('/proformas/%d/duplicar' % origen['id'], headers=AUTH)
    assert _lineas(_ultima()['id'])[0]['fecha'] is None


def test_duplicar_da_un_numero_nuevo(client):
    origen = _crear(client)
    client.post('/proformas/%d/duplicar' % origen['id'], headers=AUTH)
    copia = _ultima()
    assert copia['numero_proforma'] != origen['numero_proforma']
    assert copia['numero_secuencial'] == origen['numero_secuencial'] + 1


def test_duplicar_una_proforma_inexistente_no_revienta(client):
    r = client.post('/proformas/999/duplicar', headers=AUTH)
    assert r.status_code == 302


# ── Filtros del listado ──────────────────────────────────────────────

def _numeros_listados(client, query=''):
    html = client.get('/proformas' + query, headers=AUTH).get_data(as_text=True)
    cuerpo = html.split('<tbody>')[1].split('</tbody>')[0]
    with db.get_db() as conn:
        todas = conn.execute("SELECT numero_proforma FROM proformas").fetchall()
    return [p['numero_proforma'] for p in todas if p['numero_proforma'] in cuerpo]


def test_filtro_por_estado(client):
    borrador = _crear(client)
    enviada = _crear(client, cliente_id='2')
    with db.get_db() as conn:
        conn.execute("UPDATE proformas SET estado='enviada' WHERE id=?", (enviada['id'],))
    listado = _numeros_listados(client, '?estado=borrador')
    assert borrador['numero_proforma'] in listado
    assert enviada['numero_proforma'] not in listado


def test_filtro_por_cliente(client):
    uno = _crear(client, cliente_id='1')
    dos = _crear(client, cliente_id='2')
    listado = _numeros_listados(client, '?cliente_id=2')
    assert dos['numero_proforma'] in listado
    assert uno['numero_proforma'] not in listado


def test_buscador_por_numero_y_por_agencia(client):
    uno = _crear(client, cliente_id='1')
    dos = _crear(client, cliente_id='2')
    assert _numeros_listados(client, '?q=' + uno['numero_proforma']) == [uno['numero_proforma']]
    assert _numeros_listados(client, '?q=benidorm') == [dos['numero_proforma']]


def test_los_filtros_sobreviven_al_ordenar_y_paginar(client):
    _crear(client, cliente_id='2')
    html = client.get('/proformas?cliente_id=2&estado=borrador', headers=AUTH).get_data(as_text=True)
    assert 'cliente_id=2' in html.split('<thead>')[1].split('</thead>')[0]
    assert 'estado=borrador' in html


def test_sin_resultados_avisa_de_que_hay_filtros(client):
    _crear(client)
    html = client.get('/proformas?q=zzzz', headers=AUTH).get_data(as_text=True)
    assert 'Ninguna proforma coincide' in html


# ── Duplicados en el catálogo ────────────────────────────────────────

def test_no_se_puede_repetir_una_guia_desde_el_catalogo(client):
    client.post('/guias/nuevo', headers=AUTH, data={'nombre': 'juan pérez'})
    with db.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM guias").fetchone()[0] == 1


def test_no_se_puede_repetir_un_cliente_desde_el_catalogo(client):
    r = client.post('/clientes/nuevo', headers=AUTH,
                    data={'nombre_agencia': 'traditional tours slu', 'nif_cif': 'B123'})
    assert r.status_code == 200          # devuelve el formulario, no redirige
    assert 'B123' in r.get_data(as_text=True)   # y conserva lo escrito
    with db.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == 2


def test_el_modal_tampoco_repite_clientes(client):
    r = client.post('/api/clientes', headers=AUTH, data={'nombre_agencia': 'TRADITIONAL TOURS SLU'})
    assert r.status_code == 400
    assert 'Ya existe' in r.get_json()['error']
