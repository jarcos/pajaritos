#!/bin/sh
# Verifica que FEATURES.json es honesto. Dos invariantes:
#
#   · Una tarea PENDIENTE cuyo `check` YA PASA es un check roto. O el trabajo
#     está hecho y nadie lo marcó, o el comando no comprueba nada. Las dos
#     cosas hay que saberlas.
#   · Una tarea HECHA cuyo `check` FALLA es una regresión, o una mentira.
#
# Es la disciplina del mutante aplicada al backlog: si no has visto fallar el
# check, no sabes que comprueba algo. Sin esto, un bucle autónomo se pasa la
# noche marcando tareas contra comandos que devuelven 0 sin mirar nada.
#
# Uso:  sh pruebas/comprobar-features.sh
# Sale 0 si el fichero es honesto, 1 si no.
set -u

raiz=$(cd "$(dirname "$0")/.." && pwd)
cd "$raiz"
fallos=0

# Se lee con python3 (stdlib) para no meter dependencias por un parser de JSON.
n=$(python3 -c "import json;print(len(json.load(open('FEATURES.json'))['tareas']))")
i=0
while [ "$i" -lt "$n" ]; do
  id=$(python3 -c "import json;print(json.load(open('FEATURES.json'))['tareas'][$i]['id'])")
  hecha=$(python3 -c "import json;print(json.load(open('FEATURES.json'))['tareas'][$i]['hecha'])")
  titulo=$(python3 -c "import json;print(json.load(open('FEATURES.json'))['tareas'][$i]['titulo'])")
  check=$(python3 -c "import json;print(json.load(open('FEATURES.json'))['tareas'][$i]['check'])")

  if sh -c "$check" >/dev/null 2>&1; then pasa=si; else pasa=no; fi

  if [ "$hecha" = "True" ] && [ "$pasa" = "no" ]; then
    printf "  ROTO      %-4s hecha pero su check FALLA — regresion o mentira\n" "$id"
    printf "            %s\n" "$titulo"
    fallos=$((fallos + 1))
  elif [ "$hecha" = "False" ] && [ "$pasa" = "si" ]; then
    printf "  SOSPECHOSO %-3s pendiente pero su check YA PASA\n" "$id"
    printf "            %s\n" "$titulo"
    printf "            O el trabajo esta hecho y nadie lo marco, o el check no comprueba nada.\n"
    fallos=$((fallos + 1))
  elif [ "$hecha" = "True" ]; then
    printf "  ok        %-4s hecha, check en verde\n" "$id"
  else
    printf "  pendiente %-4s check en rojo, como debe estar\n" "$id"
  fi
  i=$((i + 1))
done

echo
if [ "$fallos" -gt 0 ]; then
  echo "FEATURES.json NO es honesto: $fallos entrada(s) que no cuadran."
  exit 1
fi
echo "FEATURES.json es honesto: cada check dice la verdad sobre su tarea."
