import os
import json
import subprocess
import threading
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify

from db import get_db, init_db, siguiente_numero_proforma, get_empresa_config, set_empresa_config
from admin_helpers import require_auth
from pdf import generar_pdf, PDF_DIR
import excel

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'proforma-admin-secret-2026')


@app.context_processor
def inject_empresa():
    return {'empresa_config': get_empresa_config()}


# ── Clientes ────────────────────────────────────────────────────────────────

@app.route('/clientes')
@require_auth
def clientes_lista():
    with get_db() as conn:
        clientes = conn.execute("SELECT * FROM clientes ORDER BY nombre_agencia").fetchall()
    return render_template('clientes/lista.html', clientes=clientes)


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


# ── Artículos ────────────────────────────────────────────────────────────────

@app.route('/articulos')
@require_auth
def articulos_lista():
    with get_db() as conn:
        articulos = conn.execute("SELECT * FROM articulos ORDER BY descripcion").fetchall()
    return render_template('articulos/lista.html', articulos=articulos)


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


# ── Proformas ────────────────────────────────────────────────────────────────

@app.route('/')
@require_auth
def index():
    return redirect(url_for('proformas_lista'))


@app.route('/proformas')
@require_auth
def proformas_lista():
    with get_db() as conn:
        proformas = conn.execute(
            """SELECT p.*, c.nombre_agencia,
                      GROUP_CONCAT(g.nombre, ', ') as guia_nombre
               FROM proformas p
               LEFT JOIN clientes c ON p.cliente_id = c.id
               LEFT JOIN proforma_guias pg ON p.id = pg.proforma_id
               LEFT JOIN guias g ON pg.guia_id = g.id
               GROUP BY p.id
               ORDER BY p.fecha DESC, p.id DESC"""
        ).fetchall()
    return render_template('proformas/lista.html', proformas=proformas)


@app.route('/proformas/nueva', methods=['GET', 'POST'])
@require_auth
def proformas_nueva():
    with get_db() as conn:
        clientes = conn.execute("SELECT * FROM clientes ORDER BY nombre_agencia").fetchall()
        guias = conn.execute("SELECT * FROM guias ORDER BY nombre").fetchall()
        articulos = conn.execute("SELECT * FROM articulos ORDER BY descripcion").fetchall()
        cuentas = conn.execute(
            "SELECT * FROM cuentas ORDER BY predeterminada DESC, nombre"
        ).fetchall()

    if request.method == 'POST':
        fecha_str = request.form.get('fecha', str(date.today()))
        cliente_id = request.form.get('cliente_id') or None
        cuenta_id = request.form.get('cuenta_id') or None
        guia_ids = [int(g) for g in request.form.getlist('guia_ids[]') if g]
        suplidos = float(request.form.get('suplidos', 0) or 0)
        comentarios = request.form.get('comentarios', '').strip()

        descripciones = request.form.getlist('linea_descripcion[]')
        cantidades = request.form.getlist('linea_cantidad[]')
        precios = request.form.getlist('linea_precio[]')
        ivas = request.form.getlist('linea_iva[]')
        articulo_ids = request.form.getlist('linea_articulo_id[]')
        fechas = request.form.getlist('linea_fecha[]')

        lineas = []
        for i in range(len(descripciones)):
            desc = descripciones[i].strip()
            if not desc:
                continue
            cantidad = float(cantidades[i] or 1)
            precio = float(precios[i] or 0)
            iva = float(ivas[i] or 21)
            art_id = articulo_ids[i] if i < len(articulo_ids) and articulo_ids[i] else None
            fecha = fechas[i].strip() if i < len(fechas) and fechas[i].strip() else None
            importe = cantidad * precio * (1 + iva / 100)
            lineas.append({
                'descripcion': desc,
                'cantidad': cantidad,
                'precio': precio,
                'porcentaje_iva': iva,
                'importe': importe,
                'articulo_id': art_id,
                'fecha': fecha,
            })

        base = sum(l['cantidad'] * l['precio'] for l in lineas)
        iva_total = sum(l['cantidad'] * l['precio'] * l['porcentaje_iva'] / 100 for l in lineas)
        total = base + iva_total
        total_suplidos = total + suplidos

        try:
            mes = int(fecha_str.split('-')[1])
        except (IndexError, ValueError):
            mes = 1
        trimestre = (mes - 1) // 3 + 1

        anio_actual = int(fecha_str.split('-')[0]) if fecha_str else date.today().year
        numero = siguiente_numero_proforma(serie='PRO', anio=anio_actual)

        with get_db() as conn:
            conn.execute(
                """INSERT INTO proformas
                   (numero_proforma, fecha, cliente_id, cuenta_id, estado, base, iva_total,
                    suplidos, total, total_suplidos, comentarios, trimestre)
                   VALUES (?, ?, ?, ?, 'borrador', ?, ?, ?, ?, ?, ?, ?)""",
                (numero, fecha_str, cliente_id, cuenta_id, base, iva_total,
                 suplidos, total, total_suplidos, comentarios, trimestre)
            )
            proforma_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for gid in guia_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO proforma_guias (proforma_id, guia_id) VALUES (?, ?)",
                    (proforma_id, gid)
                )
            for l in lineas:
                conn.execute(
                    """INSERT INTO proforma_lineas
                       (proforma_id, articulo_id, descripcion, cantidad, precio, porcentaje_iva, importe, fecha)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (proforma_id, l['articulo_id'], l['descripcion'],
                     l['cantidad'], l['precio'], l['porcentaje_iva'], l['importe'], l['fecha'])
                )

        flash(f'Proforma {numero} creada correctamente.', 'success')
        return redirect(url_for('proformas_detalle', id=proforma_id))

    articulos_json = json.dumps([
        {
            'id': a['id'],
            'codigo': a['codigo'],
            'descripcion': a['descripcion'],
            'precio': a['precio'],
            'porcentaje_iva': a['porcentaje_iva'],
        }
        for a in articulos
    ])
    cuenta_predeterminada_id = next(
        (c['id'] for c in cuentas if c['predeterminada']), None
    )
    return render_template(
        'proformas/nueva.html',
        clientes=clientes,
        guias=guias,
        articulos=articulos,
        articulos_json=articulos_json,
        cuentas=cuentas,
        cuenta_predeterminada_id=cuenta_predeterminada_id,
        hoy=str(date.today()),
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
    return render_template(
        'proformas/detalle.html',
        proforma=proforma,
        cliente=cliente,
        cuenta=cuenta,
        guias=guias,
        lineas=lineas,
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
    return render_template('config/index.html', pendientes_excel=excel.contar_pendientes())


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


if __name__ == '__main__':
    init_db()
    excel.drain_pending()  # registra en el Excel cualquier proforma que quedara en cola
    app.run(host='0.0.0.0', port=5114, debug=False)
