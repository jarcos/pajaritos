#!/bin/sh
# Publica pajaritos.josearcos.me en el tunnel TUNNEL_NAME.
#
# Dos credenciales, cada una en su sitio y con su alcance:
#   · ingress -> token de ~/.config/cloudflare/pajaritos-token (Cloudflare Tunnel: Edit)
#   · DNS     -> CF_API_TOKEN de monitoring/.env, que se queda EN EL NAS (DNS: Edit)
#
# El orden importa: primero la regla de ingress y luego el CNAME. Al revés
# habría una ventana con DNS apuntando a un tunnel sin ruta, que da Error 1033.
#
# Idempotente. Guarda copia de la configuración previa antes de escribir.
set -e

TOKEN_FILE="$HOME/.config/cloudflare/pajaritos-token"
COPIA="$HOME/.config/cloudflare/ingress-antes-de-pajaritos.json"
HOST=pajaritos.josearcos.me
DEST=http://pajaritos-web:8080
TUNEL=${TUNNEL_NAME:?exporta TUNNEL_NAME con el nombre del tunnel en Cloudflare Zero Trust}

[ -s "$TOKEN_FILE" ] || { echo "No hay token en $TOKEN_FILE"; exit 1; }
CF_TOKEN=$(tr -d ' \t\r\n' < "$TOKEN_FILE")
api() { curl -s -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" "$@"; }
py() { python3 -c "$1"; }

echo "=== cuenta y tunnel ==="
ACCOUNT_ID=$(api https://api.cloudflare.com/client/v4/accounts \
  | py "import json,sys;print(json.load(sys.stdin)['result'][0]['id'])")
T=$(api "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel?is_deleted=false")
TUNNEL_ID=$(printf '%s' "$T" \
  | py "import json,sys;print([t['id'] for t in json.load(sys.stdin)['result'] if t['name']=='$TUNEL'][0])")
echo "  cuenta $ACCOUNT_ID · tunnel $TUNEL = $TUNNEL_ID"

echo "=== configuracion actual del ingress ==="
CFG=$(api "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations")
printf '%s' "$CFG" > "$COPIA"; chmod 600 "$COPIA"
echo "  copia de seguridad en $COPIA"
printf '%s' "$CFG" | py "
import json,sys
for i in json.load(sys.stdin)['result']['config']['ingress']:
    print('   ', i.get('hostname','(catch-all)'), '->', i.get('service'))
"

if printf '%s' "$CFG" | grep -q "$HOST"; then
  echo "=== ingress: $HOST ya estaba, no se toca ==="
else
  echo "=== anadiendo la regla de ingress ==="
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
    | py "import json,sys;d=json.load(sys.stdin);print('  ok' if d['success'] else [e['message'] for e in d['errors']])"
fi

echo "=== reglas tras el cambio ==="
api "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations" | py "
import json,sys
for i in json.load(sys.stdin)['result']['config']['ingress']:
    print('   ', i.get('hostname','(catch-all)'), '->', i.get('service'))
"

echo "=== DNS (se resuelve en el NAS, con el token de monitoring) ==="
ssh nas-deploy "TUNNEL_ID=$TUNNEL_ID HOST=$HOST MONITORING_ENV=${MONITORING_ENV:?exporta MONITORING_ENV con la ruta del .env del NAS que tiene CF_API_TOKEN} sh -s" 2>/dev/null <<'REMOTO'
# Ojo con el tr: recortar solo CR, comillas y espacios. Un patrón descuidado
# como tr -d '"'\'' \r' borra tambien las letras r del token.
CF=$(sed -n 's/^CF_API_TOKEN=//p' "$MONITORING_ENV" | head -1 | tr -d '\015' | tr -d '"' | tr -d "'" | tr -d ' ')
q() { curl -s -H "Authorization: Bearer $CF" -H "Content-Type: application/json" "$@"; }
ZONE_ID=$(q "https://api.cloudflare.com/client/v4/zones?name=josearcos.me" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['result'][0]['id'])")
D=$(q "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$HOST")
N=$(printf '%s' "$D" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['result']))")
if [ "$N" = "0" ]; then
  q -X POST --data "{\"type\":\"CNAME\",\"name\":\"$HOST\",\"content\":\"$TUNNEL_ID.cfargotunnel.com\",\"proxied\":true,\"comment\":\"pajaritos - guia de aves del Odiel\"}" \
    "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
    | python3 -c "import json,sys;d=json.load(sys.stdin);print('  CNAME creado' if d['success'] else [e['message'] for e in d['errors']])"
else
  printf '%s' "$D" | python3 -c "
import json,sys
r=json.load(sys.stdin)['result'][0]
print('  ya existe:', r['type'], '->', r['content'], '· proxied', r['proxied'])"
fi
REMOTO

echo "=== comprobacion ==="
sleep 6
echo "  dig:     $(dig +short $HOST | tr '\n' ' ')"
echo "  healthz: $(curl -s --max-time 20 https://$HOST/healthz || echo '(sin respuesta todavia)')"
