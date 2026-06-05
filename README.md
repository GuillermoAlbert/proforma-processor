# proforma-admin

Internal web app for managing proforma invoices at **Guideal Services 2023 S.L.**

Built with Flask + WeasyPrint. Runs as a systemd service inside Proxmox CT-104, with data stored on a NAS mount.

---

## Features

- Create, edit and view proforma invoices
- PDF generation (WeasyPrint, branded template)
- Client and article catalog
- Optional per-line service date
- Bank account selection per proforma
- Confirm proformas → records to Excel (Hacienda reporting)
- Configurable company details (name, NIF, address, etc.) via `/config/empresa`
- HTTP Basic Auth on all routes

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3 / Flask |
| PDF | WeasyPrint |
| DB | SQLite (WAL mode) |
| Excel export | openpyxl |
| Host | Proxmox CT-104, NAS mount |

## Project structure

```
src/
  app.py              # Routes and Flask app
  db.py               # SQLite helpers and migrations
  pdf.py              # PDF generation via WeasyPrint
  excel.py            # Excel export (Hacienda)
  admin_helpers.py    # HTTP Basic Auth decorator
  templates/          # Jinja2 templates
  static/             # favicon and static assets
DOCS_ETL_PROFORMAS/
  plantilla-proforma.html   # PDF template
src/INSTALL.md              # Server setup instructions
```

## Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `/mnt/empresa/proformas.db` | SQLite database |
| `PDF_DIR` | `/mnt/empresa/proformas-pdf` | Generated PDF cache |
| `TEMPLATE_DIR` | `/mnt/empresa/proforma-admin/DOCS_ETL_PROFORMAS` | PDF template directory |
| `EXCEL_PATH` | `/mnt/empresa/facturas-emitidas.xlsx` | Hacienda Excel |
| `ADMIN_USER` | — | Basic auth username |
| `ADMIN_PASS` | — | Basic auth password |

Company details (name, NIF, address, etc.) are stored in the DB and editable at `/config/empresa`.

## Development

```bash
cd src
pip install -r requirements.txt
DB_PATH=./dev.db PDF_DIR=./pdfs TEMPLATE_DIR=../DOCS_ETL_PROFORMAS \
  ADMIN_USER=admin ADMIN_PASS=admin python3 app.py
```

## Deployment (CT-104)

See [`src/INSTALL.md`](src/INSTALL.md) for full setup. To restart after a code change:

```bash
pct exec 104 -- systemctl restart proforma-admin
```

Logs:

```bash
pct exec 104 -- journalctl -u proforma-admin -f
```
