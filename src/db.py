import os
import re
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


def _migrate_add_referencia(conn):
    """Añade proformas.referencia (texto libre opcional) si no existe. Idempotente."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(proformas)").fetchall()]
    if 'referencia' not in cols:
        conn.execute("ALTER TABLE proformas ADD COLUMN referencia TEXT")


def _migrate_add_numero_secuencial(conn):
    """Añade proformas.numero_secuencial (entero n usado al crear). Idempotente."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(proformas)").fetchall()]
    if 'numero_secuencial' not in cols:
        conn.execute("ALTER TABLE proformas ADD COLUMN numero_secuencial INTEGER")


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        _migrate_to_multi_guia(conn)
        _migrate_add_cuenta_id(conn)
        _migrate_lineas_fecha(conn)
        _migrate_add_suplidos_detalle(conn)
        _migrate_add_referencia(conn)
        _migrate_add_numero_secuencial(conn)


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
    'aviso_legal': 'Este documento es una FACTURA PROFORMA y no tiene validez fiscal. No sustituye a la factura oficial. La factura legal (Verifactu) se emitirá desde Factusol una vez confirmado el servicio.',
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


def get_setting(clave: str, default: str = '') -> str:
    """Lee un valor genérico de la tabla config. Devuelve default si no existe. Nunca lanza."""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT valor FROM config WHERE clave = ?", (clave,)
            ).fetchone()
        return row['valor'] if row and row['valor'] is not None else default
    except Exception:
        return default


def set_setting(clave: str, valor: str) -> None:
    """Guarda un valor genérico en la tabla config. Vacío elimina la clave. Nunca lanza."""
    try:
        with get_db() as conn:
            if valor:
                conn.execute(
                    "INSERT OR REPLACE INTO config (clave, valor) VALUES (?, ?)",
                    (clave, valor)
                )
            else:
                conn.execute("DELETE FROM config WHERE clave = ?", (clave,))
    except Exception:
        pass


def get_serie_config():
    return {
        'prefijo': get_setting('serie.prefijo', 'PRO'),
        'formato': get_setting('serie.formato', '{serie}-{anio}-{n}'),
        'digitos': int(get_setting('serie.digitos', '4') or '4'),
    }


def set_serie_config(prefijo, formato, digitos):
    set_setting('serie.prefijo', prefijo.strip() or 'PRO')
    set_setting('serie.formato', formato.strip() or '{serie}-{anio}-{n}')
    set_setting('serie.digitos', str(max(1, min(9, int(digitos or 4)))))


_SUFIJOS_EMPRESA = re.compile(
    r'[\s,.-]*\b(S\.?L\.?U?\.?|S\.?A\.?U?\.?|S\.?C\.?P?\.?|S\.?R\.?L\.?|'
    r'SLU|SAU|SCP|SRL|SLL|SCA|SC|SL|SA)\s*$',
    re.IGNORECASE
)


def _sanitizar_agencia(nombre):
    """Convierte un nombre de agencia en una cadena válida para numeración.
    Elimina sufijos de forma jurídica (SL, SA, S.L., etc.), quita acentos y
    convierte espacios en guiones."""
    import unicodedata
    if not nombre:
        return ''
    s = _SUFIJOS_EMPRESA.sub('', nombre.strip())
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\s+', '-', s.strip())
    s = re.sub(r'[^A-Za-z0-9-]', '', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s.upper()


_MESES_LARGO = ['enero','febrero','marzo','abril','mayo','junio',
                'julio','agosto','septiembre','octubre','noviembre','diciembre']
_MESES_CORTO = ['ene','feb','mar','abr','may','jun',
                'jul','ago','sep','oct','nov','dic']


def _aplicar_formato(cfg, anio, n, fecha=None, agencia=None):
    from datetime import date as _date
    hoy = fecha or _date.today()
    n_str = str(n).zfill(cfg['digitos'])
    mes = str(hoy.month).zfill(2)
    dd = str(hoy.day).zfill(2)
    trimestre = str((hoy.month - 1) // 3 + 1)
    mes_largo = _MESES_LARGO[hoy.month - 1]
    mes_corto = _MESES_CORTO[hoy.month - 1]
    agencia_str = _sanitizar_agencia(agencia) if agencia else ''
    try:
        return cfg['formato'].format(
            serie=cfg['prefijo'], prefijo=cfg['prefijo'],
            anio=anio, aa=str(anio)[-2:], n=n_str,
            mes=mes, mm=mes, dd=dd,
            trimestre=trimestre, tr=trimestre,
            mes_largo=mes_largo, mes_corto=mes_corto,
            agencia=agencia_str,
        )
    except (KeyError, ValueError, IndexError):
        return f"{cfg['prefijo']}-{anio}-{n_str}"


def siguiente_numero_proforma(anio, fecha=None, agencia=None):
    """Incrementa el contador y devuelve (numero_formateado, n)."""
    cfg = get_serie_config()
    serie = cfg['prefijo']
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO series (serie, anio, ultimo_numero) VALUES (?, ?, 0)",
            (serie, anio)
        )
        conn.execute(
            "UPDATE series SET ultimo_numero = ultimo_numero + 1 WHERE serie = ? AND anio = ?",
            (serie, anio)
        )
        n = conn.execute(
            "SELECT ultimo_numero FROM series WHERE serie = ? AND anio = ?",
            (serie, anio)
        ).fetchone()['ultimo_numero']
    return _aplicar_formato(cfg, anio, n, fecha=fecha, agencia=agencia), n


def recalcular_contador_serie(serie, anio):
    """Tras borrar una proforma, recalcula ultimo_numero como el MAX(numero_secuencial)
    de las proformas restantes del mismo año. Evita que el contador siga subiendo
    cuando la proforma borrada era la última."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT MAX(numero_secuencial) as mx FROM proformas
               WHERE strftime('%Y', fecha) = ? AND numero_secuencial IS NOT NULL""",
            (str(anio),)
        ).fetchone()
        mx = row['mx'] if row and row['mx'] is not None else 0
        conn.execute(
            "UPDATE series SET ultimo_numero = ? WHERE serie = ? AND anio = ?",
            (mx, serie, anio)
        )


def peek_numero_proforma(anio, fecha=None, agencia=None):
    """Returns what the next number would be without incrementing the counter."""
    cfg = get_serie_config()
    with get_db() as conn:
        row = conn.execute(
            "SELECT ultimo_numero FROM series WHERE serie = ? AND anio = ?",
            (cfg['prefijo'], anio)
        ).fetchone()
    n = (row['ultimo_numero'] if row else 0) + 1
    return _aplicar_formato(cfg, anio, n, fecha=fecha, agencia=agencia)


def set_proximo_numero(anio, proximo):
    """Sets the counter so the next auto-generated number will be `proximo`."""
    cfg = get_serie_config()
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO series (serie, anio, ultimo_numero) VALUES (?, ?, ?)",
            (cfg['prefijo'], anio, max(0, int(proximo) - 1))
        )
