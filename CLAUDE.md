# CLAUDE.md — proforma-admin (CT104)

Pipeline de **salida** de facturas de GuíasdeAlicante: crea proformas, genera
su PDF (WeasyPrint), las registra en el Excel de Hacienda al enviarlas y les
anota el cobro. **En producción**: Flask + SQLite en CT104, usado a diario.

## ⚠ En CT104 conviven DOS aplicaciones — no las confundas

| | **proforma-admin (ESTE repo)** | factura-processor (el otro) |
|---|---|---|
| Qué hace | **Salida**: proformas → PDF → Excel Hacienda | **Entrada**: facturas recibidas por Gmail → IA → BD/Excel |
| Código | NAS: `/mnt/pve/almacenamiento/datos/empresa/proforma-admin` (host) = `/mnt/empresa/proforma-admin` (CT) | Dentro del CT: `/opt/factura-processor` |
| GitHub | `GuillermoAlbert/proforma-processor` ← ojo, el repo NO se llama proforma-admin | `GuillermoAlbert/factura-processor` |
| Servicio | `proforma-admin.service` · puerto **5114** (0.0.0.0) · HTTPS tailnet `https://factura-processor.tail9d9dc4.ts.net:8443` | `factura-admin.service` · **5104** loopback tras nginx **:8080** · HTTPS tailnet `:443` · + cron pipeline cada hora |
| BD | `/mnt/empresa/proformas.db` | `/mnt/empresa/facturas.db` |
| Excel | `facturas-emitidas.xlsx` (emitidas) | `facturas.xlsx` (recibidas) |
| Instrucciones | Este `CLAUDE.md` | Su `AGENTS.md` (fichero maestro, opencode) |

**Regla:** desde este workspace el factura-processor se puede *leer* como
referencia, pero **no se toca** (ni su código ni su cron ni su BD).

## Cómo se trabaja en este repo (peculiar — leer antes de nada)

- Las sesiones de Claude Code corren **en el host Proxmox** con cwd en la ruta
  NAS de arriba (`claude` no está instalado en CT104). Por eso los comandos de
  servicio van con `pct exec 104 -- …`.
- **Editar aquí es editar producción en vivo**: el servicio ejecuta `src/`
  directamente del NAS, y WeasyPrint relee la plantilla en cada PDF. Un cambio
  a medias en `src/` puede tumbar el panel → cambios atómicos, commit antes de
  cambios grandes, y `/verify` SIEMPRE después de tocar `src/`.
- Estado vivo del proyecto: **`docs/estado.md`** (mantenerlo al día es parte de
  cada tarea; se actualiza en el mismo commit).
- Skills: **`/verify`** (tras cada cambio) · **`/cierre-sesion`** (al terminar).
- Docs de infraestructura del host: `/root/documentacion/` (leer
  `auditoria-cambios.md` antes de cambios de red/config y añadir entrada después).

## Reglas innegociables

1. **Estabilidad.** Producción diaria. No interrumpir `proforma-admin` sin
   necesidad (un restart de ~3 s tras cambios verificados sí es normal).
2. **El Excel de Hacienda es fiscal.** `facturas-emitidas.xlsx`: no cambiar el
   orden/significado de columnas ni escribir columnas manuales (Fecha Factura,
   Nº Factusol) sin confirmación explícita del usuario.
3. **Todo lo generado va al NAS** (`/mnt/empresa/`): BD, PDFs, backups, colas.
   Nunca al rootfs del CT (8 GB).
4. **factura-processor no se toca** desde aquí.
5. **Cambios de schema** solo con el patrón del repo: funciones `_migrate_*`
   idempotentes en `src/db.py` que corren en el arranque (mira
   `_migrate_estado_confirmada_a_enviada` o `_migrate_to_multi_guia`).
6. La escritura desde CT108 (`POST /api/proformas/<id>/cobrar` etc.) está
   **no implementada a propósito** (decisión 2026-06-12) — la única excepción
   ya acordada es `POST /api/proformas/borrador` (siempre crea en estado
   `borrador`, nunca confirma ni toca el Excel). No añadir más escritura por
   `/api` sin confirmación.

## Operación

```bash
pct exec 104 -- systemctl status proforma-admin      # estado
pct exec 104 -- journalctl -u proforma-admin -n 50   # logs
pct exec 104 -- systemctl restart proforma-admin     # tras cambios en src/
pct exec 104 -- bash -c 'curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5114/'   # 401 = vivo (Basic Auth)
pct exec 104 -- bash -c 'cd /mnt/empresa/proforma-admin/src && python3 test_pdf_gen.py'     # smoke PDFs → /tmp
```

- Acceso: solo Tailscale — `http://100.87.188.5:5114` o HTTPS
  `https://factura-processor.tail9d9dc4.ts.net:8443` + HTTP Basic Auth.
- Variables del unit systemd (todas con default sensato): `DB_PATH`, `PDF_DIR`,
  `TEMPLATE_DIR`, `ADMIN_USER`/`ADMIN_PASS`, `EXCEL_PATH`, `EXCEL_BACKUP_DIR`
  (rotación 30 días), `EXCEL_PENDING_FILE` (cola si el Excel está abierto),
  `EXCEL_LOCK_FILE`.
- Verificación: `python3 -m pytest src/test_direccion_modo.py src/test_numeracion_agencia.py`
  (suites pytest, aisladas en /tmp) + `test_pdf_gen.py` + smoke HTTP + el flujo manual
  en el panel (ver `/verify`).

## Mapa de `src/`

| Archivo | Qué hace |
|---|---|
| `app.py` | Flask monolítico (~1.300 líneas): rutas CRUD (clientes, artículos, guías, cuentas), proformas, estados, PDF, Excel. Registra el blueprint de `api_orquestador`. |
| `api_orquestador.py` | Blueprint `/api/*` para CT108: lectura (proformas, clientes, cobros vencidos) + `POST /api/proformas/borrador` (única escritura; siempre `borrador`). |
| `db.py` | Context manager SQLite WAL + schema DDL + migraciones `_migrate_*` idempotentes + `siguiente_numero_proforma()` + config de empresa/serie (`get_empresa_config`, `get_serie_config` — los datos de empresa viven en BD, ya no hardcodeados). |
| `pdf.py` | PDF con WeasyPrint + Jinja2 (filtros `fecha_es`, `iban_format`; `numero_corto` PREFIJO-AA-NNNN en cabecera). Plantilla: `DOCS_ETL_PROFORMAS/plantilla-proforma.html`. **Sin variable `guia`: los guías nunca van al PDF.** El bloque de pago sale de la cuenta asignada (tabla `cuentas`); fallback a la config de empresa. |
| `excel.py` | Registro en `facturas-emitidas.xlsx`: backup + lock + reintentos + cola (patrón del processor). `registrar_proforma()`, `marcar_cobrado_excel()`, `drain_pending()`. |
| `clientes_lookup.py` / `admin_helpers.py` | Búsqueda de clientes / `@require_auth` Basic Auth. |
| `templates/` | Jinja2 del panel (base + clientes/, articulos/, guias/, cuentas/, proformas/, config/). |
| `test_pdf_gen.py` | Script manual (no pytest): genera 3 PDFs de prueba en `/tmp` sin BD. |
| `test_direccion_modo.py` | Suite pytest de `empresa.direccion_modo` (completa/poblacion/oculta): config, migración, render y formulario. BD y PDFs en `/tmp`. |
| `test_numeracion_agencia.py` | Suite pytest de la numeración cuando la serie depende del cliente o la fecha (`{agencia}`, `{mes_corto}`): alta sin cliente, `peek-numero`, renumerado al editar un borrador y campo `readonly` en el alta. BD en `/tmp`. |
| `INSTALL.md` | Comandos `pct exec 104` de instalación. |

Assets de marca y plantillas: `DOCS_ETL_PROFORMAS/` (brand kit, plantilla
proforma, plantilla documento, logotipo SVG, doc Factusol pendiente).

## Modelo de datos (SQLite `proformas.db`)

`clientes` · `articulos` · `guias` · `cuentas` (bancarias, una `predeterminada`)
· `proformas` (cabecera; `cuenta_id` nullable; **sin `guia_id`**) ·
`proforma_guias` (N:M — los guías van solo al Excel col 16, concatenados) ·
`proforma_lineas` · `series` (contador por serie y año, `PRO-YYYY-NNNN`).

## Estados de la proforma (flujo lineal)

`borrador → enviada → cobrada` (`proformas.estado`):

| Transición | Ruta | Efecto en Excel |
|---|---|---|
| → `enviada` | `POST /proformas/<id>/enviar` | escribe la fila (`registrar_proforma`) |
| → `cobrada` | `POST /proformas/<id>/cobrar` (fecha editable, default hoy) | fecha en col `Cobrado` (M) |
| deshacer | `/descobrar` y `/desenviar` (simétricos) | vacía col M / borra la fila |

- Una proforma cobrada no se edita/elimina sin deshacer antes cobro y envío.
- ⚠ Gotcha openpyxl: `ws.cell(r, c, None)` es no-op; para vaciar una celda:
  `ws.cell(r, c).value = None`.
- CT108 no filtra por el string `estado`: usa `exportada_excel`, `cobrado`,
  `numero_factura` y la col `Cobrado` del Excel (`/api/cobros/vencidos`). Al
  marcar cobrada, la tarea del panel «Hoy» desaparece sola.

### Columnas del Excel que escribe la app (al enviar)

Nº Proforma (3), NIF/CIF (4), Trimestre (5), Agencia (6), Provincia (7),
Base (8), IVA (9, fórmula si un solo tipo), Total (10) y Total+suplidos (12)
como fórmulas, Suplidos (11, solo si > 0), Comentarios (14), Guía (16, todos
concatenados con `, `). **Manuales** (no tocar): Fecha Factura (2), Nº Factura
Factusol (15). `Cobrado` (13) la escribe la app al marcar cobrada.

## Convenciones

- Python simple; leer el módulo entero antes de editarlo.
- Commits estilo del log: `feat(proformas): …` / `fix(pdf): …`, en español.
  Push a `main` (`origin` = GitHub `proforma-processor`).
- Brand kit en `DOCS_ETL_PROFORMAS/brand-kit-documentos.md` — leerlo antes de
  tocar plantillas o generar documentos nuevos.
- Referencias de contexto: propuesta completa en
  `/mnt/pve/almacenamiento/datos/guillermo/documentacion-servidor/propuesta-facturacion-proforma.html`.
