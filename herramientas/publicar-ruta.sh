#!/bin/sh
# Publica pajaritos.josearcos.me en el tunnel TUNNEL_NAME.
#
#   1. lee el token de ~/.config/cloudflare/pajaritos-token
#   2. añade la regla de ingress ANTES del catch-all, sin tocar las existentes
#   3. crea el CNAME proxied al tunnel
#
# Idempotente: si la regla o el DNS ya están, no duplica ni sobrescribe.
# Antes de escribir guarda la configuración actual del tunnel en un fichero,
# por si hubiera que revertir. El token nunca se imprime.
set -e

TOKEN_FILE="$HOME/.config/cloudflare/pajaritos-token"
HOST=pajaritos.josearcos.me
DEST=http://pajaritos-web:8080
ZONA=josearcos.me
TUNEL=TUNNEL_NAME
COPIA="$HOME/.config/cloudflare/ingress-antes-de-pajaritos.json"

[ -s "$TOKEN_FILE" ] || { echo "No hay token en $TOKEN_FILE"; exit 1; }
CF_TOKEN=$(tr -d ' \t\r\n' < "$TOKEN_FILE")

api() { curl -s -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" "$@"; }
py()  { python3 -c "$1"; }

echo "=== token ==="
api https://api.cloudflare.com/client/v4/user/tokens/verify \
  | py "import json,sys;d=json.load(sys.stdin);print('  ', d['result']['status'] if d['success'] else d['errors'])"

echo "=== zona y cuenta ==="
Z=$(api "https://api.cloudflare.com/client/v4/zones?name=$ZONA")
ZONE_ID=$(printf '%s' "$Z" | py "import json,sys;d=json.load(sys.stdin);print(d['result'][0]['id'])")
ACCOUNT_ID=$(printf '%s' "$Z" | py "import json,sys;d=json.load(sys.stdin);print(d['result'][0]['account']['id'])")
echo "  zona $ZONE_ID · cuenta $ACCOUNT_ID"

echo "=== tunnel ==="
T=$(api "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel?is_deleted=false")
printf '%s' "$T" | py "
import json,sys
d=json.load(sys.stdin)
if not d['success']:
    print('  el token NO puede leer tunnels:', [e['message'] for e in d['errors']]); sys.exit(1)
if not d['result']:
    print('  el token no ve ningun tunnel: falta el permiso Account > Cloudflare Tunnel'); sys.exit(1)
for t in d['result']: print('  -', t['name'], t['id'])
"
TUNNEL_ID=$(printf '%s' "$T" | py "import json,sys;d=json.load(sys.stdin);print([t['id'] for t in d['result'] if t['name']=='$TUNEL'][0])")
echo "  $TUNEL = $TUNNEL_ID"

echo "=== configuracion actual ==="
CFG=$(api "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations")
printf '%s' "$CFG" > "$COPIA"; chmod 600 "$COPIA"
echo "  copia de seguridad en $COPIA"
printf '%s' "$CFG" | py "
import json,sys
ing=json.load(sys.stdin)['result']['config']['ingress']
for i in ing: print('  ', i.get('hostname','(catch-all)'), '->', i.get('service'))
"

if printf '%s' "$CFG" | grep -q "$HOST"; then
  echo "=== ingress: $HOST ya estaba, no se toca ==="
else
  echo "=== anadiendo ingress ==="
  NUEVO=$(printf '%s' "$CFG" | py "
import json,sys
c=json.load(sys.stdin)['result']['config']
ing=c['ingress']
assert 'hostname' not in ing[-1], 'la ultima regla no es el catch-all; abortando'
c['ingress']=ing[:-1]+[{'hostname':'$HOST','service':'$DEST','originRequest':{}}]+ing[-1:]
print(json.dumps({'config':c}))
")
  api -X PUT --data "$NUEVO" \
    "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations" \
    | py "import json,sys;d=json.load(sys.stdin);print('  ok' if d['success'] else ['  '+e['message'] for e in d['errors']])"
fi

echo "=== DNS ==="
D=$(api "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$HOST")
N=$(printf '%s' "$D" | py "import json,sys;print(len(json.load(sys.stdin)['result']))")
if [ "$N" = "0" ]; then
  api -X POST --data "{\"type\":\"CNAME\",\"name\":\"$HOST\",\"content\":\"$TUNNEL_ID.cfargotunnel.com\",\"proxied\":true,\"comment\":\"pajaritos - guia de aves del Odiel\"}" \
    "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
    | py "import json,sys;d=json.load(sys.stdin);print('  CNAME creado' if d['success'] else ['  '+e['message'] for e in d['errors']])"
else
  printf '%s' "$D" | py "import json,sys;r=json.load(sys.stdin)['result'][0];print('  ya existe:',r['type'],'->',r['content'],'proxied',r['proxied'])"
fi

echo "=== comprobacion ==="
sleep 5
echo "  dig: $(dig +short $HOST | tr '\n' ' ')"
echo "  healthz: $(curl -s --max-time 15 https://$HOST/healthz || echo 'sin respuesta todavia')"
