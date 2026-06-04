# Instalación en CT-104

## Dependencias del sistema
```
pct exec 104 -- apt-get update
pct exec 104 -- apt-get install -y python3-pip libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf2.0-0
```

## Directorio de PDFs
```
pct exec 104 -- mkdir -p /mnt/empresa/proformas-pdf
```

## Dependencias Python
```
pct exec 104 -- pip3 install flask weasyprint openpyxl
```

## Servicio systemd — crear el archivo en CT-104
```
pct exec 104 -- bash -c "cat > /etc/systemd/system/proforma-admin.service << 'EOF'
[Unit]
Description=Proforma Admin - Guías de Alicante
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/mnt/empresa/proforma-admin/src
Environment=DB_PATH=/mnt/empresa/proformas.db
Environment=PDF_DIR=/mnt/empresa/proformas-pdf
Environment=TEMPLATE_DIR=/mnt/empresa/proforma-admin/DOCS_ETL_PROFORMAS
Environment=ADMIN_USER=admin
Environment=ADMIN_PASS=admin
Environment=FLASK_ENV=production
# Fase 2 — Excel Hacienda (opcionales: todas tienen default en /mnt/empresa/)
Environment=EXCEL_PATH=/mnt/empresa/facturas-emitidas.xlsx
Environment=EXCEL_BACKUP_DIR=/mnt/empresa/backups-proformas
Environment=EXCEL_PENDING_FILE=/mnt/empresa/proforma-admin-pending-excel.json
Environment=EXCEL_LOCK_FILE=/mnt/empresa/.proforma-excel.lock
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF"
```

## Activar y arrancar el servicio
```
pct exec 104 -- systemctl daemon-reload
pct exec 104 -- systemctl enable --now proforma-admin
pct exec 104 -- systemctl status proforma-admin
```

## Verificar
```
# Logs en tiempo real
pct exec 104 -- journalctl -u proforma-admin -f

# Reiniciar tras cambios en src/
pct exec 104 -- systemctl restart proforma-admin
```

## Rollback
```
pct exec 104 -- systemctl stop proforma-admin
pct exec 104 -- systemctl disable proforma-admin
```
