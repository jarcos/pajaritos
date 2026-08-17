#!/bin/sh
# Averigua si el tunnel se gestiona en remoto (token) o en local (config.yml),
# para saber si la ruta se puede crear por API o hay que ir al panel.
export PATH=/usr/local/bin:$PATH

echo "=== carpeta cloudflared ==="
ls -la /volume1/docker/cloudflared 2>/dev/null

echo "=== compose (token redactado) ==="
if [ -f /volume1/docker/cloudflared/docker-compose.yml ]; then
  sed -e 's/eyJ[A-Za-z0-9._-]*/TOKEN-REDACTADO/g' \
      /volume1/docker/cloudflared/docker-compose.yml | head -40
fi

echo "=== config dentro del contenedor ==="
docker exec cloudflared ls -la /etc/cloudflared 2>/dev/null || echo "sin config local"

echo "=== comando del contenedor ==="
docker inspect cloudflared --format '{{json .Config.Cmd}}' 2>/dev/null \
  | sed -e 's/eyJ[A-Za-z0-9._-]*/TOKEN-REDACTADO/g'

echo "=== hay credenciales de API de Cloudflare por la casa? ==="
grep -rlsi 'CLOUDFLARE_API\|CF_API_TOKEN\|CF_DNS_API' /volume1/docker/*/.env 2>/dev/null || echo "ninguna"

echo "=== cert.pem de cloudflared (permite tunnel route dns) ==="
ls -la /volume1/docker/cloudflared/cert.pem 2>/dev/null || echo "sin cert.pem"
find /volume1/docker/cloudflared -name '*.json' -o -name 'config.y*ml' 2>/dev/null | head
