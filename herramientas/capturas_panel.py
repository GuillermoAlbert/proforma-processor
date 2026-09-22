"""Capturas del panel a 390 y 1280 px, con una auditoría de desbordes.

Es la forma de revisar la interfaz de verdad: los tests dicen que el HTML es válido, no que se
lea en un móvil. Cada pantalla se captura entera a 390 px y a 1280 px, y de paso se mide lo que
no se ve a simple vista: si la página desborda de ancho, qué elemento se sale, qué objetivos de
pulsación se quedan pequeños y si alguna tabla está escondiendo columnas tras el scroll.

**El navegador corre en el host** (el CT 104 tiene 1 GB y no tiene Chromium), contra el
**servidor de pruebas del CT en :5124**, que sirve datos inventados. Nunca contra :5114, que es
producción: ni la base real, ni el Excel fiscal, ni los PDF de verdad se abren aquí.

    pct exec 104 -- bash -lc '/mnt/empresa/proforma-admin/herramientas/servidor_pruebas.sh arrancar'
    /root/.venv-capturas/bin/python herramientas/capturas_panel.py antes
    /root/.venv-capturas/bin/python herramientas/capturas_panel.py despues --solo proformas,proforma-nueva
    /root/.venv-capturas/bin/python herramientas/capturas_panel.py --sonda /proformas/nueva
    pct exec 104 -- bash -lc '/mnt/empresa/proforma-admin/herramientas/servidor_pruebas.sh parar'

Deja las imágenes en /tmp/capturas-proformas/<sufijo>/ del host, con un informe.json. Para mirar
una captura larga a trozos: `--recortar fichero.png 0 1500` guarda esa franja al lado.

Si el entorno no existe:
    python3 -m venv /root/.venv-capturas
    /root/.venv-capturas/bin/pip install playwright pillow
    /root/.venv-capturas/bin/playwright install --with-deps chromium

Memoria: el host lleva el LLM del CT 110 cargado. Comprobar `free -m` antes; un solo navegador y
un contexto cada vez, y se cierra todo al terminar. No lanzar dos a la vez.

La contraseña del servidor de pruebas se genera en cada arranque, se lee del CT y no se imprime.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# El formato de <input type="date"> lo pinta el navegador con SU idioma, no con
# el de la página: sin esto las capturas enseñan 09/22/2026 y parece un fallo
# del panel. Manda el entorno del proceso de Chromium, no el `locale` del
# contexto ni el `--lang` de lanzamiento (probado: solo el entorno funciona).
ENTORNO = {**os.environ, "LANG": "es_ES.UTF-8", "LANGUAGE": "es_ES", "LC_ALL": "es_ES.UTF-8"}

BASE = "http://192.168.18.150:5124"
USUARIO = "capturas"
VISTAS = {"movil": (390, 844), "escritorio": (1280, 900)}
ESQUEMAS = ("light",)  # sin modo oscuro (decisión del usuario, 2026-09-22)
DESTINO_RAIZ = Path("/tmp/capturas-proformas")

AUDITORIA = """
() => {
  const w = document.documentElement.clientWidth;
  const nombre = el => el.tagName.toLowerCase() +
    (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
  const fuera = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('.table-wrap') || el.closest('dialog[open]')) continue;
    const r = el.getBoundingClientRect();
    if (r.width && (r.right > w + 1 || r.left < -1)) fuera.push(nombre(el) + ' ' + Math.round(r.left) + '-' + Math.round(r.right));
  }
  const pequenos = [];
  for (const el of document.querySelectorAll('a, button, input:not([type=hidden]), select, summary, textarea')) {
    if (el.closest('dialog:not([open])')) continue;
    const r = el.getBoundingClientRect();
    if (r.width && r.height && (r.height < 24 || r.width < 24)) pequenos.push(nombre(el) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  }
  return {
    scrollWidth: document.documentElement.scrollWidth, clientWidth: w,
    desborda: document.documentElement.scrollWidth > w,
    fuera: fuera.slice(0, 20), pequenos: pequenos.slice(0, 20),
    tablas: [...document.querySelectorAll('.table-wrap')].map(t => ({scroll: t.scrollWidth, ancho: t.clientWidth})),
  };
}
"""

SONDA = """
() => { const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('nav') || el.closest('.table-wrap') || el.closest('dialog[open]')) continue;
    const r = el.getBoundingClientRect();
    if (r.right > document.documentElement.clientWidth + 2)
      out.push(el.tagName + '.' + el.className + ' ' + Math.round(r.left) + '-' + Math.round(r.right));
  }
  return out.slice(0, 15); }
"""


def _del_ct(fichero: str) -> str:
    """Lee un fichero del servidor de pruebas dentro del CT 104."""
    salida = subprocess.run(
        ["pct", "exec", "104", "--", "cat", f"/tmp/capturas-proformas/{fichero}"],
        capture_output=True, text=True, check=False)
    if salida.returncode != 0 or not salida.stdout.strip():
        raise SystemExit(
            f"no se pudo leer /tmp/capturas-proformas/{fichero} del CT 104. "
            "¿Está arrancado el servidor de pruebas? "
            "pct exec 104 -- bash -lc '/mnt/empresa/proforma-admin/herramientas/servidor_pruebas.sh arrancar'")
    return salida.stdout.strip()


def clave_de_pruebas() -> str:
    """La contraseña aleatoria del servidor de pruebas. No se imprime nunca."""
    return _del_ct("clave")


def rutas_de_ejemplo() -> dict[str, str]:
    """Una pantalla de cada clase, con los ids de la base de mentira sembrada."""
    ids = json.loads(_del_ct("ids.json"))
    return {
        "proformas": "/proformas",
        "proforma-nueva": "/proformas/nueva",
        "proforma-editar": f"/proformas/{ids['borrador_largo']}/editar",
        "proforma-detalle": f"/proformas/{ids['cobrada']}",
        "clientes": "/clientes",
        "cliente-form": f"/clientes/{ids['cliente']}/editar",
        "articulos": "/articulos",
        "articulo-form": f"/articulos/{ids['articulo']}/editar",
        "guias": "/guias",
        "cuentas": "/cuentas",
        "cuenta-form": f"/cuentas/{ids['cuenta']}/editar",
        "config": "/config",
        "config-empresa": "/config/empresa",
        "config-numeracion": "/config/numeracion",
        "ayuda": "/ayuda",
    }


def ruta_modal_cobrar() -> str:
    """El detalle de una enviada, donde vive el botón que abre el diálogo de cobrar."""
    return f"/proformas/{json.loads(_del_ct('ids.json'))['enviada']}"


def _contexto(navegador, vista: str, ancho: int, alto: int, esquema: str, clave: str):
    # locale es-ES para el Accept-Language y el JS (el widget de fecha lo
    # arregla ENTORNO, arriba).
    return navegador.new_context(
        viewport={"width": ancho, "height": alto}, color_scheme=esquema,
        device_scale_factor=1, is_mobile=vista == "movil", has_touch=vista == "movil",
        locale="es-ES", timezone_id="Europe/Madrid",
        http_credentials={"username": USUARIO, "password": clave})


def capturar(sufijo: str, solo: list[str] | None) -> None:
    from playwright.sync_api import sync_playwright

    destino = DESTINO_RAIZ / sufijo
    destino.mkdir(parents=True, exist_ok=True)
    clave = clave_de_pruebas()
    rutas = rutas_de_ejemplo()
    modal = ruta_modal_cobrar()
    informe: dict[str, dict] = {}
    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--lang=es-ES"], env=ENTORNO)
        for esquema in ESQUEMAS:
            for vista, (ancho, alto) in VISTAS.items():
                ctx = _contexto(navegador, vista, ancho, alto, esquema, clave)
                pagina = ctx.new_page()
                for nombre, ruta in rutas.items():
                    if solo and nombre not in solo:
                        continue
                    pagina.goto(BASE + ruta)
                    pagina.wait_for_load_state("networkidle")
                    pagina.screenshot(path=str(destino / f"{nombre}-{vista}-{esquema}.png"), full_page=True)
                    informe[f"{nombre}-{vista}-{esquema}"] = pagina.evaluate(AUDITORIA)
                if not solo or "modal-cobrar" in (solo or []):
                    pagina.goto(BASE + modal)
                    pagina.wait_for_load_state("networkidle")
                    boton = pagina.locator("[data-cobrar-url]").first
                    if boton.count():
                        boton.scroll_into_view_if_needed()
                        # click() del propio elemento: el click de Playwright es por
                        # coordenadas y en móvil la cabecera fija se le pone delante.
                        boton.evaluate("b => b.click()")
                        pagina.wait_for_timeout(300)
                        pagina.screenshot(path=str(destino / f"modal-cobrar-{vista}-{esquema}.png"))
                        informe[f"modal-cobrar-{vista}-{esquema}"] = pagina.evaluate(AUDITORIA)
                ctx.close()
        navegador.close()
    (destino / "informe.json").write_text(json.dumps(informe, indent=1, ensure_ascii=False))
    problemas = 0
    for clave_informe, d in informe.items():
        avisos = []
        if d["desborda"]:
            avisos.append(f"DESBORDA {d['scrollWidth']}>{d['clientWidth']}")
        if d["fuera"]:
            avisos.append("fuera: " + "; ".join(d["fuera"][:5]))
        if d["pequenos"]:
            avisos.append("pequeños: " + "; ".join(d["pequenos"][:5]))
        if avisos:
            problemas += 1
            print(clave_informe, "->", " | ".join(avisos))
    print(f"hecho: {destino} ({len(informe)} capturas, {problemas} con avisos)")


def sondar(ruta: str) -> None:
    """Qué elementos se salen del ancho a 390 px en una ruta concreta."""
    from playwright.sync_api import sync_playwright

    clave = clave_de_pruebas()
    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--lang=es-ES"], env=ENTORNO)
        ctx = _contexto(navegador, "movil", 390, 844, "light", clave)
        pagina = ctx.new_page()
        pagina.goto(BASE + ruta)
        pagina.wait_for_load_state("networkidle")
        for linea in pagina.evaluate(SONDA):
            print(linea)
        navegador.close()


def recortar(fichero: str, y0: int, y1: int) -> None:
    from PIL import Image

    imagen = Image.open(fichero)
    salida = fichero.replace(".png", f"-{y0}.png")
    imagen.crop((0, y0, imagen.width, min(y1, imagen.height))).save(salida)
    print(salida, imagen.size)


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("sufijo", nargs="?", default="capturas",
                        help="carpeta dentro de /tmp/capturas-proformas")
    parser.add_argument("--solo", help="pantallas a capturar, separadas por comas (proformas,clientes,…)")
    parser.add_argument("--sonda", metavar="RUTA", help="listar lo que se sale del ancho en esa ruta")
    parser.add_argument("--recortar", nargs=3, metavar=("PNG", "Y0", "Y1"), help="guardar una franja")
    args = parser.parse_args(argv)
    if args.recortar:
        recortar(args.recortar[0], int(args.recortar[1]), int(args.recortar[2]))
    elif args.sonda:
        sondar(args.sonda)
    else:
        capturar(args.sufijo, args.solo.split(",") if args.solo else None)


if __name__ == "__main__":
    main(sys.argv[1:])
