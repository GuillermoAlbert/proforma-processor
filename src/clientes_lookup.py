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


# ── Orquestador principal ────────────────────────────────────────────────────

def buscar_cliente(cif: str) -> dict:
    """Busca un cliente por CIF/NIF en VIES y devuelve los campos para el formulario.

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

    algun_dato = bool(nombre_agencia or addr_fields["cp"] or addr_fields["direccion"])
    if algun_dato:
        message = aviso_validacion + "✓ CIF válido. Datos cargados desde VIES."
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

    # Consultas VIES en vivo (opcionales, requieren red)
    cifs_argv = sys.argv[1:] if len(sys.argv) > 1 else ["ESA15022510", "ESA28017895"]
    print(f"\n=== Consultas VIES en vivo: {cifs_argv} ===")
    for c in cifs_argv:
        print(f"\n  buscar_cliente({c!r}):")
        resultado = buscar_cliente(c)
        import pprint
        pprint.pprint(resultado, indent=4)
