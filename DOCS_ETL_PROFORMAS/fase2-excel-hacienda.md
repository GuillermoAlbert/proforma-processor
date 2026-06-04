# Fase 2 — Registro automático en el Excel de Hacienda

**Implementada el 2026-06-05.** Documenta qué hace la Fase 2, los cambios de código y cómo probarla.

## Qué hace

Cuando una proforma se **confirma**, la app añade automáticamente una fila al Excel definitivo
para Hacienda (`facturas-emitidas.xlsx`, en el NAS). El registro es **robusto**: hace copia de
seguridad antes de escribir, reintenta si el Excel está abierto en el PC (LibreOffice/Excel por
Samba) y, si sigue bloqueado, deja la proforma en una **cola** que se vacía sola en cuanto el
fichero se libera. No se pierde ningún registro aunque tengas el Excel abierto.

El disparador es un único botón **«Confirmar y registrar en Excel»** (en el detalle y en el
listado): pone `estado = 'confirmada'` **y** escribe la fila en una sola acción. Es idempotente:
si la proforma ya estaba registrada (`exportada_excel = 1`) no se vuelve a escribir.

> El flujo completo de estados (borrador→enviada→confirmada) y los filtros quedan para la **Fase 4**.

## Mapa de columnas de `facturas-emitidas.xlsx`

| Col | Letra | Campo | Origen |
|----|----|----|----|
| 1 | A | Índice | auto (correlativo de fila de datos) |
| 2 | B | Fecha Factura | *(vacío — se rellena al facturar en Factusol)* |
| 3 | C | Nº Proforma | `proforma.numero_proforma` |
| 4 | D | NIF/CIF | `cliente.nif_cif` |
| 5 | E | Tr | `proforma.trimestre` (1–4) |
| 6 | F | Agencia | `cliente.nombre_agencia` |
| 7 | G | Provincia | `cliente.provincia` |
| 8 | H | Base | `proforma.base` (valor, formato moneda) |
| 9 | I | IVA | **fórmula** `=H{n}*tipo` si el IVA es único; **valor** `iva_total` si la proforma mezcla tipos |
| 10 | J | Total | **fórmula** `=H{n}+I{n}` |
| 11 | K | Suplidos | `proforma.suplidos` si > 0, si no vacío (ver nota) |
| 12 | L | Total + suplidos | **fórmula** `=J{n}+K{n}` |
| 13 | M | Cobrado | *(vacío — manual)* |
| 14 | N | Comentarios | `proforma.comentarios` |
| 15 | O | Nº Factura | *(vacío — manual / Factusol)* |
| 16 | P | Guía | guías de `proforma_guias` unidas con `, ` (vacío si ninguna) |

### Decisiones de diseño

- **Fórmulas vs valores.** `Total` y `Total+suplidos` son fórmulas independientes del tipo de IVA
  (`=H+I`, `=J+K`), así que siempre cuadran. El `IVA` se escribe como fórmula `=H{n}*0.21` (o el
  tipo real) **solo cuando la proforma tiene un único tipo**; si mezcla tipos (p. ej. 21% + 10%) no
  existe una fórmula de un solo factor correcta, así que se escribe el valor `iva_total` ya
  calculado por la app. openpyxl exige el **punto** como separador decimal en la fórmula
  (`=H2*0.21`); Excel/LibreOffice en español lo muestra como `=H2*0,21`.
- **Suplidos (col 11).** La propuesta original la marcaba «manual», pero el formulario de proforma
  **sí captura** `suplidos`. Para que la fórmula `=J+K` de la columna 12 cuadre y no se pierda el
  dato, se escribe `proforma.suplidos` cuando es > 0; si es 0 se deja vacío para rellenarlo a mano.

## Cambios de código

| Archivo | Cambio |
|---|---|
| `src/excel.py` | **Nuevo.** Toda la lógica de Excel: `registrar_proforma()`, `drain_pending()`, `contar_pendientes()` + helpers de backup, lock (`fcntl`), reintentos y cola. |
| `src/app.py` | Ruta `POST /proformas/<id>/confirmar`; ruta `POST /config/reintentar-excel`; `excel.drain_pending()` al arrancar; tras un registro OK se drena la cola de forma oportunista. |
| `templates/proformas/detalle.html` | Botón «Confirmar y registrar en Excel» (si no está confirmada) + marca «✓ En Excel». |
| `templates/proformas/lista.html` | Botón «Confirmar» en la columna de acciones. |
| `templates/config/index.html` | Tarjeta «Excel de Hacienda» con el nº de pendientes y botón «Reintentar pendientes de Excel». |

Sin cambios de schema: `exportada_excel` ya existía y la consulta de guías reutiliza el mismo
`JOIN proforma_guias` que el listado de proformas.

## Variables de entorno (todas con default razonable en `/mnt/empresa/`)

| Variable | Default | Para qué |
|---|---|---|
| `EXCEL_PATH` | `/mnt/empresa/facturas-emitidas.xlsx` | Excel de Hacienda |
| `EXCEL_BACKUP_DIR` | `/mnt/empresa/backups-proformas` | Copias con sello de tiempo (rotación 30 días) |
| `EXCEL_PENDING_FILE` | `/mnt/empresa/proforma-admin-pending-excel.json` | Cola de proformas pendientes si el Excel está abierto |
| `EXCEL_LOCK_FILE` | `/mnt/empresa/.proforma-excel.lock` | Lock `fcntl` para serializar escrituras |

Como hay defaults, el servicio funciona aunque no se declaren; añadirlas al unit systemd solo es
necesario si quieres cambiar las rutas.

## Robustez

1. **Backup antes de escribir:** copia `backups-proformas/facturas-emitidas_YYYYMMDD-HHMMSS.xlsx`
   (rotación automática a 30 días). Carpeta propia, separada del factura-processor.
2. **Lock `fcntl`:** serializa las escrituras del propio proceso.
3. **Reintentos:** ante `PermissionError` (Excel abierto) reintenta 3× con 2 s de espera.
4. **Cola:** si sigue bloqueado, encola el `proforma_id` en el JSON; la fila se reconstruye desde
   la BD al drenar (nunca queda desfasada). Se drena al arrancar el servicio, tras cada registro OK
   y con el botón «Reintentar pendientes de Excel» en Configuración.

## Cómo probarlo

- **Desde la web:** crear una proforma → en el detalle pulsar «Confirmar y registrar en Excel» →
  aparece la marca «✓ En Excel» y la fila en `facturas-emitidas.xlsx`.
- **Excel abierto:** si lo tienes abierto en el PC al confirmar, verás el aviso «se registrará
  automáticamente al cerrarlo»; ciérralo y pulsa «Reintentar pendientes de Excel» (o espera al
  siguiente registro / reinicio).

Validado el 2026-06-05 con un test aislado (31 comprobaciones: idempotencia, IVA mixto, backup,
cola/drenado) y un smoke test contra el servicio real en CT-104.
