"""
clientes_lookup.py — consulta VIES para autocompletar el formulario de clientes.

Sin dependencias externas: solo stdlib (urllib, json, re).
"""

import re
import json
import urllib.request
import urllib.error
import sys

# ── Provincias por prefijo CP ────────────────────────────────────────────────

PROVINCIAS_POR_CP = {
    "01": "Álava",
    "02": "Albacete",
    "03": "Alicante",
    "04": "Almería",
    "05": "Ávila",
    "06": "Badajoz",
    "07": "Illes Balears",
    "08": "Barcelona",
    "09": "Burgos",
    "10": "Cáceres",
    "11": "Cádiz",
    "12": "Castellón",
    "13": "Ciudad Real",
    "14": "Córdoba",
    "15": "A Coruña",
    "16": "Cuenca",
    "17": "Girona",
    "18": "Granada",
    "19": "Guadalajara",
    "20": "Gipuzkoa",
    "21": "Huelva",
    "22": "Huesca",
    "23": "Jaén",
    "24": "León",
    "25": "Lleida",
    "26": "La Rioja",
    "27": "Lugo",
    "28": "Madrid",
    "29": "Málaga",
    "30": "Murcia",
    "31": "Navarra",
    "32": "Ourense",
    "33": "Asturias",
    "34": "Palencia",
    "35": "Las Palmas",
    "36": "Pontevedra",
    "37": "Salamanca",
    "38": "Santa Cruz de Tenerife",
    "39": "Cantabria",
    "40": "Segovia",
    "41": "Sevilla",
    "42": "Soria",
    "43": "Tarragona",
    "44": "Teruel",
    "45": "Toledo",
    "46": "Valencia",
    "47": "Valladolid",
    "48": "Bizkaia",
    "49": "Zamora",
    "50": "Zaragoza",
    "51": "Ceuta",
    "52": "Melilla",
}


def provincia_desde_cp(cp: str) -> str:
    """Devuelve el nombre de provincia para un CP de 5 dígitos, o '' si no se reconoce."""
    prefix = str(cp).strip()[:2]
    return PROVINCIAS_POR_CP.get(prefix, "")


# ── Normalización y validación ───────────────────────────────────────────────

def normalizar_cif(s: str) -> str:
    """Uppercase, elimina espacios, puntos y guiones.
    Si empieza por 'ES' seguido del NIF/CIF nacional, elimina el prefijo de país.
    """
    s = s.upper().replace(" ", "").replace(".", "").replace("-", "")
    if s.startswith("ES") and len(s) > 2:
        s = s[2:]
    return s


def validar_cif(cif: str) -> bool:
    """Valida NIF (DNI), NIE y CIF español con su dígito/letra de control.
    Devuelve False para entradas claramente incorrectas; es intencionalmente
    permisivo (no rechaza entradas válidas por razones de formato secundario).
    """
    if not cif:
        return False
    cif = cif.upper().strip()

    NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

    # ── DNI/NIF: 8 dígitos + letra ──────────────────────────────────────────
    m = re.fullmatch(r'(\d{8})([A-Z])', cif)
    if m:
        num, letra = int(m.group(1)), m.group(2)
        return letra == NIF_LETTERS[num % 23]

    # ── NIE: X/Y/Z + 7 dígitos + letra ─────────────────────────────────────
    m = re.fullmatch(r'([XYZ])(\d{7})([A-Z])', cif)
    if m:
        inicio, digits, letra = m.group(1), m.group(2), m.group(3)
        substitucion = {'X': '0', 'Y': '1', 'Z': '2'}[inicio]
        num = int(substitucion + digits)
        return letra == NIF_LETTERS[num % 23]

    # ── CIF de entidad: letra + 7 dígitos + control (dígito o letra) ────────
    m = re.fullmatch(r'([ABCDEFGHJNPQRSUVW])(\d{7})([0-9A-Z])', cif)
    if m:
        tipo, digits, control = m.group(1), m.group(2), m.group(3)
        total = 0
        for i, d in enumerate(digits):
            n = int(d)
            if (i + 1) % 2 == 0:
                # posiciones pares (0-indexed: 1,3,5) → sumar directamente
                total += n
            else:
                # posiciones impares → doblar y sumar dígitos del resultado
                doble = n * 2
                total += doble // 10 + doble % 10
        control_digit = (10 - (total % 10)) % 10
        control_letter = "JABCDEFGHI"[control_digit]

        # Tipos que SOLO admiten letra
        if tipo in ('P', 'Q', 'S', 'K', 'W'):
            return control == control_letter
        # Tipos que SOLO admiten dígito
        if tipo in ('A', 'B', 'E', 'H'):
            return control == str(control_digit)
        # Resto: admite cualquiera de las dos
        return control == str(control_digit) or control == control_letter

    return False


# ── Consulta VIES ────────────────────────────────────────────────────────────

_VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/ms/ES/vat/{numero}"


def consultar_vies(cif: str) -> dict:
    """Llama a VIES REST API para el número nacional español indicado (sin prefijo ES).
    Devuelve {"ok": True, "isValid": bool, "name": str, "address": str}
    o {"ok": False, "error": "<mensaje corto>"} en caso de error.
    Nunca lanza excepciones.
    """
    numero = normalizar_cif(cif)  # por si llega con ES-prefijo
    url = _VIES_URL.format(numero=numero)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "proforma-admin/1.0 (contact@guiasdealicante.com)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        return {
            "ok": True,
            "isValid": bool(data.get("isValid", False)),
            "name": data.get("name") or "",
            "address": data.get("address") or "",
        }
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"Red: {e.reason}"}
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return {"ok": False, "error": f"Respuesta inesperada: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:80]}


# ── Parseo de dirección ──────────────────────────────────────────────────────

def parsear_direccion(address: str) -> dict:
    """Extrae campos de una dirección española devuelta por VIES (puede contener \\n).
    Devuelve {"direccion": str, "cp": str, "poblacion": str, "provincia": str}.
    Nunca lanza excepciones.
    """
    empty = {"direccion": "", "cp": "", "poblacion": "", "provincia": ""}
    if not address or not address.strip():
        return empty

    try:
        # Normalizar separadores: reemplazar newlines por espacios para búsqueda
        flat = re.sub(r'[\r\n]+', ' ', address)

        # Buscar CP de 5 dígitos (evitar que forme parte de un número mayor)
        cp_match = re.search(r'\b(\d{5})\b', flat)
        if not cp_match:
            # Sin CP: devolver todo como dirección
            direccion = re.sub(r'\s+', ' ', flat).strip().strip(',').strip('-').strip()
            return {**empty, "direccion": _title(direccion)}

        cp = cp_match.group(1)
        pos = cp_match.start()

        # Texto antes del CP → dirección
        antes = flat[:pos]
        direccion = re.sub(r'\s+', ' ', antes).strip().rstrip(',-').strip()

        # Texto después del CP → población (+ posible "(PROVINCIA)")
        despues = flat[cp_match.end():].strip()
        # Quitar parentéticos tipo "(ALICANTE)" o "ALICANTE"
        paren_match = re.search(r'\s*\(([^)]+)\)\s*$', despues)
        paren_text = ""
        if paren_match:
            paren_text = paren_match.group(1).strip()
            despues = despues[:paren_match.start()].strip()

        poblacion = re.sub(r'\s+', ' ', despues).strip().rstrip(',-').strip()

        # Provincia: primero desde tabla CP, luego desde el parentético
        provincia = provincia_desde_cp(cp)
        if not provincia and paren_text:
            provincia = _title(paren_text)

        return {
            "direccion": _title(direccion),
            "cp": cp,
            "poblacion": _title(poblacion),
            "provincia": _title(provincia) if provincia else "",
        }
    except Exception:
        return empty


def _title(s: str) -> str:
    """Title-case básico que respeta partículas comunes en topónimos españoles."""
    if not s:
        return s
    # Palabras que NO se ponen en mayúscula cuando van en medio
    MINUSCULAS = {'de', 'del', 'la', 'las', 'los', 'el', 'y', 'i', 'a', 'en'}
    palabras = s.title().split()
    resultado = []
    for i, p in enumerate(palabras):
        if i > 0 and p.lower() in MINUSCULAS:
            resultado.append(p.lower())
        else:
            resultado.append(p)
    return ' '.join(resultado)


# ── Consulta einforma ────────────────────────────────────────────────────────

_EINFORMA_URL = "https://www.einforma.com/servlet/app/portal/ENTP/prod/ETIQUETA_EMPRESA/nif/{cif}"
_BROWSER_UA   = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def consultar_einforma_url(url: str) -> dict:
    """GET de una URL arbitraria de einforma con User-Agent de navegador + decodificación ISO-8859-1.
    Devuelve {"ok": True, "html": str} o {"ok": False, "error": str}.
    Nunca lanza excepciones.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _BROWSER_UA})
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
        html = raw.decode("iso-8859-1", errors="replace")
        return {"ok": True, "html": html}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"Red: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:80]}


def consultar_einforma(cif: str) -> dict:
    """GET einforma para el CIF dado (sin prefijo ES).
    Devuelve {"ok": True, "html": str} o {"ok": False, "error": str}.
    Nunca lanza excepciones.
    """
    url = _EINFORMA_URL.format(cif=cif)
    return consultar_einforma_url(url)


_EINFORMA_LISTADO_URL = (
    "https://www.einforma.com/servlet/app/portal/ENTP/prod/LISTADO_EMPRESAS"
    "/searchccaa/empresas/razonsocial/{nombre}"
)


def buscar_einforma_slug(nombre: str) -> "str | None":
    """Busca 'nombre' en el listado de einforma y devuelve la primera URL de ficha
    del tipo https://www.einforma.com/informacion-empresa/{slug}, o None si no la encuentra.
    Nunca lanza excepciones.
    """
    try:
        import urllib.parse
        nombre_enc = urllib.parse.quote(nombre.strip(), safe='')
        url = _EINFORMA_LISTADO_URL.format(nombre=nombre_enc)
        resp = consultar_einforma_url(url)
        if not resp["ok"]:
            return None
        html = resp["html"]
        # Buscar la primera href de ficha de empresa
        m = re.search(r'href="(https://www\.einforma\.com/informacion-empresa/[^"]+)"', html)
        if m:
            return m.group(1)
        return None
    except Exception:
        return None


def _strip_tags(text: str) -> str:
    """Elimina etiquetas HTML de una cadena."""
    return re.sub(r'<[^>]+>', ' ', text)


def parsear_einforma(html: str) -> dict:
    """Extrae nombre_agencia, CIF y dirección del HTML de einforma.
    Reutiliza parsear_direccion() y provincia_desde_cp() / _title().
    Devuelve {"nombre_agencia","nif_cif","direccion","cp","poblacion","provincia"} (vacíos si no encuentra).
    Nunca lanza excepciones.
    """
    empty = {"nombre_agencia": "", "nif_cif": "", "direccion": "", "cp": "", "poblacion": "", "provincia": ""}
    if not html:
        return empty

    try:
        # Decodificar a UTF-8 si llegó como bytes; si ya es str, reencoding no aplica.
        # El HTML fue decodificado de ISO-8859-1; re-encodear+decodificar a utf-8 no ayuda.
        # Trabajamos directamente con la cadena.

        # — Nombre: dataLayer JS
        nombre_agencia = ""
        m = re.search(r"'nombreEmpresa':\s*'([^']*)'", html)
        if m:
            nombre_agencia = _title(m.group(1).strip())

        # — CIF: microdata itemprop="taxID" (ignorar placeholder A00000000)
        nif_cif = ""
        m_cif = re.search(r'itemprop="taxID">\s*([A-W][0-9]{8})', html)
        if m_cif:
            candidate = m_cif.group(1)
            if candidate != "A00000000":
                nif_cif = candidate

        # — Dirección: el layout de einforma tiene dos celdas separadas:
        #   "Domicilio social actual:" → calle (+ enlace Ver Mapa en misma celda)
        #   "Localidad:"              → CP POBLACION (PROVINCIA)
        addr_fields = {"direccion": "", "cp": "", "poblacion": "", "provincia": ""}
        anchor = "Domicilio social actual:"
        idx = html.find(anchor)
        if idx != -1:
            # Bloque completo para la búsqueda (hasta 1500 chars)
            zona = html[idx: idx + 1500]

            # Decodificar entidades HTML en la zona
            def _decode_ents(s):
                s = s.replace('&ntilde;', 'ñ').replace('&Ntilde;', 'Ñ')
                s = s.replace('&eacute;', 'é').replace('&Eacute;', 'É')
                s = s.replace('&aacute;', 'á').replace('&Aacute;', 'Á')
                s = s.replace('&iacute;', 'í').replace('&Iacute;', 'Í')
                s = s.replace('&oacute;', 'ó').replace('&Oacute;', 'Ó')
                s = s.replace('&uacute;', 'ú').replace('&Uacute;', 'Ú')
                s = s.replace('&amp;', '&').replace('&nbsp;', ' ')
                return s
            zona = _decode_ents(zona)

            # Calle: texto hasta el primer enlace/tag (antes de "Ver Mapa")
            street_blob = zona[len(anchor):]
            street_text = re.sub(r'\s+', ' ', _strip_tags(
                re.split(r'Ver Mapa|<a ', street_blob, maxsplit=1)[0]
            )).strip()

            # Localidad: celda del row siguiente — buscar "Localidad:" y extraer su td
            loc_match = re.search(
                r'Localidad:</strong></td><td[^>]*>([^<]+)', zona
            )
            localidad_text = ""
            if loc_match:
                localidad_text = _decode_ents(loc_match.group(1).strip())

            # Combinar calle + localidad como una sola cadena de dirección para parsear
            full_addr = (street_text.rstrip(', ') + ' ' + localidad_text).strip()
            if full_addr:
                addr_fields = parsear_direccion(full_addr)

        # Completar provincia desde CP si falta
        if not addr_fields["provincia"] and addr_fields["cp"]:
            addr_fields["provincia"] = provincia_desde_cp(addr_fields["cp"])

        return {
            "nombre_agencia": nombre_agencia,
            "nif_cif": nif_cif,
            "direccion": addr_fields["direccion"],
            "cp": addr_fields["cp"],
            "poblacion": addr_fields["poblacion"],
            "provincia": addr_fields["provincia"],
        }
    except Exception:
        return empty


# ── Extracción con DeepSeek ──────────────────────────────────────────────────

_DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def extraer_con_deepseek(texto: str, api_key: str) -> dict:
    """Llama a DeepSeek para extraer campos de empresa del texto de la página.
    Devuelve {"nombre_agencia","direccion","cp","poblacion","provincia"} (vacíos en cualquier fallo).
    Nunca lanza excepciones.
    """
    empty = {"nombre_agencia": "", "direccion": "", "cp": "", "poblacion": "", "provincia": ""}
    if not texto or not api_key:
        return empty

    try:
        prompt = (
            "Extrae del siguiente texto de una página de empresa española un objeto JSON con "
            "exactamente estas claves: nombre_agencia, direccion, cp, poblacion. "
            "Sin inventar; solo campos presentes en el texto. Valores string vacío si no aparecen.\n\n"
            + texto[:3000]
        )
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }).encode("utf-8")
        req = urllib.request.Request(
            _DEEPSEEK_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "proforma-admin/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        nombre_agencia = _title(str(parsed.get("nombre_agencia") or "").strip())
        cp = str(parsed.get("cp") or "").strip()
        addr_fields = {
            "direccion": str(parsed.get("direccion") or "").strip(),
            "cp": cp,
            "poblacion": _title(str(parsed.get("poblacion") or "").strip()),
            "provincia": provincia_desde_cp(cp) if cp else "",
        }
        return {
            "nombre_agencia": nombre_agencia,
            **addr_fields,
        }
    except Exception:
        return empty


# ── Orquestador principal ────────────────────────────────────────────────────

def buscar_cliente(cif: str, deepseek_api_key: str = None) -> dict:
    """Busca un cliente por CIF/NIF en VIES y, para España, completa desde einforma.

    Retorna:
        {
            "ok": bool,
            "message": str,
            "fields": {"nombre_agencia", "direccion", "cp", "poblacion", "provincia"}
        }
    """
    empty_fields = {
        "nombre_agencia": "",
        "direccion": "",
        "cp": "",
        "poblacion": "",
        "provincia": "",
    }

    normalizado = normalizar_cif(cif)
    if not normalizado:
        return {"ok": False, "message": "CIF vacío.", "fields": empty_fields}

    # Validación local (no bloqueante: aviso pero continúa)
    aviso_validacion = ""
    if not validar_cif(normalizado):
        aviso_validacion = f"Aviso: '{normalizado}' no supera la validación local del dígito de control. "

    # Consulta VIES
    vies = consultar_vies(normalizado)
    if not vies["ok"]:
        msg = f"{aviso_validacion}No se pudo consultar VIES: {vies['error']}."
        return {"ok": False, "message": msg, "fields": empty_fields}

    if not vies["isValid"]:
        msg = (
            f"{aviso_validacion}"
            "CIF no encontrado en el registro VIES (puede no estar dado de alta para IVA intracomunitario)."
        )
        return {"ok": False, "message": msg, "fields": empty_fields}

    # CIF válido en VIES — extraer campos.
    # España enmascara nombre/dirección: VIES los devuelve como "---" (o vacío).
    nombre_raw = vies["name"].strip()
    address_raw = vies["address"].strip()
    if set(nombre_raw) <= {"-", "—", " "}:
        nombre_raw = ""

    nombre_agencia = _title(nombre_raw) if nombre_raw else ""
    addr_fields = parsear_direccion(address_raw)

    fuente = "VIES"
    algun_dato_vies = bool(nombre_agencia or addr_fields["cp"] or addr_fields["direccion"])

    # Si VIES no aportó nombre/dirección (España los enmascara), intentar einforma
    if not algun_dato_vies:
        einforma_resp = consultar_einforma(normalizado)
        if einforma_resp["ok"]:
            ei = parsear_einforma(einforma_resp["html"])
            nombre_agencia   = ei["nombre_agencia"]  or nombre_agencia
            if ei["direccion"] or ei["cp"]:
                addr_fields = {
                    "direccion": ei["direccion"],
                    "cp":        ei["cp"],
                    "poblacion": ei["poblacion"],
                    "provincia": ei["provincia"],
                }
            fuente = "einforma"

        # Si todavía faltan campos clave y hay API key de DeepSeek, usar IA
        if deepseek_api_key and (not nombre_agencia or not addr_fields["direccion"]):
            html_para_ds = einforma_resp.get("html", "") if einforma_resp["ok"] else ""
            texto_plano = re.sub(r'\s+', ' ', _strip_tags(html_para_ds)).strip() if html_para_ds else ""
            if texto_plano:
                ds = extraer_con_deepseek(texto_plano, deepseek_api_key)
                nombre_agencia   = nombre_agencia   or ds["nombre_agencia"]
                addr_fields["direccion"] = addr_fields["direccion"] or ds["direccion"]
                addr_fields["cp"]        = addr_fields["cp"]        or ds["cp"]
                addr_fields["poblacion"] = addr_fields["poblacion"] or ds["poblacion"]
                addr_fields["provincia"] = addr_fields["provincia"] or ds["provincia"]
                if ds["nombre_agencia"] or ds["direccion"]:
                    fuente = "DeepSeek"

    # Completar provincia desde CP si sigue vacía
    if not addr_fields["provincia"] and addr_fields["cp"]:
        addr_fields["provincia"] = provincia_desde_cp(addr_fields["cp"])

    algun_dato = bool(nombre_agencia or addr_fields["cp"] or addr_fields["direccion"])
    if algun_dato:
        message = aviso_validacion + f"✓ CIF válido. Datos sugeridos desde {fuente} — verifica antes de guardar."
    else:
        message = aviso_validacion + "✓ CIF válido (verificado en VIES)."

    return {
        "ok": True,
        "message": message.strip(),
        "fields": {
            "nombre_agencia": nombre_agencia,
            "direccion": addr_fields["direccion"],
            "cp": addr_fields["cp"],
            "poblacion": addr_fields["poblacion"],
            "provincia": addr_fields["provincia"],
        },
    }


def buscar_cliente_por_nombre(nombre: str, deepseek_api_key: str = None) -> dict:
    """Busca un cliente por nombre de empresa en einforma.

    Retorna:
        {
            "ok": bool,
            "message": str,
            "fields": {"nombre_agencia","nif_cif","direccion","cp","poblacion","provincia"}
        }
    Nunca lanza excepciones.
    """
    empty_fields = {
        "nombre_agencia": "",
        "nif_cif": "",
        "direccion": "",
        "cp": "",
        "poblacion": "",
        "provincia": "",
    }

    nombre = (nombre or "").strip()
    if not nombre:
        return {"ok": False, "message": "Introduce un nombre.", "fields": empty_fields}

    # Buscar slug en el listado
    slug_url = buscar_einforma_slug(nombre)
    if not slug_url:
        return {
            "ok": False,
            "message": "No se encontró ninguna empresa con ese nombre en einforma.",
            "fields": empty_fields,
        }

    # Descargar y parsear la ficha
    ficha = consultar_einforma_url(slug_url)
    if not ficha["ok"]:
        return {
            "ok": False,
            "message": f"Error al acceder a la ficha de einforma: {ficha.get('error', '')}",
            "fields": empty_fields,
        }

    ei = parsear_einforma(ficha["html"])
    nombre_agencia = ei["nombre_agencia"]
    nif_cif = ei["nif_cif"]
    addr = {
        "direccion": ei["direccion"],
        "cp": ei["cp"],
        "poblacion": ei["poblacion"],
        "provincia": ei["provincia"],
    }

    # Fallback a DeepSeek si no se extrajeron datos y hay API key
    todo_vacio = not nombre_agencia and not nif_cif and not addr["direccion"]
    if todo_vacio and deepseek_api_key:
        texto_plano = re.sub(r'\s+', ' ', _strip_tags(ficha["html"])).strip()
        if texto_plano:
            ds = extraer_con_deepseek(texto_plano, deepseek_api_key)
            nombre_agencia = nombre_agencia or ds.get("nombre_agencia", "")
            addr["direccion"] = addr["direccion"] or ds.get("direccion", "")
            addr["cp"] = addr["cp"] or ds.get("cp", "")
            addr["poblacion"] = addr["poblacion"] or ds.get("poblacion", "")
            addr["provincia"] = addr["provincia"] or ds.get("provincia", "")

    # Completar provincia desde CP si falta
    if not addr["provincia"] and addr["cp"]:
        addr["provincia"] = provincia_desde_cp(addr["cp"])

    return {
        "ok": True,
        "message": "Datos sugeridos desde einforma — verifica antes de guardar.",
        "fields": {
            "nombre_agencia": nombre_agencia,
            "nif_cif": nif_cif,
            "direccion": addr["direccion"],
            "cp": addr["cp"],
            "poblacion": addr["poblacion"],
            "provincia": addr["provincia"],
        },
    }


# ── Tests manuales CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Tests offline de validar_cif
    print("=== Tests validar_cif ===")
    casos = [
        ("12345678Z", True),   # NIF válido (Z = TRWAGMYFPDXBNJZSQVHLCKE[12345678 % 23])
        ("12345678A", False),  # NIF con letra incorrecta
        ("X1234567L", True),   # NIE válido
        ("X1234567A", False),  # NIE con letra incorrecta
        ("A15022510", True),   # CIF (Inditex sin prefijo ES)
        ("A28017895", True),   # CIF (El Corte Inglés sin prefijo ES)
        ("AAAAA", False),      # Claramente inválido
    ]
    for valor, esperado in casos:
        resultado = validar_cif(valor)
        estado = "OK" if resultado == esperado else "FALLO"
        print(f"  [{estado}] validar_cif({valor!r}) = {resultado} (esperado {esperado})")

    # Test provincia_desde_cp
    print("\n=== Tests provincia_desde_cp ===")
    assert provincia_desde_cp("03001") == "Alicante", f"Fallo: {provincia_desde_cp('03001')!r}"
    assert provincia_desde_cp("28080") == "Madrid", f"Fallo: {provincia_desde_cp('28080')!r}"
    assert provincia_desde_cp("99999") == "", f"Fallo: {provincia_desde_cp('99999')!r}"
    print("  OK: 03xxx→Alicante, 28xxx→Madrid, 99xxx→''")

    # Test parsear_direccion
    print("\n=== Tests parsear_direccion ===")
    r = parsear_direccion("C/ EJEMPLO 12\n03001 ALICANTE")
    print(f"  Resultado: {r}")
    assert r["cp"] == "03001", f"CP incorrecto: {r['cp']!r}"
    assert r["provincia"] == "Alicante", f"Provincia incorrecta: {r['provincia']!r}"
    assert "Alicante" in r["poblacion"], f"Población incorrecta: {r['poblacion']!r}"
    print("  OK: CP, provincia y población correctos")

    # Consultas en vivo (requieren red)
    cifs_argv = sys.argv[1:] if len(sys.argv) > 1 else ["ESA15022510", "ESA28017895"]
    import pprint

    # Smoke test einforma directo
    print(f"\n=== Smoke test einforma: {cifs_argv[0]} ===")
    cif_test = normalizar_cif(cifs_argv[0])
    ei_resp = consultar_einforma(cif_test)
    if ei_resp["ok"]:
        ei_parsed = parsear_einforma(ei_resp["html"])
        print(f"  consultar_einforma: ok, html len={len(ei_resp['html'])}")
        print(f"  parsear_einforma:   {ei_parsed}")
    else:
        print(f"  consultar_einforma: fallo — {ei_resp.get('error')}")

    print(f"\n=== Consultas buscar_cliente en vivo: {cifs_argv} ===")
    for c in cifs_argv:
        print(f"\n  buscar_cliente({c!r}):")
        resultado = buscar_cliente(c)
        pprint.pprint(resultado, indent=4)

    # Smoke test buscar_cliente_por_nombre
    nombre_test = "VIAJES EL CORTE INGLES"
    print(f"\n=== Smoke test buscar_cliente_por_nombre({nombre_test!r}) ===")
    resultado_nombre = buscar_cliente_por_nombre(nombre_test)
    pprint.pprint(resultado_nombre, indent=4)
    if resultado_nombre.get("ok"):
        f = resultado_nombre["fields"]
        print(f"  nombre_agencia : {f['nombre_agencia']!r}")
        print(f"  nif_cif        : {f['nif_cif']!r}")
        print(f"  direccion      : {f['direccion']!r}")
        print(f"  cp/poblacion   : {f['cp']!r} / {f['poblacion']!r}")
        print(f"  provincia      : {f['provincia']!r}")
    else:
        print(f"  ERROR: {resultado_nombre.get('message')}")
