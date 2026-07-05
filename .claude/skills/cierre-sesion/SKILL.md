---
name: cierre-sesion
description: Cierre de una sesión de trabajo en proforma-admin — docs/estado.md al día, working tree limpio, servicio activo, commit y push. Usar al terminar cualquier tarea que haya tocado código, plantilla o docs.
---

# Cierre de sesión (proforma-admin · CT104)

Este repo es producción en vivo (el servicio ejecuta `src/` del NAS): no se
deja NADA a medias en el working tree. Checklist completo:

1. **`docs/estado.md` al día**: lo hecho a «Historial» (fecha + commit), lo
   abierto a «Pendiente». `CLAUDE.md` solo si cambió algo estructural (módulo
   nuevo, decisión nueva, regla nueva).
2. **Working tree limpio**: `git status` sin restos. Un cambio sin commitear
   aquí ES producción sin registrar — o se commitea o se revierte con
   `git checkout -- <fichero>` (y en ese caso, reinicia el servicio para
   volver al código commiteado).
3. **Commit y push**: estilo del log (`feat(proformas): …`, español), docs
   incluidos, `git push` a `main` (GitHub `proforma-processor` — sí, el repo
   remoto se llama distinto; es el correcto).
4. **Servicio como debe**: `pct exec 104 -- systemctl is-active proforma-admin`
   → `active`. Si montaste una instancia aislada de prueba, mátala y borra sus
   copias de `/tmp`.
5. **Docs del host**: si cambiaste config/red/servicio (no solo código), la
   entrada en `/root/documentacion/auditoria-cambios.md` + copia a
   `/mnt/pve/almacenamiento/datos/guillermo/documentacion-servidor/` — esta
   sesión corre en el host, así que puedes hacerlo tú.
6. **Traspaso**: lo que deba retomar la próxima sesión, escrito en
   `docs/estado.md` §Pendiente con el siguiente paso concreto.
