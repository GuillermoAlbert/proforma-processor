# Fuentes locales del PDF de proforma

Subconjuntos `latin` y `latin-ext` de **Lora** e **Inter**, descargados de Google
Fonts el 2026-09-10 y servidos desde aquí para que WeasyPrint no dependa de
internet al generar cada PDF.

Motivo: con el `<link>` remoto, cada render tardaba **1,39 s** (1,05 s solo en
bajar las fuentes) y, si CT 104 se quedaba sin red, la proforma salía en
Georgia/Arial **sin avisar**. Con los ficheros locales el render baja a 0,33 s.

- Los cuatro `.woff2` son **fuentes variables**: un fichero por familia y
  subconjunto cubre los pesos 400 y 600. Verificado con `pdffonts`: WeasyPrint
  instancia `Lora-Semi-Bold` e `Inter-Semi-Bold` de verdad, no las sintetiza.
- Licencia **SIL Open Font License 1.1** (ambas familias): redistribuibles.
- Los `unicode-range` de `plantilla-proforma.html` son los que sirve Google para
  esos subconjuntos; no los cambies sin volver a mirar el CSS de origen.

Para actualizarlas: bajar de nuevo el CSS de `fonts.googleapis.com/css2` con un
User-Agent de navegador moderno, coger las URL de los bloques `latin` y
`latin-ext`, y comprobar después con `pdffonts` que las cuatro siguen embebidas.
