#!/bin/sh
# Una descarga al arrancar (para no esperar al primer cron) y luego
# diaria a las 04:05 hora local. Una petición al día por estación:
# carga insignificante para PORTUS y respetuosa con la fuente.
set -e
echo "[mareas] arranque · $(date -Is)"
/app/fetch_mareas.py || echo "[mareas] fallo en la descarga inicial, se reintentará en el cron"

echo "5 4 * * * /app/fetch_mareas.py >> /proc/1/fd/1 2>> /proc/1/fd/2" > /etc/crontabs/root
exec crond -f -l 8
