# Estado del proyecto — proforma-admin

> **Última actualización: 2026-09-04.** Fuente de verdad del estado. Se
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
