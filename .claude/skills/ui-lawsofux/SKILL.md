---
name: ui-lawsofux
description: Diseñar y revisar las pantallas de proforma-admin (Flask + Jinja2, HTML servido en servidor) aplicando las leyes de UX de lawsofux.com — usar SIEMPRE antes de crear o cambiar una plantilla, un formulario, una tabla, el CSS o el JS inline del panel.
---

# Leyes de UX aplicadas al panel de proformas

Cuándo aplicar: cada vez que se cree o modifique una plantilla Jinja2, un formulario, una tabla, una tarjeta, un mensaje de estado o la navegación del panel. Antes de dar el trabajo por terminado, pasar la tabla de leyes como criterio de diseño y el checklist final como control de calidad. No es teoría decorativa: cada ley se traduce en una regla comprobable sobre HTML/CSS concreto.

## Contexto del proyecto (dar por sentado)

- HTML renderizado en servidor con **Flask + Jinja2**. Sin frameworks JS.
- **Quien lo usa** es una persona sin perfil técnico, a diario, para crear, guardar, descargar y
  enviar proformas. **No se mueve, renombra ni reagrupa nada que ya use** sin decisión explícita
  del usuario (dueño del proyecto). La Ley de Jakob aquí es «lo que ella ya conoce», no lo que
  conoce Internet.
- **Un solo fichero CSS: `src/static/estilos.css`, ≤ 24 KB** (lo vigila `src/test_ui.py`; para
  subir el tope, primero buscar de dónde recortar y anotar el motivo en `docs/revision-ui.md`).
  Tokens en `:root`: la paleta de marca (`--navy` acento y acciones primarias, `--terra` solo
  peligro/error, `--gold` solo aviso, `--sand`/`--ink`/`--stone` fondos y texto), los tres pares
  de estado (`--ok`/`--ok-fondo`, `--error`/`--error-fondo`, `--aviso`/`--aviso-fondo`), espaciado
  en escala 4/8/12/16/24/32/48 px, `--radius 8px`. **Ningún color hex fuera de `:root`.**
- **Tipografía de marca:** Lora (títulos) e Inter (interfaz), **servidas en local** desde
  `src/static/fuentes/` con `@font-face` (`font-display: swap`), con `Georgia, serif` y
  `system-ui, sans-serif` de respaldo. **Ningún recurso externo** (fuentes, CDN, iconos): el
  panel se usa por Tailscale y tiene que funcionar sin salida a Internet.
- **Solo modo claro** (decisión del 2026-09-22). Si algún día se añade el oscuro, será por
  `prefers-color-scheme` y con tokens, nunca duplicando reglas.
- **JavaScript:** existe y se queda (líneas dinámicas de la proforma, totales en vivo, aviso de
  cambios sin guardar, modales `<dialog>` de alta rápida). Regla para lo nuevo: **nada de JS para
  lo que HTML ya resuelve** (`<details>`, `required`, `pattern`, `<dialog>` con `showModal()` de
  una línea); un bloque nuevo de JS se justifica en `docs/revision-ui.md` y no pasa de 40 líneas.
- **Escritorio primero, móvil digno.** La pantalla de referencia es 1280 px. A 390 px la página
  **no puede tener scroll horizontal** (las tablas sí, dentro de `.table-wrap`) y todo se puede
  usar.
- **Contraste AA** (4.5:1 texto normal, 3:1 texto grande y UI). Ojo con `--stone` sobre `--sand`
  y con el dorado `--gold` como texto: comprobarlos, no suponerlos.
- **Los estados** (éxito, error, aviso, pendiente) siempre con icono + texto + color. Los iconos
  son SVG inline del sistema de marca o caracteres Unicode neutros (✓ ✕ !), nunca emojis.
- **Se revisa con capturas, no de memoria:** `herramientas/capturas_panel.py` (abajo, «Antes de
  dar por terminado»). Nunca contra `:5114`.
- **El PDF no es de esta skill.** `pdf.py` y `DOCS_ETL_PROFORMAS/plantilla-proforma.html` tienen
  sus propias reglas (brand-kit); la skill solo cubre el panel web.

## Las leyes, aplicadas

| Ley / efecto | Enunciado | En este panel |
|---|---|---|
| **Ley de Fitts** | El tiempo para alcanzar un objetivo depende de su tamaño y de la distancia hasta él. | Botones primarios (acción de guardar/confirmar) ≥ 44×44 px y pegados físicamente al elemento que afectan (p. ej. el botón «Guardar» dentro del propio formulario, no en un menú aparte). |
| **Ley de Hick** | El tiempo de decisión crece con el número y la complejidad de las opciones. | Máximo 5 acciones visibles por pantalla; el resto va agrupado bajo un «Más» (`<details>`). Los formularios largos se dividen en secciones con encabezado claro, no en una sola lista plana. |
| **Ley de Jakob** | Los usuarios transfieren a un sitio nuevo las expectativas de los sitios que ya conocen. | Usar patrones estándar: `label` encima del campo, tabla con cabecera `thead` fija y filas alternas, botón primario a la derecha/abajo del formulario, breadcrumbs o navegación en la cabecera. No inventar interacciones propias. |
| **Ley de Miller** | La memoria de trabajo retiene unos 7 (±2) elementos. | Ninguna lista de opciones (select, checkboxes, menú) supera 7-9 ítems sin agrupar; si hay más, se buscan o se paginan. |
| **Fragmentación / Chunking** | La información se retiene mejor si se agrupa en bloques con sentido. | Agrupar campos relacionados en tarjetas (`<fieldset>`) de ≤ 7 elementos, con un título de grupo claro. |
| **Ley de Prägnanz** | Ante formas ambiguas, se percibe la interpretación más simple. | Layouts de rejilla regular, alineación consistente, evitar formas o agrupaciones visuales irregulares. |
| **Navaja de Occam** | Entre soluciones válidas, elegir la que hace menos suposiciones / es más simple. | Quitar de la pantalla todo lo que no ayude a decidir: sin adornos, sin campos opcionales visibles por defecto, sin textos redundantes. |
| **Ley de Proximidad** | Los elementos próximos se perciben como un grupo. | Espaciado entre grupos de campos (24-32 px) claramente mayor que el espaciado interno de cada grupo (8-12 px). |
| **Ley de la Semejanza** | Elementos con el mismo aspecto visual se perciben como del mismo tipo. | Un solo estilo de botón por función (primario/secundario/peligro); no mezclar formas o colores para el mismo tipo de acción en distintas pantallas. |
| **Ley de Región Común** | Los elementos dentro de un borde o fondo compartido se perciben agrupados. | Tarjetas con borde/fondo sutil para separar secciones del formulario o bloques de la tabla, en vez de solo espacio en blanco. |
| **Ley de Conectividad Uniforme** | Los elementos conectados visualmente (línea, color, marco) se perciben más relacionados que los no conectados. | Usar el mismo color de borde/acento para vincular una etiqueta de estado con su fila, o un enlace con la tarjeta a la que pertenece. |
| **Ley de Tesler** | Toda interfaz tiene una complejidad irreductible: si no la asume el sistema, la asume el usuario. | La complejidad que se pueda automatizar (detectar tipo de enlace, formato de fecha, validar formato) la resuelve el servidor; el usuario nunca rellena a mano algo que el sistema puede deducir. |
| **Ley de Postel** | Sé estricto en lo que envías, flexible en lo que aceptas. | Aceptar entradas variadas (URLs con o sin `https://`, con espacios sobrantes, mayúsculas/minúsculas) y normalizarlas en servidor; si no es válido, mensaje de error claro y específico, nunca genérico. |
| **Efecto Von Restorff** | Lo que difiere del resto se recuerda mejor. | Un único elemento destacado por pantalla (p. ej. la acción principal o el aviso crítico); si todo resalta, nada resalta. |
| **Efecto de posición en serie** | Se recuerda mejor lo primero y lo último de una lista; lo del medio se olvide. | La información más importante de una tabla o lista va al principio o al final visible (primeras columnas, primera fila, resumen final), no enterrada en medio. |
| **Efecto estético-usabilidad** | Un diseño visualmente cuidado se percibe como más usable, aunque no lo sea objetivamente. | Consistencia estricta de espaciado, una sola tipografía, un único color de acento — la pulcritud visual genera confianza. |
| **Umbral de Doherty** | La productividad se dispara cuando el sistema responde en menos de 400 ms. | Cualquier acción que tarde más de 400 ms muestra un indicador de carga (spinner, texto «Guardando…»); nunca una pantalla congelada sin señal. |
| **Regla de fin de pico (pico-final)** | Se juzga una experiencia por su momento más intenso y por cómo termina, no por el promedio. | El último paso de cualquier flujo (guardar, confirmar, vincular) muestra un mensaje de confirmación explícito y claro sobre qué ha pasado exactamente. |
| **Efecto Zeigarnik** | Se recuerdan mejor las tareas incompletas que las completadas. | En flujos de varios pasos (p. ej. vincular Telegram: 1. nombre → 2. código → 3. confirmado) mostrar siempre en qué paso está el usuario y cuántos faltan. |
| **Efecto de tendencia a la meta** | La motivación aumenta cuanto más cerca se está de terminar. | Barra o indicador de progreso en flujos multi-paso, reforzando visualmente la cercanía a completar la tarea. |
| **Ley de Parkinson** | Una tarea se expande para ocupar todo el tiempo disponible. | Formularios y procesos con límites claros (sin pasos opcionales que alarguen indefinidamente el flujo); pedir solo lo imprescindible en cada paso. |
| **Principio de Pareto** | El 80 % de los efectos provienen del 20 % de las causas. | Priorizar en pantalla las acciones y datos que cubren la mayoría de los casos de uso reales; lo infrecuente va en «más opciones» o en una pantalla secundaria. |
| **Paradoja del usuario activo** | Los usuarios no leen manuales, empiezan a usar la interfaz directamente. | La interfaz debe ser autoexplicativa sin necesitar ayuda externa: labels claros, placeholders con ejemplo, texto de ayuda visible junto al campo (no en un manual aparte). |
| **Atención selectiva** | El usuario filtra e ignora lo que no coincide con lo que busca. | Reducir ruido visual alrededor de la acción principal de cada pantalla; nada compite con lo que el usuario vino a hacer. |
| **Carga cognitiva / Memoria de trabajo** | Hay un límite de información que se puede procesar y retener a la vez. | No pedir que el usuario recuerde datos de una pantalla a otra; repetir el contexto necesario (p. ej. mostrar qué registro se está editando). |
| **Modelo mental** | El usuario interpreta la interfaz según expectativas previas de cómo «debería» funcionar. | Nombrar acciones y campos con el vocabulario que el usuario ya usa (evitar jerga técnica interna del proyecto). |
| **Sesgo cognitivo / Sobrecarga de opciones** | Demasiadas opciones simultáneas paralizan o llevan a peores decisiones. | Ofrecer un valor por defecto sensato en cada campo/selector siempre que sea posible, en vez de forzar a elegir entre muchas opciones neutras. |
| **Fluir (Flow)** | El estado óptimo se da cuando el reto encaja con la habilidad, sin fricción ni distracción. | Minimizar interrupciones (confirmaciones innecesarias, redirecciones extra) en tareas repetitivas y bien conocidas por el usuario habitual del panel. |

## Reglas de la casa (lo que ya está decidido; no reinventarlo)

Arrancan con las que salen de la spec del 2026-09-22 y crecen con cada pasada de capturas
anotada en `docs/revision-ui.md`.

1. **Navegación:** 7 entradas en la cabecera, en este orden: Proformas (con contador), Clientes,
   Artículos, Guías, Cuentas, Configuración, Ayuda. Activa por `request.endpoint`, con
   `aria-current="page"`. No añadir entradas sin mirar el menú a 390 px.
2. **Botón principal de una proforma:** «Descargar PDF y marcar enviada» en el detalle del
   borrador (desde el 2026-09-10). Es **el** elemento destacado de esa pantalla (Von Restorff);
   nada más compite con él. No se renombra.
3. **Bandeja «¿las enviaste?»** en el listado con contador en el nav: se queda tal cual.
4. **Formularios:** `label` encima del campo, **cada `input`/`select`/`textarea` con su `label`
   asociado por `for`/`id`** (las líneas dinámicas de la proforma usan `aria-label` con el nombre
   de la columna, porque el `label` visible es la cabecera de la fila). Grupos de campos en
   `<fieldset>` con `<legend>` cuando hay más de 7 campos (Datos del cliente / Líneas / Totales /
   Pago). Botón de guardar dentro del `<form>`, abajo a la derecha, ≥ 44 px de alto.
5. **Tablas:** `<table class="data-table">` dentro de `.table-wrap` (scroll propio), con
   `<caption>` (puede ir visualmente oculto con `.visualmente-oculto`, pero existe), `<thead>` con
   la macro `sort_th`, y la columna del importe alineada a la derecha con `.num`.
6. **Estados:** `li.flash-{success,error,warning}` con icono + texto; el `ul.flash-list` lleva
   `role="status" aria-live="polite"`. Las píldoras de estado de proforma (borrador / enviada /
   cobrada) llevan texto siempre, nunca solo color.
7. **Foco:** `:focus-visible` con `outline: 2px solid var(--navy); outline-offset: 2px` en todo
   lo interactivo. `outline: none` prohibido sin sustituto.
8. **Modales:** solo `<dialog>` nativo, con `<form method="dialog">` para cancelar, un `h2` dentro
   y `autofocus` en el primer campo. Los tres de alta rápida y el de cobrar ya son así; lo nuevo, igual.
9. **Fechas** en formato español (`dd/mm/aaaa`), como ya hace el filtro del PDF; el ISO solo en
   `datetime="…"` y en `<input type="date">`.
10. **Textos:** los que usa la usuaria («proforma», «cobrada», «enviada»), no los internos
    (`estado`, `borrador_id`). Placeholders con ejemplo real: `Ej.: Agencia Sol y Playa S.L.`.

### Móvil: las tablas apiladas (desde la Fase 5, 2026-09-22)

El panel se usa también en el móvil. Por debajo de **720 px** las tablas de datos no hacen
scroll: **cada fila se apila como una ficha**.

1. Cada `<td>` que no sea el principal lleva `data-etiqueta="Lo que dice su cabecera"`: es lo que
   se pinta delante del dato cuando la fila se apila. Sin `data-etiqueta`, en móvil sale una ficha
   de números sin nombre.
2. La celda principal —el número de proforma, el nombre del cliente— lleva `class="principal"` y
   sube al primer puesto. Un `<th scope="row">` hace de principal solo.
3. Una celda que apilada solo diría «—» lleva `class="solo-escritorio"` y desaparece.
4. En escritorio, el scroll horizontal es de `.table-wrap`, **nunca de la página**.
5. Números largos y descripciones se parten en `.principal`; no poner `overflow-wrap: anywhere`
   a toda la tabla, que estrecha las columnas hasta partir nombres letra a letra.
6. Un `<select>` o `<input>` dentro de una celda apilada necesita `min-width: 0`, o desborda.
7. El menú se pliega en un `<details class="nav-plegable">` cuyo `<summary>` dice **en qué sección
   estás** (plegado no se ve el `aria-current`, y el «dónde estoy» no se puede perder). En
   escritorio se abre de oficio y el rótulo se esconde.
8. **A 1280 px nada de esto se nota**: todas las reglas van dentro de `@media (max-width: 720px)`.

## Antes de dar por terminado: capturas

```bash
pct exec 104 -- bash -lc '/mnt/empresa/proforma-admin/herramientas/servidor_pruebas.sh arrancar'
/root/.venv-capturas/bin/python herramientas/capturas_panel.py despues              # todo
/root/.venv-capturas/bin/python herramientas/capturas_panel.py despues --solo proformas,proforma-nueva
/root/.venv-capturas/bin/python herramientas/capturas_panel.py --sonda /proformas/nueva   # qué se sale a 390 px
pct exec 104 -- bash -lc '/mnt/empresa/proforma-admin/herramientas/servidor_pruebas.sh parar'
```

Si el entorno no existe, la cabecera del script dice cómo crearlo (un venv aparte,
`/root/.venv-capturas`, con Playwright y Chromium; el navegador corre **en el host**, que el
CT 104 tiene 1 GB y no tiene Chromium).

Deja `/tmp/capturas-proformas/<sufijo>/` con una imagen por pantalla y vista. **Mirarlas**, sobre
todo las de 390 px y las dos de la proforma con 12 líneas. Cero «DESBORDA». Un solo navegador
cada vez, y `free -m` antes: el host lleva el LLM del CT 110 cargado. Antes de una fase, `antes`;
al acabar, `despues`; comparar.

## Checklist de revisión

Antes de dar por buena una plantilla, marcar:

- ☐ Nada que la usuaria ya usa ha cambiado de sitio, nombre o aspecto (si hace falta, va a `docs/revision-ui.md` como pendiente de decisión).
- ☐ Cada acción primaria mide ≥ 44 px y está junto a lo que afecta (Fitts).
- ☐ ≤ 5 acciones visibles por pantalla; el resto en «Más» (Hick).
- ☐ Cada `<input>`/`<select>`/`<textarea>` tiene un `<label>` asociado (`for`/`id`).
- ☐ Contraste AA en modo claro: ≥ 4.5:1 (texto normal) / 3:1 (grande o UI).
- ☐ Foco visible (`:focus-visible`) en todos los elementos interactivos, sin `outline: none` sin sustituto.
- ☐ Navegable por teclado de principio a fin (tab order lógico, sin trampas de foco).
- ☐ Los estados (éxito/error/aviso/pendiente) llevan icono + texto + color, nunca solo color.
- ☐ Mensajes dinámicos (confirmaciones, errores de validación) en un contenedor `aria-live="polite"`.
- ☐ Animaciones y transiciones respetan `prefers-reduced-motion: reduce`.
- ☐ La página es usable a 400 px de ancho sin scroll horizontal, **comprobado con `capturas_panel.py`** (0 «DESBORDA»), y las capturas de 390 px se han mirado.
- ☐ Cada tabla lleva `<caption>` y su `.table-wrap`.
- ☐ Toda tabla nueva lleva `class="principal"` en su celda principal y `data-etiqueta` en las demás, y se ha mirado apilada a 390 px.
- ☐ Cada `<dialog>` tiene `h2`, `autofocus` y cancelar por `method="dialog"`.
- ☐ Ningún recurso externo (`grep -r "https\?://" src/templates` solo devuelve enlaces a documentación, no `link`/`script`/`@import`).
- ☐ Campos agrupados en bloques de ≤ 7 elementos, con espaciado mayor entre grupos que dentro de ellos (Miller/Proximidad).
- ☐ Un único elemento destacado por pantalla, no varios compitiendo (Von Restorff).
- ☐ Entradas de usuario flexibles en lo que se acepta, normalizadas en servidor, con error específico si no son válidas (Postel).
- ☐ Toda acción que pueda tardar >400 ms muestra un indicador de progreso (Doherty).
- ☐ El paso final de cualquier flujo confirma explícitamente qué ha ocurrido (pico-final).
- ☐ Flujos de varios pasos muestran en qué paso está el usuario y cuántos quedan (Zeigarnik/tendencia a la meta).
- ☐ Un solo estilo de botón por función en todo el panel (Semejanza).
- ☐ Nada de lo mostrado obliga al usuario a recordar datos de otra pantalla (carga cognitiva).
- ☐ CSS sigue usando solo los tokens de `:root` (sin colores/espaciados sueltos fuera de la escala).
- ☐ JS nuevo: ninguno, o ≤ 40 líneas justificadas en `docs/revision-ui.md`.
- ☐ `python3 -m pytest src/test_ui.py` en verde dentro del CT.

## Antipatrones (no hacer)

- Emojis como parte de la interfaz (solo texto e iconos SVG/sistema consistentes).
- Más de un color de acento en toda la aplicación.
- Tablas de datos sin `<caption>` que explique qué contienen.
- Botón «Guardar» separado del formulario al que pertenece (rompe Fitts).
- `white-space: nowrap` en una cabecera de tabla para que algo no se descuelgue: ensancha la tabla hasta que hay que hacer scroll.
- Modales para lo que cabe en la propia página (rompen el flujo y el modelo mental).
- Texto en gris claro sobre blanco que no cumple contraste AA.
- Iconos sin texto que los acompañe (ambigüedad, no accesible).
- JavaScript para abrir/cerrar, mostrar/ocultar o validar algo que `<details>`, `:checked` o `required`/`pattern` ya resuelven.
- Campos opcionales visibles por defecto en vez de ocultos tras «más opciones» (Hick/Occam).
- Distinto estilo de botón o de tabla entre pantallas del mismo panel (rompe Jakob/Semejanza).

## Fuente

- Índice: https://lawsofux.com/es/
- Ley de Fitts — https://lawsofux.com/es/ley-de-fitts/
- Ley de Hick — https://lawsofux.com/es/ley-de-hick/
- Ley de Jakob — https://lawsofux.com/es/ley-de-jakob/
- Ley de Miller — https://lawsofux.com/es/ley-de-miller/
- Ley de Prägnanz — https://lawsofux.com/es/ley-de-pr%C3%A4gnanz/
- Ley de Proximidad — https://lawsofux.com/es/ley-de-proximidad/
- Ley de la Semejanza — https://lawsofux.com/es/ley-de-la-semejanza/
- Ley de Región Común — https://lawsofux.com/es/ley-de-regi%C3%B3n-com%C3%BAn/
- Ley de Conectividad Uniforme — https://lawsofux.com/es/ley-de-conectividad-uniforme/
- Ley de Tesler — https://lawsofux.com/es/ley-de-tesler/
- Ley de Postel — https://lawsofux.com/es/ley-de-postel/
- Ley de Parkinson — https://lawsofux.com/es/ley-de-parkinson/
- Efecto Von Restorff — https://lawsofux.com/es/efecto-von-restorff/
- Efecto de Posición en Serie — https://lawsofux.com/es/efecto-de-posici%C3%B3n-en-serie/
- Efecto de Estética-Usabilidad — https://lawsofux.com/es/efecto-de-est%C3%A9tica-usabilidad/
- Umbral de Doherty — https://lawsofux.com/es/umbral-de-doherty/
- Regla de fin de pico — https://lawsofux.com/es/regla-de-fin-de-pico/
- Efecto Zeigarnik — https://lawsofux.com/es/efecto-zeigarnik/
- Efecto de Tendencia a la Meta — https://lawsofux.com/es/efecto-de-tendencia-a-la-meta/
- La Navaja de Occam — https://lawsofux.com/es/la-navaja-de-occam/
- Principio de Pareto — https://lawsofux.com/es/principio-de-pareto/
- Paradoja del Usuario Activo — https://lawsofux.com/es/paradoja-del-usuario-activo/
- Atención selectiva — https://lawsofux.com/es/atenci%C3%B3n-selectiva/
- Carga Cognitiva — https://lawsofux.com/es/carga-cognitiva/
- La memoria de Trabajo — https://lawsofux.com/es/la-memoria-de-trabajo/
- Modelo Mental — https://lawsofux.com/es/modelo-mental/
- Sesgo Cognitivo — https://lawsofux.com/es/sesgo-cognitivo/
- Sobrecarga de Opciones — https://lawsofux.com/es/sobrecarga-de-opciones/
- Fluir — https://lawsofux.com/es/fluir/
- Fragmentación — https://lawsofux.com/es/fragmentaci%C3%B3n/
