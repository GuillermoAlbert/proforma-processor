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
| PDF | WeasyPrint | Librería Python pura, sin binarios externos |
| BD | SQLite (WAL) | `proformas.db` en el NAS, no en el rootfs del CT |
| Excel | openpyxl | Patrón con backup + reintentos del processor |
| Auth | HTTP Basic | `admin_helpers.py` del processor reutilizable |

## Qué reutilizar de `/opt/factura-processor/`

```bash
pct exec 104 -- ls /opt/factura-processor/
```

- `admin_helpers.py` — autenticación Basic y helpers del panel
- `admin_ui.py` — CSS y barra de navegación (mismo look)
- `db.py` — patrón context manager SQLite WAL (fix WAL truncado aplicado)
- `pipeline.py` (sección Excel) — backup previo + reintentos + cola si el Excel está abierto

Copiar y adaptar, no importar directamente (proyectos independientes).

## DOCS_ETL_PROFORMAS — assets que el usuario sube

Ruta en el host / desde el PC (Samba): `empresa/proforma-admin/DOCS_ETL_PROFORMAS/`
Ruta dentro del CT: `/mnt/empresa/proforma-admin/DOCS_ETL_PROFORMAS/`

Aquí el usuario deja los ficheros de referencia para el diseño y la implementación:

| Fichero esperado | Para qué |
|---|---|
| `plantilla-proforma.html` | Plantilla HTML de la proforma (diseño final con huecos Jinja2) |
| `brand-kit.*` | Colores, tipografías, instrucciones de diseño |
| `factusol-importacion.pdf` | Documentación técnica de importación de tu versión de Factusol |
| `ejemplo-proforma.*` | PDF o imagen de referencia visual |

## Modelo de datos (tablas SQLite)

Ver propuesta completa para el DDL detallado. Resumen:

- `clientes` — agencias/clientes reutilizables (NIF, dirección, código Factusol)
- `articulos` — catálogo de servicios con precio e IVA por defecto
- `guias` — nombres de guías (columna "Guía" del Excel de Hacienda)
- `proformas` — cabecera: cliente, guía, totales, estado, ruta PDF
- `proforma_lineas` — líneas de cada proforma
- `series` — contador de numeración por serie y año

## Reglas de trabajo

1. **El factura-processor (CT-104 puerto 8080) no se toca.** El cron horario sigue corriendo. Proyectos totalmente independientes.
2. **Toda la BD y los ficheros generados van al NAS** (`/mnt/empresa/`), nunca al rootfs del CT (8 GB limitado).
3. **El código vive en el NAS** (`./src/`). Editar aquí es editar en producción — hacer commit antes de cambios grandes.
4. **Antes de cualquier cambio de red o config**, leer `/root/documentacion/auditoria-cambios.md` y añadir entrada tras el cambio.
5. **RAM CT-104**: 1 GB (subido desde 512 MB el 2026-06-04). Si hay problemas de memoria en el host, este CT es el primero en bajar.
6. **Rollback**: `systemctl stop proforma-admin && systemctl disable proforma-admin`. El processor queda intacto.

## Plan de implementación por fases

- **Fase 1** — BD + catálogo (clientes, servicios, guías) + crear proforma + generar PDF con WeasyPrint
- **Fase 2** — Registro en Excel Hacienda (patrón robusto del processor)
- **Fase 3** — Export fichero importación Factusol (necesita doc técnica de tu versión)
- **Fase 4** — Estados (borrador→enviada→confirmada), filtros, pulido
