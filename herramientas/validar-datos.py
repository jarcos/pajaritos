#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprueba que los datos y el versionado de la app son coherentes. Es lo que
corre en CI antes de dejar desplegar, y lo mismo se puede lanzar en local.

Cada comprobación está aquí porque algo se rompió de verdad:

 1. Los JSON parsean. Obvio, pero un JSON a medias deja la app en blanco.
 2. Toda especie tiene entrada en sinonimos.json. Durante meses solo 8 de las
    60 la tenían: las demás caían en el `|| esp.cientifico` de app.js y la
    ficha no decía ni «verificada» ni «por verificar». Categoría sin comprobar
    y sin avisarlo.
 3. La versión de app.js coincide en index.html y en la lista ARMAZON de
    sw.js. Si se desincronizan, el Service Worker precarga una URL que la
    página no pide, y quien ya tenga la app instalada se queda con el JS
    viejo para siempre.
 4. Las referencias cruzadas cierran: el grupo de cada especie existe, y los
    puntos que declara cada zona existen en puntos.geojson.

Uso:  herramientas/validar-datos.py [--datos app/datos] [--app app]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default="app/datos")
    ap.add_argument("--app", default="app")
    a = ap.parse_args()
    datos, app = Path(a.datos), Path(a.app)
    fallos: list[str] = []

    def cargar(nombre):
        try:
            return json.loads((datos / nombre).read_text(encoding="utf-8"))
        except Exception as e:                        # noqa: BLE001
            fallos.append(f"{nombre}: no parsea · {e}")
            return None

    especies = cargar("especies.json")
    sinonimos = cargar("sinonimos.json")
    zonas = cargar("zonas.json")
    puntos = cargar("puntos.geojson")
    if fallos:
        return _salir(fallos)

    ids = [e["id"] for e in especies["especies"]]
    if len(ids) != len(set(ids)):
        fallos.append("especies.json: hay ids repetidos")

    # 2 · cobertura de sinonimos.json
    con_sinonimo = {s["id"] for s in sinonimos["entradas"]}
    faltan = [i for i in ids if i not in con_sinonimo]
    if faltan:
        fallos.append(f"sinonimos.json: {len(faltan)} especies sin entrada "
                      f"(caerían en el fallback silencioso): {faltan[:5]}"
                      + (" …" if len(faltan) > 5 else ""))
    sobran = [s for s in con_sinonimo if s not in set(ids)]
    if sobran:
        fallos.append(f"sinonimos.json: entradas de especies que ya no existen: {sobran}")

    # 3 · versión de app.js sincronizada entre index.html y sw.js
    html = (app / "index.html").read_text(encoding="utf-8")
    sw = (app / "sw.js").read_text(encoding="utf-8")
    v_html = re.search(r'app\.js\?v=([\w.-]+)', html)
    v_sw = re.search(r"'app\.js\?v=([\w.-]+)'", sw)
    if not v_html or not v_sw:
        fallos.append("no encuentro la versión de app.js en index.html o en sw.js")
    elif v_html.group(1) != v_sw.group(1):
        fallos.append(f"versión de app.js desincronizada: index.html dice "
                      f"«{v_html.group(1)}» y sw.js «{v_sw.group(1)}»")

    # 4 · referencias cruzadas
    grupos = {g["id"] for g in especies["grupos"]}
    huerfanas = [e["id"] for e in especies["especies"] if e["grupo"] not in grupos]
    if huerfanas:
        fallos.append(f"especies con grupo inexistente: {huerfanas}")
    ids_punto = {f["properties"]["id"] for f in puntos["features"]}
    for z in zonas["zonas"]:
        malos = [p for p in z.get("puntos", []) if p not in ids_punto]
        if malos:
            fallos.append(f"zona {z['id']}: puntos que no existen en puntos.geojson: {malos}")

    if fallos:
        return _salir(fallos)
    ver = sum(1 for e in especies["especies"] if e["confianza"] == "verificado")
    cat = sum(1 for s in sinonimos["entradas"] if s["commonsVerificado"])
    print(f"ok · {len(ids)} especies ({ver} con fenología verificada) · "
          f"{cat}/{len(sinonimos['entradas'])} categorías de Commons verificadas · "
          f"{len(ids_punto)} puntos · app.js v{v_html.group(1)}")
    return 0


def _salir(fallos: list[str]) -> int:
    for f in fallos:
        print(f"[FALLO] {f}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
