# Revisión de interfaz — proforma-admin

> Una sección por pasada de capturas (`herramientas/capturas_panel.py`). Las
> imágenes no se suben al repo: viven en `/tmp/capturas-proformas/<sufijo>/` del
> host y se rehacen cuando hagan falta. Aquí queda **lo que se vio**, con
> palabras, y lo que quedó pendiente de decidir.
>
> Regla de oro de la spec (`/root/documentacion/spec-proforma-admin-ui-lawsofux-2026-09-22.md`):
> **nada cambia de sitio, de nombre ni de aspecto a 1280 px** para la usuaria.
> Lo que una regla de la skill exigiría mover se anota abajo como *pendiente de
> decisión* y **no se aplica**.

---

## Pasada `antes` — 2026-09-22 (Fase 0)

Servidor de pruebas en `:5124` con los datos inventados de
`herramientas/datos_prueba.py`. 32 capturas (16 pantallas × móvil 390 px y
escritorio 1280 px), solo esquema claro. **25 con avisos.**

### Lo que se ve

- **A 1280 px el panel está bien.** Rejilla regular, un solo acento (`--navy`),
  la tabla cabe, las acciones de cada fila en su cuadrícula 2×2. Esta es la
  imagen que hay que conservar intacta.
- **A 390 px ninguna pantalla cabe: las 16 desbordan.** Y siempre por lo mismo:
  `ul.nav-links` mide **811 px** (las 7 entradas en una fila que no se pliega),
  así que el documento entero mide 811 px de ancho. El contenido sí se ha
  maquetado a 390 y queda una franja de 421 px de fondo vacío a la derecha —
  media pantalla desperdiciada en cada scroll horizontal.
- `proformas/nueva` y `editar` desbordan aún más (**860 px**): a los 811 del
  menú se suma la tabla de líneas.
- **Las tablas se cortan.** `.table-wrap` tiene su scroll propio (bien: la
  página no debería desbordar por ellas), pero a 390 px se ve «Número, Fecha,
  Cliente» y la columna Guía queda partida por la mitad; Total, Estado y
  Acciones no existen para quien mire el móvil. La tabla de la bandeja
  «¿las enviaste?» **no** está en un `.table-wrap` y se sale sin scroll.
- **Objetivos de pulsación por debajo de 24 px** (Fitts pide 44): los enlaces de
  ordenación de las cabeceras (21 px de alto), los `input[type=checkbox]` de
  guías y de «predeterminada» (13×13), el botón de borrar línea `.btn-del-line`
  (25×23), y todos los `.btn-sm` (23 px): Marcar enviada, Filtrar, Eliminar
  guía, Eliminar cuenta.
- El diálogo de cobrar sí se comporta: a 390 px se queda en `min(360px, 92vw)`
  y no desborda por su cuenta.

### Lo que dicen los números del punto de partida (§1 de la spec, confirmado)

| | |
|---|---|
| `@media` en todo el CSS | **0** |
| `aria-*`, `role=`, `focus-visible` | **0** de cada |
| `outline: none` sin sustituto | **1** (`.form-group input:focus`) |
| `<caption>` en las tablas | **0** |
| Recurso externo | **1** (Google Fonts en `base.html`) |
| Hojas de estilo | 2 `<style>` inline (`base.html` 332 líneas, `ayuda.html` ~140) |

### Los que no salen limpios

| Criterio | Estado | Dónde |
|---|---|---|
| Sin scroll horizontal a 390 px | **no** | las 16 pantallas (causa: `ul.nav-links`) |
| Objetivos ≥ 44 px | **no** | `sort-link`, checkboxes, `.btn-sm`, `.btn-del-line` |
| `:focus-visible` en lo interactivo | **no** | todo el panel |
| Foco sin `outline: none` huérfano | **no** | `.form-group input:focus` |
| Tablas con `<caption>` | **no** | las 6 tablas |
| Flash con icono + texto + `aria-live` | **no** | `base.html` (solo color) |
| `aria-current="page"` en el nav | **no** | `base.html` (usa `class="active"`) |
| Cero recursos externos | **no** | Google Fonts |
| Un solo CSS con tokens | **no** | 2 `<style>` inline, 24 hex, estados fuera de `:root` |
| Cada campo con su `label` | **parcial** | listas dinámicas de `nueva`/`editar` sin etiqueta |
| Un solo `h1` por pantalla | **sí** | — |
| `lang="es"` | **sí** | `base.html` |
| Estados con texto (no solo color) | **sí** | píldoras `badge-*` llevan la palabra |
| Un único elemento destacado (Von Restorff) | **sí** | «Descargar PDF y marcar enviada» en el detalle |
| Modales `<dialog>` nativos | **sí** | los cuatro; falta `autofocus` |
| Contraste AA | **por medir** | ojo con `--stone` sobre `--sand` y `--gold` como texto |

### Pendiente de decisión del usuario

1. **Fechas en ISO a la vista.** El listado, la bandeja «¿las enviaste?» y el
   detalle pintan `2026-09-17`, no `17/09/2026`. La regla 9 de la skill pide
   formato español, pero es un **cambio visible** en pantallas que la usuaria
   mira a diario → no se aplica sin decirlo. (Afecta a `proformas/lista.html`,
   `detalle.html` y la bandeja de `base.html`/`lista.html`.)
2. **Objetivos de 44 px.** Subir `.btn-sm` de 23 a 44 px de alto **cambiaría el
   aspecto** de todas las filas del listado a 1280 px. Propuesta para cuando se
   decida: dejarlos como están en escritorio y engordarlos solo por debajo de
   720 px (Fase 5). Los checkboxes de 13×13 sí se pueden subir a 18–20 px sin
   que nadie lo note, pero también es aspecto: va aquí.
3. **La tabla de la bandeja «¿las enviaste?»** no tiene `.table-wrap`. Meterla
   en uno no mueve nada a 1280 px y arregla el desborde en móvil → **esto sí se
   hará** en la Fase 5, se anota solo para dejar constancia de por qué.

### Herramientas que quedan montadas

- `herramientas/datos_prueba.py` — 3 clientes, 3 artículos, 2 guías, 2 cuentas,
  6 proformas (2 borradores —uno con 12 líneas y un concepto de 140 caracteres—,
  2 enviadas, 1 cobrada, 1 borrador con el PDF descargado para que salga la
  bandeja y el contador del nav) y empresa «Empresa de Ejemplo S.L.».
- `herramientas/servidor_pruebas.sh arrancar|parar` — segunda instancia en
  `:5124` dentro del CT, con base, Excel, PDF y colas en `/tmp` y contraseña
  aleatoria por arranque. `parar` mata por PID (y, de red, a quien tenga el
  5124): **nunca por patrón**, que se llevaría el servicio real.
- `herramientas/capturas_panel.py` — Chromium en el host (venv
  `/root/.venv-capturas`), nunca contra `:5114`.
- **Firewall:** el CT 104 no lo tiene activo; `:5124` se alcanza desde el host
  sin añadir ninguna regla. No hubo que tocar `red-ips.md`.
