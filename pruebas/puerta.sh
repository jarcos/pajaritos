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

echo "-- 1/6 · datos coherentes -------------------------------"
python3 herramientas/validar-datos.py

echo
echo "-- 2/6 · app.js parsea ----------------------------------"
node --check app/app.js && echo "ok"

echo
echo "-- 3/6 · los .sh parsean --------------------------------"
for f in herramientas/*.sh scripts/*.sh pruebas/*.sh; do
  [ -e "$f" ] || continue
  sh -n "$f" || { echo "sintaxis rota: $f"; exit 1; }
done
echo "ok"

echo
echo "-- 4/6 · nada de basura de macOS ------------------------"
sucio=$(git ls-files | grep -E '(^|/)\._|\.DS_Store$' || true)
if [ -n "$sucio" ]; then
  echo "ficheros AppleDouble commiteados:"
  echo "$sucio"
  exit 1
fi
echo "ok"

echo
echo "-- 5/6 · suite de tests ---------------------------------"
sh pruebas/correr.sh

echo
echo "-- 6/6 · el tablero dice la verdad ----------------------"
# Un backlog cuyos checks no se comprueban es una lista de deseos. Y en un
# bucle autonomo es peor: el agente marca tareas contra comandos que devuelven
# 0 sin mirar nada, y por la manana tienes cinco tareas "hechas" y cero hechas.
sh pruebas/comprobar-features.sh

echo
echo "PUERTA EN VERDE"
