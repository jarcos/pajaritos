#!/bin/sh
# Construye y levanta la pila de pajaritos en el NAS.
set -e
export PATH=/usr/local/bin:$PATH
cd /volume1/docker/pajaritos

echo "=== validando la composicion ==="
docker compose config --quiet && echo "compose OK"

echo "=== construyendo ==="
docker compose build 2>&1 | tail -15

echo "=== levantando ==="
docker compose up -d 2>&1 | tail -15

echo "=== estado ==="
sleep 8
docker compose ps

echo "=== healthz interno ==="
docker compose exec -T web wget -qO- http://localhost:8080/healthz || echo "(web aun no responde)"

echo "=== log de mareas ==="
docker compose logs --tail 15 mareas

echo "=== log de api ==="
docker compose logs --tail 10 api
