#!/bin/bash
# Hook SessionStart — contexto de situación al abrir sesión en proforma-admin.
# Corre en el HOST Proxmox (workspace en el NAS); el servicio vive en CT104.
cd /mnt/pve/almacenamiento/datos/empresa/proforma-admin 2>/dev/null || exit 0

echo "=== proforma-admin (CT104) · $(date '+%Y-%m-%d %H:%M') ==="
echo "RECUERDA: en CT104 hay DOS apps. Esta es proforma-admin (:5114, proformas.db)."
echo "factura-processor (:5104/nginx :8080, facturas.db) es OTRO repo y no se toca."

echo "--- servicio ---"
echo "proforma-admin: $(pct exec 104 -- systemctl is-active proforma-admin 2>/dev/null || echo '?')"

echo "--- git (últimos 3 commits) ---"
git log --oneline -3 2>/dev/null
sucio=$(git status --porcelain 2>/dev/null)
if [ -n "$sucio" ]; then
  echo "⚠ WORKING TREE SUCIO — aquí eso es producción sin registrar; revisar antes de empezar:"
  echo "$sucio" | head -10
else
  echo "working tree limpio"
fi

echo "--- docs/estado.md · Pendiente ---"
awk '/^## Pendiente/{f=1;next}/^## /{f=0}f' docs/estado.md 2>/dev/null | sed '/^$/d' | head -8

exit 0
