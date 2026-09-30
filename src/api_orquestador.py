"""Rutas de lectura JSON para el orquestador CT108.

Añadir en app.py antes de if __name__ == '__main__':
    from api_orquestador import bp as bp_api
    app.register_blueprint(bp_api)

No modifica datos. Misma autenticación que el panel HTML.
"""
from __future__ import annotations
import os
from datetime import date, datetime
from flask import Blueprint, jsonify, request
from admin_helpers import require_auth

bp = Blueprint("api_orquestador", __name__, url_prefix="/api")

EXCEL_PATH = os.environ.get("EXCEL_PATH", "/mnt/empresa/facturas-emitidas.xlsx")


@bp.route("/proformas")
@require_auth
def api_proformas():
    """Lista de proformas con nombre del cliente. Filtros: ?estado=X &cliente=X
    Con ?con_lineas=1 cada fila lleva además `lineas` y `guia_ids`."""
    from db import get_db
    estado = request.args.get("estado")
    cliente = request.args.get("cliente")
    sql = """
        SELECT p.*, c.nombre_agencia
        FROM proformas p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        WHERE 1=1
    """
    params = []
    if estado:
        sql += " AND p.estado=?"
        params.append(estado)
    if cliente:
        sql += " AND c.nombre_agencia LIKE ?"
        params.append(f"%{cliente}%")
    sql += " ORDER BY p.fecha DESC LIMIT 200"
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        if request.args.get("con_lineas") == "1" and rows:
            _anadir_lineas_y_guias(conn, rows)
    return jsonify(rows)


def _anadir_lineas_y_guias(conn, rows):
    """Añade `lineas` y `guia_ids` a cada proforma, con dos consultas en total."""
    ids = [r["id"] for r in rows]
    marcas = ",".join("?" * len(ids))
    por_id = {i: ([], []) for i in ids}
    for l in conn.execute(
        f"""SELECT proforma_id, fecha, articulo_id, descripcion, cantidad, precio,
                   porcentaje_iva, importe
            FROM proforma_lineas WHERE proforma_id IN ({marcas}) ORDER BY id""", ids
    ).fetchall():
        d = dict(l)
        por_id[d.pop("proforma_id")][0].append(d)
    for g in conn.execute(
        f"""SELECT proforma_id, guia_id FROM proforma_guias
            WHERE proforma_id IN ({marcas}) ORDER BY guia_id""", ids
    ).fetchall():
        por_id[g["proforma_id"]][1].append(int(g["guia_id"]))
    for r in rows:
        r["lineas"], r["guia_ids"] = por_id[r["id"]]


@bp.route("/articulos")
@require_auth
def api_articulos():
    """Catálogo de artículos (incluye inactivos, con `activo` booleano)."""
    from db import get_db
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, descripcion, precio, porcentaje_iva, IFNULL(activo, 1) AS activo "
            "FROM articulos ORDER BY descripcion"
        ).fetchall()
    return jsonify([{**dict(r), "activo": bool(r["activo"])} for r in rows])


@bp.route("/guias")
@require_auth
def api_guias():
    """Guías (solo id, nombre y activo; sin datos personales)."""
    from db import get_db
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, nombre, IFNULL(activo, 1) AS activo FROM guias ORDER BY nombre"
        ).fetchall()
    return jsonify([{**dict(r), "activo": bool(r["activo"])} for r in rows])


@bp.route("/cuentas")
@require_auth
def api_cuentas():
    """Cuentas para elegir `cuenta_id`. Sin IBAN ni datos bancarios."""
    from db import get_db
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, nombre, IFNULL(predeterminada, 0) AS predeterminada "
            "FROM cuentas ORDER BY predeterminada DESC, nombre"
        ).fetchall()
    return jsonify([{**dict(r), "predeterminada": bool(r["predeterminada"])} for r in rows])


@bp.route("/proformas/<int:pid>")
@require_auth
def api_proforma(pid):
    from db import get_db
    sql = """
        SELECT p.*, c.nombre_agencia, c.email, c.nif_cif
        FROM proformas p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        WHERE p.id=?
    """
    with get_db() as conn:
        row = conn.execute(sql, (pid,)).fetchone()
    if row is None:
        return jsonify({"error": "no encontrada"}), 404
    return jsonify(dict(row))


@bp.route("/clientes")
@require_auth
def api_clientes():
    from db import get_db
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM clientes ORDER BY nombre_agencia"
        ).fetchall()]
    return jsonify(rows)


@bp.route("/cobros/vencidos")
@require_auth
def api_cobros_vencidos():
    """Proformas sin cobrar con fecha <= hoy.

    Lee facturas-emitidas.xlsx (columna 'Cobrado' vacía + 'Fecha Factura' <= hoy).
    """
    import openpyxl
    hoy = date.today()
    vencidos = []
    try:
        wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
        ws = wb.active
        headers = None
        for row in ws.iter_rows(values_only=True):
            if headers is None:
                headers = [str(h).strip() if h else "" for h in row]
                continue
            if not any(row):
                continue
            d = dict(zip(headers, row))
            cobrado = d.get("Cobrado")
            fecha = d.get("Fecha Factura")
            if cobrado not in (None, ""):
                continue
            if fecha is None:
                continue
            if isinstance(fecha, datetime):
                fecha_d = fecha.date()
            elif isinstance(fecha, date):
                fecha_d = fecha
            else:
                continue
            if fecha_d <= hoy:
                vencidos.append({
                    "fecha": str(fecha_d),
                    "proforma": d.get("Nº Proforma"),
                    "agencia": d.get("Agencia"),
                    "total": d.get("Total + suplidos") or d.get("Total"),
                    "comentarios": d.get("Comentarios"),
                    "dias_vencido": (hoy - fecha_d).days,
                })
        wb.close()
    except FileNotFoundError:
        return jsonify({"error": f"no encontrado: {EXCEL_PATH}"}), 500
    vencidos.sort(key=lambda x: x["fecha"])
    return jsonify(vencidos)
