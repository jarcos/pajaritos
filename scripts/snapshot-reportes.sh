#!/bin/sh
# Instantánea consistente de reportes.db para Hyper Backup.
#
# POR QUÉ NO BASTA COPIAR EL FICHERO: si Hyper Backup copia un SQLite mientras
# hay una escritura en vuelo, la copia puede salir corrupta — y en modo WAL, el
# .db sin su .db-wal está incompleto. VACUUM INTO produce una copia coherente y
# ya compactada, con la base de datos en uso. Es el mismo patrón que vuestro
# job nocturno de bases de datos.
#
# Programar en el Task Scheduler de DSM antes de la ventana de Hyper Backup.
set -eu
DB="${REPORTES_DB:-/reportes/reportes.db}"
DESTINO="${DESTINO:-/snapshots}"
SELLO="$(date +%Y%m%d-%H%M)"
SALIDA="${DESTINO}/reportes-${SELLO}.db"
RETENCION_DIAS="${RETENCION_DIAS:-14}"

mkdir -p "$DESTINO"
python3 - "$DB" "$SALIDA" <<'PY'
import sqlite3, sys
origen, salida = sys.argv[1], sys.argv[2]
con = sqlite3.connect(f"file:{origen}?mode=ro", uri=True, timeout=30)
con.execute("VACUUM INTO ?", (salida,))
con.close()
PY

# Verificar que la instantánea es legible antes de darla por buena.
FILAS=$(python3 -c "
import sqlite3,sys
con=sqlite3.connect(f'file:{sys.argv[1]}?mode=ro',uri=True)
print(con.execute('SELECT count(*) FROM reportes').fetchone()[0])
" "$SALIDA")

echo "{\"nivel\":\"info\",\"msg\":\"instantanea creada\",\"archivo\":\"$SALIDA\",\"reportes\":$FILAS}"

find "$DESTINO" -name 'reportes-*.db' -type f -mtime "+${RETENCION_DIAS}" -delete
