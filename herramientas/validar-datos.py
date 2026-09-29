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
 5. El nombre científico de cada especie es el vigente. sinonimos.json ya trae
    el campo `vigente` contrastado contra Wikidata; que especies.json diga otra
    cosa significa que la ficha enseña un nombre que la comunidad ya no usa, y
    que quien lo busque fuera no lo encuentra. El nombre del PDF de la
    Autoridad Portuaria se conserva aparte, en `enPdfSeo`.
 6. Toda especie declara de dónde sale su texto de identificación. La ficha lo
    enseña, y una especie sin `fuenteIdentificacion` se leería con la misma
    autoridad que una cotejada contra la guía publicada. El mismo principio que
    con la fenología: un hueco declarado antes que un respaldo supuesto.
 7. Los pares de confusión son recíprocos y comparten hábitat. En el campo la
    duda va en las dos direcciones: si el tridáctilo avisa del común, el común
    tiene que avisar del tridáctilo. Y un par que según nuestros propios datos
    no coincide en ningún hábitat, o sobra, o revela un hábitat mal declarado.

 8. Las fotos cumplen el criterio de licencia t39.1 (29-09-2026). Una foto
    «lista» lleva autor, licencia libre (CC0, dominio público, CC BY o
    CC BY-SA), enlace a su página de Commons y fecha de revisión, y su fichero
    existe en app/fotos/ con la huella del contenido en el nombre (nginx las
    sirve como inmutables un año). CC BY y CC BY-SA obligan a atribuir: enseñar una foto
    sin decir de quién es incumple la licencia con la que se descargó. Y una
    especie sin campo `foto` mata la ficha, porque app.js lee `esp.foto.estado`.

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

    # 3b · logica.js: mismo agujero que app.js, y hay que taparlo el mismo día
    #      que nace el fichero. Si no se declara en index.html, `Logica` es
    #      undefined y la app muere en la primera marea; si no entra en el
    #      ARMAZON del service worker, funciona con red y se rompe sin ella,
    #      que es exactamente donde se usa.
    v_l_html = re.search(r'logica\.js\?v=([\w.-]+)', html)
    v_l_sw = re.search(r"'logica\.js\?v=([\w.-]+)'", sw)
    if not v_l_html:
        fallos.append("logica.js no está declarada en index.html")
    if not v_l_sw:
        fallos.append("logica.js no está en el ARMAZON de sw.js (no se precarga)")
    if v_l_html and v_l_sw and v_l_html.group(1) != v_l_sw.group(1):
        fallos.append(f"versión de logica.js desincronizada: index.html dice "
                      f"«{v_l_html.group(1)}» y sw.js «{v_l_sw.group(1)}»")
    if v_l_html and v_html and v_l_html.group(1) != v_html.group(1):
        fallos.append(f"logica.js y app.js con versiones distintas en index.html: "
                      f"«{v_l_html.group(1)}» y «{v_html.group(1)}». Se cachean "
                      f"juntas o se quedan descompasadas.")

    # 5 · nomenclatura vigente
    def rotulo(e):
        return e.get("nombre") or e.get("id") or "?"

    por_id = {s["id"]: s for s in sinonimos["entradas"]}
    viejos = []
    for e in especies["especies"]:
        sin = por_id.get(e["id"])
        if sin and sin.get("vigente") and e.get("cientifico") \
                and sin["vigente"] != e["cientifico"]:
            viejos.append(f"{rotulo(e)}: «{e['cientifico']}» → «{sin['vigente']}»")
    if viejos:
        fallos.append(f"nombres científicos desfasados respecto al campo "
                      f"`vigente` de sinonimos.json ({len(viejos)}): " + " · ".join(viejos))

    # 6 · procedencia del texto de identificación
    FUENTES = {"guia-seo", "propia"}
    malas = [f"{rotulo(e)}: {e.get('fuenteIdentificacion') or 'sin declarar'}"
             for e in especies["especies"]
             if e.get("identificacion") and e.get("fuenteIdentificacion") not in FUENTES]
    if malas:
        fallos.append(f"especies sin procedencia válida del texto de identificación "
                      f"({len(malas)}, se aceptan {sorted(FUENTES)}): " + " · ".join(malas[:5])
                      + (" …" if len(malas) > 5 else ""))
    mudas = [rotulo(e) for e in especies["especies"]
             if e.get("fuenteIdentificacion") == "propia" and not e.get("notaIdentificacion")]
    if mudas:
        fallos.append("texto de identificación propio sin decir por qué el PDF no lo "
                      f"respalda: {mudas}")

    # 7 · pares de confusión
    por_esp = {e["id"]: e for e in especies["especies"]}
    pares = {(e["id"], c["especie"])
             for e in especies["especies"] for c in (e.get("confusiones") or [])}
    rotas = [p for p in pares if p[1] not in por_esp]
    if rotas:
        fallos.append(f"confusiones que apuntan a especies inexistentes: {sorted(rotas)}")
    mancas = sorted(p for p in pares if p[1] in por_esp and (p[1], p[0]) not in pares)
    if mancas:
        fallos.append(f"pares de confusión sin recíproco ({len(mancas)}): "
                      + " · ".join(f"{rotulo(por_esp[a])} → {rotulo(por_esp[b])}"
                                   for a, b in mancas))
    sin_solape = sorted({tuple(sorted(p)) for p in pares
                         if p[1] in por_esp
                         and not (set(por_esp[p[0]].get("habitat") or [])
                                  & set(por_esp[p[1]].get("habitat") or []))})
    if sin_solape:
        fallos.append(f"pares de confusión que no comparten ningún hábitat "
                      f"({len(sin_solape)}): "
                      + " · ".join(f"{rotulo(por_esp[a])}/{rotulo(por_esp[b])}"
                                   for a, b in sin_solape))

    # 8 · fotos
    ESTADOS_FOTO = ("pendiente", "lista")
    LICENCIA_LIBRE = re.compile(r"^(CC0( 1\.0)?|Public domain|CC BY(-SA)? [1-4]\.\d)$")
    FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    NOMBRE_FICHERO = re.compile(r"^[\w.-]+\.(webp|jpg|jpeg|png)$")
    CON_HUELLA = re.compile(r"-[0-9a-f]{8}\.(webp|jpg|jpeg|png)$")
    PAGINA_COMMONS = "https://commons.wikimedia.org/wiki/File:"
    for e in especies["especies"]:
        r, foto = rotulo(e), e.get("foto")
        if not isinstance(foto, dict):
            fallos.append(f"{r}: sin campo foto (app.js lee esp.foto.estado y la ficha muere)")
            continue
        estado = foto.get("estado")
        if estado not in ESTADOS_FOTO:
            fallos.append(f"{r}: foto.estado «{estado}» no es ninguno de {list(ESTADOS_FOTO)}")
            continue
        if estado == "pendiente":
            if foto.get("archivo"):
                fallos.append(f"{r}: foto pendiente con archivo «{foto['archivo']}»: "
                              f"o está lista o está pendiente")
            continue
        archivo = foto.get("archivo") or ""
        if not NOMBRE_FICHERO.match(archivo):
            fallos.append(f"{r}: foto lista con archivo «{archivo}» que no es un nombre "
                          f"de fichero simple (sin rutas, .webp .jpg .png)")
        elif not CON_HUELLA.search(archivo):
            fallos.append(f"{r}: foto lista con archivo «{archivo}» sin huella del contenido "
                          f"en el nombre (-1a2b3c4d.webp): nginx sirve /fotos/ como "
                          f"inmutable un año y otra foto tiene que ser otra URL")
        elif not (app / "fotos" / archivo).is_file():
            fallos.append(f"{r}: foto lista pero app/fotos/{archivo} no existe")
        if not foto.get("autor"):
            fallos.append(f"{r}: foto lista sin autor (CC BY y CC BY-SA obligan a atribuir)")
        licencia = foto.get("licencia") or ""
        if not licencia:
            fallos.append(f"{r}: foto lista sin licencia")
        elif not LICENCIA_LIBRE.match(licencia):
            fallos.append(f"{r}: licencia «{licencia}» fuera del criterio "
                          f"(CC0, dominio público, CC BY, CC BY-SA)")
        elif not licencia.startswith("Public domain") \
                and not (foto.get("licenciaUrl") or "").startswith("https://creativecommons.org/"):
            fallos.append(f"{r}: foto lista sin licenciaUrl de creativecommons.org")
        if not (foto.get("paginaArchivo") or "").startswith(PAGINA_COMMONS):
            fallos.append(f"{r}: foto lista con paginaArchivo que no apunta a un archivo "
                          f"de Commons ({PAGINA_COMMONS}…)")
        if not FECHA.match(foto.get("revisada") or ""):
            fallos.append(f"{r}: foto lista sin fecha revisada AAAA-MM-DD "
                          f"(la revisión humana es la que da por buena la identificación)")

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
    listas = sum(1 for e in especies["especies"] if e["foto"]["estado"] == "lista")
    print(f"ok · {len(ids)} especies ({ver} con fenología verificada, {listas} con foto) · "
          f"{cat}/{len(sinonimos['entradas'])} categorías de Commons verificadas · "
          f"{len(ids_punto)} puntos · app.js v{v_html.group(1)}")
    return 0


def _salir(fallos: list[str]) -> int:
    for f in fallos:
        print(f"[FALLO] {f}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
