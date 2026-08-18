#!/usr/bin/env bash
#
# Genera el basemap de la provincia de Huelva a partir del build diario del
# planeta de Protomaps y lo deja en el volumen que sirve nginx.
#
# NO descarga los ~127 GB del planeta: `pmtiles extract` lee por rangos HTTP
# solo los tiles del recuadro pedido.
#
# ⚠️ EL LÍMITE QUE MANDA: Cloudflare (plan gratuito) solo cachea ficheros de
# hasta 512 MB. Un .pmtiles más grande deja de cachearse y CADA petición de
# rango viaja por el tunnel hasta el NAS. Además se han reportado resets de
# stream HTTP/2 en descargas largas a través de Cloudflare Tunnel. Conclusión:
# el archivo debe quedar por debajo de 512 MB; si se pasa, bajar MAXZOOM.
#
set -euo pipefail

FECHA_BUILD="${FECHA_BUILD:-$(date -u -d '3 days ago' +%Y%m%d 2>/dev/null || date -u -v-3d +%Y%m%d)}"
# Recuadro de la provincia de Huelva: cubre Odiel, Piedras, El Portil,
# Palos y Las Madres, Doñana occidental, el Andévalo y la Sierra de Aracena.
BBOX="${BBOX:--7.55,36.75,-6.10,38.30}"
MAXZOOM="${MAXZOOM:-14}"
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
scp "${SALIDA}" "nas-deploy:${DESTINO}/"

cat <<NOTA

✓ Listo. Ahora, en el NAS:

    ln -sfn ${DESTINO}/${SALIDA} ${DESTINO}/actual.pmtiles

  Y en la app, apuntar a  pmtiles:///mapas/${SALIDA}
  (nombre versionado ⇒ inmutable ⇒ cacheable un año en el borde).

  Recuerda purgar el caché de Cloudflare solo si reutilizas un nombre. Si el
  nombre cambia, no hace falta purgar nada: es la ventaja de versionar.

  Atribución obligatoria en el mapa: © OpenStreetMap contributors.
NOTA
