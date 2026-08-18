#!/bin/sh
# Qué alcanza el token nuevo. No imprime el token.
CF_TOKEN=$(tr -d ' \t\r\n' < "$HOME/.config/cloudflare/pajaritos-token")
api() { curl -s -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" "$@"; }
py() { python3 -c "$1" 2>&1; }

echo "=== verify (con grupos de permisos) ==="
api https://api.cloudflare.com/client/v4/user/tokens/verify | py "
import json,sys
d=json.load(sys.stdin)
print(' exito:', d['success'], '·', d.get('result',{}).get('status'))
for m in d.get('messages',[]): print('  ', m.get('message'))
"

echo "=== cuentas visibles ==="
api https://api.cloudflare.com/client/v4/accounts | py "
import json,sys
d=json.load(sys.stdin)
print('  exito:', d['success'])
for a in d.get('result') or []: print('  -', a['name'], a['id'])
for e in d.get('errors') or []: print('  error:', e.get('code'), e.get('message'))
"

echo "=== zonas visibles ==="
api https://api.cloudflare.com/client/v4/zones | py "
import json,sys
d=json.load(sys.stdin)
print('  exito:', d['success'])
for z in d.get('result') or []: print('  -', z['name'], z['id'])
for e in d.get('errors') or []: print('  error:', e.get('code'), e.get('message'))
"

echo "=== tunnels en la cuenta conocida ==="
ACC=CF_ACCOUNT_ID
api "https://api.cloudflare.com/client/v4/accounts/$ACC/cfd_tunnel?is_deleted=false" | py "
import json,sys
d=json.load(sys.stdin)
print('  exito:', d['success'])
for t in d.get('result') or []: print('  -', t['name'], t['id'])
for e in d.get('errors') or []: print('  error:', e.get('code'), e.get('message'))
"
