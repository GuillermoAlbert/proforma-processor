import os
import json
import subprocess
import threading
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify

from db import (get_db, init_db, siguiente_numero_proforma, peek_numero_proforma,
                get_serie_config, set_serie_config, set_proximo_numero,
                get_empresa_config, set_empresa_config, get_setting, set_setting,
                recalcular_contador_serie)
from admin_helpers import require_auth
from pdf import generar_pdf, PDF_DIR
import excel
from clientes_lookup import (
    buscar_cliente as _buscar_cliente_vies,
    buscar_cliente_por_nombre as _buscar_cliente_nombre,
    provincia_desde_cp,
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'proforma-admin-secret-2026')


@app.context_processor
def inject_empresa():
    return {'empresa_config': get_empresa_config()}


# ── Clientes ────────────────────────────────────────────────────────────────

@app.route('/clientes')
@require_auth
def clientes_lista():
    sort = request.args.get('sort', 'agencia')
    direction = request.args.get('dir', 'asc')
    try:
        page = max(1, int(request.args.get('page', 1) or 1))
    except ValueError:
        page = 1
    per_page = 30

    sort_map = {'agencia': 'nombre_agencia', 'poblacion': 'poblacion'}
    sort_col = sort_map.get(sort, 'nombre_agencia')
    sort_dir = 'ASC' if direction == 'asc' else 'DESC'

    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        clientes = conn.execute(
            f"SELECT * FROM clientes ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page)
        ).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        'clientes/lista.html',
        clientes=clientes,
        page=page, total_pages=total_pages, sort=sort, direction=direction, total=total,
    )


@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@require_auth
def clientes_nuevo():
    if request.method == 'POST':
        with get_db() as conn:
            conn.execute(
                """INSERT INTO clientes
                   (nombre_agencia, nif_cif, direccion, cp, poblacion, provincia, email, telefono, codigo_factusol)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request.form.get('nombre_agencia', '').strip(),
                    request.form.get('nif_cif', '').strip(),
                    request.form.get('direccion', '').strip(),
                    request.form.get('cp', '').strip(),
                    request.form.get('poblacion', '').strip(),
                    request.form.get('provincia', '').strip(),
                    request.form.get('email', '').strip(),
                    request.form.get('telefono', '').strip(),
                    request.form.get('codigo_factusol', '').strip(),
                )
            )
        flash('Cliente creado correctamente.', 'success')
        return redirect(url_for('clientes_lista'))
    return render_template('clientes/form.html', cliente=None)


@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@require_auth
def clientes_editar(id):
    with get_db() as conn:
        cliente = conn.execute("SELECT * FROM clientes WHERE id = ?", (id,)).fetchone()
        if cliente is None:
            flash('Cliente no encontrado.', 'error')
            return redirect(url_for('clientes_lista'))
        if request.method == 'POST':
            conn.execute(
                """UPDATE clientes SET nombre_agencia=?, nif_cif=?, direccion=?, cp=?,
                   poblacion=?, provincia=?, email=?, telefono=?, codigo_factusol=?
                   WHERE id=?""",
                (
                    request.form.get('nombre_agencia', '').strip(),
                    request.form.get('nif_cif', '').strip(),
                    request.form.get('direccion', '').strip(),
                    request.form.get('cp', '').strip(),
                    request.form.get('poblacion', '').strip(),
                    request.form.get('provincia', '').strip(),
                    request.form.get('email', '').strip(),
                    request.form.get('telefono', '').strip(),
                    request.form.get('codigo_factusol', '').strip(),
                    id,
                )
            )
            flash('Cliente actualizado.', 'success')
            return redirect(url_for('clientes_lista'))
    return render_template('clientes/form.html', cliente=cliente)


@app.route('/clientes/lookup')
@require_auth
def clientes_lookup():
    cif = request.args.get('cif', '').strip()
    if not cif:
        return jsonify({"ok": False, "message": "Introduce un CIF/NIF."}), 400
    enabled = get_setting('integraciones.deepseek_enabled') == '1'
    api_key = get_setting('integraciones.deepseek_api_key') if enabled else None
    return jsonify(_buscar_cliente_vies(cif, deepseek_api_key=api_key or None))


@app.route('/clientes/lookup-nombre')
@require_auth
def clientes_lookup_nombre():
    nombre = request.args.get('nombre', '').strip()
    enabled = get_setting('integraciones.deepseek_enabled') == '1'
    api_key = get_setting('integraciones.deepseek_api_key') if enabled else None
    return jsonify(_buscar_cliente_nombre(nombre, deepseek_api_key=api_key or None))


@app.route('/clientes/provincia')
@require_auth
def clientes_provincia():
    """Devuelve la provincia derivada de un código postal (tabla local, sin red)."""
    cp = request.args.get('cp', '').strip()
    return jsonify({"provincia": provincia_desde_cp(cp)})


# ── Artículos ────────────────────────────────────────────────────────────────

@app.route('/articulos')
@require_auth
def articulos_lista():
    sort = request.args.get('sort', 'descripcion')
    direction = request.args.get('dir', 'asc')
    try:
        page = max(1, int(request.args.get('page', 1) or 1))
    except ValueError:
        page = 1
    per_page = 30

    sort_map = {
        'codigo':      'codigo',
        'descripcion': 'descripcion',
        'precio':      'precio',
        'iva':         'porcentaje_iva',
    }
    sort_col = sort_map.get(sort, 'descripcion')
    sort_dir = 'ASC' if direction == 'asc' else 'DESC'

    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM articulos").fetchone()[0]
        articulos = conn.execute(
            f"SELECT * FROM articulos ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page)
        ).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        'articulos/lista.html',
        articulos=articulos,
        page=page, total_pages=total_pages, sort=sort, direction=direction, total=total,
    )


@app.route('/articulos/nuevo', methods=['GET', 'POST'])
@require_auth
def articulos_nuevo():
    if request.method == 'POST':
        with get_db() as conn:
            conn.execute(
                "INSERT INTO articulos (codigo, descripcion, precio, porcentaje_iva, familia) VALUES (?, ?, ?, ?, ?)",
                (
                    request.form.get('codigo', '').strip(),
                    request.form.get('descripcion', '').strip(),
                    float(request.form.get('precio', 0) or 0),
                    float(request.form.get('porcentaje_iva', 21) or 21),
                    request.form.get('familia', '').strip(),
                )
            )
        flash('Artículo creado correctamente.', 'success')
        return redirect(url_for('articulos_lista'))
    return render_template('articulos/form.html', articulo=None)


@app.route('/articulos/<int:id>/editar', methods=['GET', 'POST'])
@require_auth
def articulos_editar(id):
    with get_db() as conn:
        articulo = conn.execute("SELECT * FROM articulos WHERE id = ?", (id,)).fetchone()
        if articulo is None:
            flash('Artículo no encontrado.', 'error')
            return redirect(url_for('articulos_lista'))
        if request.method == 'POST':
            conn.execute(
                """UPDATE articulos SET codigo=?, descripcion=?, precio=?, porcentaje_iva=?, familia=?
                   WHERE id=?""",
                (
                    request.form.get('codigo', '').strip(),
                    request.form.get('descripcion', '').strip(),
                    float(request.form.get('precio', 0) or 0),
                    float(request.form.get('porcentaje_iva', 21) or 21),
                    request.form.get('familia', '').strip(),
                    id,
                )
            )
            flash('Artículo actualizado.', 'success')
            return redirect(url_for('articulos_lista'))
    return render_template('articulos/form.html', articulo=articulo)


# ── Guías ────────────────────────────────────────────────────────────────────

@app.route('/guias')
@require_auth
def guias_lista():
    with get_db() as conn:
        guias = conn.execute("SELECT * FROM guias ORDER BY nombre").fetchall()
    return render_template('guias/lista.html', guias=guias)


@app.route('/guias/nuevo', methods=['POST'])
@require_auth
def guias_nuevo():
    nombre = request.form.get('nombre', '').strip()
    if nombre:
        with get_db() as conn:
            conn.execute("INSERT INTO guias (nombre) VALUES (?)", (nombre,))
        flash('Guía creada.', 'success')
    return redirect(url_for('guias_lista'))


@app.route('/guias/<int:id>/editar', methods=['POST'])
@require_auth
def guias_editar(id):
    nombre = request.form.get('nombre', '').strip()
    if nombre:
        with get_db() as conn:
            conn.execute("UPDATE guias SET nombre = ? WHERE id = ?", (nombre, id))
        flash('Guía actualizada.', 'success')
    return redirect(url_for('guias_lista'))


@app.route('/guias/<int:id>/eliminar', methods=['POST'])
@require_auth
def guias_eliminar(id):
    with get_db() as conn:
        en_uso = conn.execute(
            "SELECT COUNT(*) FROM proforma_guias WHERE guia_id = ?", (id,)
        ).fetchone()[0]
        if en_uso > 0:
            flash('No se puede eliminar: la guía tiene proformas asociadas.', 'error')
        else:
            conn.execute("DELETE FROM guias WHERE id = ?", (id,))
            flash('Guía eliminada.', 'success')
    return redirect(url_for('guias_lista'))


# ── Cuentas bancarias ─────────────────────────────────────────────────────────

def _aplicar_predeterminada(conn, cuenta_id, marcar):
    """Si marcar es True, deja esta cuenta como única predeterminada."""
    if marcar:
        conn.execute("UPDATE cuentas SET predeterminada = 0")
        conn.execute("UPDATE cuentas SET predeterminada = 1 WHERE id = ?", (cuenta_id,))
    else:
        conn.execute("UPDATE cuentas SET predeterminada = 0 WHERE id = ?", (cuenta_id,))


@app.route('/cuentas')
@require_auth
def cuentas_lista():
    with get_db() as conn:
        cuentas = conn.execute(
            "SELECT * FROM cuentas ORDER BY predeterminada DESC, nombre"
        ).fetchall()
    return render_template('cuentas/lista.html', cuentas=cuentas)


@app.route('/cuentas/nueva', methods=['GET', 'POST'])
@require_auth
def cuentas_nueva():
    if request.method == 'POST':
        with get_db() as conn:
            conn.execute(
                """INSERT INTO cuentas (nombre, titular, iban, banco, bic, predeterminada)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (
                    request.form.get('nombre', '').strip(),
                    request.form.get('titular', '').strip(),
                    request.form.get('iban', '').strip(),
                    request.form.get('banco', '').strip(),
                    request.form.get('bic', '').strip(),
                )
            )
            cuenta_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            # La primera cuenta creada queda predeterminada automáticamente.
            es_unica = conn.execute("SELECT COUNT(*) FROM cuentas").fetchone()[0] == 1
            _aplicar_predeterminada(conn, cuenta_id, request.form.get('predeterminada') or es_unica)
        flash('Cuenta creada correctamente.', 'success')
        return redirect(url_for('cuentas_lista'))
    return render_template('cuentas/form.html', cuenta=None)


@app.route('/cuentas/<int:id>/editar', methods=['GET', 'POST'])
@require_auth
def cuentas_editar(id):
    with get_db() as conn:
        cuenta = conn.execute("SELECT * FROM cuentas WHERE id = ?", (id,)).fetchone()
        if cuenta is None:
            flash('Cuenta no encontrada.', 'error')
            return redirect(url_for('cuentas_lista'))
        if request.method == 'POST':
            conn.execute(
                """UPDATE cuentas SET nombre=?, titular=?, iban=?, banco=?, bic=?
                   WHERE id=?""",
                (
                    request.form.get('nombre', '').strip(),
                    request.form.get('titular', '').strip(),
                    request.form.get('iban', '').strip(),
                    request.form.get('banco', '').strip(),
                    request.form.get('bic', '').strip(),
                    id,
                )
            )
            _aplicar_predeterminada(conn, id, request.form.get('predeterminada'))
            flash('Cuenta actualizada.', 'success')
            return redirect(url_for('cuentas_lista'))
    return render_template('cuentas/form.html', cuenta=cuenta)


@app.route('/cuentas/<int:id>/eliminar', methods=['POST'])
@require_auth
def cuentas_eliminar(id):
    with get_db() as conn:
        en_uso = conn.execute(
            "SELECT COUNT(*) FROM proformas WHERE cuenta_id = ?", (id,)
        ).fetchone()[0]
        if en_uso > 0:
            flash('No se puede eliminar: la cuenta está asignada a proformas.', 'error')
        else:
            conn.execute("DELETE FROM cuentas WHERE id = ?", (id,))
            flash('Cuenta eliminada.', 'success')
    return redirect(url_for('cuentas_lista'))


# ── Proformas — helpers ──────────────────────────────────────────────────────

def _parse_lineas(form):
    """Extrae las líneas de servicio del formulario y calcula importes."""
    descripciones = form.getlist('linea_descripcion[]')
    cantidades    = form.getlist('linea_cantidad[]')
    precios       = form.getlist('linea_precio[]')
    ivas          = form.getlist('linea_iva[]')
    articulo_ids  = form.getlist('linea_articulo_id[]')
    fechas        = form.getlist('linea_fecha[]')
    lineas = []
    for i, desc in enumerate(descripciones):
        desc = desc.strip()
        if not desc:
            continue
        cantidad  = float(cantidades[i] or 1)
        precio    = float(precios[i] or 0)
        iva       = float(ivas[i] or 21)
        art_id    = articulo_ids[i] if i < len(articulo_ids) and articulo_ids[i] else None
        fecha     = fechas[i].strip() if i < len(fechas) and fechas[i].strip() else None
        lineas.append({
            'descripcion': desc, 'cantidad': cantidad, 'precio': precio,
            'porcentaje_iva': iva, 'importe': cantidad * precio * (1 + iva / 100),
            'articulo_id': art_id, 'fecha': fecha,
        })
    return lineas


def _parse_suplidos(form):
    """Extrae los ítems de suplidos del formulario. Devuelve (total_float, json_str_or_None).

    Cada ítem puede ser plano (solo importe, p. ej. dieta) o calculado por
    unidades (cantidad × precio, p. ej. entradas a museo). En los calculados el
    importe se recalcula aquí desde cantidad × precio para no fiarse del campo
    de solo lectura del formulario.
    """
    descs    = form.getlist('suplido_desc[]')
    cants    = form.getlist('suplido_cantidad[]')
    precios  = form.getlist('suplido_precio[]')
    importes = form.getlist('suplido_importe[]')
    items, total = [], 0.0
    for idx, d in enumerate(descs):
        d = d.strip()
        precio   = float(precios[idx]) if idx < len(precios) and precios[idx].strip() else 0.0
        cant_raw = cants[idx].strip() if idx < len(cants) else ''
        if precio > 0:
            cant = float(cant_raw) if cant_raw else 1.0
            imp  = round(cant * precio, 2)
        else:
            cant = None
            imp  = round(float(importes[idx] or 0) if idx < len(importes) else 0.0, 2)
        if not (d or imp):
            continue
        item = {'desc': d, 'importe': imp}
        if precio > 0:
            item['cantidad'] = cant
            item['precio']   = round(precio, 2)
        items.append(item)
        total += imp
    return round(total, 2), (json.dumps(items, ensure_ascii=False) if items else None)


def _calcular_totales(lineas, suplidos):
    base      = sum(l['cantidad'] * l['precio'] for l in lineas)
    iva_total = sum(l['cantidad'] * l['precio'] * l['porcentaje_iva'] / 100 for l in lineas)
    total     = base + iva_total
    return base, iva_total, total, total + suplidos


def _insertar_lineas(conn, proforma_id, lineas):
    for l in lineas:
        conn.execute(
            """INSERT INTO proforma_lineas
               (proforma_id, articulo_id, descripcion, cantidad, precio, porcentaje_iva, importe, fecha)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (proforma_id, l['articulo_id'], l['descripcion'],
             l['cantidad'], l['precio'], l['porcentaje_iva'], l['importe'], l['fecha'])
        )


def _insertar_guias(conn, proforma_id, guia_ids):
    for gid in guia_ids:
        conn.execute(
            "INSERT OR IGNORE INTO proforma_guias (proforma_id, guia_id) VALUES (?, ?)",
            (proforma_id, gid)
        )


def _form_context(conn):
    """Carga las listas necesarias para los formularios de proforma."""
    return {
        'clientes':  conn.execute("SELECT * FROM clientes ORDER BY nombre_agencia").fetchall(),
        'guias':     conn.execute("SELECT * FROM guias ORDER BY nombre").fetchall(),
        'articulos': conn.execute("SELECT * FROM articulos ORDER BY descripcion").fetchall(),
        'cuentas':   conn.execute("SELECT * FROM cuentas ORDER BY predeterminada DESC, nombre").fetchall(),
    }


# ── Proformas ────────────────────────────────────────────────────────────────

@app.route('/')
@require_auth
def index():
    return redirect(url_for('proformas_lista'))


@app.route('/proformas')
@require_auth
def proformas_lista():
    sort = request.args.get('sort', 'numero')
    direction = request.args.get('dir', 'desc')
    try:
        page = max(1, int(request.args.get('page', 1) or 1))
    except ValueError:
        page = 1
    per_page = 30

    sort_map = {
        'numero':  'p.numero_proforma',
        'fecha':   'p.fecha',
        'total':   'p.total_suplidos',
    }
    sort_col = sort_map.get(sort, 'p.fecha')
    sort_dir = 'ASC' if direction == 'asc' else 'DESC'

    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM proformas").fetchone()[0]
        proformas = conn.execute(
            f"""SELECT p.*, c.nombre_agencia,
                      GROUP_CONCAT(g.nombre, ', ') as guia_nombre
               FROM proformas p
               LEFT JOIN clientes c ON p.cliente_id = c.id
               LEFT JOIN proforma_guias pg ON p.id = pg.proforma_id
               LEFT JOIN guias g ON pg.guia_id = g.id
               GROUP BY p.id
               ORDER BY {sort_col} {sort_dir}, p.id {sort_dir}
               LIMIT ? OFFSET ?""",
            (per_page, (page - 1) * per_page)
        ).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        'proformas/lista.html',
        proformas=proformas,
        page=page,
        total_pages=total_pages,
        sort=sort,
        direction=direction,
        total=total,
    )


@app.route('/proformas/nueva', methods=['GET', 'POST'])
@require_auth
def proformas_nueva():
    with get_db() as conn:
        ctx = _form_context(conn)

    if request.method == 'POST':
        fecha_str  = request.form.get('fecha', str(date.today()))
        cliente_id = request.form.get('cliente_id') or None
        cuenta_id  = request.form.get('cuenta_id') or None
        guia_ids   = [int(g) for g in request.form.getlist('guia_ids[]') if g]
        suplidos, suplidos_detalle = _parse_suplidos(request.form)
        comentarios = request.form.get('comentarios', '').strip()
        referencia  = request.form.get('referencia', '').strip() or None

        lineas = _parse_lineas(request.form)
        base, iva_total, total, total_suplidos = _calcular_totales(lineas, suplidos)
        try:
            trimestre = (int(fecha_str.split('-')[1]) - 1) // 3 + 1
        except (IndexError, ValueError):
            trimestre = 1
        anio = int(fecha_str.split('-')[0]) if fecha_str else date.today().year
        try:
            fecha_obj = date.fromisoformat(fecha_str) if fecha_str else date.today()
        except ValueError:
            fecha_obj = date.today()
        nombre_agencia = None
        if cliente_id:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT nombre_agencia FROM clientes WHERE id=?", (int(cliente_id),)
                ).fetchone()
                if row:
                    nombre_agencia = row['nombre_agencia']
        numero_form = request.form.get('numero_proforma', '').strip()
        numero_auto, n_secuencial = siguiente_numero_proforma(anio, fecha=fecha_obj, agencia=nombre_agencia)
        cfg_serie = get_serie_config()
        usa_agencia = '{agencia}' in cfg_serie.get('formato', '')
        numero = numero_auto if usa_agencia else (numero_form or numero_auto)
        if numero != numero_auto:
            with get_db() as conn:
                if conn.execute(
                    "SELECT 1 FROM proformas WHERE numero_proforma=?", (numero,)
                ).fetchone():
                    flash(f'El número «{numero}» ya está en uso.', 'error')
                    return redirect(url_for('proformas_nueva'))

        with get_db() as conn:
            conn.execute(
                """INSERT INTO proformas
                   (numero_proforma, fecha, cliente_id, cuenta_id, estado, base, iva_total,
                    suplidos, suplidos_detalle, total, total_suplidos, comentarios, trimestre,
                    referencia, numero_secuencial)
                   VALUES (?, ?, ?, ?, 'borrador', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (numero, fecha_str, cliente_id, cuenta_id, base, iva_total,
                 suplidos, suplidos_detalle, total, total_suplidos, comentarios, trimestre,
                 referencia, n_secuencial)
            )
            proforma_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            _insertar_guias(conn, proforma_id, guia_ids)
            _insertar_lineas(conn, proforma_id, lineas)

        flash(f'Proforma {numero} creada correctamente.', 'success')
        return redirect(url_for('proformas_detalle', id=proforma_id))

    anio_hoy = date.today().year
    articulos_json = json.dumps([
        {'id': a['id'], 'codigo': a['codigo'], 'descripcion': a['descripcion'],
         'precio': a['precio'], 'porcentaje_iva': a['porcentaje_iva']}
        for a in ctx['articulos']
    ])
    cuenta_predeterminada_id = next(
        (c['id'] for c in ctx['cuentas'] if c['predeterminada']), None
    )
    return render_template(
        'proformas/nueva.html',
        **ctx,
        articulos_json=articulos_json,
        cuenta_predeterminada_id=cuenta_predeterminada_id,
        hoy=str(date.today()),
        numero_sugerido=peek_numero_proforma(anio_hoy),
    )


@app.route('/proformas/<int:id>')
@require_auth
def proformas_detalle(id):
    with get_db() as conn:
        proforma = conn.execute("SELECT * FROM proformas WHERE id = ?", (id,)).fetchone()
        if proforma is None:
            flash('Proforma no encontrada.', 'error')
            return redirect(url_for('proformas_lista'))
        cliente = None
        if proforma['cliente_id']:
            cliente = conn.execute(
                "SELECT * FROM clientes WHERE id = ?", (proforma['cliente_id'],)
            ).fetchone()
        cuenta = None
        if proforma['cuenta_id']:
            cuenta = conn.execute(
                "SELECT * FROM cuentas WHERE id = ?", (proforma['cuenta_id'],)
            ).fetchone()
        guias = conn.execute(
            """SELECT g.* FROM guias g
               JOIN proforma_guias pg ON g.id = pg.guia_id
               WHERE pg.proforma_id = ?
               ORDER BY g.nombre""",
            (id,)
        ).fetchall()
        lineas = conn.execute(
            "SELECT * FROM proforma_lineas WHERE proforma_id = ? ORDER BY id", (id,)
        ).fetchall()
    raw = proforma['suplidos_detalle']
    if raw:
        try:
            suplidos_items = json.loads(raw)
        except (ValueError, TypeError):
            suplidos_items = []
    elif proforma['suplidos']:
        suplidos_items = [{'desc': '', 'importe': proforma['suplidos']}]
    else:
        suplidos_items = []

    return render_template(
        'proformas/detalle.html',
        proforma=proforma,
        cliente=cliente,
        cuenta=cuenta,
        guias=guias,
        lineas=lineas,
        suplidos_items=suplidos_items,
    )


@app.route('/proformas/<int:id>/editar', methods=['GET', 'POST'])
@require_auth
def proformas_editar(id):
    with get_db() as conn:
        proforma = conn.execute("SELECT * FROM proformas WHERE id = ?", (id,)).fetchone()
        if proforma is None:
            flash('Proforma no encontrada.', 'error')
            return redirect(url_for('proformas_lista'))

    if request.method == 'POST':
        fecha_str   = request.form.get('fecha', str(date.today()))
        cliente_id  = request.form.get('cliente_id') or None
        cuenta_id   = request.form.get('cuenta_id') or None
        guia_ids    = [int(g) for g in request.form.getlist('guia_ids[]') if g]
        suplidos, suplidos_detalle = _parse_suplidos(request.form)
        comentarios = request.form.get('comentarios', '').strip()
        referencia  = request.form.get('referencia', '').strip() or None
        numero_nuevo = request.form.get('numero_proforma', '').strip() or proforma['numero_proforma']

        if numero_nuevo != proforma['numero_proforma']:
            with get_db() as conn:
                if conn.execute(
                    "SELECT 1 FROM proformas WHERE numero_proforma=? AND id!=?", (numero_nuevo, id)
                ).fetchone():
                    flash(f'El número «{numero_nuevo}» ya está en uso.', 'error')
                    return redirect(url_for('proformas_editar', id=id))

        lineas = _parse_lineas(request.form)
        base, iva_total, total, total_suplidos = _calcular_totales(lineas, suplidos)
        try:
            trimestre = (int(fecha_str.split('-')[1]) - 1) // 3 + 1
        except (IndexError, ValueError):
            trimestre = 1

        with get_db() as conn:
            ruta_pdf = conn.execute(
                "SELECT ruta_pdf FROM proformas WHERE id=?", (id,)
            ).fetchone()['ruta_pdf']
            conn.execute(
                """UPDATE proformas SET numero_proforma=?, fecha=?, cliente_id=?, cuenta_id=?,
                   base=?, iva_total=?, suplidos=?, suplidos_detalle=?, total=?, total_suplidos=?,
                   comentarios=?, trimestre=?, referencia=?, ruta_pdf=NULL WHERE id=?""",
                (numero_nuevo, fecha_str, cliente_id, cuenta_id, base, iva_total,
                 suplidos, suplidos_detalle, total, total_suplidos, comentarios, trimestre, referencia, id)
            )
            conn.execute("DELETE FROM proforma_lineas WHERE proforma_id=?", (id,))
            _insertar_lineas(conn, id, lineas)
            conn.execute("DELETE FROM proforma_guias WHERE proforma_id=?", (id,))
            _insertar_guias(conn, id, guia_ids)

        if ruta_pdf and os.path.exists(ruta_pdf):
            try:
                os.remove(ruta_pdf)
            except OSError:
                pass

        flash('Proforma actualizada correctamente.', 'success')
        return redirect(url_for('proformas_lista'))

    with get_db() as conn:
        ctx = _form_context(conn)
        lineas = conn.execute(
            "SELECT * FROM proforma_lineas WHERE proforma_id=? ORDER BY id", (id,)
        ).fetchall()
        guia_ids_actuales = set(
            r['guia_id'] for r in conn.execute(
                "SELECT guia_id FROM proforma_guias WHERE proforma_id=?", (id,)
            ).fetchall()
        )

    raw = proforma['suplidos_detalle']
    if raw:
        try:
            suplidos_items = json.loads(raw)
        except (ValueError, TypeError):
            suplidos_items = []
    elif proforma['suplidos']:
        suplidos_items = [{'desc': '', 'importe': proforma['suplidos']}]
    else:
        suplidos_items = []

    articulos_json = json.dumps([
        {'id': a['id'], 'codigo': a['codigo'], 'descripcion': a['descripcion'],
         'precio': a['precio'], 'porcentaje_iva': a['porcentaje_iva']}
        for a in ctx['articulos']
    ])
    return render_template(
        'proformas/editar.html',
        proforma=proforma,
        lineas=lineas,
        suplidos_items=suplidos_items,
        **ctx,
        articulos_json=articulos_json,
        guia_ids_actuales=guia_ids_actuales,
    )


@app.route('/proformas/<int:id>/pdf')
@require_auth
def proformas_pdf(id):
    with get_db() as conn:
        proforma = conn.execute("SELECT * FROM proformas WHERE id = ?", (id,)).fetchone()
        if proforma is None:
            flash('Proforma no encontrada.', 'error')
            return redirect(url_for('proformas_lista'))
        ruta_pdf = proforma['ruta_pdf']

    if ruta_pdf and os.path.exists(ruta_pdf):
        return send_file(ruta_pdf, as_attachment=True,
                         download_name=os.path.basename(ruta_pdf))

    try:
        ruta_pdf = generar_pdf(id)
    except Exception as e:
        flash(f'Error al generar el PDF: {e}', 'error')
        return redirect(url_for('proformas_detalle', id=id))

    return send_file(ruta_pdf, as_attachment=True,
                     download_name=os.path.basename(ruta_pdf))


@app.route('/proformas/<int:id>/eliminar', methods=['POST'])
@require_auth
def proformas_eliminar(id):
    with get_db() as conn:
        proforma = conn.execute("SELECT * FROM proformas WHERE id = ?", (id,)).fetchone()
        if proforma is None:
            flash('Proforma no encontrada.', 'error')
            return redirect(url_for('proformas_lista'))
        if proforma['estado'] == 'confirmada':
            flash('No se puede eliminar una proforma confirmada (ya registrada en Hacienda).', 'error')
            return redirect(url_for('proformas_detalle', id=id))
        ruta_pdf = proforma['ruta_pdf']
        fecha_proforma = proforma['fecha']
        conn.execute("DELETE FROM proforma_lineas WHERE proforma_id = ?", (id,))
        conn.execute("DELETE FROM proforma_guias WHERE proforma_id = ?", (id,))
        conn.execute("DELETE FROM proformas WHERE id = ?", (id,))
    if ruta_pdf and os.path.exists(ruta_pdf):
        try:
            os.remove(ruta_pdf)
        except OSError:
            pass
    try:
        anio_borrada = int(fecha_proforma.split('-')[0])
        recalcular_contador_serie(get_serie_config()['prefijo'], anio_borrada)
    except Exception:
        pass
    flash('Proforma eliminada correctamente.', 'success')
    return redirect(url_for('proformas_lista'))


@app.route('/proformas/<int:id>/confirmar', methods=['POST'])
@require_auth
def proformas_confirmar(id):
    with get_db() as conn:
        proforma = conn.execute("SELECT * FROM proformas WHERE id = ?", (id,)).fetchone()
        if proforma is None:
            flash('Proforma no encontrada.', 'error')
            return redirect(url_for('proformas_lista'))
        if proforma['estado'] != 'confirmada':
            conn.execute("UPDATE proformas SET estado = 'confirmada' WHERE id = ?", (id,))

    resultado = excel.registrar_proforma(id)
    if resultado == excel.OK:
        pendientes = excel.drain_pending()  # el Excel está libre: aprovecha y vacía la cola
        extra = f' (+{pendientes} pendiente{"s" if pendientes != 1 else ""})' if pendientes else ''
        flash(f'Proforma confirmada y registrada en el Excel de Hacienda{extra}.', 'success')
    elif resultado == excel.YA_REGISTRADA:
        flash('Proforma confirmada. Ya estaba registrada en el Excel.', 'success')
    elif resultado == excel.EN_COLA:
        flash('Proforma confirmada. El Excel está abierto; se registrará automáticamente al cerrarlo.', 'success')
    else:
        flash('Proforma confirmada, pero no se pudo registrar en el Excel.', 'error')
    return redirect(url_for('proformas_detalle', id=id))


@app.route('/proformas/<int:id>/desconfirmar', methods=['POST'])
@require_auth
def proformas_desconfirmar(id):
    with get_db() as conn:
        proforma = conn.execute("SELECT * FROM proformas WHERE id = ?", (id,)).fetchone()
        if proforma is None:
            flash('Proforma no encontrada.', 'error')
            return redirect(url_for('proformas_lista'))
        if proforma['estado'] != 'confirmada':
            flash('La proforma no está confirmada.', 'error')
            return redirect(url_for('proformas_detalle', id=id))

        numero = proforma['numero_proforma']
        resultado = excel.eliminar_fila_excel(numero)
        conn.execute(
            "UPDATE proformas SET estado = 'borrador', exportada_excel = 0 WHERE id = ?", (id,)
        )

    if resultado is True:
        flash('Proforma desconfirmada y fila eliminada del Excel de Hacienda. Ya puedes editarla y volver a confirmarla.', 'success')
    elif resultado is None:
        flash('Proforma desconfirmada, pero el Excel estaba bloqueado y no se pudo eliminar la fila. Elimínala manualmente antes de re-confirmar.', 'warning')
    else:
        flash('Proforma desconfirmada. No se encontró su fila en el Excel (puede que no estuviera registrada).', 'success')

    if request.form.get('next') == 'edit':
        return redirect(url_for('proformas_editar', id=id))
    return redirect(url_for('proformas_detalle', id=id))


# ── API (creación rápida desde modales) ──────────────────────────────────────

@app.route('/api/articulos', methods=['POST'])
@require_auth
def api_articulos_nuevo():
    descripcion = request.form.get('descripcion', '').strip()
    if not descripcion:
        return jsonify({'error': 'La descripción es obligatoria.'}), 400
    precio = float(request.form.get('precio', 0) or 0)
    porcentaje_iva = float(request.form.get('porcentaje_iva', 21) or 21)
    codigo = request.form.get('codigo', '').strip()
    familia = request.form.get('familia', '').strip()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO articulos (codigo, descripcion, precio, porcentaje_iva, familia) VALUES (?, ?, ?, ?, ?)",
            (codigo, descripcion, precio, porcentaje_iva, familia)
        )
        art_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify({
        'id': art_id,
        'descripcion': descripcion,
        'precio': precio,
        'porcentaje_iva': porcentaje_iva,
        'codigo': codigo,
    })


@app.route('/api/clientes', methods=['POST'])
@require_auth
def api_clientes_nuevo():
    nombre = request.form.get('nombre_agencia', '').strip()
    if not nombre:
        return jsonify({'error': 'El nombre es obligatorio.'}), 400
    nif_cif = request.form.get('nif_cif', '').strip()
    email = request.form.get('email', '').strip()
    telefono = request.form.get('telefono', '').strip()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO clientes (nombre_agencia, nif_cif, email, telefono) VALUES (?, ?, ?, ?)",
            (nombre, nif_cif, email, telefono)
        )
        cli_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify({'id': cli_id, 'nombre_agencia': nombre})


@app.route('/config')
@require_auth
def config_index():
    return render_template(
        'config/index.html',
        pendientes_excel=excel.contar_pendientes(),
        deepseek_configurada=bool(get_setting('integraciones.deepseek_api_key')),
        deepseek_enabled=get_setting('integraciones.deepseek_enabled') == '1',
    )


@app.route('/config/integraciones', methods=['POST'])
@require_auth
def config_integraciones():
    valor = request.form.get('deepseek_api_key', '').strip()
    if valor:
        set_setting('integraciones.deepseek_api_key', valor)
    enabled = '1' if request.form.get('deepseek_enabled') else '0'
    set_setting('integraciones.deepseek_enabled', enabled)
    flash('Configuración de integraciones guardada.', 'success')
    return redirect(url_for('config_index'))


@app.route('/config/descargar-excel')
@require_auth
def config_descargar_excel():
    excel_path = os.environ.get('EXCEL_PATH', '/mnt/empresa/facturas-emitidas.xlsx')
    if not os.path.exists(excel_path):
        flash('El fichero Excel no existe todavía (aún no se ha confirmado ninguna proforma).', 'error')
        return redirect(url_for('config_index'))
    return send_file(excel_path, as_attachment=True,
                     download_name=os.path.basename(excel_path))


@app.route('/config/reintentar-excel', methods=['POST'])
@require_auth
def config_reintentar_excel():
    escritas = excel.drain_pending()
    if escritas:
        flash(f'{escritas} proforma(s) pendiente(s) registrada(s) en el Excel.', 'success')
    else:
        flash('No había pendientes que registrar (o el Excel sigue abierto).', 'success')
    return redirect(url_for('config_index'))


@app.route('/config/empresa', methods=['GET', 'POST'])
@require_auth
def config_empresa():
    if request.method == 'POST':
        fields = {
            'nombre': request.form.get('nombre', '').strip(),
            'nif': request.form.get('nif', '').strip(),
            'direccion': request.form.get('direccion', '').strip(),
            'cp': request.form.get('cp', '').strip(),
            'poblacion': request.form.get('poblacion', '').strip(),
            'provincia': request.form.get('provincia', '').strip(),
            'email': request.form.get('email', '').strip(),
            'telefono': request.form.get('telefono', '').strip(),
            'web': request.form.get('web', '').strip(),
            'condiciones_pago': request.form.get('condiciones_pago', '').strip(),
            'tagline': request.form.get('tagline', '').strip(),
            'mostrar_direccion': '1' if request.form.get('mostrar_direccion') else '0',
            'aviso_legal': request.form.get('aviso_legal', '').strip(),
        }
        set_empresa_config(fields)
        _purgar_cache_pdf()
        flash('Datos de empresa actualizados. La caché de PDFs se ha limpiado.', 'success')
        return redirect(url_for('config_empresa'))
    return render_template('config/empresa.html', empresa=get_empresa_config())


def _purgar_cache_pdf():
    """Borra los PDF cacheados y limpia ruta_pdf. Se regeneran al vuelo en la
    siguiente descarga, así un reinicio refleja siempre los cambios de plantilla."""
    borrados = 0
    if os.path.isdir(PDF_DIR):
        for nombre in os.listdir(PDF_DIR):
            if nombre.endswith('.pdf'):
                try:
                    os.remove(os.path.join(PDF_DIR, nombre))
                    borrados += 1
                except OSError:
                    pass
    with get_db() as conn:
        conn.execute("UPDATE proformas SET ruta_pdf = NULL")
    return borrados


@app.route('/config/reboot', methods=['POST'])
@require_auth
def config_reboot():
    borrados = _purgar_cache_pdf()

    def _restart():
        subprocess.run(['systemctl', 'restart', 'proforma-admin'])
    threading.Timer(0.5, _restart).start()
    flash(f'Caché de PDF limpiada ({borrados} fichero(s)). Reiniciando… '
          'vuelve a cargar en unos segundos.', 'success')
    return redirect(url_for('config_index'))


@app.route('/config/numeracion', methods=['GET', 'POST'])
@require_auth
def config_numeracion():
    anio_actual = date.today().year
    if request.method == 'POST':
        prefijo = request.form.get('prefijo', 'PRO').strip() or 'PRO'
        formato = request.form.get('formato', '{serie}-{anio}-{n}').strip() or '{serie}-{anio}-{n}'
        digitos = request.form.get('digitos', '4').strip() or '4'
        set_serie_config(prefijo, formato, int(digitos))
        proximo_raw = request.form.get('proximo_numero', '').strip()
        if proximo_raw:
            try:
                set_proximo_numero(anio_actual, int(proximo_raw))
            except ValueError:
                flash('El próximo número debe ser un entero.', 'error')
                return redirect(url_for('config_numeracion'))
        flash('Configuración de numeración guardada.', 'success')
        return redirect(url_for('config_numeracion'))
    cfg = get_serie_config()
    with get_db() as conn:
        row = conn.execute(
            "SELECT ultimo_numero FROM series WHERE serie=? AND anio=?",
            (cfg['prefijo'], anio_actual)
        ).fetchone()
    proximo_n = (row['ultimo_numero'] if row else 0) + 1
    return render_template(
        'config/numeracion.html',
        cfg=cfg,
        anio_actual=anio_actual,
        ejemplo=peek_numero_proforma(anio_actual),
        proximo_n=proximo_n,
    )


@app.route('/api/peek-numero')
@require_auth
def api_peek_numero():
    """Devuelve el siguiente número de proforma sin incrementar el contador.
    Parámetros GET: fecha (YYYY-MM-DD), cliente_id (int)."""
    fecha_str = request.args.get('fecha', str(date.today()))
    cliente_id = request.args.get('cliente_id') or None
    try:
        fecha_obj = date.fromisoformat(fecha_str)
    except ValueError:
        fecha_obj = date.today()
    anio = fecha_obj.year
    nombre_agencia = None
    if cliente_id:
        with get_db() as conn:
            row = conn.execute(
                "SELECT nombre_agencia FROM clientes WHERE id=?", (int(cliente_id),)
            ).fetchone()
            if row:
                nombre_agencia = row['nombre_agencia']
    numero = peek_numero_proforma(anio, fecha=fecha_obj, agencia=nombre_agencia)
    return jsonify({'numero': numero})


@app.route('/ayuda')
@require_auth
def ayuda():
    return render_template('ayuda.html')


from api_orquestador import bp as bp_api_orq
app.register_blueprint(bp_api_orq)

if __name__ == '__main__':
    init_db()
    excel.drain_pending()  # registra en el Excel cualquier proforma que quedara en cola
    app.run(host='0.0.0.0', port=5114, debug=False)
