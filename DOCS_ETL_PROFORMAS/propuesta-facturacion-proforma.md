# Pipeline de facturas proforma — Propuesta de arquitectura

**Guías de Alicante · generación de proformas, registro para Hacienda y enlace con Factusol**
*Documento de propuesta · v1 · 2026-06-01 · pendiente de implementar*

> **Qué es este documento.** Una propuesta de diseño, **no** código implementado. Recoge la idea y la arquitectura sugerida. Cuando se da el visto bueno, se implementa por fases. Todas las decisiones marcadas abajo ya están acordadas.

---

## 1. Resumen ejecutivo

El **factura-processor** (CT 104) hace el camino de *entrada*: lee las facturas recibidas en Gmail, las interpreta con IA y las vuelca a Excel/PDF/base de datos. Lo que se añade ahora es el camino de *salida*: una herramienta para **generar proformas** cuando se confirma un servicio, con un panel web parecido, que ahorre tiempo y mantenga ordenado el papeleo.

### Qué hará la herramienta ✅

- Guardar **clientes** y un **catálogo de servicios** con precios reutilizables.
- Crear una **proforma** en segundos eligiendo cliente + líneas de servicio.
- Generar el **PDF de la proforma** con la plantilla HTML de empresa.
- Registrar cada operación en el **Excel definitivo para Hacienda**.
- Preparar un **fichero de importación para Factusol** en una carpeta del NAS.

### Qué NO hará (a propósito) ❌

- No emite la **factura legal/electrónica**. Una proforma *no* es un documento fiscal.
- No sustituye a **Factusol**: la factura oficial (y el cumplimiento **Verifactu**) se sigue emitiendo desde Factusol en el PC.
- No toca el PC ni se conecta directamente a la base de datos de Factusol.

> **Filosofía:** la app se encarga de lo repetitivo y tedioso (datos, proforma, Excel, preparar la importación); Factusol se queda con lo que la ley exige que haga un programa certificado (la factura electrónica).

---

## 2. Decisiones acordadas

| Tema | Decisión | Por qué |
|---|---|---|
| **Dónde se aloja** | CT 104, puerto `5114`, RAM subida a 1 GB. | App ligera. Evita crear otro CT con RAM ajustada. Poca contención con el cron horario del processor. |
| **Documentos que genera** | Solo la **proforma** (PDF). La factura legal la emite Factusol. | Más simple y sin riesgo legal. |
| **Enlace con Factusol** | **Fichero de importación** en carpeta del NAS (Samba); se importa desde el PC. | Factusol vive en el PC. Método soportado oficialmente por DELSOL. |
| **Entrada de datos** | **Formulario web + catálogo** de clientes y servicios guardados. | El ahorro real viene de no re-teclear; se reutilizan clientes y precios. |

---

## 3. Flujo de trabajo

```
PRESUPUESTO          CONFIRMACIÓN            LA APP (CT 104)                       PC
───────────          ────────────            ───────────────                      ────
                                         ┌─────────────────────────┐
Pasas precio  ─────►  El cliente    ───► │ 1. Nueva proforma        │
al cliente            confirma           │    (cliente + servicios) │
                                         │ 2. Genera PDF proforma   │──► PDF a cliente / NAS
                                         │ 3. Apunta en Excel       │──► Excel Hacienda (NAS)
                                         │    "definitivo Hacienda" │
                                         │ 4. Prepara fichero       │──► carpeta factusol-import
                                         │    de importación        │        (NAS / Samba)
                                         └─────────────────────────┘                │
                                                                                     ▼
                                                                         ┌────────────────────────┐
                                                                         │ Abres Factusol e        │
                                                                         │ IMPORTAS el fichero     │
                                                                         │ → emites la FACTURA     │
                                                                         │   ELECTRÓNICA (Verifactu)│
                                                                         └────────────────────────┘
```

Estados de cada proforma: `borrador` → `enviada` → `confirmada`. Los pasos 3 y 4 se disparan al marcar como `confirmada`.

---

## 4. Arquitectura técnica

### Servicio web
- **Flask** en CT 104, servicio systemd `proforma-admin`.
- Puerto **5114**, accesible solo por **Tailscale** + **HTTP Basic Auth**.
- Mismo estilo visual que el panel actual (reutiliza CSS/auth del factura-processor).

### Base de datos
- **SQLite (modo WAL)** en el NAS: `/mnt/empresa/proforma-admin/proformas.db`
- Independiente de la del processor (no se mezclan datos).
- Backup diario verificado (mismo patrón que `backup_db.sh`).

### Generación del PDF
- Plantilla **HTML** → motor **Jinja2** (rellena los datos).
- HTML → PDF con **WeasyPrint** (librería Python pura).
- Numeración automática con serie: `PRO-2026-0001`.

### Excel para Hacienda
- **openpyxl**, con el patrón robusto del processor: copia de seguridad antes de escribir, reintentos si el Excel está abierto, cola de pendientes si sigue bloqueado.

### Modelo de datos (tablas SQLite)

```sql
-- clientes/agencias reutilizables  (columna "Agencia" del Excel)
clientes(id, nombre_agencia, nif_cif, direccion, cp, poblacion, provincia, email, telefono, codigo_factusol)

-- catálogo de servicios con precio
articulos(id, codigo, descripcion, precio, porcentaje_iva, familia)

-- guías que realizan el servicio  (columna "Guía": Alisa, ...)
guias(id, nombre)

-- cabecera: la proforma
proformas(id, numero_proforma, fecha, cliente_id, guia_id, estado,
          base, iva_total, suplidos, total, total_suplidos,
          comentarios, ruta_pdf,
          numero_factura, trimestre, cobrado,
          exportada_excel, exportada_factusol)

-- líneas de cada proforma
proforma_lineas(id, proforma_id, articulo_id, descripcion, cantidad, precio,
                porcentaje_iva, importe)

-- contador de numeración
series(serie, anio, ultimo_numero)
```

### Excel para Hacienda — mapa de columnas (orden real)

Orden y nombres confirmados con el Excel real de la empresa. Ejemplo de fila:
`01 | 10/01 | 01 | BXXXXX | 1 | Traditional Tours SLU | Gerona | 440,00€ | 92,40€ | 532,40€ | 20,00€ | 552,40€ | 18/12 | Grupo 1 09 y 10/01/2026 | 106 | Elisa`

| # | Columna | Origen | Notas |
|---|---|---|---|
| 1 | **Índice** | auto | Correlativo de fila. |
| 2 | **Fecha Factura** | manual | Fecha de emisión (dd/mm). Se rellena al facturar en Factusol. |
| 3 | **Nº Proforma** | **la app ★** | Generado por la app (`PRO-YYYY-NNNN`). Columna clave del enlace. |
| 4 | **NIF/CIF** | ficha del cliente | El de la agencia. Se reutiliza. |
| 5 | **Tr** (trimestre) | auto | Derivado de la fecha (1–4). |
| 6 | **Agencia** | ficha del cliente | Nombre de la agencia/cliente. |
| 7 | **Provincia** | ficha del cliente | Se reutiliza. |
| 8 | **Base** | calculado | Suma de las líneas de la proforma. |
| 9 | **IVA** | fórmula | Base × % IVA (21% en el ejemplo: 440 × 21% = 92,40 €). |
| 10 | **Total** | fórmula | Base + IVA. |
| 11 | **Suplidos** | manual | Gastos por operación (entradas, transporte…). |
| 12 | **Total + suplidos** | fórmula | Total + Suplidos. |
| 13 | **Cobrado** | manual | Fecha de cobro (dd/mm). Vacío hasta que se cobra. |
| 14 | **Comentarios** | proforma | Descripción del servicio (grupo y fechas del tour). |
| 15 | **Nº Factura** | manual / Factusol | Número de la factura legal emitida en Factusol. Se rellena a posteriori. |
| 16 | **Guía** | catálogo de guías | Nombre del guía que realiza el servicio. |

> **Columnas que rellena la app automáticamente al confirmar la proforma:** Nº Proforma (3), NIF/CIF (4), Tr (5), Agencia (6), Provincia (7), Base (8), IVA (9), Total (10), Total+suplidos (12), Comentarios (14), Guía (16).
> **Columnas que se rellenan a mano después:** Fecha Factura (2), Suplidos (11), Cobrado (13), Nº Factura (15).

---

## 5. Pantallas del panel

| Pantalla | Qué permite |
|---|---|
| **Clientes** | Alta/edición de clientes; se reutilizan en cada proforma. Campo opcional *código Factusol*. |
| **Catálogo de servicios** | Lista de servicios habituales con precio, % IVA y % IRPF por defecto. |
| **Nueva proforma** | Elige cliente, añade líneas desde el catálogo (o libres); totales calculados automáticamente. |
| **Listado de proformas** | Filtros por estado/cliente/fecha. Cambio de estado borrador→enviada→confirmada. |
| **Exportar** | Descargar PDF, registrar en Excel Hacienda, generar fichero Factusol. |
| **Configuración** | Serie/numeración, datos de empresa, rutas, credenciales del panel. |

---

## 6. Qué reutilizamos del factura-processor

| Pieza existente | Para qué |
|---|---|
| `admin_helpers.py` | Autenticación HTTP Basic y helpers comunes del panel. |
| `admin_ui.py` | CSS y barra de navegación → mismo aspecto que el panel actual. |
| Patrón de `db.py` | Capa SQLite en modo WAL, context manager, índices y acceso seguro. |
| Escritura Excel de `pipeline.py` | Backup previo + reintentos + cola de pendientes si el Excel está abierto. |
| Plantilla systemd + `backup_db.sh` | Servicio que arranca solo y backup diario verificado. |

---

## 7. Integración con Factusol

Factusol importa datos desde ficheros **Excel (.xlsx)** a través de *Utilidades → Importaciones → Ficheros .XLSX*. La app generará esos ficheros en `/mnt/empresa/factusol-import/` (visible desde el PC por Samba).

### Reglas del formato (oficiales de DELSOL)
- Un registro por fila, un campo por columna; **sin filas vacías** entre registros.
- Las columnas **A y B son obligatorias** (código y nombre/descripción).
- Campos numéricos: solo números, coma decimal y signo; **2 decimales** como máximo.

### Qué exportaremos
- **Clientes** nuevos (para que existan en Factusol antes de facturar).
- **Artículos/servicios** del catálogo (opcional, una sola vez o cuando cambien).
- El **documento** de la operación confirmada, para que en Factusol solo haya que revisar y emitir la factura electrónica.

> **¿Por qué no emitir la factura electrónica desde la app?** Con **Verifactu** la factura debe salir de un programa certificado de inalterabilidad y registro. Factusol ya lo hace. Replicarlo sería mucho trabajo y un riesgo legal innecesario.

---

## 8. Impacto en el host y estabilidad

- **RAM:** CT 104 subido a 1 GB (desde 512 MB, 2026-06-04) para alojar el segundo servicio con holgura.
- **Aislamiento:** servicio y base de datos separados del processor; el cron horario de facturas recibidas no se toca.
- **Rollback sencillo:** `systemctl stop proforma-admin && systemctl disable proforma-admin`. El factura-processor queda intacto.

---

## 9. Plan de implementación por fases

| Fase | Contenido |
|---|---|
| **Fase 1** | Catálogo + proforma + PDF. Clientes, servicios, crear proforma con cálculo de totales y generar el PDF con la plantilla. Ya útil por sí sola. |
| **Fase 2** | Excel para Hacienda. Registro automático de cada operación con el patrón robusto del processor. |
| **Fase 3** | Export a Factusol. Ficheros de importación en la carpeta del NAS, según la documentación técnica de la instalación de Factusol. |
| **Fase 4** | Estados y pulido. Flujo borrador→enviada→confirmada, filtros, numeración por serie y pequeños automatismos. |

---

## 10. Lo que se necesita para implementar

- La **plantilla HTML** de la proforma (con los huecos a rellenar: cliente, líneas, totales…) → subir a `DOCS_ETL_PROFORMAS/`.
- La **documentación técnica de importación** de Factusol (*Utilidades → Importaciones → "Descargar documentación técnica"*) → subir a `DOCS_ETL_PROFORMAS/`.
- Cómo se quiere la **numeración/serie** de proformas (formato y si reinicia cada año) y cómo casa con el **Nº Factura** de Factusol.
- La lista de **guías** habituales para precargar el catálogo.
- Datos fijos de empresa para el pie de la proforma (razón social, NIF, dirección, IBAN, etc.).
