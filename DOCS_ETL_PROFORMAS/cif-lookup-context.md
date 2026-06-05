# CIF Lookup — Hallazgos, Limitaciones y Opciones

Contexto para futuras sesiones sobre autocompletado del formulario de clientes a partir de un CIF/NIF español.

---

## Lo que ya está implementado

| Fichero | Qué hace |
|---|---|
| `src/clientes_lookup.py` | Módulo puro stdlib: valida NIF/NIE/CIF por dígito de control, consulta VIES, tabla CP→provincia |
| `src/app.py` | Rutas `/clientes/lookup?cif=` y `/clientes/provincia?cp=` |
| `src/templates/clientes/form.html` | Botón «🔍 Validar» junto al CIF; CP autocompleta Provincia al perder foco |

---

## Hallazgo crítico: VIES no sirve para España

**VIES** (`https://ec.europa.eu/taxation_customs/vies/rest-api/ms/ES/vat/{n}`) es el registro IVA de la UE, oficial y gratuito.

**Problema:** España (como Alemania y otros) ha optado por **no publicar nombre ni dirección** en VIES. Para cualquier CIF español la respuesta es:

```json
{ "isValid": true, "name": "---", "address": "" }
```

Verificado en producción contra Inditex (`ESA15022510`) y El Corte Inglés (`ESA28017895`). El endpoint actual solo sirve para **validar** que el CIF existe en el registro IVA intracomunitario, no para rellenar el formulario.

**Lo único gratis que sí funciona:** la tabla CP→provincia (primeros 2 dígitos del CP → provincia, 01–52). Está implementada en `clientes_lookup.provincia_desde_cp()` y se activa automáticamente al escribir el CP en el formulario.

---

## Opciones reales para autofill de nombre + dirección

### Opción A — Web scraping de directorios públicos españoles (coste: 0€, fragilidad: alta)

Los siguientes sitios publican ficha pública por CIF, scrapeables con una petición HTTP + extracción de texto:

| Directorio | URL patrón | Datos disponibles | Notas |
|---|---|---|---|
| **Empresia** | `https://empresia.es/empresa/?txt={CIF}` | Nombre, dirección, CP, población, teléfono, actividad | Más completo; JS ligero |
| **Infocif** | `https://infocif.es/ficha-empresa/{CIF}` | Nombre, dirección, NIF | Requiere verificar estructura HTML |
| **einforma** | `https://www.einforma.com/buscar/{CIF}` | Nombre, dirección, actividad | Más agresivo con bots |
| **Axesor** | `https://www.axesor.es/Informes-Empresas/buscar?q={CIF}` | Nombre, dirección | Redirige a ficha |

**Implementación sugerida:**
1. `urllib.request` para hacer la petición (ya disponible, sin pip).
2. Regex o parsing básico de HTML para extraer los campos (no necesita BeautifulSoup para estructuras simples).
3. Marcar los datos como "sugeridos" en el formulario — nunca son tan fiables como un registro oficial.
4. Timeout corto (5s), silencioso en fallo — el usuario siempre puede rellenar a mano.

**Si el HTML es irregular:** aquí sí justifica usar DeepSeek/Claude para extraer campos del HTML crudo (`"extrae nombre, dirección, CP y población de este HTML de ficha de empresa"`). Llamada puntual, bajo coste.

**Caveats legales:** scraping de datos públicos con fines privados es zona gris en España. Para uso interno de facturación (volumen muy bajo, datos ya públicos) el riesgo es mínimo, pero no es lo mismo que un producto comercial.

### Opción B — API de Registro Mercantil / BORME (coste: bajo, oficial)

- **BORME** (Boletín Oficial del Registro Mercantil) tiene API REST no oficial pero estable: `https://boe.es/diario_borme/` — útil para altas/bajas, no para dirección actual.
- Servicios de terceros sobre datos del Registro: **Infoempresa API**, **Lexnova**, **Coalvi** — de pago, fiables, cubren NIF→razón social + domicilio fiscal actualizado.

### Opción C — Hacienda (AEAT) — no disponible para terceros

El único registro con nombre + dirección fiscal 100% fiable para cualquier NIF español es la AEAT, pero **no expone API pública**. Solo accesible con certificado digital del propio titular.

### Opción D — Google Maps / Places API

Para agencias de viajes con nombre conocido, la Places API devuelve nombre, dirección, teléfono, email (web). Requiere clave API (~$0.017/consulta). Funciona mejor buscando por nombre que por CIF.

---

## Recomendación para implementar

Si se quiere autofill real con mínimo esfuerzo:

1. **Primera petición:** intentar scraping de Empresia (`urllib` + regex para CP de 5 dígitos y texto adyacente).
2. **Si falla o el HTML cambia:** pasar el HTML a DeepSeek con prompt: `"Del siguiente HTML de ficha de empresa española, extrae en JSON: nombre_agencia, direccion, cp, poblacion. Solo los campos que estén presentes, sin inventar."` DeepSeek es más barato que Claude para esta tarea repetitiva.
3. **Fallback siempre:** CP→provincia sigue funcionando aunque falle todo lo demás.
4. **UX:** marcar visualmente campos como "sugeridos" (fondo amarillo ya implementado en `form.html`). Nunca autoenviar el formulario con datos no confirmados por el usuario.

---

## Variables de entorno a añadir si se usa DeepSeek

```
DEEPSEEK_API_KEY=sk-...
```

En el unit systemd de CT-104 (`/etc/systemd/system/proforma-admin.service`), sección `[Service]`:
```ini
Environment="DEEPSEEK_API_KEY=sk-..."
```

Endpoint DeepSeek: `https://api.deepseek.com/v1/chat/completions`, modelo `deepseek-chat`. La respuesta es JSON estándar OpenAI-compatible.

---

## Archivos clave del módulo actual

```
src/clientes_lookup.py
  normalizar_cif(s)          # limpia y normaliza
  validar_cif(s) -> bool     # check digit NIF/NIE/CIF
  PROVINCIAS_POR_CP          # dict "01".."52" → nombre provincia
  provincia_desde_cp(cp)     # lookup tabla local
  consultar_vies(cif)        # llama VIES REST, devuelve {ok, isValid, name, address}
  parsear_direccion(address)  # extrae cp/poblacion/direccion de blob VIES
  buscar_cliente(cif)        # orquestador → {ok, message, fields}
```
