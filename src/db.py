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


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        _migrate_to_multi_guia(conn)


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
