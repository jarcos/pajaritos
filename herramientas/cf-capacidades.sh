#!/bin/sh
# Comprueba qué puede hacer el token de Cloudflare que ya hay en la casa.
# El token NUNCA se imprime: solo se dice si sirve o no para cada cosa.
set -e
ENVF=/volume1/docker/REDACTED_STACK/.env

CF_TOKEN=$(grep -aE '^(CLOUDFLARE_API_TOKEN|CF_API_TOKEN|CLOUDFLARE_DNS_API_TOKEN|CF_DNS_API_TOKEN)=' "$ENVF" \
  | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')
CF_ACCOUNT=$(grep -aE '^(CLOUDFLARE_ACCOUNT_ID|CF_ACCOUNT_ID)=' "$ENVF" \
  | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')

echo "claves de Cloudflare presentes en monitoring/.env:"
grep -aoE '^(CLOUDFLARE|CF)_[A-Z_]+' "$ENVF" | sort -u | sed 's/^/  /'

if [ -z "$CF_TOKEN" ]; then echo "no hay token utilizable"; exit 0; fi
echo "token localizado (longitud ${#CF_TOKEN}), account_id: ${CF_ACCOUNT:-no definido}"

api() { curl -s -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" "$@"; }

echo "=== verify ==="
api https://api.cloudflare.com/client/v4/user/tokens/verify \
  | sed -e 's/.*"status":"\([a-z]*\)".*/  estado del token: \1/' | head -1

echo "=== cuentas visibles ==="
api https://api.cloudflare.com/client/v4/accounts \
  | tr ',' '\n' | grep -E '"(id|name)"' | head -6 | sed 's/^/  /'

echo "=== zonas visibles ==="
api https://api.cloudflare.com/client/v4/zones \
  | tr ',' '\n' | grep -E '"name"' | head -6 | sed 's/^/  /'

if [ -n "$CF_ACCOUNT" ]; then
  echo "=== tunnels (necesita permiso Cloudflare Tunnel) ==="
  api "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT/cfd_tunnel?is_deleted=false" \
    | tr ',' '\n' | grep -E '"(name|id)"|"code"|"message"' | head -12 | sed 's/^/  /'
fi
