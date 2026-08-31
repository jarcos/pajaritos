#!/bin/sh
# Corre la suite entera: Python (unittest, stdlib) y JS (node --test, viene en
# Node). Sin dependencias de producción, sin package.json, sin node_modules.
#
# Uso:  pruebas/correr.sh
set -e

raiz=$(cd "$(dirname "$0")/.." && pwd)
cd "$raiz"

echo "-- Python -----------------------------------------------"
python3 -m unittest discover -s pruebas/python -t . -v

echo
echo "-- JavaScript -------------------------------------------"
# `node --test pruebas/js/` NO vale: node 22 intenta resolver el directorio
# como modulo y muere con MODULE_NOT_FOUND. Estuvo escrito asi desde el primer
# dia y nunca se noto, porque no habia ni un solo .test.js que lo ejecutara.
# Un runner que nunca ha corrido nada tampoco esta probado.
ficheros=$(find pruebas/js -name '*.test.js' | sort)
if [ -n "$ficheros" ]; then
  # shellcheck disable=SC2086
  # --test-reporter=tap NO es cosmetico: sin el, node elige formato segun
  # version y segun si stdout es un TTY, y cualquier cosa que lea esta salida
  # (los checks de FEATURES.json, por ejemplo) da un resultado distinto segun
  # la maquina. Paso el 31-08-2026: verde en la VM, rojo en el Mac.
  node --test --test-reporter=tap $ficheros
else
  echo "sin tests de JS todavia -- ver AGENTS.md, «Deuda declarada»"
fi

echo
echo "suite en verde"
