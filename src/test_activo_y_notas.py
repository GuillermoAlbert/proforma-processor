"""
Tests de la interfaz de `activo` (artículos y guías) y de las notas internas del
detalle de proforma. BD aislada en /tmp.

Uso (dentro de CT 104):
    cd /mnt/empresa/proforma-admin/src && python3 -m pytest test_activo_y_notas.py -v
"""
import base64
import os
import sys

TEST_DB = '/tmp/test_activo_notas.db'
os.environ['DB_PATH'] = TEST_DB
os.environ['PDF_DIR'] = '/tmp/test_activo_notas_pdf'
os.environ['EXCEL_PATH'] = '/tmp/test_activo_notas.xlsx'
os.environ['EXCEL_BACKUP_DIR'] = '/tmp/test_activo_notas_bak'
os.environ['EXCEL_PENDING_FILE'] = '/tmp/test_activo_notas_pendientes.json'
os.environ['EXCEL_LOCK_FILE'] = '/tmp/test_activo_notas.lock'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import db  # noqa: E402

AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'admin:admin').decode()}


@pytest.fixture(autouse=True)
def bd_limpia():
    db.DB_PATH = TEST_DB
    for sufijo in ('', '-wal', '-shm'):
        try:
            os.remove(TEST_DB + sufijo)
        except FileNotFoundError:
            pass
    db.init_db()
    with db.get_db() as conn:
        conn.execute("INSERT INTO clientes (id, nombre_agencia) VALUES (1, 'Agencia Uno SL')")
    yield


@pytest.fixture()
def client():
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _proforma(client, **extra):
    cuerpo = {'fecha_servicio': '2026-09-10', 'concepto': 'Visita', 'importe': 100,
              'cliente_id': 1}
    cuerpo.update(extra)
    r = client.post('/api/proformas/borrador', headers=AUTH, json=cuerpo)
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()['id']


def _fila(tabla, id):
    with db.get_db() as conn:
        return conn.execute(f"SELECT * FROM {tabla} WHERE id=?", (id,)).fetchone()


# ── Notas internas en el detalle ─────────────────────────────────────

def test_detalle_muestra_notas_internas_y_origen(client):
    pid = _proforma(client, notas='Llamar antes\nsegunda línea <b>x</b>', origen_ref='msg-77')
    html = client.get(f'/proformas/{pid}', headers=AUTH).get_data(as_text=True)
    assert 'Notas internas' in html and 'no salen en el PDF' in html
    assert 'Llamar antes' in html and 'Origen: msg-77' in html
    assert '<b>x</b>' not in html and '&lt;b&gt;x&lt;/b&gt;' in html  # escapado


def test_detalle_solo_origen_tambien_muestra_el_bloque(client):
    pid = _proforma(client, origen_ref='solo-ref')
    html = client.get(f'/proformas/{pid}', headers=AUTH).get_data(as_text=True)
    assert 'Notas internas' in html and 'Origen: solo-ref' in html


def test_detalle_sin_notas_no_muestra_el_bloque(client):
    pid = _proforma(client)
    html = client.get(f'/proformas/{pid}', headers=AUTH).get_data(as_text=True)
    assert 'Notas internas' not in html and 'Origen:' not in html


def test_html_del_pdf_no_lleva_las_notas(client):
    import pdf
    pid = _proforma(client, notas='NOTA-SECRETA', origen_ref='REF-SECRETA')
    p, c, e = pdf._cargar_datos(pid)
    html = pdf.render_proforma_html(p, c, e)
    assert 'NOTA-SECRETA' not in html and 'REF-SECRETA' not in html
    assert 'Notas internas' not in html


# ── Artículos ────────────────────────────────────────────────────────

def _alta_articulo(client, **extra):
    datos = {'descripcion': 'Art de prueba', 'precio': '10', 'porcentaje_iva': '21'}
    datos.update(extra)
    r = client.post('/articulos/nuevo', headers=AUTH, data=datos)
    assert r.status_code == 302
    with db.get_db() as conn:
        return conn.execute("SELECT id FROM articulos ORDER BY id DESC LIMIT 1").fetchone()['id']


def test_alta_articulo_desde_formulario_queda_activo(client):
    aid = _alta_articulo(client, activo='1')  # la casilla viene marcada por defecto
    assert _fila('articulos', aid)['activo'] == 1
    html = client.get('/articulos/nuevo', headers=AUTH).get_data(as_text=True)
    assert 'name="activo"' in html and 'checked' in html


def test_editar_articulo_desmarcar_y_volver_a_marcar(client):
    aid = _alta_articulo(client, activo='1')
    base = {'descripcion': 'Art de prueba', 'precio': '10', 'porcentaje_iva': '21'}
    client.post(f'/articulos/{aid}/editar', headers=AUTH, data=base)  # sin activo
    assert _fila('articulos', aid)['activo'] == 0
    html = client.get(f'/articulos/{aid}/editar', headers=AUTH).get_data(as_text=True)
    assert 'name="activo"' in html and 'checked' not in html.split('name="activo"')[1].split('>')[0]
    client.post(f'/articulos/{aid}/editar', headers=AUTH, data={**base, 'activo': '1'})
    assert _fila('articulos', aid)['activo'] == 1


def test_listado_articulos_marca_inactivo_con_texto(client):
    a1 = _alta_articulo(client, activo='1', descripcion='Art vivo')
    a2 = _alta_articulo(client, descripcion='Art retirado')  # sin activo -> 0
    assert _fila('articulos', a1)['activo'] == 1 and _fila('articulos', a2)['activo'] == 0
    html = client.get('/articulos', headers=AUTH).get_data(as_text=True)
    assert html.count('>Inactivo<') == 1
    pos = html.index('Art retirado')
    assert html.index('>Inactivo<') > pos
    assert html.index('>Inactivo<') < html.index('</td>', pos)


# ── Guías ────────────────────────────────────────────────────────────

def _alta_guia(client, nombre, **extra):
    r = client.post('/guias/nuevo', headers=AUTH, data={'nombre': nombre, **extra})
    assert r.status_code == 302
    with db.get_db() as conn:
        return conn.execute("SELECT id FROM guias WHERE nombre=?", (nombre,)).fetchone()['id']


def test_alta_guia_desde_formulario_queda_activa(client):
    gid = _alta_guia(client, 'Guia Nueva', activo='1')
    assert _fila('guias', gid)['activo'] == 1
    html = client.get('/guias', headers=AUTH).get_data(as_text=True)
    assert 'id="activo"' in html


def test_editar_guia_desmarcar_y_volver_a_marcar(client):
    gid = _alta_guia(client, 'Guia Ana', activo='1')
    client.post(f'/guias/{gid}/editar', headers=AUTH, data={'nombre': 'Guia Ana'})
    assert _fila('guias', gid)['activo'] == 0
    client.post(f'/guias/{gid}/editar', headers=AUTH, data={'nombre': 'Guia Ana', 'activo': '1'})
    assert _fila('guias', gid)['activo'] == 1


def test_listado_guias_marca_inactiva_con_texto(client):
    _alta_guia(client, 'Guia Viva', activo='1')
    gid = _alta_guia(client, 'Guia Retirada')
    assert _fila('guias', gid)['activo'] == 0
    html = client.get('/guias', headers=AUTH).get_data(as_text=True)
    assert html.count('>Inactivo<') == 1
    assert f'id="activo-{gid}"' in html
