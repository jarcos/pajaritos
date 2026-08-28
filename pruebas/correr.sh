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
  node --test $ficheros
else
  echo "sin tests de JS todavia -- ver AGENTS.md, «Deuda declarada»"
fi

echo
echo "suite en verde"
