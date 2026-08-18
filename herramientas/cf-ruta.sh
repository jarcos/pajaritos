#!/bin/sh
# Publica la ruta del tunnel para pajaritos.josearcos.me vía API de Cloudflare.
#   1. localiza zona, cuenta y tunnel
#   2. añade la regla de ingress  pajaritos.josearcos.me -> http://pajaritos-web:8080
#      SIN tocar las reglas que ya existen
#   3. crea el CNAME proxied al tunnel
# Idempotente: si la regla o el DNS ya están, no duplica.
# El token nunca se imprime.
set -e
ENVF=${MONITORING_ENV:?exporta MONITORING_ENV con la ruta del .env que tiene CF_API_TOKEN}
HOST=pajaritos.josearcos.me
DEST=http://pajaritos-web:8080

CF_TOKEN=$(grep -aE '^CF_API_TOKEN=' "$ENVF" | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')
api() { curl -s -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" "$@"; }

j() { python3 -c "import json,sys;d=json.load(sys.stdin);print(eval(sys.argv[1],{'d':d}))" "$1" 2>/dev/null; }

ZONA=$(api "https://api.cloudflare.com/client/v4/zones?name=josearcos.me")
ZONE_ID=$(printf '%s' "$ZONA" | j "d['result'][0]['id']")
ACCOUNT_ID=$(printf '%s' "$ZONA" | j "d['result'][0]['account']['id']")
echo "zona josearcos.me: ${ZONE_ID:-NO}  cuenta: ${ACCOUNT_ID:-NO}"
[ -n "$ZONE_ID" ] || { echo "sin acceso a la zona"; exit 1; }

TUN=$(api "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel?is_deleted=false")
OK=$(printf '%s' "$TUN" | j "d['success']")
if [ "$OK" != "True" ]; then
  echo "el token NO puede leer tunnels:"
  printf '%s' "$TUN" | j "[e['message'] for e in d.get('errors',[])]"
  echo "=> la ruta hay que crearla a mano en el panel (Zero Trust > Networks > Tunnels)"
  exit 2
fi
printf '%s' "$TUN" | j "[(t['name'],t['id']) for t in d['result']]"
TUNEL=${TUNNEL_NAME:?exporta TUNNEL_NAME con el nombre del tunnel en Cloudflare Zero Trust}
TUNNEL_ID=$(printf '%s' "$TUN" | j "[t['id'] for t in d['result'] if t['name']=='$TUNEL'][0]")
echo "tunnel $TUNEL: ${TUNNEL_ID:-NO ENCONTRADO}"
[ -n "$TUNNEL_ID" ] || exit 3

CFG=$(api "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations")
echo "hostnames ya publicados:"
printf '%s' "$CFG" | j "[i.get('hostname','(catch-all)') for i in d['result']['config']['ingress']]"

if printf '%s' "$CFG" | grep -q "$HOST"; then
  echo "$HOST ya estaba en el ingress: no se toca"
else
  NUEVO=$(printf '%s' "$CFG" | python3 -c "
import json,sys
d=json.load(sys.stdin)['result']['config']
ing=d['ingress']
regla={'hostname':'$HOST','service':'$DEST','originRequest':{}}
# la regla nueva va antes del catch-all final
d['ingress']=ing[:-1]+[regla]+ing[-1:]
print(json.dumps({'config':d}))
")
  RES=$(api -X PUT --data "$NUEVO" \
    "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations")
  echo "alta de ingress: $(printf '%s' "$RES" | j "d['success']")"
  printf '%s' "$RES" | j "[e['message'] for e in d.get('errors',[])]"
fi

DNS=$(api "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$HOST")
if [ "$(printf '%s' "$DNS" | j "len(d['result'])")" = "0" ]; then
  RES=$(api -X POST --data "{\"type\":\"CNAME\",\"name\":\"$HOST\",\"content\":\"$TUNNEL_ID.cfargotunnel.com\",\"proxied\":true,\"comment\":\"pajaritos - guia de aves del Odiel\"}" \
    "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records")
  echo "alta de DNS: $(printf '%s' "$RES" | j "d['success']")"
  printf '%s' "$RES" | j "[e['message'] for e in d.get('errors',[])]"
else
  echo "el registro DNS ya existe: $(printf '%s' "$DNS" | j "d['result'][0]['content']")"
fi
