# Brand Kit para documentos — GuiasdeAlicante

> Resumen de la identidad visual de la web para crear documentos coherentes
> (PDFs de tarifas, resúmenes de tours, propuestas). Valores extraídos
> directamente de `app/globals.css` e `instructions/08-design-system.md`.
> Plantilla lista para usar: `relevant-documents/plantilla-documento.html`.

---

## 1. Colores

| Uso en el documento | Nombre | HEX | RGB |
|---|---|---|---|
| Fondo de página (no blanco puro) | Arena | `#F7F4EF` | 247, 244, 239 |
| Texto principal | Tinta | `#1A1714` | 26, 23, 20 |
| Texto secundario / pies | Piedra oscura | `#4A4540` | 74, 69, 64 |
| Títulos, cabeceras, filetes | Azul marino | `#1B3A6B` | 27, 58, 107 |
| Subtítulos / enlaces | Azul marino claro | `#2B5499` | 43, 84, 153 |
| Acento / precio / CTA / barra sobre H2 | Terracota | `#C8402A` | 200, 64, 42 |
| Hover terracota (solo web, no impresión) | Terracota claro | `#E05A40` | 224, 90, 64 |
| Estrellas / sello hero / filete de énfasis de bloque | Dorado | `#C0882A` | 192, 136, 42 |
| Dorado sobre fondo oscuro (palabra destacada en título) | Dorado claro | `#E8B946` | 232, 185, 70 |
| Fondo de icono dorado | Dorado pálido | `rgba(192,136,42,0.12)` | 192, 136, 42 @ 12 % |
| Iconos / separadores / bordes (nunca texto) | Piedra | `#8A8278` | 138, 130, 120 |
| Fondo de cajas / filas suaves | Arena oscura | `#EDE8E0` | 237, 232, 224 |
| Fondo de badge azul | Azul marino pálido | `#E8EEF8` | 232, 238, 248 |
| Fondo de badge terracota | Terracota pálido | `#FAF0EE` | 250, 240, 238 |
| Incluido / OK (texto) | Verde éxito | `#1A6B3A` | sobre `#EAF5EF` |
| Aviso (texto) | Ámbar | `#8A5A00` | sobre `#FFF8E6` |
| Error (texto) | Rojo | `#B91C1C` | sobre `#FEF2F2` |

### Reglas de uso

- **Nunca blanco puro de fondo**: usar arena `#F7F4EF`.
- **Terracota solo para acentos** (precio final, sello de urgencia, CTA, barra corta sobre un título H2). Máximo 1–2 por página. Nunca como fondo de texto largo.
- **Azul marino** manda en títulos, cabeceras de tabla y en el filete vertical de cajas estructurales (índices, FAQ, ficha de guía).
- **Dorado** es el acento de calidad/confianza: estrellas de valoración, sello sobre el hero y el filete vertical izquierdo del **bloque introductorio destacado**. La palabra destacada en cursiva de un título usa dorado (claro `#E8B946` sobre fondo oscuro, base `#C0882A` sobre fondo claro). No usar dorado como fondo de texto largo.
- **Filete de énfasis** = línea vertical izquierda de un bloque. Dorado para el bloque intro; azul marino para cajas estructurales. Cuenta como uno de los acentos de la página.
- **Piedra `#8A8278`** queda reservada a iconos, separadores y bordes — **nunca texto** (no cumple contraste). Para texto secundario usar piedra oscura `#4A4540`.
- Filetes/separadores discretos: `0.5pt` color `rgba(26, 23, 20, 0.15)`, nunca negro puro.

---

## 2. Tipografía

| Rol | Fuente | Fallback |
|---|---|---|
| Títulos / cabeceras (incl. títulos de tour) | **Lora** | Georgia, serif |
| Palabra destacada en un título | **Lora** *itálica* (color dorado) | Georgia, serif |
| Cuerpo, tablas, todo lo demás | **Inter** | system-ui, Arial |

- Solo dos familias por documento (Lora + Inter). Nunca cuerpo en serif.
- Playfair Display y DM Sans **ya no se usan** — se eliminaron el 2026-05-21 al homogeneizar la tipografía. Todos los títulos son Lora.
- Pesos realmente cargados en la web: **Lora 400 y 600**; **Inter 400, 500 y 600**. El 700 (bold) no está cargado y cae a negrita sintética — para documentos, tope a 600 (semibold) salvo que embebas la fuente bold.

### Escala (A4, en pt)

| Elemento | Tamaño | Peso | Interlineado |
|---|---|---|---|
| Título principal (H1) | 28–36 pt | 700 | 1.2 |
| Título de sección (H2) | 20–24 pt | 600–700 | 1.3 |
| Subtítulo (H3) | 16–18 pt | 600 | 1.4 |
| Cuerpo | 11–12 pt | 400 | 1.6–1.75 |
| Eyebrow / etiqueta | 10 pt | 600 mayúsculas | — |
| Notas / pie / legal | 9–10 pt | 400 | 1.5 |
| **Mínimo absoluto** | **9 pt** | — | — |

---

## 3. Espaciado y forma

- Todo en **múltiplos de 4 pt** (4, 8, 12, 16, 24, 32, 48, 64).
- Márgenes de página generosos (filosofía: "mediterráneo minimalista, mucho aire").
- Radio de esquinas: cajas 8–12 pt, sellos/pills 4 pt o completamente redondeados.
- Sombras muy sutiles si el medio lo permite (`0 1px 2px rgba(0,0,0,0.05)`).

---

## 4. Patrones reutilizables

- **Cabecera "hero"**: banda azul marino `#1B3A6B` (o degradado `#0D2340 → #4A7ABF`), título blanco en Lora, palabra destacada en Lora itálica dorada (`#E8B946` sobre el navy). Sello dorado opcional sobre el título (fondo `rgba(192,136,42,0.9)`, texto blanco, mayúsculas). Eyebrow en mayúsculas opcional (blanco al 75 %).
- **Bloque destacado / intro**: línea vertical **dorada `#C0882A`** de 4 pt a la izquierda + sangría (acento de énfasis). Las cajas estructurales (índice, FAQ, ficha de guía) usan el mismo filete pero en **azul marino**.
- **Barra sobre H2**: regla corta terracota `#C8402A` (~44 × 3 pt) encima del título de sección — recurso de la web, opcional en documentos.
- **Valoración / estrellas**: estrellas en dorado `#C0882A`, número de nota en azul marino negrita Lora. Es el patrón de confianza estándar (★ 4,9).
- **Tabla de tarifas**: cabecera azul marino con texto blanco; filas alternas arena `#F7F4EF` / arena oscura `#EDE8E0`; precio en terracota negrita; "incluido" en verde `#1A6B3A`.
- **Sellos / badges**: fondo suave + texto del mismo tono oscuro.
  - Azul: fondo `#E8EEF8`, texto `#1B3A6B`
  - Terracota: fondo `#FAF0EE`, texto `#C8402A`
  - Confianza: fondo `#EAF5EF`, texto `#1A6B3A`
- **Caja CTA / cierre**: recuadro azul marino, texto blanco, radio 12 pt.
- **Pie**: texto 9–10 pt color `#4A4540`, separado por filete fino. Incluir
  "Guías oficiales de la Comunidad Valenciana desde 1992".

---

*Coherente con Design System v1.0 · WCAG 2.2 AA · paleta acantilado terracota + palmera azul marino.*
