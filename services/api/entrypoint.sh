#!/bin/sh
# Arranca como root solo para dejar el directorio de la base de datos con el
# owner correcto, y acto seguido baja a uid 10001 para servir.
#
# El directorio, no solo el fichero: en modo WAL, SQLite necesita crear
# reportes.db-wal y reportes.db-shm junto a la base de datos. Con el directorio
# propiedad de root, el proceso sin privilegios falla con "unable to open
# database file" y cuesta un rato entender por qué. Es el mismo tipo de
# problema que el exporter que no podía leer su .cnf (runbook §11).
set -e
DB="${REPORTES_DB:-/reportes/reportes.db}"
DIR="$(dirname "$DB")"

mkdir -p "$DIR"
chown -R 10001:10001 "$DIR"
chmod 750 "$DIR"

echo "{\"nivel\":\"info\",\"servicio\":\"pajaritos-api\",\"msg\":\"volumen listo\",\"dir\":\"$DIR\"}"
exec su-exec pajaritos python /app/app.py
