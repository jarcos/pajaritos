#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Incorpora a la app las fotos elegidas en un manifiesto (por ejemplo
herramientas/fotos-piloto.json): las baja de Commons, las guarda en app/fotos/
y declara cada una en especies.json con el autor y la licencia que exige el
criterio t39.1 (29-09-2026).

Qué hace y qué NO hace, por orden de importancia:

 · Solo declara «lista» una foto cuyo fichero está de verdad en app/fotos/.
   Declarar lista una foto que no se bajó sube a producción como un icono roto.
 · No elige fotos. La elección (identificación inequívoca, sin personas, sin
   fotos de museo ni de zoo) es humana y ya viene hecha en el manifiesto.
 · Pide a Commons la miniatura de --ancho píxeles en vez del original de 7 000:
   pesa unos 200 KB y no hace falta nada más para una ficha de móvil. Si hay
   Pillow instalado la pasa a WebP (~90 KB); si no, se queda en JPEG.
 · Reescribe especies.json byte a byte igual salvo las fotos, para que el diff
   de git diga qué foto entró y no «cambió todo».
 · El nombre del fichero lleva la huella de su contenido (avoceta-1a2b3c4d.webp):
   nginx sirve /fotos/ como inmutable un año, así que otra foto tiene que ser otra URL.
 · Es idempotente: si el fichero ya está en app/fotos/, no lo vuelve a bajar.
 · Escribe app/fotos/atribucion.csv, derivado de especies.json, como copia
   legible de quién es cada foto y con qué licencia.

Uso:
  herramientas/incorporar-fotos.py                       # baja y escribe
  herramientas/incorporar-fotos.py --simular             # solo dice qué haría
  herramientas/incorporar-fotos.py --manifiesto otro.json

Después: sh pruebas/puerta.sh (el validador comprueba que todo cuadra).
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Wikimedia pide un User-Agent que diga quién llama y cómo localizarlo. Sin
# él responde 403. (Sin correo a propósito: este repo es público.)
USER_AGENT = "pajaritos-odiel/1.0 (https://pajaritos.josearcos.me; guia de aves)"
ANCHO_POR_DEFECTO = 1280
PAUSA_ENTRE_DESCARGAS = 1.5      # segundos; Commons no es un CDN nuestro


# ── Piezas puras (lo que decide qué se baja y qué se escribe) ─────────────

def huella(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()[:8]


def nombre_local(especie_id: str, ext: str, huella_contenido: str) -> str:
    """El id de la especie más la huella del contenido. nginx sirve /fotos/
    como inmutable un año y el service worker es cache-first: una foto nueva
    con el nombre de la vieja no llegaría a nadie que ya tenga la vieja."""
    return f"{especie_id}-{huella_contenido}.{ext}"


def url_miniatura(archivo: str, ancho: int) -> str:
    nombre = urllib.parse.quote(archivo.replace(" ", "_"), safe="")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{nombre}?width={ancho}"


def entrada_foto(item: dict, archivo_local: str, revisada: str) -> dict:
    for campo in ("autor", "licencia", "paginaArchivo"):
        if not item.get(campo):
            raise ValueError(f"{item.get('archivo', '?')}: falta «{campo}»; "
                             f"sin atribución completa la foto no entra")
    return {
        "estado": "lista",
        "archivo": archivo_local,
        "autor": item["autor"],
        "licencia": item["licencia"],
        "licenciaUrl": item.get("licenciaUrl", ""),
        "paginaArchivo": item["paginaArchivo"],
        "origen": "commons",
        "archivoCommons": item["archivo"],
        "modificada": True,          # siempre se redimensiona
        "revisada": revisada,
    }


def aplicar(datos: dict, manifiesto: dict, archivos: dict, revisada: str) -> dict:
    """Devuelve una copia de `datos` con las fotos bajadas declaradas listas.

    `archivos` dice qué ids se bajaron de verdad y con qué nombre de fichero:
    lo que no está ahí no se toca, aunque esté en el manifiesto."""
    nuevo = copy.deepcopy(datos)
    por_id = {e["id"]: e for e in nuevo["especies"]}
    for eid, item in manifiesto.items():
        if eid not in por_id:
            raise KeyError(f"el manifiesto habla de «{eid}», que no está en especies.json")
        if eid not in archivos:
            continue
        por_id[eid]["foto"] = entrada_foto(item, archivos[eid], revisada)
    return nuevo


def serializar(datos: dict) -> str:
    """Mismo formato que tiene especies.json hoy: sangría de 1, UTF-8 sin
    escapar y sin salto de línea final."""
    return json.dumps(datos, ensure_ascii=False, indent=1)


def atribucion_csv(datos: dict) -> str:
    salida = io.StringIO()
    w = csv.writer(salida, lineterminator="\n")
    w.writerow(["especie", "nombre", "archivo", "autor", "licencia", "licenciaUrl",
                "paginaArchivo", "archivoCommons", "revisada"])
    for e in datos["especies"]:
        f = e.get("foto") or {}
        if f.get("estado") != "lista":
            continue
        w.writerow([e["id"], e.get("nombre", ""), f["archivo"], f["autor"], f["licencia"],
                    f.get("licenciaUrl", ""), f["paginaArchivo"], f.get("archivoCommons", ""),
                    f["revisada"]])
    return salida.getvalue()


# ── Lo que toca la red y el disco ─────────────────────────────────────────

def descargar(url: str, intentos: int = 4) -> bytes:
    for n in range(1, intentos + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and n < intentos:
                time.sleep(5 * n)           # Commons pide que se afloje el ritmo
                continue
            raise
    raise RuntimeError("inalcanzable")


def convertir(datos_imagen: bytes) -> tuple[bytes, str]:
    """Devuelve (bytes, extensión). WebP si hay Pillow, y si no, tal cual."""
    try:
        from PIL import Image                       # noqa: PLC0415
    except ImportError:
        return datos_imagen, "jpg"
    salida = io.BytesIO()
    with Image.open(io.BytesIO(datos_imagen)) as im:
        im.convert("RGB").save(salida, "WEBP", quality=80, method=6)
    return salida.getvalue(), "webp"


def main() -> int:
    raiz = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifiesto", default=str(raiz / "herramientas" / "fotos-piloto.json"))
    ap.add_argument("--especies", default=str(raiz / "app" / "datos" / "especies.json"))
    ap.add_argument("--fotos", default=str(raiz / "app" / "fotos"))
    ap.add_argument("--ancho", type=int, default=ANCHO_POR_DEFECTO)
    ap.add_argument("--simular", action="store_true", help="no baja ni escribe nada")
    a = ap.parse_args()

    man = json.loads(Path(a.manifiesto).read_text(encoding="utf-8"))
    revisada, items = man["revisada"], man["fotos"]
    ruta_esp = Path(a.especies)
    datos = json.loads(ruta_esp.read_text(encoding="utf-8"))
    carpeta = Path(a.fotos)

    archivos: dict[str, str] = {}
    for eid, item in items.items():
        ya = sorted(f.name for f in carpeta.glob(f"{eid}-*")
                    if re.fullmatch(rf"{re.escape(eid)}-[0-9a-f]{{8}}\.(webp|jpg)", f.name)) \
            if carpeta.is_dir() else []
        if ya:
            print(f"= {eid}: ya está ({ya[-1]})")
            archivos[eid] = ya[-1]
            continue
        url = url_miniatura(item["archivo"], a.ancho)
        if a.simular:
            print(f"· {eid}: bajaría {url}")
            continue
        carpeta.mkdir(parents=True, exist_ok=True)
        try:
            contenido, ext = convertir(descargar(url))
        except Exception as e:                      # noqa: BLE001
            print(f"[FALLO] {eid}: {e}", file=sys.stderr)
            continue
        nombre = nombre_local(eid, ext, huella(contenido))
        (carpeta / nombre).write_bytes(contenido)
        archivos[eid] = nombre
        print(f"+ {eid}: {nombre} ({len(contenido) // 1024} KB)")
        time.sleep(PAUSA_ENTRE_DESCARGAS)

    if a.simular:
        return 0
    nuevo = aplicar(datos, items, archivos, revisada)
    ruta_esp.write_text(serializar(nuevo), encoding="utf-8")
    (carpeta / "atribucion.csv").write_text(atribucion_csv(nuevo), encoding="utf-8")
    faltan = [e for e in items if e not in archivos]
    print(f"\n{len(archivos)} de {len(items)} fotos incorporadas"
          + (f"; sin bajar: {', '.join(faltan)} (vuelve a lanzarlo)" if faltan else ""))
    print("Siguiente paso: sh pruebas/puerta.sh")
    return 1 if faltan else 0


if __name__ == "__main__":
    sys.exit(main())
