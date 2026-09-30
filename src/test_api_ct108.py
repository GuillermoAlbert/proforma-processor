"""
Tests del API para el orquestador CT108: POST /api/proformas/borrador ampliado,
notas internas, `activo` en artículos y guías, y los GET de catálogo.

Uso (dentro de CT 104, con BD de prueba en /tmp):
    cd /mnt/empresa/proforma-admin/src && python3 -m pytest test_api_ct108.py -v
"""
import base64
import json
import os
import sqlite3
import sys

# Aislar de producción ANTES de importar db/app (leen el env al importar).
TEST_DB = '/tmp/test_api_ct108.db'
os.environ['DB_PATH'] = TEST_DB
os.environ['PDF_DIR'] = '/tmp/test_api_ct108_pdf'
os.environ['EXCEL_PATH'] = '/tmp/test_api_ct108.xlsx'
os.environ['EXCEL_BACKUP_DIR'] = '/tmp/test_api_ct108_bak'
os.environ['EXCEL_PENDING_FILE'] = '/tmp/test_api_ct108_pendientes.json'
os.environ['EXCEL_LOCK_FILE'] = '/tmp/test_api_ct108.lock'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import db  # noqa: E402

AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'admin:admin').decode()}
URL = '/api/proformas/borrador'


def _borrar_bd():
    db.DB_PATH = TEST_DB  # el módulo db se importa una vez por proceso
    for sufijo in ('', '-wal', '-shm'):
        try:
            os.remove(TEST_DB + sufijo)
        except FileNotFoundError:
            pass


@pytest.fixture(autouse=True)
def bd_limpia():
    _borrar_bd()
    db.init_db()
    with db.get_db() as conn:
        conn.execute("INSERT INTO clientes (id, nombre_agencia) VALUES (1, 'Agencia Uno SL')")
        conn.execute("INSERT INTO articulos (id, descripcion, precio, porcentaje_iva) "
                     "VALUES (1, 'Visita activa', 100, 21)")
        conn.execute("INSERT INTO articulos (id, descripcion, precio, porcentaje_iva, activo) "
                     "VALUES (2, 'Articulo retirado usado', 50, 10, 0)")
        conn.execute("INSERT INTO articulos (id, descripcion, precio, porcentaje_iva, activo) "
                     "VALUES (3, 'Articulo retirado suelto', 60, 21, 0)")
        conn.execute("INSERT INTO guias (id, nombre) VALUES (1, 'Guia Ana')")
        conn.execute("INSERT INTO guias (id, nombre) VALUES (2, 'Guia Beto')")
        conn.execute("INSERT INTO guias (id, nombre, activo) VALUES (3, 'Guia retirado usado', 0)")
        conn.execute("INSERT INTO guias (id, nombre, activo) VALUES (4, 'Guia retirado suelto', 0)")
        conn.execute("INSERT INTO cuentas (id, nombre, iban, predeterminada) "
                     "VALUES (1, 'Zeta', 'ES1111111111111111111111', 0)")
        conn.execute("INSERT INTO cuentas (id, nombre, iban, predeterminada) "
                     "VALUES (2, 'Principal', 'ES2222222222222222222222', 1)")
        conn.execute("INSERT INTO cuentas (id, nombre, iban, predeterminada) "
                     "VALUES (3, 'Alfa', 'ES3333333333333333333333', 0)")
    yield


@pytest.fixture()
def client():
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _post(client, **kw):
    cuerpo = {'fecha_servicio': '2026-09-10', 'concepto': 'Visita guiada', 'importe': 200}
    cuerpo.update(kw)
    return client.post(URL, headers=AUTH, json=cuerpo)


def _proforma(pid):
    with db.get_db() as conn:
        return conn.execute("SELECT * FROM proformas WHERE id=?", (pid,)).fetchone()


def _lineas(pid):
    with db.get_db() as conn:
        return conn.execute(
            "SELECT * FROM proforma_lineas WHERE proforma_id=? ORDER BY id", (pid,)).fetchall()


def _contar():
    with db.get_db() as conn:
        return tuple(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                     for t in ('proformas', 'proforma_lineas', 'proforma_guias', 'clientes'))


# ── Migración ────────────────────────────────────────────────────────

def test_migracion_idempotente_sobre_schema_antiguo():
    _borrar_bd()
    conn = sqlite3.connect(TEST_DB)
    conn.executescript(db.SCHEMA)        # schema antiguo: sin las columnas nuevas
    conn.execute("INSERT INTO articulos (descripcion) VALUES ('Viejo')")
    conn.execute("INSERT INTO guias (nombre) VALUES ('Viejo')")
    conn.commit()
    cols = lambda t: [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]  # noqa: E731
    assert 'notas_internas' not in cols('proformas')
    assert 'activo' not in cols('articulos')
    conn.close()

    db.init_db()
    db.init_db()                         # segunda vez: no debe fallar
    conn = sqlite3.connect(TEST_DB)
    assert {'notas_internas', 'origen_ref'} <= set(cols('proformas'))
    assert 'activo' in cols('articulos') and 'activo' in cols('guias')
    assert conn.execute("SELECT activo FROM articulos").fetchone()[0] == 1
    assert conn.execute("SELECT activo FROM guias").fetchone()[0] == 1
    conn.close()


# ── Payload antiguo y notas internas ─────────────────────────────────

def test_payload_antiguo_da_lo_mismo_que_siempre(client):
    r = _post(client, cliente_id=1)
    assert r.status_code == 201
    j = r.get_json()
    assert set(j) == {'id', 'numero_proforma', 'url'}
    assert j['url'] == f"/proformas/{j['id']}/editar"
    p = _proforma(j['id'])
    assert p['estado'] == 'borrador'
    assert p['cliente_id'] == 1
    assert p['base'] == 200 and round(p['iva_total'], 2) == 42 and round(p['total'], 2) == 242
    assert p['suplidos'] == 0 and p['suplidos_detalle'] is None
    assert p['cuenta_id'] == 2           # la predeterminada
    assert p['ruta_pdf'] is None and p['exportada_excel'] == 0
    (l,) = _lineas(j['id'])
    assert (l['descripcion'], l['cantidad'], l['precio'], l['porcentaje_iva']) == ('Visita guiada', 1, 200, 21)
    assert round(l['importe'], 2) == 242 and l['fecha'] == '2026-09-10' and l['articulo_id'] is None


def test_notas_y_origen_ref_van_a_sus_columnas_no_a_comentarios(client):
    r = _post(client, notas='Pidió factura rápida', origen_ref='msg-123')
    p = _proforma(r.get_json()['id'])
    assert p['notas_internas'] == 'Pidió factura rápida'
    assert p['origen_ref'] == 'msg-123'
    assert not p['comentarios']
    assert 'origen CT108' not in (p['comentarios'] or '')


def test_sin_notas_quedan_nulas(client):
    p = _proforma(_post(client).get_json()['id'])
    assert p['notas_internas'] is None and p['origen_ref'] is None


def test_notas_internas_no_salen_en_el_html_del_pdf(client):
    import pdf
    pid = _post(client, cliente_id=1, notas='SECRETO-INTERNO', origen_ref='REF-OCULTA',
                comentarios='Texto visible').get_json()['id']
    proforma_d, cliente_d, empresa = pdf._cargar_datos(pid)
    html = pdf.render_proforma_html(proforma_d, cliente_d, empresa)
    assert 'Texto visible' in html
    assert 'SECRETO-INTERNO' not in html and 'REF-OCULTA' not in html


def test_editar_proforma_no_pisa_notas_internas(client):
    pid = _post(client, cliente_id=1, notas='nota', origen_ref='ref').get_json()['id']
    r = client.post(f'/proformas/{pid}/editar', headers=AUTH, data={
        'fecha': '2026-09-11', 'cliente_id': '1', 'comentarios': 'x',
        'linea_descripcion[]': ['Otra'], 'linea_cantidad[]': ['1'], 'linea_precio[]': ['10'],
        'linea_iva[]': ['21'], 'linea_articulo_id[]': [''], 'linea_fecha[]': ['']})
    assert r.status_code == 302
    p = _proforma(pid)
    assert (p['notas_internas'], p['origen_ref']) == ('nota', 'ref')


def test_duplicar_no_copia_notas_ni_origen(client):
    pid = _post(client, cliente_id=1, notas='nota', origen_ref='ref').get_json()['id']
    client.post(f'/proformas/{pid}/duplicar', headers=AUTH)
    with db.get_db() as conn:
        copia = conn.execute("SELECT * FROM proformas ORDER BY id DESC LIMIT 1").fetchone()
    assert copia['id'] != pid
    assert copia['notas_internas'] is None and copia['origen_ref'] is None


# ── Payload completo ─────────────────────────────────────────────────

def test_payload_completo(client):
    r = _post(client, cliente_id=1, referencia='REF-7', comentarios='Hola', guia_ids=[1, 2, 2],
              cuenta_id=3, concepto='ignorado', importe=9999,
              lineas=[
                  {'descripcion': 'Visita', 'articulo_id': 1, 'cantidad': 2, 'precio': 100},
                  {'descripcion': 'Entrada', 'precio': 50, 'iva': 10, 'fecha': '2026-09-12'},
              ],
              suplidos=[{'descripcion': 'Museo', 'cantidad': 3, 'precio': 4.5},
                        {'descripcion': 'Dieta', 'importe': 12}])
    assert r.status_code == 201, r.data
    pid = r.get_json()['id']
    p = _proforma(pid)
    assert p['referencia'] == 'REF-7' and p['comentarios'] == 'Hola'
    assert p['cuenta_id'] == 3
    assert p['base'] == 250
    assert round(p['iva_total'], 2) == round(42 + 5, 2)
    assert round(p['total'], 2) == 297
    assert p['suplidos'] == 25.5 and round(p['total_suplidos'], 2) == 322.5
    assert json.loads(p['suplidos_detalle']) == [
        {'desc': 'Museo', 'importe': 13.5, 'cantidad': 3.0, 'precio': 4.5},
        {'desc': 'Dieta', 'importe': 12.0},
    ]
    l1, l2 = _lineas(pid)
    assert (l1['articulo_id'], l1['cantidad'], round(l1['importe'], 2), l1['fecha']) == (1, 2, 242, '2026-09-10')
    assert (l2['articulo_id'], l2['porcentaje_iva'], round(l2['importe'], 2), l2['fecha']) == (None, 10, 55, '2026-09-12')
    with db.get_db() as conn:
        gids = [g[0] for g in conn.execute(
            "SELECT guia_id FROM proforma_guias WHERE proforma_id=? ORDER BY guia_id", (pid,))]
    assert gids == [1, 2]


def test_lineas_ignora_concepto_e_importe_y_concepto_deja_de_ser_obligatorio(client):
    r = client.post(URL, headers=AUTH, json={
        'fecha_servicio': '2026-09-10', 'lineas': [{'descripcion': 'Solo línea', 'precio': 10}]})
    assert r.status_code == 201
    (l,) = _lineas(r.get_json()['id'])
    assert l['descripcion'] == 'Solo línea'


def test_cliente_nuevo_por_nombre_se_crea_y_se_reutiliza(client):
    a = _post(client, cliente={'nombre_agencia': 'Nueva Agencia', 'email': 'a@b.c'})
    b = _post(client, cliente={'nombre_agencia': 'nueva agencia'})
    assert _proforma(a.get_json()['id'])['cliente_id'] == _proforma(b.get_json()['id'])['cliente_id']
    with db.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == 2


# ── Validación: todo 400 y sin efectos ───────────────────────────────

CASOS_400 = [
    ('cliente_inexistente', {'cliente_id': 99}, 'No existe el cliente 99.'),
    ('articulo', {'lineas': [{'descripcion': 'x', 'precio': 1, 'articulo_id': 5}]}, 'No existe el artículo 5.'),
    ('guia_una', {'guia_ids': [9]}, 'No existe el guía 9.'),
    ('guias_varias', {'guia_ids': [1, 9, 11]}, 'No existen los guías 9, 11.'),
    ('cuenta', {'cuenta_id': 77}, 'No existe la cuenta 77.'),
    ('importe_texto', {'importe': 'mucho'}, 'importe debe ser numérico.'),
    ('precio_texto', {'lineas': [{'descripcion': 'x', 'precio': 'abc'}]}, 'precio'),
    ('cantidad_texto', {'lineas': [{'descripcion': 'x', 'precio': 1, 'cantidad': 'dos'}]}, 'cantidad'),
    ('iva_texto', {'lineas': [{'descripcion': 'x', 'precio': 1, 'iva': 'x'}]}, 'iva'),
    ('suplido_texto', {'suplidos': [{'descripcion': 'x', 'importe': 'x'}]}, 'suplido'),
    ('guia_id_texto', {'guia_ids': ['a']}, 'guia_ids'),
    ('cuenta_texto', {'cuenta_id': 'a'}, 'cuenta_id'),
    ('lineas_no_lista', {'lineas': 'x'}, 'lineas debe ser una lista.'),
    ('suplidos_no_lista', {'suplidos': {'a': 1}}, 'suplidos debe ser una lista.'),
    ('guia_ids_no_lista', {'guia_ids': 3}, 'guia_ids debe ser una lista.'),
    ('linea_sin_descripcion', {'lineas': [{'descripcion': '  ', 'precio': 1}]}, 'La línea 1 no tiene descripción.'),
    ('linea_sin_precio', {'lineas': [{'descripcion': 'x'}]}, 'La línea 1 no tiene precio.'),
    ('linea_no_objeto', {'lineas': ['x']}, 'La línea 1 debe ser un objeto.'),
    ('fecha_linea_mala', {'lineas': [{'descripcion': 'x', 'precio': 1, 'fecha': 'ayer'}]}, 'fecha'),
]


@pytest.mark.parametrize('nombre,extra,fragmento', CASOS_400, ids=[c[0] for c in CASOS_400])
def test_errores_son_400_y_no_crean_nada(client, nombre, extra, fragmento):
    antes = _contar()
    # con `cliente` nuevo para comprobar que tampoco se crea el cliente
    r = _post(client, cliente={'nombre_agencia': 'No Debe Crearse'}, **extra)
    assert r.status_code == 400, r.data
    assert fragmento in r.get_json()['error']
    assert _contar() == antes


def test_sin_fecha_o_concepto_y_cuerpo_no_objeto(client):
    assert client.post(URL, headers=AUTH, json={'concepto': 'x'}).status_code == 400
    assert client.post(URL, headers=AUTH, json={'fecha_servicio': '2026-09-10'}).status_code == 400
    assert client.post(URL, headers=AUTH, json=[1]).status_code == 400
    assert client.post(URL, headers=AUTH, json={'fecha_servicio': 'mañana', 'concepto': 'x'}).status_code == 400


def test_sin_auth_es_401(client):
    assert client.post(URL, json={}).status_code == 401
    assert client.get('/api/cuentas').status_code == 401


# ── GET de catálogo ──────────────────────────────────────────────────

def test_get_articulos(client):
    r = client.get('/api/articulos', headers=AUTH)
    assert r.status_code == 200
    datos = r.get_json()
    assert [a['descripcion'] for a in datos] == sorted(a['descripcion'] for a in datos)
    assert set(datos[0]) == {'id', 'descripcion', 'precio', 'porcentaje_iva', 'activo'}
    por_id = {a['id']: a for a in datos}
    assert por_id[1]['activo'] is True and por_id[2]['activo'] is False


def test_get_guias_sin_dni(client):
    datos = client.get('/api/guias', headers=AUTH).get_json()
    assert [g['nombre'] for g in datos] == sorted(g['nombre'] for g in datos)
    assert all(set(g) == {'id', 'nombre', 'activo'} for g in datos)
    assert {g['id']: g['activo'] for g in datos} == {1: True, 2: True, 3: False, 4: False}


def test_get_cuentas_sin_iban_y_predeterminada_primero(client):
    r = client.get('/api/cuentas', headers=AUTH)
    datos = r.get_json()
    assert [c['nombre'] for c in datos] == ['Principal', 'Alfa', 'Zeta']
    assert all(set(c) == {'id', 'nombre', 'predeterminada'} for c in datos)
    assert [c['predeterminada'] for c in datos] == [True, False, False]
    assert 'ES1111' not in r.get_data(as_text=True)


def test_get_proformas_sin_y_con_lineas(client):
    a = _post(client, cliente_id=1, guia_ids=[2, 1],
              lineas=[{'descripcion': 'L1', 'precio': 10}, {'descripcion': 'L2', 'precio': 20, 'iva': 10}]).get_json()['id']
    b = _post(client, cliente_id=1).get_json()['id']

    simple = client.get('/api/proformas', headers=AUTH).get_json()
    assert all('lineas' not in f and 'guia_ids' not in f for f in simple)

    filas = {f['id']: f for f in client.get('/api/proformas?con_lineas=1', headers=AUTH).get_json()}
    assert set(filas) == {a, b}
    assert filas[a]['guia_ids'] == [1, 2]
    assert [l['descripcion'] for l in filas[a]['lineas']] == ['L1', 'L2']
    assert set(filas[a]['lineas'][0]) == {'fecha', 'articulo_id', 'descripcion', 'cantidad',
                                          'precio', 'porcentaje_iva', 'importe'}
    assert filas[b]['guia_ids'] == [] and len(filas[b]['lineas']) == 1
    # las columnas de hoy siguen presentes
    assert filas[a]['nombre_agencia'] == 'Agencia Uno SL'


def test_get_proformas_con_lineas_sin_filas(client):
    assert client.get('/api/proformas?con_lineas=1', headers=AUTH).get_json() == []


def test_post_articulos_y_guias_siguen_funcionando(client):
    r = client.post('/api/articulos', headers=AUTH, data={'descripcion': 'Nuevo art', 'precio': '5'})
    assert r.status_code == 200 and r.get_json()['descripcion'] == 'Nuevo art'
    r = client.post('/api/guias', headers=AUTH, data={'nombre': 'Guia Nueva'})
    assert r.status_code == 200 and r.get_json()['nombre'] == 'Guia Nueva'
    assert any(a['descripcion'] == 'Nuevo art' and a['activo'] is True
               for a in client.get('/api/articulos', headers=AUTH).get_json())
    assert any(g['nombre'] == 'Guia Nueva' and g['activo'] is True
               for g in client.get('/api/guias', headers=AUTH).get_json())


# ── Desplegables con `activo` ────────────────────────────────────────

def test_editar_incluye_inactivos_usados_y_excluye_el_resto(client):
    pid = _post(client, cliente_id=1, guia_ids=[3],
                lineas=[{'descripcion': 'Con retirado', 'precio': 10, 'articulo_id': 2}]).get_json()['id']
    html = client.get(f'/proformas/{pid}/editar', headers=AUTH).get_data(as_text=True)
    assert 'Articulo retirado usado' in html and 'Guia retirado usado' in html
    assert 'Visita activa' in html and 'Guia Ana' in html
    assert 'Articulo retirado suelto' not in html and 'Guia retirado suelto' not in html


def test_nueva_solo_muestra_activos(client):
    html = client.get('/proformas/nueva', headers=AUTH).get_data(as_text=True)
    assert 'Visita activa' in html and 'Guia Ana' in html
    assert 'retirado' not in html
