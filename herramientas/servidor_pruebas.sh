#!/bin/bash
# Segunda instancia de proforma-admin, en :5124, con datos inventados, para las
# capturas de la interfaz. NO toca nada de producción: base, Excel, PDF y colas
# viven en /tmp/capturas-proformas dentro del CT, y el servicio real (:5114)
# sigue corriendo como si nada.
#
# Se usa desde el host:
#   pct exec 104 -- bash -lc '/mnt/empresa/proforma-admin/herramientas/servidor_pruebas.sh arrancar'
#   pct exec 104 -- bash -lc '/mnt/empresa/proforma-admin/herramientas/servidor_pruebas.sh parar'
#
# `parar` mata EL PID que guardó `arrancar`; nunca un pkill por patrón, que se
# llevaría por delante el servicio real (también es «python3 app.py»).
set -euo pipefail

RAIZ=/mnt/empresa/proforma-admin
TRABAJO=/tmp/capturas-proformas
PUERTO=5124
PID_FILE="$TRABAJO/pid"
CLAVE_FILE="$TRABAJO/clave"

exportar_entorno() {
  export DB_PATH="$TRABAJO/proformas.db"
  export PDF_DIR="$TRABAJO/pdf"
  export TEMPLATE_DIR="$RAIZ/DOCS_ETL_PROFORMAS"
  export EXCEL_PATH="$TRABAJO/facturas-emitidas.xlsx"
  export EXCEL_BACKUP_DIR="$TRABAJO/backups"
  export EXCEL_PENDING_FILE="$TRABAJO/pendientes.json"
  export EXCEL_LOCK_FILE="$TRABAJO/excel.lock"
  export PORT="$PUERTO"
}

arrancar() {
  parar >/dev/null 2>&1 || true
  mkdir -p "$TRABAJO/pdf" "$TRABAJO/backups"
  exportar_entorno
  export ADMIN_USER=capturas
  ADMIN_PASS="$(openssl rand -hex 16)"
  export ADMIN_PASS
  printf '%s' "$ADMIN_PASS" > "$CLAVE_FILE"
  chmod 600 "$CLAVE_FILE"

  ( cd "$RAIZ" && python3 herramientas/datos_prueba.py > "$TRABAJO/ids.json" )

  # setsid + fds cerrados: si no, `pct exec` se queda esperando al hijo y no vuelve.
  ( cd "$RAIZ/src" && setsid python3 app.py < /dev/null > "$TRABAJO/servidor.log" 2>&1 &
    echo $! > "$PID_FILE" )

  for _ in $(seq 1 40); do
    if curl -sf -o /dev/null -u "capturas:$ADMIN_PASS" "http://127.0.0.1:$PUERTO/"; then
      echo "servidor de pruebas en :$PUERTO (pid $(cat "$PID_FILE"))"
      return 0
    fi
    sleep 0.5
  done
  echo "el servidor de pruebas no respondió; mira $TRABAJO/servidor.log" >&2
  parar || true
  return 1
}

matar() {
  pid="$1"
  [ -n "$pid" ] || return 0
  # Solo si sigue siendo nuestro python: el PID podría haberse reciclado.
  [ -r "/proc/$pid/cmdline" ] || return 0
  tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q 'app.py' || return 0
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    [ -d "/proc/$pid" ] || return 0
    sleep 0.2
  done
  kill -9 "$pid" 2>/dev/null || true
}

parar() {
  [ -f "$PID_FILE" ] && matar "$(cat "$PID_FILE")"
  # Red de seguridad: si el fichero de PID se perdió, se mata a quien tenga el
  # PUERTO de pruebas. Nunca por patrón de proceso: el servicio real (:5114)
  # también es «python3 app.py».
  for pid in $(ss -ltnpH "sport = :$PUERTO" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u); do
    matar "$pid"
  done
  rm -rf "$TRABAJO"
  echo "servidor de pruebas parado y $TRABAJO borrado"
}

case "${1:-}" in
  arrancar) arrancar ;;
  parar)    parar ;;
  *) echo "uso: $0 {arrancar|parar}" >&2; exit 2 ;;
esac
