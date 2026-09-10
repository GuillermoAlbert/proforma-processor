# Estado del proyecto — proforma-admin

> **Última actualización: 2026-09-10.** Fuente de verdad del estado. Se
> actualiza **en el mismo commit** de cada pieza: lo terminado pasa a
> «Historial» (fecha + commit), «Pendiente» refleja lo que queda.

## Qué funciona hoy

- Catálogo completo (clientes, artículos, guías, cuentas bancarias de cobro) y
  creación de proformas con líneas dinámicas y totales en vivo.
- Alta rápida sin salir del formulario de proforma (modales + `/api/*`):
  cliente, artículo y guía. El navegador avisa si se abandona la página con
  cambios sin guardar.
- PDF con WeasyPrint (plantilla del brand kit, número corto `PREFIJO-AA-NNNN`
  en cabecera, bloque de pago según la cuenta asignada, guías nunca en el PDF).
  Fuentes **locales** (`DOCS_ETL_PROFORMAS/fuentes/`) y **ajuste automático a
  una hoja** cuando el contenido se desborda. El estado interno **no** se
  imprime; un borrador solo produce vista previa con marca de agua.
- **Descargar el PDF de un borrador es enviarlo**: el botón principal
  (`/enviar-y-descargar`) genera el definitivo, marca `enviada`, escribe la fila
  del Excel y descarga. Bandeja «¿las enviaste?» en el listado + contador en el
  nav para los borradores cuyo PDF ya se descargó.
- Flujo de 3 estados `borrador → enviada → cobrada` con deshacer simétrico;
  registro automático en el Excel de Hacienda al enviar y fecha de cobro en la
  col `Cobrado` al cobrar (backup + lock + reintentos + cola).
- API para CT108 (`api_orquestador.py`): lectura de proformas/clientes/cobros
  vencidos + `POST /api/proformas/borrador` (única escritura, siempre borrador).
- Datos de empresa y serie configurables en BD (`get_empresa_config` /
  `get_serie_config`), no hardcodeados.

## Pendiente

- **Fase 3 · Export Factusol** — bloqueada: falta `factusol-importacion.pdf`
  en `DOCS_ETL_PROFORMAS/` (🧍 Guillermo). El campo `exportada_factusol` ya
  existe en el schema.
- **Fase 4 · restos**: filtros del listado hechos (estado, cliente y buscador,
  2026-09-04); queda el filtro por rango de fechas y pulido suelto de UI.
- Decisión aparcada (2026-06-12, no reabrir sin preguntar): endpoint de
  escritura `POST /api/proformas/<id>/cobrar` para que CT108 marque cobradas —
  preparado pero **no implementado a propósito**.

## Historial

- **2026-09-10** — `c474617`→`0f576f3` **el flujo de envío arreglado, la 26-054
  en una hoja y las fuentes en local.** Cuatro cosas, en este orden:

  1. **Fuentes locales** (`c474617`). WeasyPrint bajaba Lora e Inter de
     `fonts.googleapis.com` en CADA render: 1,39 s por PDF, 1,05 s de descarga,
     y sin red el PDF salía en Georgia/Arial sin avisar. Ahora los cuatro woff2
     (latin + latin-ext, variables) viven en `DOCS_ETL_PROFORMAS/fuentes/` con
     `@font-face`. **0,50 s por PDF.** `pdffonts` confirma que se embeben.
  2. **El estado interno fuera del PDF** (`e542626`). Siete de los ocho PDF que
     había en `proformas-pdf/` llevaban impresa la palabra «Borrador» — y son
     los que se mandaron a las agencias. Fuera el sello (y su rama muerta
     `confirmada`); en su lugar, marca de agua «BORRADOR · SIN VALIDEZ» que
     depende de **cómo se pide** el PDF (`borrador_preview`), no del estado.
  3. **Ajuste automático + vista previa + fix del Excel** (`4b50e02`).
     La 26-054 se iba a dos páginas: le faltaban ~90 px de los 1069,6 útiles y
     `.payment-box` (con `break-inside: avoid`) saltaba entera. `pdf.py`
     renderiza normal y **solo si sale a más de una página** reintenta con
     peldaños de compactación del espaciado (y la tipografía −6 % como último
     recurso). Las 14 proformas reales caben ya en una hoja; las que cabían no
     cambian. ⚠ Las hojas de `render(stylesheets=)` van **antes** del `<style>`
     del documento: necesitan `!important` o no hacen nada (WeasyPrint 69).
     `generar_pdf_preview()` devuelve el PDF **en memoria** y no toca
     `ruta_pdf`; `GET /pdf` sobre un borrador sirve siempre la vista previa
     ignorando `ruta_pdf`, lo que neutraliza los siete PDF cacheados con sello.
     `/enviar` y `/desenviar` invalidan `ruta_pdf` y borran el fichero.
     **Fix de la carrera del Excel fiscal**: el servicio es multihilo y un doble
     clic escribía DOS filas de la misma proforma (`exportada_excel` se miraba
     fuera del `_file_lock()`). Ahora la comprobación y la marca van dentro del
     lock, y la transición es atómica (`UPDATE … WHERE estado='borrador'` +
     `rowcount`). Reproducido con test que fuerza el solape: antes 2, ahora 1.
  4. **Descargar = enviar, y bandeja de pendientes** (`0f576f3`). Ocho de las
     últimas catorce proformas (5.154,60 €) seguían en borrador y fuera del
     Excel porque el botón de enviar no se pulsaba nunca. Nueva ruta
     `POST /proformas/<id>/enviar-y-descargar` como botón principal del
     borrador. La descarga se dispara desde `?descargar=1` con navegación
     normal, **no con un iframe oculto** — dentro de un iframe, un fallo de
     generación dejaba la proforma enviada, sin PDF y sin mensaje. Se bloquea si
     no hay cliente (la fila del Excel saldría sin agencia ni NIF). Migración
     idempotente `_migrate_add_pdf_previsualizado_en`, que además sella los
     borradores que ya tenían PDF con la fecha del fichero (solo esa columna).
     Bandeja en el listado + contador en el nav. Ayuda reescrita.

  Plan y auditoría previa (un agente Fable revisó el plan contra el código y
  encontró el fallo del iframe, la carrera del Excel y que
  `_purgar_cache_pdf()` —que corre también al **guardar Configuración →
  Empresa**— vacía `ruta_pdf` de todo, que era el criterio frágil de la bandeja).
  Suite nueva `src/test_envio_y_vista_previa.py` (13 tests). **51 tests.**
  Las 8 proformas en borrador **no se enviaron**: decisión del usuario, se
  gestionan desde la bandeja.

- **2026-09-08** — **BIC/SWIFT en el PDF y en la lista de cuentas.** El campo
  `bic` ya existía en el formulario y en la BD (las dos cuentas lo tenían
  guardado), pero `pdf.py` no lo pasaba a la plantilla y
  `plantilla-proforma.html` no lo pintaba. Ahora la cuenta seleccionada aporta
  también `empresa.bic` y el bloque de pago muestra un par etiqueta/valor «BIC / SWIFT» en
  negrita, con el mismo estilo que el IBAN (solo si hay valor). La lista de cuentas tiene columna BIC / SWIFT.
  `test_pdf_gen.py` incluye el BIC en los datos de prueba. 38 tests OK.

- **2026-09-04** — tres mejoras pequeñas pedidas tras el arreglo de numeración:
  (1) **Duplicar proforma** (`POST /proformas/<id>/duplicar`, botón en listado y
  detalle): crea un borrador con cliente, cuenta, guías, líneas, suplidos,
  comentarios y referencia; fecha de hoy, número nuevo de la serie y **fechas de
  servicio de las líneas en blanco** a propósito. (2) **Filtros del listado** por
  estado y cliente + buscador (número, agencia o comentarios); los macros
  `sort_th`/`pagination_bar` aceptan `extra` para conservarlos al ordenar y
  paginar. (3) Pulido: modales con Escape / clic fuera / Enter, alta de guía y
  de cliente sin duplicados también desde el catálogo y desde `/api/clientes`
  (helper `_ya_existe`), y el aviso de cambios sin guardar movido a `base.html`
  (`<form data-avisar-cambios>`), aplicado también a los formularios de cliente,
  cuenta y artículo. Suite nueva `src/test_duplicar_y_filtros.py` (13 tests).
- **2026-09-04** — `b080f75`→ el número de proforma se rehace solo cuando cambia
  lo que lo compone. Con series tipo `{serie}-{aa}-{n}-{agencia}-{mes_corto}_{aa}`,
  un borrador creado sin cliente (lo permite `POST /api/proformas/borrador` del
  asistente) nacía con el hueco de la agencia vacío y ya no se arreglaba nunca:
  `/proformas/<id>/editar` conservaba el número tal cual. Ahora:
  `db.formatear_numero_proforma()` reconstruye un número con **su mismo
  secuencial**; al guardar una edición en borrador con el número intacto se
  renumera con el cliente y la fecha de ese momento (`_renumerar_borrador`, que
  no toca proformas enviadas/cobradas ni pisa un número ya usado);
  `/api/peek-numero?proforma_id=` previsualiza el de una proforma existente y
  `editar.html` lo refresca en vivo como ya hacía `nueva.html`; en el alta, si
  la serie usa `{agencia}` el campo va `readonly` (el número escrito a mano se
  descartaba en silencio). Suite nueva: `src/test_numeracion_agencia.py`
  (15 tests). Las dos suites fijan `db.DB_PATH` en su fixture y ya se pueden
  correr juntas.
- **2026-09-04** — `bec067c` alta rápida de guía desde el formulario de proforma:
  `POST /api/guias` (rechaza vacío y duplicado `COLLATE NOCASE`) + modal
  «Nuevo guía» con el mismo patrón que el de cliente, en `nueva.html` y
  `editar.html`; el guía creado se inserta marcado y en orden alfabético en la
  lista de checkboxes. Añadido además el aviso `beforeunload` al salir del
  formulario con cambios sin guardar (compara un snapshot `FormData` del
  formulario, así que detecta también líneas añadidas, borradas o reordenadas).
  Repaso de copy: **«guía» es masculino en toda la app** («el guía», «Guía
  creado»), y los botones «+ Nuevo» de cliente y de guía van los dos en la fila
  del encabezado del campo, no pegados al desplegable.
- **2026-08-14** — modo de dirección de la empresa en el PDF:
  `empresa.direccion_modo` (`completa` / `poblacion` / `oculta`) sustituye al
  checkbox binario `mostrar_direccion` (migración idempotente
  `_migrate_mostrar_direccion_a_modo`; `'0'` → `oculta`). Selector en
  Config → Empresa, render extraído a `pdf.render_proforma_html()` y primera
  suite pytest del repo: `src/test_direccion_modo.py` (10 tests, TDD).
- **2026-07-05** — `e9a432d` número corto en el PDF + cabecera sin desbordes
  (consolidado de una sesión anterior) y `test_pdf_gen.py` reparado (filtros
  jinja). `6cb0feb` `POST /api/proformas/borrador` para la pieza 4 de CT108
  (desplegado con instancia aislada de prueba, 9 casos verificados).
- **2026-06-12** — `47a53bd`→`ff21780` modelo de 3 estados
  `borrador→enviada→cobrada` (migración idempotente desde `confirmada`),
  «Marcar cobrada» con fecha editable en modal reutilizable, fecha de cobro al
  Excel. Fase 4 parcial.
- **2026-06-09** — `ebedaa3` blueprint `/api/*` de lectura para CT108 (Fase 0
  del asistente).
- **2026-06-05/08** — Fase 2: registro en Excel Hacienda al confirmar
  (backup+lock+reintentos+cola); mejoras de numeración y listado (`7186c32`);
  toggle DeepSeek (`d16aad3`). Detalle Fase 2:
  `DOCS_ETL_PROFORMAS/fase2-excel-hacienda.md`.
- **2026-06-04** — Fase 1: BD + catálogo + proformas + PDF WeasyPrint.
  RAM de CT104 subida a 1 GB para alojar este segundo servicio.
