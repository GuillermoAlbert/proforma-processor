"""
Tests de interfaz: la parte del checklist de la skill `ui-lawsofux` que una
máquina puede comprobar. El resto (contraste, Fitts, Hick, «nada cambió de
sitio») se mira con `herramientas/capturas_panel.py` y se anota en
`docs/revision-ui.md`.

Sin dependencias nuevas: `html.parser` de la biblioteca estándar (el CT no
tiene html5lib y no se instala nada).

Uso (dentro de CT 104, con BD de prueba en /tmp):
    cd /mnt/empresa/proforma-admin/src && python3 -m pytest test_ui.py -v
"""
import base64
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Aislar de producción ANTES de importar db/app (leen el env al importar).
TEST_DB = '/tmp/test_ui.db'
os.environ['DB_PATH'] = TEST_DB
os.environ['PDF_DIR'] = '/tmp/test_ui_pdf'
os.environ['EXCEL_PATH'] = '/tmp/test_ui.xlsx'
os.environ['EXCEL_BACKUP_DIR'] = '/tmp/test_ui_bak'
os.environ['EXCEL_PENDING_FILE'] = '/tmp/test_ui_pendientes.json'
os.environ['EXCEL_LOCK_FILE'] = '/tmp/test_ui.lock'

SRC = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent / 'herramientas'))

import pytest  # noqa: E402

import db  # noqa: E402

AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'admin:admin').decode()}

CSS = SRC / 'static' / 'estilos.css'
PLANTILLAS = sorted((SRC / 'templates').rglob('*.html'))
FUENTES = ('lora-latin.woff2', 'lora-latin-ext.woff2',
           'inter-latin.woff2', 'inter-latin-ext.woff2')

PENDIENTE = 'pendiente: lo arregla una fase posterior de la spec de UI del 2026-09-22'


# --------------------------------------------------------------------------- #
# Aparejo: una BD de mentira con las mismas pantallas que capturan las capturas
# --------------------------------------------------------------------------- #

def _borrar_bd():
    for sufijo in ('', '-wal', '-shm'):
        try:
            os.remove(TEST_DB + sufijo)
        except FileNotFoundError:
            pass


@pytest.fixture(scope='module')
def ids():
    db.DB_PATH = TEST_DB  # el módulo db se importa una vez por proceso
    _borrar_bd()
    import datos_prueba
    return datos_prueba.sembrar()


@pytest.fixture(scope='module')
def client(ids):
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def rutas(ids) -> dict:
    """Las mismas 15 pantallas GET que captura `herramientas/capturas_panel.py`."""
    return {
        'proformas': '/proformas',
        'proforma-nueva': '/proformas/nueva',
        'proforma-editar': f"/proformas/{ids['borrador_largo']}/editar",
        'proforma-detalle': f"/proformas/{ids['cobrada']}",
        'clientes': '/clientes',
        'cliente-form': f"/clientes/{ids['cliente']}/editar",
        'articulos': '/articulos',
        'articulo-form': f"/articulos/{ids['articulo']}/editar",
        'guias': '/guias',
        'cuentas': '/cuentas',
        'cuenta-form': f"/cuentas/{ids['cuenta']}/editar",
        'config': '/config',
        'config-empresa': '/config/empresa',
        'config-numeracion': '/config/numeracion',
        'ayuda': '/ayuda',
    }


CON_FORMULARIO = ('proforma-nueva', 'proforma-editar', 'cliente-form', 'articulo-form',
                  'cuenta-form', 'config-empresa', 'config-numeracion', 'proformas', 'guias')


def _html(client, ruta: str) -> str:
    r = client.get(ruta, headers=AUTH)
    assert r.status_code == 200, f'{ruta} devolvió {r.status_code}'
    return r.get_data(as_text=True)


def _bloque_root(css: str) -> str:
    """El contenido del bloque `:root { … }`, donde deben vivir todos los colores."""
    m = re.search(r':root\s*\{(.*?)\}', css, re.S)
    return m.group(1) if m else ''


class _Arbol(HTMLParser):
    """Árbol mínimo: cada nodo es (tag, attrs, hijos, padre). Suficiente para
    preguntar «¿este input tiene un label?» y «¿esta tabla está en .table-wrap?»."""

    VACIAS = {'input', 'img', 'br', 'hr', 'meta', 'link', 'source', 'col'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = ('#raiz', {}, [], None)
        self.pila = [self.raiz]
        self.nodos = []

    def handle_starttag(self, tag, attrs):
        nodo = (tag, dict(attrs), [], self.pila[-1])
        self.pila[-1][2].append(nodo)
        self.nodos.append(nodo)
        if tag not in self.VACIAS:
            self.pila.append(nodo)

    def handle_startendtag(self, tag, attrs):
        nodo = (tag, dict(attrs), [], self.pila[-1])
        self.pila[-1][2].append(nodo)
        self.nodos.append(nodo)

    def handle_endtag(self, tag):
        for i in range(len(self.pila) - 1, 0, -1):
            if self.pila[i][0] == tag:
                del self.pila[i:]
                return


def _arbol(html: str) -> _Arbol:
    p = _Arbol()
    p.feed(html)
    return p


def _tiene_ancestro(nodo, clase: str) -> bool:
    padre = nodo[3]
    while padre is not None:
        if clase in padre[1].get('class', '').split():
            return True
        padre = padre[3]
    return False


def _ancestros(nodo):
    padre = nodo[3]
    while padre is not None:
        yield padre
        padre = padre[3]


def _descendientes(nodo):
    for hijo in nodo[2]:
        yield hijo
        yield from _descendientes(hijo)


# --------------------------------------------------------------------------- #
# 1-3, 8, 9: el CSS
# --------------------------------------------------------------------------- #

@pytest.mark.xfail(strict=True, reason=PENDIENTE + ' (Fase 2)')
def test_el_css_cabe_en_16_kb_y_no_trae_nada_de_fuera():
    assert CSS.exists(), f'no existe {CSS}'
    tamano = CSS.stat().st_size
    assert tamano <= 16384, (
        f'{CSS.name} ocupa {tamano} bytes (tope 16384). Buscar de dónde recortar '
        'antes de subir el tope, y anotar el motivo en docs/revision-ui.md.')
    css = CSS.read_text()
    assert '@import' not in css, 'el CSS no puede traer nada con @import'
    assert 'url(http' not in css, 'el CSS no puede apuntar a ningún recurso externo'
    assert ':focus-visible' in css, 'falta el foco visible (:focus-visible)'
    assert 'prefers-reduced-motion' in css, 'faltan las reglas de prefers-reduced-motion'


@pytest.mark.xfail(strict=True, reason=PENDIENTE + ' (Fase 2)')
def test_ninguna_plantilla_carga_recursos_externos():
    culpables = []
    for f in PLANTILLAS:
        texto = f.read_text()
        for patron in (r'<link[^>]+href=["\']https?:', r'<script[^>]+src=["\']https?:',
                       r'@import\s+url\(["\']?https?:'):
            if re.search(patron, texto, re.I):
                culpables.append(f'{f.relative_to(SRC)}: {patron}')
    assert not culpables, (
        'el panel se usa por Tailscale y tiene que funcionar sin salida a Internet; '
        'estas plantillas cargan algo de fuera: ' + '; '.join(culpables))


@pytest.mark.xfail(strict=True, reason=PENDIENTE + ' (Fase 2)')
def test_ningun_color_suelto_fuera_de_root():
    assert CSS.exists(), f'no existe {CSS}'
    css = CSS.read_text()
    dentro = _bloque_root(css)
    fuera = [c for c in re.findall(r'#[0-9a-fA-F]{3,8}\b', css)
             if c not in re.findall(r'#[0-9a-fA-F]{3,8}\b', dentro)]
    assert not fuera, (
        'todo color va como token en :root; sueltos por el CSS: ' + ', '.join(sorted(set(fuera))))


@pytest.mark.xfail(strict=True, reason=PENDIENTE + ' (Fase 3)')
def test_no_hay_outline_none_sin_sustituto():
    assert CSS.exists(), f'no existe {CSS}'
    css = CSS.read_text()
    culpables = []
    for m in re.finditer(r'([^{}]*)\{([^}]*)\}', css):
        selector, cuerpo = m.group(1).strip(), m.group(2)
        if not re.search(r'outline\s*:\s*(none|0)\b', cuerpo):
            continue
        # Vale si la misma regla pone un sustituto visible, o si el selector es
        # un :focus que tiene su pareja :focus-visible en otro sitio del CSS.
        if re.search(r'box-shadow\s*:(?!\s*none)', cuerpo):
            continue
        if ':focus-visible' in selector:
            continue
        culpables.append(selector)
    assert not culpables, (
        'quitar el outline sin poner nada en su sitio deja el panel sin foco visible: '
        + '; '.join(culpables))


@pytest.mark.xfail(strict=True, reason=PENDIENTE + ' (Fase 2)')
def test_las_fuentes_estan_en_local():
    faltan = [f for f in FUENTES if not (SRC / 'static' / 'fuentes' / f).exists()]
    assert not faltan, f'faltan las fuentes locales en src/static/fuentes/: {faltan}'
    assert CSS.exists(), f'no existe {CSS}'
    css = CSS.read_text()
    for familia in ('Lora', 'Inter'):
        bloques = [b for b in re.findall(r'@font-face\s*\{[^}]*\}', css, re.S) if familia in b]
        assert bloques, f'no hay @font-face para {familia}'
        assert any('/static/fuentes/' in b for b in bloques), (
            f'el @font-face de {familia} no apunta a /static/fuentes/')


# --------------------------------------------------------------------------- #
# 4-7: las pantallas
# --------------------------------------------------------------------------- #

@pytest.mark.xfail(strict=True, reason=PENDIENTE + ' (Fase 3)')
def test_las_pantallas_traen_lo_minimo_de_accesibilidad(client, ids):
    fallos = []
    for nombre, ruta in rutas(ids).items():
        html = _html(client, ruta)
        if 'lang="es"' not in html:
            fallos.append(f'{nombre}: falta lang="es"')
        n_h1 = len(re.findall(r'<h1\b', html))
        if n_h1 != 1:
            fallos.append(f'{nombre}: {n_h1} <h1> (tiene que haber exactamente uno)')
        if 'aria-live="polite"' not in html:
            fallos.append(f'{nombre}: falta el contenedor aria-live="polite" de los avisos')
        n_actual = len(re.findall(r'aria-current="page"', html))
        if n_actual != 1:
            fallos.append(f'{nombre}: aria-current="page" aparece {n_actual} veces (tiene que ser 1)')
        n_style = len(re.findall(r'<style\b', html))
        if n_style:
            fallos.append(f'{nombre}: {n_style} <style> inline (el CSS va en estilos.css)')
        for href in re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', html, re.I):
            if 'estilos.css' not in href:
                fallos.append(f'{nombre}: hoja de estilo que no es estilos.css → {href[:80]}')
    assert not fallos, '\n'.join(fallos)


@pytest.mark.xfail(strict=True, reason=PENDIENTE + ' (Fase 3)')
def test_cada_campo_tiene_etiqueta(client, ids):
    """Cada campo, con su `label for=`, su `aria-label` o su `aria-labelledby`.

    Las filas que el JS clona (`.linea-row`, `.suplido-row-tpl`) ya están en el
    HTML servido, así que se comprueban aquí mismo.
    """
    sin_tipo = {'submit', 'button', 'hidden', 'reset', 'image'}
    fallos = []
    todas = rutas(ids)
    for nombre in CON_FORMULARIO:
        arbol = _arbol(_html(client, todas[nombre]))
        etiquetados = {n[1]['for'] for n in arbol.nodos if n[0] == 'label' and 'for' in n[1]}
        for nodo in arbol.nodos:
            tag, attrs = nodo[0], nodo[1]
            if tag not in ('input', 'select', 'textarea'):
                continue
            if tag == 'input' and attrs.get('type', 'text').lower() in sin_tipo:
                continue
            if 'aria-label' in attrs or 'aria-labelledby' in attrs:
                continue
            if attrs.get('id') and attrs['id'] in etiquetados:
                continue
            # Un campo envuelto por su propio <label> también está etiquetado.
            if any(p[0] == 'label' for p in _ancestros(nodo)):
                continue
            quien = attrs.get('id') or attrs.get('name') or attrs.get('class') or tag
            fallos.append(f'{nombre}: <{tag}> sin etiqueta → {quien}')
    assert not fallos, '\n'.join(fallos)


@pytest.mark.xfail(strict=True, reason=PENDIENTE + ' (Fase 3)')
def test_cada_tabla_tiene_caption_y_marco(client, ids):
    fallos = []
    for nombre, ruta in rutas(ids).items():
        arbol = _arbol(_html(client, ruta))
        for i, tabla in enumerate([n for n in arbol.nodos if n[0] == 'table'], 1):
            if not any(h[0] == 'caption' for h in _descendientes(tabla)):
                fallos.append(f'{nombre}: tabla #{i} sin <caption>')
            if not _tiene_ancestro(tabla, 'table-wrap'):
                fallos.append(f'{nombre}: tabla #{i} fuera de un .table-wrap')
    assert not fallos, '\n'.join(fallos)


@pytest.mark.xfail(strict=True, reason=PENDIENTE + ' (Fase 3)')
def test_los_flash_llevan_icono_y_texto(client, ids):
    """Un aviso que solo se distingue por el color no se distingue."""
    categorias = {'success': 'Guardado', 'error': 'No se pudo guardar', 'warning': 'Revísalo'}
    with client.session_transaction() as sesion:
        sesion['_flashes'] = [(c, t) for c, t in categorias.items()]
    arbol = _arbol(_html(client, '/proformas'))
    listas = [n for n in arbol.nodos if n[0] == 'ul' and 'flash-list' in n[1].get('class', '')]
    assert listas, 'no se pintó la lista de avisos'
    assert listas[0][1].get('role') == 'status', 'el ul.flash-list necesita role="status"'
    assert listas[0][1].get('aria-live') == 'polite', 'el ul.flash-list necesita aria-live="polite"'

    # El primer GET se llevó los avisos por delante: hay que volver a sembrarlos.
    with client.session_transaction() as sesion:
        sesion['_flashes'] = [(c, t) for c, t in categorias.items()]
    html = _html(client, '/proformas')
    for categoria, texto in categorias.items():
        m = re.search(r'<li[^>]*flash-' + categoria + r'[^>]*>(.*?)</li>', html, re.S)
        assert m, f'no hay <li> para la categoría {categoria}'
        cuerpo = m.group(1)
        assert texto in cuerpo, f'el aviso {categoria} perdió su texto'
        assert '<svg' in cuerpo or re.search(r'[✓✕!⚠]', cuerpo), (
            f'el aviso {categoria} no lleva icono: solo el color lo distingue')
