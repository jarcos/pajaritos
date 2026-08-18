#!/bin/sh
# Crea el CNAME de pajaritos.josearcos.me al tunnel TUNNEL_NAME.
# Usa el token de ~/.config/cloudflare/pajaritos-token, que necesita
# el permiso  Zone · DNS · Edit  sobre josearcos.me.
# Idempotente: si el registro ya existe, lo dice y no lo toca.
set -e
HOST=pajaritos.josearcos.me
TUNNEL_ID=eed2f48e-8f3f-41cc-8106-fabc67b37acc

CF=$(tr -d ' \t\r\n' < "$HOME/.config/cloudflare/pajaritos-token")
q() { curl -s -H "Authorization: Bearer $CF" -H "Content-Type: application/json" "$@"; }

echo "=== zona ==="
Z=$(q "https://api.cloudflare.com/client/v4/zones?name=josearcos.me")
printf '%s' "$Z" | python3 -c "
import json,sys
d=json.load(sys.stdin)
if not d['success'] or not d['result']:
    print('  el token no ve la zona: le falta Zone > DNS > Edit sobre josearcos.me')
    for e in d.get('errors') or []: print('  error:', e.get('code'), e.get('message'))
    sys.exit(1)
print('  ', d['result'][0]['name'], d['result'][0]['id'])
"
ZONE_ID=$(printf '%s' "$Z" | python3 -c "import json,sys;print(json.load(sys.stdin)['result'][0]['id'])")

echo "=== registro ==="
D=$(q "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$HOST")
printf '%s' "$D" | python3 -c "
import json,sys
d=json.load(sys.stdin)
if not d['success']:
    print('  no puedo leer los registros DNS:')
    for e in d.get('errors') or []: print('  error:', e.get('code'), e.get('message'))
    sys.exit(1)
print('  encontrados:', len(d['result']))
"
N=$(printf '%s' "$D" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['result']))")

if [ "$N" = "0" ]; then
  echo "=== creando CNAME ==="
  q -X POST \
    --data "{\"type\":\"CNAME\",\"name\":\"$HOST\",\"content\":\"$TUNNEL_ID.cfargotunnel.com\",\"proxied\":true,\"comment\":\"pajaritos - guia de aves del Odiel\"}" \
    "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
    | python3 -c "
import json,sys
d=json.load(sys.stdin)
if d['success']:
    r=d['result']; print('  creado:', r['name'], '->', r['content'], '· proxied', r['proxied'])
else:
    print('  fallo:', [ (e.get('code'), e.get('message')) for e in d['errors'] ]); sys.exit(1)
"
else
  printf '%s' "$D" | python3 -c "
import json,sys
r=json.load(sys.stdin)['result'][0]
print('  ya existe:', r['name'], r['type'], '->', r['content'], '· proxied', r['proxied'])"
fi

echo "=== comprobacion ==="
sleep 6
echo "  dig:     $(dig +short $HOST | tr '\n' ' ')"
echo "  healthz: $(curl -s --max-time 20 https://$HOST/healthz || echo '(sin respuesta todavia)')"
