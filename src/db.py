import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get('DB_PATH', '/mnt/empresa/proformas.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_agencia TEXT NOT NULL,
    nif_cif TEXT,
    direccion TEXT,
    cp TEXT,
    poblacion TEXT,
    provincia TEXT,
    email TEXT,
    telefono TEXT,
    codigo_factusol TEXT
);
CREATE TABLE IF NOT EXISTS articulos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT,
    descripcion TEXT NOT NULL,
    precio REAL DEFAULT 0,
    porcentaje_iva REAL DEFAULT 21,
    familia TEXT
);
CREATE TABLE IF NOT EXISTS guias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proformas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_proforma TEXT UNIQUE NOT NULL,
    fecha TEXT NOT NULL,
    cliente_id INTEGER REFERENCES clientes(id),
    estado TEXT DEFAULT 'borrador',
    base REAL DEFAULT 0,
    iva_total REAL DEFAULT 0,
    suplidos REAL DEFAULT 0,
    total REAL DEFAULT 0,
    total_suplidos REAL DEFAULT 0,
    comentarios TEXT,
    ruta_pdf TEXT,
    numero_factura TEXT,
    trimestre INTEGER,
    cobrado INTEGER DEFAULT 0,
    exportada_excel INTEGER DEFAULT 0,
    exportada_factusol INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS proforma_guias (
    proforma_id INTEGER NOT NULL REFERENCES proformas(id) ON DELETE CASCADE,
    guia_id INTEGER NOT NULL REFERENCES guias(id),
    PRIMARY KEY (proforma_id, guia_id)
);
CREATE TABLE IF NOT EXISTS proforma_lineas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proforma_id INTEGER NOT NULL REFERENCES proformas(id) ON DELETE CASCADE,
    articulo_id INTEGER REFERENCES articulos(id),
    descripcion TEXT NOT NULL,
    cantidad REAL DEFAULT 1,
    precio REAL DEFAULT 0,
    porcentaje_iva REAL DEFAULT 21,
    importe REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS series (
    serie TEXT NOT NULL,
    anio INTEGER NOT NULL,
    ultimo_numero INTEGER DEFAULT 0,
    PRIMARY KEY (serie, anio)
);
CREATE TABLE IF NOT EXISTS cuentas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    titular TEXT,
    iban TEXT,
    banco TEXT,
    bic TEXT,
    predeterminada INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS config (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_to_multi_guia(conn):
    """Migra proformas.guia_id → proforma_guias. Idempotente."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(proformas)").fetchall()]
    if 'guia_id' not in cols:
        return
    conn.execute("""
        INSERT OR IGNORE INTO proforma_guias (proforma_id, guia_id)
        SELECT id, guia_id FROM proformas WHERE guia_id IS NOT NULL
    """)
    conn.execute("""
        CREATE TABLE proformas_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_proforma TEXT UNIQUE NOT NULL,
            fecha TEXT NOT NULL,
            cliente_id INTEGER REFERENCES clientes(id),
            estado TEXT DEFAULT 'borrador',
            base REAL DEFAULT 0,
            iva_total REAL DEFAULT 0,
            suplidos REAL DEFAULT 0,
            total REAL DEFAULT 0,
            total_suplidos REAL DEFAULT 0,
            comentarios TEXT,
            ruta_pdf TEXT,
            numero_factura TEXT,
            trimestre INTEGER,
            cobrado INTEGER DEFAULT 0,
            exportada_excel INTEGER DEFAULT 0,
            exportada_factusol INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        INSERT INTO proformas_new
        SELECT id, numero_proforma, fecha, cliente_id, estado, base, iva_total,
               suplidos, total, total_suplidos, comentarios, ruta_pdf,
               numero_factura, trimestre, cobrado, exportada_excel, exportada_factusol
        FROM proformas
    """)
    conn.execute("DROP TABLE proformas")
    conn.execute("ALTER TABLE proformas_new RENAME TO proformas")


def _migrate_add_cuenta_id(conn):
    """Añade proformas.cuenta_id (FK a cuentas) si no existe. Idempotente."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(proformas)").fetchall()]
    if 'cuenta_id' not in cols:
        conn.execute("ALTER TABLE proformas ADD COLUMN cuenta_id INTEGER REFERENCES cuentas(id)")


def _migrate_lineas_fecha(conn):
    """Añade proforma_lineas.fecha (TEXT, opcional) si no existe. Idempotente."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(proforma_lineas)").fetchall()]
    if 'fecha' not in cols:
        conn.execute("ALTER TABLE proforma_lineas ADD COLUMN fecha TEXT")


def _migrate_add_suplidos_detalle(conn):
    """Añade proformas.suplidos_detalle (JSON de ítems) si no existe. Idempotente."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(proformas)").fetchall()]
    if 'suplidos_detalle' not in cols:
        conn.execute("ALTER TABLE proformas ADD COLUMN suplidos_detalle TEXT")


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        _migrate_to_multi_guia(conn)
        _migrate_add_cuenta_id(conn)
        _migrate_lineas_fecha(conn)
        _migrate_add_suplidos_detalle(conn)


_EMPRESA_DEFAULTS = {
    'nombre': 'Guías de Alicante',
    'nif': 'XXXXXXXXX',
    'direccion': 'Alicante',
    'cp': '03001',
    'poblacion': 'Alicante',
    'provincia': 'Alicante',
    'email': 'info@guiasdealicante.es',
    'telefono': '+34 661 639 964',
    'web': 'guiasdealicante.es',
    'iban': 'ES00 0000 0000 0000 0000 0000',
    'banco': 'Entidad bancaria',
    'condiciones_pago': '30 días desde fecha de factura',
    'tagline': 'Guías oficiales de la Comunidad Valenciana desde 1992',
    'mostrar_direccion': '1',
}


def get_empresa_config():
    """Returns empresa dict, merging DB overrides over hardcoded defaults."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT clave, valor FROM config WHERE clave LIKE 'empresa.%'"
        ).fetchall()
    result = dict(_EMPRESA_DEFAULTS)
    for row in rows:
        key = row['clave'][len('empresa.'):]
        if row['valor'] is not None:
            result[key] = row['valor']
    return result


def set_empresa_config(fields):
    """Saves empresa fields to config table. Empty string deletes the key (reverts to default)."""
    with get_db() as conn:
        for k, v in fields.items():
            if v:
                conn.execute(
                    "INSERT OR REPLACE INTO config (clave, valor) VALUES (?, ?)",
                    (f'empresa.{k}', v)
                )
            else:
                conn.execute("DELETE FROM config WHERE clave = ?", (f'empresa.{k}',))


def siguiente_numero_proforma(serie='PRO', anio=2026):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO series (serie, anio, ultimo_numero) VALUES (?, ?, 0)",
            (serie, anio)
        )
        conn.execute(
            "UPDATE series SET ultimo_numero = ultimo_numero + 1 WHERE serie = ? AND anio = ?",
            (serie, anio)
        )
        row = conn.execute(
            "SELECT ultimo_numero FROM series WHERE serie = ? AND anio = ?",
            (serie, anio)
        ).fetchone()
        n = row['ultimo_numero']
    return f"{serie}-{anio}-{n:04d}"
