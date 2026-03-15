#!/bin/sh
set -e

echo "→ Ejecutando migraciones..."
python manage.py migrate --noinput

echo "→ Recopilando archivos estáticos..."
python manage.py collectstatic --noinput --clear

echo "→ Iniciando Gunicorn en puerto ${GUNICORN_PORT:-8000}..."
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${GUNICORN_PORT:-8000}" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile -
