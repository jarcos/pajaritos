#!/bin/sh
# La puerta local. Corre exactamente lo que corre el job `comprobar` de CI,
# más la suite de tests. Si esto sale verde, el push no debería romper CI.
#
# Uso:  pruebas/puerta.sh
#
# No confundir con herramientas/verificar.sh, que es otra cosa: un humo
# contra el contenedor YA DESPLEGADO en el NAS, desde la red `tunnel`.
set -e

raiz=$(cd "$(dirname "$0")/.." && pwd)
cd "$raiz"

echo "-- 1/5 · datos coherentes -------------------------------"
python3 herramientas/validar-datos.py

echo
echo "-- 2/5 · app.js parsea ----------------------------------"
node --check app/app.js && echo "ok"

echo
echo "-- 3/5 · los .sh parsean --------------------------------"
for f in herramientas/*.sh scripts/*.sh pruebas/*.sh; do
  [ -e "$f" ] || continue
  sh -n "$f" || { echo "sintaxis rota: $f"; exit 1; }
done
echo "ok"

echo
echo "-- 4/5 · nada de basura de macOS ------------------------"
sucio=$(git ls-files | grep -E '(^|/)\._|\.DS_Store$' || true)
if [ -n "$sucio" ]; then
  echo "ficheros AppleDouble commiteados:"
  echo "$sucio"
  exit 1
fi
echo "ok"

echo
echo "-- 5/5 · suite de tests ---------------------------------"
sh pruebas/correr.sh

echo
echo "PUERTA EN VERDE"
