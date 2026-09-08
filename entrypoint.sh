#!/bin/sh
# =============================================================================
# entrypoint.sh
# =============================================================================
# Eseguito all'avvio del container. Tabelle mancanti, migrazioni dello
# schema (vedi app/migrations.py) e utente admin di default vengono tutti
# gestiti automaticamente da create_app() al primo import dell'app — vedi
# app/__init__.py — quindi qui non serve alcun passo separato: basta
# avviare gunicorn.
# =============================================================================
set -e

echo "=========================================="
echo " Valigia — avvio del container"
echo " Ambiente: ${VALIGIA_ENV:-production}"
echo "=========================================="

exec gunicorn \
    --workers 2 \
    --threads 4 \
    --bind 0.0.0.0:8000 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
