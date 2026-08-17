#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrae datos/*.json del bundle autocontenido index-preview.html.

El preview lleva incrustado el bloque <script type="application/json"
id="datos-incrustados"> con especies, zonas, puntos y sinonimos. Sirve para
reconstruir app/datos/ sin volver a transferir los ficheros.
Uso: extraer-datos-preview.py <preview.html> <destino/datos>
"""
import hashlib
import json
import pathlib
import re
import sys

origen = pathlib.Path(sys.argv[1])
destino = pathlib.Path(sys.argv[2])
destino.mkdir(parents=True, exist_ok=True)

html = origen.read_text(encoding="utf-8")
m = re.search(
    r'<script type="application/json" id="datos-incrustados">(.*?)</script>',
    html, re.S)
if not m:
    sys.exit("no encuentro el bloque de datos incrustados")

datos = json.loads(m.group(1).replace("<\\/", "</"))
NOMBRE = {"especies": "especies.json", "zonas": "zonas.json",
          "puntos": "puntos.geojson", "sinonimos": "sinonimos.json"}

for clave, fichero in NOMBRE.items():
    if clave not in datos:
        print(f"[aviso] falta {clave}")
        continue
    # Mismo formato que el generador: ensure_ascii=False, indent=1.
    texto = json.dumps(datos[clave], ensure_ascii=False, indent=1)
    ruta = destino / fichero
    ruta.write_text(texto, encoding="utf-8")
    md5 = hashlib.md5(texto.encode("utf-8")).hexdigest()
    print(f"{fichero:20s} {len(texto):7d} B  md5 {md5}")
