#!/bin/sh
# Commit + push, pero SOLO si la puerta esta verde y lo que entra es lo que
# se espera que entre. Pensado para que lo llame el bucle desatendido.
#
# Uso:  sh pruebas/commit-en-verde.sh "mensaje" [fichero...]
#       sin ficheros hace `git add -A`, con ficheros solo esos.
#
# Por que existe: en un bucle sin nadie mirando, los dos fallos caros son
# commitear rojo y commitear de mas. Los dos se evitan con comandos, no con
# buena intencion. Y el orden importa: la puerta se corre ANTES del commit,
# porque un commit deshecho a mano a las 3 de la manana no lo deshace nadie.
set -e

raiz=$(cd "$(dirname "$0")/.." && pwd)
cd "$raiz"

mensaje=$1
if [ -z "$mensaje" ]; then
  echo "uso: sh pruebas/commit-en-verde.sh \"mensaje\" [fichero...]" >&2
  exit 2
fi
shift

abortar() {
  echo
  echo "PARO: $1"
  git reset -q 2>/dev/null || true
  exit 1
}

echo "-- 0/6 . identidad de git ------------------------------"
# Sin esto el bucle corre la puerta entera, tarda lo que tarde, y muere en el
# ultimo paso con "Author identity unknown". Fallar barato y pronto.
if [ -z "$(git config --get user.email)" ] || [ -z "$(git config --get user.name)" ]; then
  echo "PARO: git no sabe quien eres. Configura user.name y user.email."
  exit 1
fi
echo "$(git config --get user.name) <$(git config --get user.email)>"

echo "-- 1/6 . rama ------------------------------------------"
rama=$(git rev-parse --abbrev-ref HEAD)
if [ "$rama" != "main" ]; then
  abortar "estas en '$rama'. En esta cartera se trabaja en main."
fi
echo "main, ok"

echo
echo "-- 2/6 . hay algo que commitear ------------------------"
if [ -z "$(git status --porcelain)" ]; then
  echo "PARO: el arbol esta limpio, no hay nada que commitear."
  exit 1
fi
git status --short

echo
echo "-- 3/6 . preparando el indice --------------------------"
if [ $# -gt 0 ]; then
  git add -- "$@"
  echo "anadidos solo: $*"
else
  git add -A
  echo "anadido todo el arbol"
fi

echo
echo "-- 4/6 . QUE entra exactamente -------------------------"
# El paso que se salta todo el mundo. Se imprime siempre, aunque no lo lea
# nadie: queda en el log del bucle y es lo primero que se mira cuando algo
# aparece commiteado sin saber por que.
git diff --cached --stat
entran=$(git diff --cached --name-only)
if [ -z "$entran" ]; then
  echo "PARO: el indice esta vacio despues del add."
  exit 1
fi

prohibido=$(printf '%s\n' "$entran" | grep -E '(^|/)\._|\.DS_Store$|(^|/)\.env$|\.sql\.gz$|(^|/)node_modules/|(^|/)dumps/|\.log$|(^|/)\.venv/' || true)
if [ -n "$prohibido" ]; then
  echo "ficheros que no deben versionarse:"
  printf '%s\n' "$prohibido"
  abortar "hay basura en el indice."
fi

grandes=""
for f in $entran; do
  [ -f "$f" ] || continue
  bytes=$(wc -c < "$f" | tr -d ' ')
  if [ "$bytes" -gt 1048576 ]; then
    grandes="$grandes$f ($bytes bytes)
"
  fi
done
if [ -n "$grandes" ]; then
  printf '%s' "$grandes"
  abortar "fichero de mas de 1 MB en el indice. En un bucle desatendido eso casi siempre es un descuido, no una feature."
fi
echo "nada sospechoso"

echo
echo "-- 5/6 . la puerta -------------------------------------"
if ! sh pruebas/puerta.sh; then
  abortar "puerta en rojo. Rojo no se commitea."
fi

echo
echo "-- 6/6 . commit y push ---------------------------------"
git commit -q -m "$mensaje"
echo "commit: $(git log --oneline -1)"
if git push -q origin main 2>/dev/null; then
  echo "empujado a origin/main"
else
  echo "AVISO: el commit esta hecho en local pero el push ha fallado."
  echo "       Queda pendiente: git push origin main"
fi
