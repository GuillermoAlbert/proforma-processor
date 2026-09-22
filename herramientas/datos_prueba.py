"""Siembra una base de datos de mentira para las capturas de la interfaz.

NUNCA toca la base real: trabaja sobre la que diga `DB_PATH`, que
`servidor_pruebas.sh` fija en /tmp dentro del CT. Todos los nombres son
inventados y no se parecen a ningún cliente real.

Imprime al final un JSON con los ids que necesitan las capturas
(`herramientas/capturas_panel.py`), que `arrancar` guarda en ids.json.

Uso (dentro del CT 104):
    DB_PATH=/tmp/capturas-proformas/proformas.db python3 herramientas/datos_prueba.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import db  # noqa: E402

HOY = date.today()


def _fecha(dias_atras: int) -> str:
    return (HOY - timedelta(days=dias_atras)).isoformat()


def _trimestre(iso: str) -> int:
    return (int(iso[5:7]) - 1) // 3 + 1


CLIENTES = [
    # nombre, nif, direccion, cp, poblacion, provincia, email, persona, telefono
    ("Agencia de Prueba Uno S.L.", "B00000001", "Calle Inventada 1", "03001",
     "Alicante", "Alicante", "reservas@ejemplo-uno.invalid", "Ana Ejemplo", "+34 600 000 001"),
    ("Viajes Ficticios S.A.", "A00000002", "Avenida Imaginaria 22", "46001",
     "Valencia", "Valencia", "grupos@ejemplo-dos.invalid", None, "+34 600 000 002"),
    ("Turismo Ejemplo", "B00000003", None, "30001",
     "Murcia", "Murcia", "info@ejemplo-tres.invalid", "Carlos Muestra", "+34 600 000 003"),
]

ARTICULOS = [
    ("VG01", "Visita guiada de medio día en Alicante", 180.0, 21.0, "Visitas"),
    ("VG02", "Visita guiada de día completo con traslado", 320.0, 21.0, "Visitas"),
    ("SUP1", "Entradas a monumentos (suplido)", 12.5, 0.0, "Suplidos"),
]

GUIAS = ["Guía de Prueba Uno", "Guía de Prueba Dos"]

CUENTAS = [
    ("Cuenta principal de ejemplo", "Empresa de Ejemplo S.L.", "ES00 0000 0000 0000 0000 0001",
     "Banco de Ejemplo", "EJEMESMMXXX", 1),
    ("Cuenta secundaria de ejemplo", "Empresa de Ejemplo S.L.", "ES00 0000 0000 0000 0000 0002",
     "Otro Banco de Ejemplo", "OTRXESMMXXX", 0),
]

EMPRESA = {
    "nombre": "Empresa de Ejemplo S.L.",
    "nif": "B00000000",
    "direccion": "Calle de Ejemplo 10, bajo",
    "cp": "03002",
    "poblacion": "Alicante",
    "provincia": "Alicante",
    "email": "ejemplo@ejemplo.invalid",
    "telefono": "+34 600 000 000",
    "web": "ejemplo.invalid",
    "iban": "ES00 0000 0000 0000 0000 0001",
    "banco": "Banco de Ejemplo",
    "condiciones_pago": "30 días desde fecha de factura",
    "tagline": "Datos inventados para las capturas de la interfaz",
    "direccion_modo": "completa",
}

# Un concepto de 140 caracteres, para ver en las capturas qué hace una descripción larga.
CONCEPTO_LARGO = (
    "Visita guiada de día completo con traslado en autobús, entradas incluidas, "
    "almuerzo de grupo y acompañamiento de guía oficial en dos idiomas"
)
assert len(CONCEPTO_LARGO) == 140, len(CONCEPTO_LARGO)


def _crear_proforma(conn, numero, secuencial, fecha, cliente_id, cuenta_id, estado,
                    lineas, guias, suplidos=0.0, comentarios=None, referencia=None,
                    fecha_cobro=None, pdf_previsualizado_en=None):
    base = round(sum(c * p for _, c, p, _ in lineas), 2)
    iva = round(sum(c * p * i / 100 for _, c, p, i in lineas), 2)
    total = round(base + iva, 2)
    cobrado = 1 if estado == "cobrada" else 0
    exportada = 1 if estado in ("enviada", "cobrada") else 0
    cur = conn.execute(
        """INSERT INTO proformas (numero_proforma, numero_secuencial, fecha, cliente_id,
                                  cuenta_id, estado, base, iva_total, suplidos, total,
                                  total_suplidos, comentarios, referencia, trimestre,
                                  cobrado, fecha_cobro, exportada_excel, pdf_previsualizado_en)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (numero, secuencial, fecha, cliente_id, cuenta_id, estado, base, iva, suplidos,
         total, round(total + suplidos, 2), comentarios, referencia, _trimestre(fecha),
         cobrado, fecha_cobro, exportada, pdf_previsualizado_en),
    )
    pid = cur.lastrowid
    for i, (descripcion, cantidad, precio, iva_pct) in enumerate(lineas):
        conn.execute(
            """INSERT INTO proforma_lineas (proforma_id, descripcion, cantidad, precio,
                                            porcentaje_iva, importe, fecha)
               VALUES (?,?,?,?,?,?,?)""",
            (pid, descripcion, cantidad, precio, iva_pct, round(cantidad * precio, 2),
             _fecha(30 - i)),
        )
    for gid in guias:
        conn.execute("INSERT INTO proforma_guias (proforma_id, guia_id) VALUES (?,?)", (pid, gid))
    return pid


def sembrar() -> dict:
    db.init_db()
    db.set_empresa_config(EMPRESA)
    db.set_serie_config("PRO", "{serie}-{aa}-{n}", 4)
    ids: dict[str, int] = {}
    with db.get_db() as conn:
        clientes = [
            conn.execute(
                """INSERT INTO clientes (nombre_agencia, nif_cif, direccion, cp, poblacion,
                                         provincia, email, persona_contacto, telefono)
                   VALUES (?,?,?,?,?,?,?,?,?)""", c).lastrowid
            for c in CLIENTES
        ]
        articulos = [
            conn.execute(
                "INSERT INTO articulos (codigo, descripcion, precio, porcentaje_iva, familia)"
                " VALUES (?,?,?,?,?)", a).lastrowid
            for a in ARTICULOS
        ]
        guias = [
            conn.execute("INSERT INTO guias (nombre) VALUES (?)", (g,)).lastrowid
            for g in GUIAS
        ]
        cuentas = [
            conn.execute(
                "INSERT INTO cuentas (nombre, titular, iban, banco, bic, predeterminada)"
                " VALUES (?,?,?,?,?,?)", c).lastrowid
            for c in CUENTAS
        ]

        aa = HOY.strftime("%y")
        # 1. Borrador largo: 12 líneas y un concepto de 140 caracteres (el que se mira en las capturas).
        lineas_largas = [(CONCEPTO_LARGO if i == 0 else f"Visita guiada de grupo, jornada {i + 1}",
                          1 + (i % 3), 180.0 + 10 * i, 21.0) for i in range(12)]
        ids["borrador_largo"] = _crear_proforma(
            conn, f"PRO-{aa}-0101", 101, _fecha(3), clientes[0], cuentas[0], "borrador",
            lineas_largas, guias, suplidos=87.4,
            comentarios="Borrador de ejemplo con doce líneas para ver cómo se comporta la tabla.",
            referencia="REF-EJEMPLO-12")
        # 2. Borrador corto y normal.
        ids["borrador_corto"] = _crear_proforma(
            conn, f"PRO-{aa}-0102", 102, _fecha(2), clientes[1], cuentas[0], "borrador",
            [("Visita guiada de medio día en Alicante", 2, 180.0, 21.0)], guias[:1])
        # 3 y 4. Enviadas sin cobrar.
        ids["enviada"] = _crear_proforma(
            conn, f"PRO-{aa}-0098", 98, _fecha(20), clientes[0], cuentas[0], "enviada",
            [("Visita guiada de día completo con traslado", 1, 320.0, 21.0)], guias[:1],
            comentarios="Grupo de 30 personas.")
        ids["enviada_2"] = _crear_proforma(
            conn, f"PRO-{aa}-0099", 99, _fecha(15), clientes[2], cuentas[1], "enviada",
            [("Visita guiada de medio día en Alicante", 3, 180.0, 21.0)], guias[1:],
            suplidos=45.0)
        # 5. Cobrada.
        ids["cobrada"] = _crear_proforma(
            conn, f"PRO-{aa}-0097", 97, _fecha(45), clientes[1], cuentas[0], "cobrada",
            [("Visita guiada de día completo con traslado", 2, 320.0, 21.0)], guias,
            comentarios="Cobrada por transferencia.", fecha_cobro=_fecha(10))
        # 6. Borrador con el PDF ya descargado: sale en la bandeja «¿las enviaste?»
        #    del listado y en el contador del nav.
        ids["pendiente_confirmar"] = _crear_proforma(
            conn, f"PRO-{aa}-0100", 100, _fecha(5), clientes[2], cuentas[0], "borrador",
            [("Visita guiada de medio día en Alicante", 1, 180.0, 21.0)], guias[:1],
            pdf_previsualizado_en=_fecha(4) + " 10:00:00")
        conn.execute("UPDATE series SET ultimo_numero = 102 WHERE serie = 'PRO'")

        ids["cliente"] = clientes[0]
        ids["articulo"] = articulos[0]
        ids["guia"] = guias[0]
        ids["cuenta"] = cuentas[0]
    return ids


if __name__ == "__main__":
    print(json.dumps(sembrar(), indent=1))
