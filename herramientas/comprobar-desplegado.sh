#!/bin/sh
# ¿Está produccion sirviendo EXACTAMENTE los ficheros de este repo?
#
# Uso:  herramientas/comprobar-desplegado.sh https://pajaritos.josearcos.me [dir-app]
#
# No pregunta si el despliegue "fue bien": pregunta por el hash del byte que
# devuelve el servidor. Es la unica respuesta que no se puede discutir. Un CI
# en verde dice que el build paso; un contenedor "healthy" dice que arranco.
# Ninguno de los dos dice que el navegador de alguien este recibiendo esto.
#
# La version de app.js y logica.js NO se pasa por parametro a proposito: se lee
# del index.html que sirve produccion. Asi, si el index desplegado es viejo, se
# compara el fichero viejo contra el nuevo del repo y salta, en vez de pedirle
# al servidor justo la version que queremos oir.
set -e

BASE=${1:?falta la URL base, p.ej. https://pajaritos.josearcos.me}
DIR=${2:-app}
BASE=${BASE%/}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

hash_de() { sha256sum "$1" | cut -d' ' -f1; }

# `--fail` es lo que separa "no coincide" de "no esta": sin el, un 404 devuelve
# una pagina de error con su hash tan tranquila y el fallo sale como diferencia.
bajar() {
  curl -fsSL --max-time 30 -o "$2" "$1" 2>/dev/null
}

fallos=0
aviso() { echo "  FALLO  $1"; fallos=$((fallos + 1)); }

if ! bajar "$BASE/index.html" "$tmp/index.html"; then
  echo "  FALLO  no he podido descargar $BASE/index.html"
  echo
  echo "NO SE PUEDE COMPROBAR: produccion no responde."
  exit 1
fi

# La version que produccion declara, no la que nos gustaria que declarara.
VER=$(sed -n 's|.*app\.js?v=\([A-Za-z0-9._-]*\).*|\1|p' "$tmp/index.html" | head -1)
if [ -z "$VER" ]; then
  echo "  FALLO  el index.html desplegado no declara ninguna version de app.js"
  exit 1
fi
echo "  version que sirve produccion: $VER"

comparar() {  # $1 = ruta relativa   $2 = query string (puede ir vacia)
  ruta=$1; query=$2
  local_f="$DIR/$ruta"
  if [ ! -f "$local_f" ]; then aviso "$ruta no existe en el repo"; return; fi
  if ! bajar "$BASE/$ruta$query" "$tmp/bajado"; then
    aviso "$ruta$query no se sirve (404 o error)"
    return
  fi
  a=$(hash_de "$tmp/bajado"); b=$(hash_de "$local_f")
  if [ "$a" = "$b" ]; then
    echo "  ok     $ruta$query"
  else
    aviso "$ruta$query difiere · produccion ${a%${a#??????????}} · repo ${b%${b#??????????}}"
  fi
}

comparar index.html ""
comparar logica.js "?v=$VER"
comparar app.js "?v=$VER"
comparar sw.js ""
comparar manifest.webmanifest ""

echo
if [ "$fallos" -gt 0 ]; then
  echo "DESPLIEGUE DESFASADO: $fallos fichero(s) no coinciden con el repo."
  exit 1
fi
echo "DESPLIEGUE AL DIA: produccion sirve exactamente este repo."
