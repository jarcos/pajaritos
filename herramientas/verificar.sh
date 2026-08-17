#!/bin/sh
# Verifica el origen exactamente como lo verá cloudflared: desde la red `tunnel`,
# contra pajaritos-web:8080. Lo único que no se prueba aquí es el salto del
# borde de Cloudflare, que depende de publicar la ruta del tunnel.
export PATH=/usr/local/bin:$PATH
B=http://pajaritos-web:8080
IMG=nginx:1.27-alpine

run() { docker run --rm --network tunnel $IMG sh -c "$1" 2>&1; }

echo "=== codigos de respuesta ==="
run "for r in /healthz / /index.html /app.js /sw.js /manifest.webmanifest \
       /datos/especies.json /datos/mareas.json /icono.svg \
       /api/reportes /api/admin /datos/reportes.db /api/reporte; do
       c=\$(wget -S -qO /dev/null $B\$r 2>&1 | sed -n 's|.*HTTP/1.1 \\([0-9]*\\).*|\\1|p' | tail -1)
       printf '  %-26s %s\n' \"\$r\" \"\$c\"
     done"

echo "=== cabeceras de seguridad por ruta ==="
for R in / /index.html /sw.js /app.js /datos/mareas.json; do
  N=$(run "wget -S -qO /dev/null $B$R 2>&1 | grep -ci 'content-security-policy'")
  P=$(run "wget -S -qO /dev/null $B$R 2>&1 | grep -ci 'permissions-policy'")
  printf "  %-22s CSP:%s  Permissions-Policy:%s\n" "$R" "$N" "$P"
done

echo "=== CSP completa en la raiz ==="
run "wget -S -qO /dev/null $B/ 2>&1 | grep -i 'content-security-policy'" | sed 's/^ */  /'

echo "=== cache de sw.js ==="
run "wget -S -qO /dev/null $B/sw.js 2>&1 | grep -iE 'cache-control|service-worker-allowed'" | sed 's/^ */  /'

echo "=== POST valido ==="
T=$(python3 -c "import time;print(int((time.time()-30)*1000))")
run "wget -qO- --header='Content-Type: application/json' \
  --post-data='{\"tipo\":\"fenologia\",\"especie\":\"platalea-leucorodia\",\"mensaje\":\"segunda prueba tras arreglar cabeceras\",\"abiertoEn\":$T}' \
  $B/api/reporte"
echo ""

echo "=== rate limit (12 envios seguidos) ==="
run "for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
      wget -S -qO /dev/null --header='Content-Type: application/json' \
        --post-data='{\"tipo\":\"error\",\"mensaje\":\"prueba de limite de ritmo\",\"abiertoEn\":$T}' \
        $B/api/reporte 2>&1 | sed -n 's|.*HTTP/1.1 \\([0-9]*\\).*|\\1|p' | tail -1 | tr '\n' ' '
    done"
echo ""

echo "=== base de datos ==="
cd /volume1/docker/pajaritos
docker compose exec -T api python /scripts/ver-reportes.py resumen 2>&1 | head -14
