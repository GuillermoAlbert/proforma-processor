# proforma-admin — CLAUDE.md

Pipeline de **salida** de facturas para Guías de Alicante: genera proformas en PDF, registra en Excel para Hacienda y prepara ficheros de importación para Factusol.

## Contexto del proyecto

- **Propuesta completa** (decisiones acordadas, esquema de BD, pantallas): `/mnt/pve/almacenamiento/datos/guillermo/documentacion-servidor/propuesta-facturacion-proforma.html`
- **Assets de diseño y contexto**: `./DOCS_ETL_PROFORMAS/` (brand kit, plantilla HTML, doc Factusol)
- **Documentación de infraestructura general**: `/root/documentacion/` (IPs, auditoría, CTs)
- **PENDIENTE.md del servidor**: `/root/PENDIENTE.md`
- **Este workspace vive en**: `/mnt/pve/almacenamiento/datos/empresa/proforma-admin/` (NAS, accesible desde el PC por Samba y desde CT-104 en `/mnt/empresa/proforma-admin/`)

## Arquitectura: dónde vive cada cosa

| Elemento | Ubicación |
|---|---|
| **Código de la app** | `./src/` en este repo (= CT-104 `/mnt/empresa/proforma-admin/src/`) |
| **Base de datos** | `/mnt/empresa/proformas.db` (= NAS `empresa/proformas.db`) |
| **PDFs generados** | `/mnt/empresa/proformas-pdf/` |
| **Excel Hacienda** | `/mnt/empresa/facturas-emitidas.xlsx` |
| **Import Factusol** | `/mnt/empresa/factusol-import/` |
| **Assets / brand kit** | `./DOCS_ETL_PROFORMAS/` (logotipo SVG, plantilla HTML, doc Factusol) |
| **Logotipo JPG** | `/mnt/pve/almacenamiento/datos/empresa/logotipo guiasdealicante.jpg` |
| **Workspace Claude Code** | Este directorio (`/mnt/pve/almacenamiento/datos/empresa/proforma-admin/`) |

El NAS (`/mnt/pve/almacenamiento/datos/empresa`) ya está montado dentro de CT-104 en `/mnt/empresa` — es el mismo directorio físico, no hay copia.

## Cómo trabajar

El código vive en `./src/` (este repo, en el NAS). Dentro de CT-104 se monta en `/mnt/empresa/proforma-admin/src/`. No hay que copiar ficheros — editar aquí es editar dentro del CT.

```bash
# Arrancar sesión Claude Code en este proyecto (desde el host PVE)
cd /mnt/pve/almacenamiento/datos/empresa/proforma-admin && claude

# Estado del servicio en CT-104
pct exec 104 -- systemctl status proforma-admin

# Logs en tiempo real
pct exec 104 -- journalctl -u proforma-admin -f

# Reiniciar el servicio tras cambios en src/
pct exec 104 -- systemctl restart proforma-admin

# Instalar dependencias Python dentro del CT
pct exec 104 -- bash -c "cd /mnt/empresa/proforma-admin && pip install -r src/requirements.txt"
```

## Servicio web

- **Puerto**: `5114` (Flask, systemd `proforma-admin`)
- **Acceso**: solo Tailscale (`http://100.87.188.5:5114`) + HTTP Basic Auth
- **Serie de proformas**: `PRO-YYYY-NNNN` (reinicia cada año)

## Stack técnico

| Pieza | Tecnología | Notas |
|---|---|---|
| Web | Flask | Mismo patrón que `factura-processor` |
| Plantillas | Jinja2 | HTML de proforma → datos inyectados |
| PDF | WeasyPrint | Librería Python pura. Plantilla: `DOCS_ETL_PROFORMAS/plantilla-proforma.html`. Contexto Jinja2: `proforma`, `cliente`, `empresa`, `proforma.lineas` (cada una: `descripcion`, `cantidad`, `precio`, `porcentaje_iva`, `importe`). Serie: `PRO-YYYY-NNNN`. **Sin variable `guia` — los guías no van al PDF.** |
| BD | SQLite (WAL) | `proformas.db` en el NAS, no en el rootfs del CT |
| Excel | openpyxl | Patrón con backup + reintentos del processor |
| Auth | HTTP Basic | `admin_helpers.py` del processor reutilizable |

## Estructura de `src/` (Fases 1–2 implementadas)

| Archivo | Qué hace |
|---|---|
| `app.py` | Flask app + rutas (CRUD clientes/artículos/guías/cuentas, proformas, PDF, **confirmar→Excel**) |
| `db.py` | Context manager SQLite WAL, schema DDL, `siguiente_numero_proforma()` |
| `pdf.py` | Generación PDF con WeasyPrint + Jinja2. Datos empresa hardcodeados aquí. |
| `excel.py` | **Fase 2.** Registro en `facturas-emitidas.xlsx`: backup + lock + reintentos + cola. `registrar_proforma()`, `drain_pending()`, `contar_pendientes()`. |
| `admin_helpers.py` | Decorator `@require_auth` HTTP Basic Auth |
| `requirements.txt` | flask, weasyprint, openpyxl |
| `INSTALL.md` | Comandos `pct exec 104` para instalar en CT-104 |
| `templates/base.html` | Layout nav + CSS brand kit completo |
| `templates/clientes/` | lista.html + form.html |
| `templates/articulos/` | lista.html + form.html |
| `templates/guias/lista.html` | CRUD inline |
| `templates/cuentas/` | lista.html + form.html — CRUD de cuentas bancarias de cobro (una `predeterminada`) |
| `templates/proformas/lista.html` | Listado con enlace a PDF + botón Confirmar |
| `templates/proformas/nueva.html` | Form con líneas dinámicas (JS vanilla) + totales en tiempo real + selector de cuenta de cobro |
| `templates/proformas/detalle.html` | Vista + descarga PDF + Confirmar y registrar en Excel |
| `templates/config/index.html` | Reiniciar servicio + reintentar pendientes de Excel |

**Datos de empresa** (NIF, dirección, condiciones de pago, IBAN por defecto): editar en `src/pdf.py` (dict `EMPRESA`). **El IBAN/entidad/titular del PDF se toma de la cuenta seleccionada en la proforma** (tabla `cuentas`, gestionada en la pantalla **Cuentas**); el `EMPRESA['iban']`/`['banco']` solo se usan como fallback cuando la proforma no tiene cuenta asignada.

**Variables de entorno del servicio** (en el unit systemd):
- `DB_PATH` — default `/mnt/empresa/proformas.db`
- `PDF_DIR` — default `/mnt/empresa/proformas-pdf`
- `TEMPLATE_DIR` — default `/mnt/empresa/proforma-admin/DOCS_ETL_PROFORMAS`
- `ADMIN_USER` / `ADMIN_PASS` — credenciales Basic Auth
- `EXCEL_PATH` — default `/mnt/empresa/facturas-emitidas.xlsx` (Excel Hacienda, Fase 2)
- `EXCEL_BACKUP_DIR` — default `/mnt/empresa/backups-proformas` (copias con rotación 30 días)
- `EXCEL_PENDING_FILE` — default `/mnt/empresa/proforma-admin-pending-excel.json` (cola si el Excel está abierto)
- `EXCEL_LOCK_FILE` — default `/mnt/empresa/.proforma-excel.lock`

Todas las de Excel tienen default, así que el servicio funciona sin declararlas.

## DOCS_ETL_PROFORMAS — assets que el usuario sube

Ruta en el host / desde el PC (Samba): `empresa/proforma-admin/DOCS_ETL_PROFORMAS/`
Ruta dentro del CT: `/mnt/empresa/proforma-admin/DOCS_ETL_PROFORMAS/`

Aquí el usuario deja los ficheros de referencia para el diseño y la implementación:

| Fichero | Estado | Para qué |
|---|---|---|
| `plantilla-proforma.html` | ✅ listo | Jinja2 → WeasyPrint. Variables: `proforma.*`, `cliente.*`, `empresa.*`, `proforma.lineas`. **`guia` eliminado del contexto PDF — los guías no aparecen en el PDF.** Ver sección "PDF" abajo. |
| `brand-kit-documentos.md` | ✅ listo | Colores, tipografías e instrucciones de diseño (Design System v1.0) |
| `plantilla-documento.html` | ✅ listo | Plantilla base de documentos (tarifas, resúmenes) — mismos patrones CSS que la proforma |
| `logotipo-guiasdealicante.svg` | ✅ listo | Logo vectorial (paths terracota + navy; renderizar en blanco sobre fondos oscuros) |
| `factusol-importacion.pdf` | ⏳ pendiente | Documentación técnica de importación de tu versión de Factusol (necesaria para Fase 3) |

## Modelo de datos (tablas SQLite)

Ver propuesta completa para el DDL detallado. Resumen:

- `clientes` — agencias/clientes reutilizables (NIF, dirección, código Factusol)
- `articulos` — catálogo de servicios con precio e IVA por defecto
- `guias` — nombres de guías (columna "Guía" del Excel de Hacienda)
- `cuentas` — cuentas bancarias de cobro (nombre/alias, titular, iban, banco, bic, `predeterminada`). La cuenta elegida define el bloque de pago del PDF. Solo una `predeterminada` a la vez; se preselecciona en proformas nuevas.
- `proforma_guias` — tabla puente muchos-a-muchos: una proforma puede tener varios guías. **Los guías solo van al Excel (col 16, todos concatenados con coma), nunca al PDF.**
- `proformas` — cabecera: cliente, `cuenta_id` (cuenta de cobro, FK → cuentas, nullable), totales, estado, ruta PDF. **No tiene `guia_id` — la relación es a través de `proforma_guias`.**
- `proforma_lineas` — líneas de cada proforma
- `series` — contador de numeración por serie y año

## Reglas de trabajo

1. **El factura-processor (CT-104 puerto 8080) no se toca.** El cron horario sigue corriendo. Proyectos totalmente independientes.
2. **Toda la BD y los ficheros generados van al NAS** (`/mnt/empresa/`), nunca al rootfs del CT (8 GB limitado).
3. **El código vive en el NAS** (`./src/`). Editar aquí es editar en producción — hacer commit antes de cambios grandes.
4. **Antes de cualquier cambio de red o config**, leer `/root/documentacion/auditoria-cambios.md` y añadir entrada tras el cambio.
5. **RAM CT-104**: 1 GB (subido desde 512 MB el 2026-06-04). Si hay problemas de memoria en el host, este CT es el primero en bajar.
6. **Rollback**: `systemctl stop proforma-admin && systemctl disable proforma-admin`. El processor queda intacto.

## Estado de implementación por fases

| Fase | Estado | Contenido |
|---|---|---|
| **Fase 1** | ✅ **implementada** (2026-06-04) | BD + catálogo (clientes, artículos, guías) + crear proforma + generar PDF con WeasyPrint |
| **Fase 2** | ✅ **implementada** (2026-06-05) | Registro automático en Excel Hacienda (`facturas-emitidas.xlsx`) al confirmar una proforma (botón «Confirmar y registrar en Excel»). Patrón robusto: backup + reintentos + cola si el Excel está abierto. Detalle: [`DOCS_ETL_PROFORMAS/fase2-excel-hacienda.md`](./DOCS_ETL_PROFORMAS/fase2-excel-hacienda.md). |
| **Fase 3** | ⏳ bloqueada | Export fichero importación Factusol. **Requiere** subir `factusol-importacion.pdf` a `DOCS_ETL_PROFORMAS/`. Campo `exportada_factusol` ya existe en el schema. |
| **Fase 4** | ⏳ pendiente | Flujo de estados (borrador→enviada→confirmada), filtros por estado/cliente/fecha, pulido UI |

### Fase 2 — detalle de columnas Excel que rellena la app

Al confirmar una proforma la app escribe automáticamente: Nº Proforma (col 3), NIF/CIF (4), Trimestre (5), Agencia (6), Provincia (7), Base (8), IVA (9), Total (10), Total+suplidos (12), Comentarios (14), Guía (16).

- **Guía (col 16)**: todos los guías asignados a la proforma, concatenados con `, ` (coma + espacio). Si no hay ninguno, la celda queda vacía. Los guías **no aparecen en el PDF** en ningún caso.
- **Fórmulas vs valores**: `Total` y `Total+suplidos` se escriben como fórmulas (`=H+I`, `=J+K`). El `IVA` es fórmula (`=H*tipo`) si la proforma tiene un único tipo de IVA, y valor `iva_total` si mezcla tipos.
- **Suplidos (col 11)**: la app la rellena con `proforma.suplidos` cuando es > 0 (desviación documentada de la propuesta, que la marcaba «manual»), para que la fórmula de la col 12 cuadre. Si es 0, se deja en blanco.

Columnas que se rellenan a mano después: Fecha Factura (2), Cobrado (13), Nº Factura Factusol (15), y Suplidos (11) cuando se añaden gastos a posteriori.

> **Nota:** la migración multi-guía (`proforma_guias`, eliminación de `proformas.guia_id`) ya está hecha en el schema de la Fase 1 (`db.py: _migrate_to_multi_guia`), no es un pendiente de la Fase 2.
