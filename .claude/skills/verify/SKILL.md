---
name: verify
description: Verificar un cambio de proforma-admin de verdad — smoke de PDFs, reinicio del servicio en CT104 y comprobación HTTP de lo que cambiaste. Usar SIEMPRE tras tocar src/ o la plantilla, y antes de git commit.
---

# Verificar un cambio (proforma-admin · CT104)

Recuerda: la sesión corre en el **host** y el servicio ejecuta `src/` del NAS
**en vivo** — lo que acabas de editar ya es lo que producción va a ejecutar.
No hay suite pytest; la verificación es funcional. En orden:

## 1. Sintaxis / imports

```bash
pct exec 104 -- bash -c 'cd /mnt/empresa/proforma-admin/src && python3 -m py_compile app.py db.py pdf.py excel.py api_orquestador.py'
```

## 2. Smoke de PDFs (si tocaste `pdf.py` o la plantilla)

```bash
pct exec 104 -- bash -c 'cd /mnt/empresa/proforma-admin/src && python3 test_pdf_gen.py'
```

Debe generar 3 PDFs en `/tmp` del CT sin traceback. Si cambiaste el diseño,
pide a Guillermo que abra los PDFs (o descárgalos con `pct pull`) antes de dar
el visual por bueno.

## 3. Reinicio y salud del servicio

```bash
pct exec 104 -- systemctl restart proforma-admin
sleep 2
pct exec 104 -- systemctl is-active proforma-admin
pct exec 104 -- bash -c 'curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5114/'
```

`active` + `401` (Basic Auth) = vivo. Otra cosa →
`pct exec 104 -- journalctl -u proforma-admin -n 50` y arreglar antes de seguir.

## 4. Smoke de lo que cambiaste

- Rutas del panel: cúrlalas con las credenciales del unit (`ADMIN_USER`/
  `ADMIN_PASS` en `systemctl cat proforma-admin`, o pídelas) esperando `200`.
- `/api/*`: `pct exec 104 -- bash -c 'curl -s -u USER:PASS http://127.0.0.1:5114/api/proformas | head -c 400'`.
- Si tocaste `excel.py` o el flujo de estados: **cuidado, el Excel de Hacienda
  es fiscal**. Prueba con una proforma de prueba y deshaz después
  (`/desenviar` borra la fila), o monta una instancia aislada como la del
  2026-07-05 (puerto libre + `DB_PATH`/`EXCEL_PATH` a copias en `/tmp`).
- El cron horario del factura-processor es ajeno a este repo: no lo toques ni
  lo esperes.

## 5. Antes del commit

- `git status` / `git diff --stat` — solo lo tuyo, sin `.bak` ni artefactos.
- `docs/estado.md` actualizado en el mismo commit.
