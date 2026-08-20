#!/usr/bin/env bash
#
# Genera el basemap de la provincia de Huelva a partir del build diario del
# planeta de Protomaps y lo deja en el volumen que sirve nginx.
#
# NO descarga los ~127 GB del planeta: `pmtiles extract` lee por rangos HTTP
# solo los tiles del recuadro pedido.
#
# EL LÍMITE QUE SE TEMÍA NO ERA EL LÍMITE. Medido el 20/08/2026 sobre el build
# del 17/08 y este mismo recuadro:
#
#     z14 → 21 MB      z15 → 39 MB      z16 → 39 MB (idénticos)
#
# z16 pesa lo mismo que z15 porque el build diario del planeta de Protomaps
# TERMINA en z15: pedir más devuelve exactamente los mismos 26 514 tiles. Así
# que 39 MB es el máximo posible para Huelva, trece veces por debajo de los
# 512 MB que cachea Cloudflare en el plan gratuito. El techo que condicionó el
# diseño no aprieta; el que manda es el de la fuente.
#
# Se conserva la comprobación de tamaño por si algún día cambia el recuadro o
# Protomaps sube su maxzoom.
#
set -euo pipefail

FECHA_BUILD="${FECHA_BUILD:-$(date -u -d '3 days ago' +%Y%m%d 2>/dev/null || date -u -v-3d +%Y%m%d)}"
# Recuadro de la provincia de Huelva: cubre Odiel, Piedras, El Portil,
# Palos y Las Madres, Doñana occidental, el Andévalo y la Sierra de Aracena.
BBOX="${BBOX:--7.55,36.75,-6.10,38.30}"
MAXZOOM="${MAXZOOM:-15}"   # 15 es el techo de la fuente, no una elección
LIMITE_MB="${LIMITE_MB:-512}"
SALIDA="huelva-${FECHA_BUILD}-z${MAXZOOM}.pmtiles"
DESTINO="${DESTINO:-/volume1/docker/pajaritos/mapas}"

command -v pmtiles >/dev/null || { echo "falta el binario pmtiles (protomaps/go-pmtiles)"; exit 1; }

echo "▸ extrayendo  build=${FECHA_BUILD}  bbox=${BBOX}  maxzoom=${MAXZOOM}"
pmtiles extract "https://build.protomaps.com/${FECHA_BUILD}.pmtiles" "${SALIDA}" \
  --bbox="${BBOX}" --maxzoom="${MAXZOOM}"

TAM_MB=$(( $(stat -c%s "${SALIDA}" 2>/dev/null || stat -f%z "${SALIDA}") / 1048576 ))
echo "▸ resultado: ${SALIDA} · ${TAM_MB} MB"

if [ "${TAM_MB}" -gt "${LIMITE_MB}" ]; then
  echo "✗ ${TAM_MB} MB supera el límite de caché de Cloudflare (${LIMITE_MB} MB)."
  echo "  Vuelve a lanzarlo con MAXZOOM=$((MAXZOOM-1)) — cada nivel casi duplica el tamaño."
  exit 2
fi

echo "▸ verificando"
pmtiles show "${SALIDA}" | head -20

echo "▸ copiando al NAS"
# El puerto y el usuario salen del alias nas-deploy de ~/.ssh/config.
# -O fuerza el protocolo SCP clásico. Sin él, el scp de OpenSSH ≥9 habla SFTP
# y el sshd del Synology no trae ese subsistema: falla con «subsystem request
# failed on channel 0». Es la misma familia de sorpresa que el rsync capado.
scp -O "${SALIDA}" "nas-deploy:${DESTINO}/"

echo "▸ apuntando actual.pmtiles"
ssh nas-deploy "ln -sfn ${DESTINO}/${SALIDA} ${DESTINO}/actual.pmtiles"

cat <<NOTA

✓ Listo. actual.pmtiles ya apunta a ${SALIDA}.

  En la app, apuntar a  pmtiles:///mapas/${SALIDA}
  (nombre versionado ⇒ inmutable ⇒ cacheable un año en el borde).

  Recuerda purgar el caché de Cloudflare solo si reutilizas un nombre. Si el
  nombre cambia, no hace falta purgar nada: es la ventaja de versionar.

  Atribución obligatoria en el mapa: © OpenStreetMap contributors.
NOTA
