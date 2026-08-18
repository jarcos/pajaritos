#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica contra Wikimedia Commons la categoría de foto de cada especie y
reescribe app/datos/sinonimos.json con el resultado.

POR QUÉ EXISTE ESTO
La ficha de especie no enseña foto todavía: enseña un placeholder que enlaza a
la búsqueda `deepcategory:"<categoriaCommons>"` en Commons. Si esa categoría no
existe, es una redirección o pertenece a otro taxón, el enlace no lleva a
ninguna parte hoy y, cuando exista el banco de imágenes, traerá fotos de otra
especie. Por eso `sinonimos.json` distingue verificado de pendiente, y por eso
este script no marca nada como verificado sin haberlo comprobado.

EL PROBLEMA DE FONDO son los cambios de género. El PDF de la Autoridad
Portuaria usa nombres antiguos (Larus melanocephalus, Sterna sandvicensis,
Oceanodroma leucorhoa) y Commons categoriza casi siempre por el nombre
vigente (Ichthyaetus, Thalasseus, Hydrobates)... salvo cuando no lo hace:
`Category:Oceanodroma leucorhoa` sigue siendo la buena y el nombre vigente ni
siquiera existe como categoría. No hay regla; hay que preguntar.

CÓMO LO RESUELVE

 1. Pregunta a la API de Commons por las 60 categorías candidatas de golpe
    (lotes de 50, `prop=categoryinfo&redirects=1`). De ahí salen tres cosas:
    si la página existe, si es una redirección y a dónde, y cuántos archivos
    tiene. Una categoría vacía es tan inútil como una que no existe.

 2. Para las que fallan, va a Wikidata: busca el nombre científico, se queda
    con el ítem que sea un taxón (P225 = nombre del taxón) y lee su categoría
    de Commons (P373). Wikidata sí mantiene la cadena sinónimo → vigente, que
    es justo lo que aquí falta. La candidata que sale de ahí se vuelve a
    comprobar en Commons, porque P373 también se queda obsoleta.

 3. Solo marca `commonsVerificado: true` si la categoría existe, no es
    redirección, tiene al menos un archivo y su nombre coincide con el taxón
    que Wikidata reconoce para esa especie. Cualquier otra cosa queda en false
    con el diagnóstico escrito en `nota`.

LO QUE NO COMPRUEBA, Y CONVIENE SABERLO: que las fotos DENTRO de la categoría
estén bien identificadas. La entrada de Puffinus mauretanicus ya avisa a mano
de que buena parte de su categoría son págalos mal clasificados. Eso solo lo
ve un ojo humano, así que las notas escritas a mano se conservan.

Uso:
    herramientas/verificar-commons.py                 # comprueba y escribe
    herramientas/verificar-commons.py --dry-run       # comprueba e imprime
    herramientas/verificar-commons.py --informe i.md  # además, informe markdown
    herramientas/verificar-commons.py --solo larus-fuscus,alca-torda

Sin dependencias: solo la biblioteca estándar. Tarda ~1 minuto por las pausas
de cortesía con la API.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

COMMONS = "https://commons.wikimedia.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"

# Wikimedia exige un User-Agent que identifique al cliente y dé un contacto.
# Sin él responden 403 sin más explicación.
UA = ("pajaritos.josearcos.me/1.0 (guia de observacion de aves del Odiel; "
      "contacto: {}) python-urllib")

LOTE = 50          # titles= admite 50 por petición a usuarios anónimos
PAUSA = 0.4        # segundos entre peticiones

# Una categoría sin NADA dentro no sirve. Pero «sin archivos directos» no es lo
# mismo que vacía: Category:Podiceps nigricollis es un contenedor puro, con 10
# subcategorías y 0 archivos propios. Por eso la ficha busca con `deepcategory:`
# y aquí cuenta como buena si tiene archivos O subcategorías.


def util(inf: dict) -> bool:
    return inf["existe"] and (inf["archivos"] >= 1 or inf["subcats"] >= 1)


NOTAS_GENERICAS = {"", "Por verificar", "Previsible, por verificar"}


class FuenteRota(RuntimeError):
    """La API no tiene la forma esperada. Nunca escribir en este caso."""


# ─────────────────────────────── red ────────────────────────────────

def _api(base: str, params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2", "maxlag": "5"}
    url = f"{base}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA.format(os.environ.get("ALERT_EMAIL", "n/a")),
        "Accept": "application/json",
    })
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                obj = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and intento < 2:
                time.sleep(2 ** intento * 2)
                continue
            raise FuenteRota(f"HTTP {e.code} en {base}") from e
        except urllib.error.URLError as e:
            raise FuenteRota(f"red: {e}") from e
        # maxlag: la réplica va retrasada, reintentar es lo correcto
        if obj.get("error", {}).get("code") == "maxlag" and intento < 2:
            time.sleep(5)
            continue
        if "error" in obj:
            raise FuenteRota(f"{base}: {obj['error'].get('info', obj['error'])}")
        time.sleep(PAUSA)
        return obj
    raise FuenteRota(f"{base}: agotados los reintentos")


def consultar_categorias(nombres: list[str]) -> dict[str, dict]:
    """nombre de categoría (sin prefijo) → {existe, redirigeA, archivos, subcats}.

    `redirects=1` hace que la API siga las redirecciones, así que el resultado
    llega bajo el título de destino: la lista `redirects` es la que dice de
    dónde venía. Sin ella, una redirección pasaría por categoría buena.
    """
    fuera: dict[str, dict] = {}
    for i in range(0, len(nombres), LOTE):
        trozo = nombres[i:i + LOTE]
        obj = _api(COMMONS, {
            "action": "query",
            "prop": "categoryinfo",
            "redirects": "1",
            "titles": "|".join(f"Category:{n}" for n in trozo),
        })
        q = obj.get("query")
        if not isinstance(q, dict) or "pages" not in q:
            raise FuenteRota("respuesta de Commons sin query.pages")

        # origen normalizado → destino final, siguiendo la cadena
        salto: dict[str, str] = {}
        for n in q.get("normalized", []):
            salto[n["from"]] = n["to"]
        for r in q.get("redirects", []):
            salto[r["from"]] = r["to"]

        def destino(titulo: str) -> str:
            visto = set()
            while titulo in salto and titulo not in visto:
                visto.add(titulo)
                titulo = salto[titulo]
            return titulo

        paginas = {p["title"]: p for p in q["pages"]}
        for n in trozo:
            fin = destino(f"Category:{n}")
            p = paginas.get(fin, {})
            ci = p.get("categoryinfo") or {}
            fuera[n] = {
                "existe": "missing" not in p,
                "redirigeA": fin[len("Category:"):] if fin != f"Category:{n}" else None,
                "archivos": int(ci.get("files", 0)),
                "subcats": int(ci.get("subcats", 0)),
            }
    return fuera


def taxon_en_wikidata(cientifico: str) -> dict | None:
    """Busca el nombre científico y devuelve el ítem que sea un taxón.

    Interesan dos propiedades: P225 (nombre del taxón, o sea el vigente según
    Wikidata) y P373 (categoría de Commons). Un sinónimo antiguo suele tener
    ítem propio que apunta al vigente; por eso se miran varios resultados y se
    prefiere el que traiga P373.
    """
    busq = _api(WIKIDATA, {
        "action": "wbsearchentities", "language": "en", "uselang": "en",
        "type": "item", "limit": "7", "search": cientifico,
    })
    ids = [h["id"] for h in busq.get("search", [])]
    if not ids:
        return None
    ent = _api(WIKIDATA, {
        "action": "wbgetentities", "ids": "|".join(ids),
        "props": "claims|labels", "languages": "en",
    }).get("entities", {})

    def valor(claims, prop):
        for c in claims.get(prop, []):
            v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(v, str):
                return v
        return None

    candidatos = []
    for qid in ids:                      # respetar el orden de relevancia
        e = ent.get(qid) or {}
        claims = e.get("claims", {})
        p225 = valor(claims, "P225")
        if not p225:
            continue                     # no es un taxón
        candidatos.append({
            "qid": qid,
            "taxon": p225,
            "categoria": valor(claims, "P373"),
            "etiqueta": (e.get("labels", {}).get("en") or {}).get("value"),
        })
    if not candidatos:
        return None
    # Preferir el que trae categoría de Commons; si ninguno, el primero.
    return next((c for c in candidatos if c["categoria"]), candidatos[0])


# ──────────────────────────── verificación ────────────────────────────

def dictaminar(esp: dict, candidata: str, info: dict, wd: dict | None,
               vigente_previo: str | None = None) -> dict:
    """Decide categoría final, si vale, y por qué. Devuelve la entrada nueva."""
    nombre_cientifico = esp["cientifico"]
    motivos: list[str] = []
    final = candidata
    inf = info

    if inf["redirigeA"]:
        motivos.append(f"«{candidata}» redirige a «{inf['redirigeA']}»")
        final = inf["redirigeA"]
    elif not inf["existe"]:
        motivos.append(f"«{candidata}» no existe en Commons")

    ok = util(inf)
    if inf["existe"] and not ok:
        motivos.append(f"«{final}» existe pero está vacía")
    elif ok and inf["archivos"] == 0:
        motivos.append(f"«{final}» no tiene archivos propios: {inf['subcats']} "
                       f"subcategorías, la ficha las alcanza con deepcategory")

    # Wikidata solo se consulta para las dudosas, así que en la mayoría de los
    # casos no hay taxón vigente que leer. Conservar el que ya hubiera escrito a
    # mano en sinonimos.json: si no, «Ichthyaetus audouinii» se degradaría al
    # «Larus audouinii» del PDF y el fichero pasaría a decir algo que no es.
    vigente = (wd["taxon"] if wd else None) or vigente_previo
    if ok and vigente and vigente.lower() != final.lower():
        # La categoría existe y tiene fotos, pero no se llama como el taxón
        # que Wikidata reconoce. Puede ser correcto (Commons conserva nombres
        # antiguos a propósito), así que se avisa sin descartarla.
        motivos.append(f"Wikidata da como vigente «{vigente}»; "
                       f"la categoría con fotos es «{final}»")

    return {
        "final": final,
        "verificado": bool(ok),
        "archivos": inf["archivos"] if inf["existe"] else None,
        "subcats": inf["subcats"] if inf["existe"] else None,
        "vigente": vigente or nombre_cientifico,
        "motivos": motivos,
    }


def escribir_atomico(destino: Path, payload: dict) -> None:
    """temp + rename en el mismo volumen: la app nunca ve un JSON a medias."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=".sinonimos-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, destino)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", default=None, help="carpeta app/datos (por defecto, la del repo)")
    ap.add_argument("--dry-run", action="store_true", help="no escribe sinonimos.json")
    ap.add_argument("--informe", metavar="FICHERO.md", help="escribe un informe markdown")
    ap.add_argument("--solo", metavar="ids", help="lista de ids separados por comas")
    args = ap.parse_args()

    raiz = Path(__file__).resolve().parent.parent
    datos = Path(args.datos) if args.datos else raiz / "app" / "datos"
    f_esp, f_sin = datos / "especies.json", datos / "sinonimos.json"
    if not f_esp.exists():
        return _fallo(f"no encuentro {f_esp}")

    especies = json.loads(f_esp.read_text(encoding="utf-8"))["especies"]
    previo = json.loads(f_sin.read_text(encoding="utf-8")) if f_sin.exists() else {"entradas": []}
    antes = {e["id"]: e for e in previo.get("entradas", [])}

    if args.solo:
        pedidos = {s.strip() for s in args.solo.split(",") if s.strip()}
        especies = [e for e in especies if e["id"] in pedidos]
        if not especies:
            return _fallo(f"ningún id de --solo existe en especies.json")

    # Candidata: lo que ya hubiera a mano, y si no el científico de la ficha.
    candidata = {e["id"]: (antes.get(e["id"], {}).get("categoriaCommons") or e["cientifico"])
                 for e in especies}

    print(f"[1/3] Commons · {len(especies)} categorías candidatas", file=sys.stderr, flush=True)
    try:
        info = consultar_categorias(sorted({c for c in candidata.values()}))
    except FuenteRota as e:
        return _fallo(str(e))

    # Segunda vuelta: Wikidata solo para las dudosas. Ahorra ~50 peticiones.
    dudosas = [e for e in especies
               if not util(info[candidata[e["id"]]])
               or info[candidata[e["id"]]]["redirigeA"]]
    print(f"[2/3] Wikidata · {len(dudosas)} dudosas", file=sys.stderr, flush=True)
    wd: dict[str, dict | None] = {}
    for e in dudosas:
        try:
            wd[e["id"]] = taxon_en_wikidata(e["cientifico"])
        except FuenteRota as err:
            print(f"[aviso] Wikidata falló para {e['cientifico']}: {err}", file=sys.stderr)
            wd[e["id"]] = None

    # Las que Wikidata propone otra categoría hay que comprobarlas también.
    extra = sorted({w["categoria"] for w in wd.values()
                    if w and w.get("categoria") and w["categoria"] not in info})
    if extra:
        print(f"[3/3] Commons · {len(extra)} categorías propuestas por Wikidata",
              file=sys.stderr, flush=True)
        try:
            info.update(consultar_categorias(extra))
        except FuenteRota as e:
            return _fallo(str(e))

    entradas, resumen = [], {"verificadas": 0, "pendientes": 0, "cambiadas": 0}
    for e in especies:
        cand = candidata[e["id"]]
        previo = antes.get(e["id"], {}).get("vigente")
        d = dictaminar(e, cand, info[cand], wd.get(e["id"]), previo)

        # Si la candidata no vale y Wikidata propuso otra, probar con esa.
        alt = (wd.get(e["id"]) or {}).get("categoria")
        if not d["verificado"] and alt and alt in info:
            d2 = dictaminar(e, alt, info[alt], wd.get(e["id"]), previo)
            if d2["verificado"]:
                d2["motivos"].insert(0, f"«{cand}» descartada: " + "; ".join(d["motivos"]))
                d = d2

        vieja = antes.get(e["id"], {})
        nota_humana = (vieja.get("nota") or "").strip()
        if nota_humana in NOTAS_GENERICAS:
            nota_humana = ""
        nota = "; ".join(d["motivos"]) or ("Comprobada, sin incidencias" if d["verificado"] else "")
        if nota_humana:
            nota = f"{nota_humana}. {nota}" if nota else nota_humana

        if vieja.get("categoriaCommons") and vieja["categoriaCommons"] != d["final"]:
            resumen["cambiadas"] += 1
        resumen["verificadas" if d["verificado"] else "pendientes"] += 1

        entradas.append({
            "id": e["id"],
            "vigente": d["vigente"],
            "enPdfSeo": vieja.get("enPdfSeo") or e["cientifico"],
            "categoriaCommons": d["final"],
            "commonsVerificado": d["verificado"],
            "archivos": d["archivos"],
            "subcategorias": d["subcats"],
            "comprobado": date.today().isoformat(),
            "nota": nota,
        })

    # Si se usó --solo, conservar las entradas no tocadas.
    if args.solo:
        tocados = {x["id"] for x in entradas}
        entradas = sorted([*(v for k, v in antes.items() if k not in tocados), *entradas],
                          key=lambda x: x["id"])

    n_ok = sum(1 for x in entradas if x["commonsVerificado"])
    payload = {
        "version": date.today().isoformat(),
        "nota": (f"{n_ok} de {len(entradas)} categorías verificadas contra la API de "
                 f"Wikimedia Commons el {date.today():%d/%m/%Y} con "
                 f"herramientas/verificar-commons.py. Verificado significa: la "
                 f"categoría existe, no es una redirección y tiene contenido. No "
                 f"significa que las fotos de dentro estén bien identificadas."),
        "entradas": entradas,
    }

    for x in entradas:
        marca = "ok  " if x["commonsVerificado"] else "PDTE"
        arch = f"{x['archivos']:>5}" if x["archivos"] is not None else "    –"
        print(f"{marca} {arch}  {x['id']:<28} {x['categoriaCommons']}"
              + (f"   · {x['nota']}" if x["nota"] else ""))
    print(f"\n{resumen['verificadas']} verificadas · {resumen['pendientes']} pendientes"
          f" · {resumen['cambiadas']} categorías cambiadas", file=sys.stderr)

    if args.informe:
        Path(args.informe).write_text(_informe(payload), encoding="utf-8")
        print(f"[ok] informe en {args.informe}", file=sys.stderr)

    if args.dry_run:
        print("[dry-run] no se ha escrito nada", file=sys.stderr)
        return 0
    escribir_atomico(f_sin, payload)
    print(f"[ok] escrito {f_sin}", file=sys.stderr)
    return 0


def _informe(payload: dict) -> str:
    filas = ["| Especie | Categoría | Estado | Archivos | Nota |",
             "| --- | --- | --- | ---: | --- |"]
    for x in payload["entradas"]:
        filas.append(f"| `{x['id']}` | {x['categoriaCommons']} | "
                     f"{'verificada' if x['commonsVerificado'] else 'pendiente'} | "
                     f"{x['archivos'] if x['archivos'] is not None else '—'} | "
                     f"{x['nota'] or ''} |")
    return ("# Verificación de categorías de Wikimedia Commons\n\n"
            + payload["nota"] + "\n\n" + "\n".join(filas) + "\n")


def _fallo(msg: str) -> int:
    print(f"[FALLO] {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
