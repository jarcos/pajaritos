#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconstruye app/index.html y app/app.js desde index-preview.html.

El preview es el bundle autocontenido: lleva el JSON de datos incrustado y el
JS en línea. Esto deshace ambas cosas para dejar el árbol de producción, donde
el JS va en fichero aparte porque la CSP del sitio es script-src 'self'.

Uso: reconstruir-app.py <preview.html> <destino/app>
"""
import hashlib
import pathlib
import re
import sys

CABECERA = (
    "/* Aves del Odiel — lógica de la aplicación.\n"
    "   Fichero externo a propósito: la CSP del sitio es script-src 'self',\n"
    "   sin 'unsafe-inline'. Sigue siendo una sola página sin dependencias. */\n"
)

origen = pathlib.Path(sys.argv[1])
destino = pathlib.Path(sys.argv[2])
destino.mkdir(parents=True, exist_ok=True)

html = origen.read_text(encoding="utf-8")

# 1. Fuera el bloque de datos incrustados: en producción se sirven por HTTP.
html = re.sub(
    r'<script type="application/json" id="datos-incrustados">.*?</script>\n?',
    "", html, flags=re.S)

# 2. Los bloques <script> en línea se funden en app.js, en orden.
bloques = re.findall(r"<script>\n(.*?)</script>", html, re.S)
if not bloques:
    sys.exit("no encuentro bloques de script en línea")

cuerpo = "\n".join(b.replace('"use strict";\n', "", 1).strip() for b in bloques)
js = '"use strict";\n' + CABECERA + cuerpo + "\n"

html = re.sub(r"<script>\n.*?</script>\n?", "", html, flags=re.S)
html = html.replace("</body>", '<script src="app.js" defer></script>\n</body>')

(destino / "app.js").write_text(js, encoding="utf-8")
(destino / "index.html").write_text(html, encoding="utf-8")

for f in ("index.html", "app.js"):
    d = (destino / f).read_bytes()
    print(f"{f:12s} {len(d):7d} B  md5 {hashlib.md5(d).hexdigest()}  "
          f"({len(bloques)} bloques)" if f == "app.js" else
          f"{f:12s} {len(d):7d} B  md5 {hashlib.md5(d).hexdigest()}")
