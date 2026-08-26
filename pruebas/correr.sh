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
if find pruebas/js -name '*.test.js' 2>/dev/null | grep -q .; then
  node --test pruebas/js/
else
  echo "sin tests de JS todavia -- ver AGENTS.md, «Deuda declarada»"
fi

echo
echo "suite en verde"
