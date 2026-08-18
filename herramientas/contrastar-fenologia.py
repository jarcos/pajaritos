#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Contrasta la matriz mensual de especies.json con los barcharts de eBird de los
hotspots del Odiel y propone (o escribe) la fenología corregida.

QUÉ PROBLEMA RESUELVE
23 de las 60 especies llevan `"confianza": "verificado"` porque su matriz está
transcrita del plan de la guía. Las otras 37 entraron como `"estimado"` con
presencia genérica —doce meses a 1, que no dice nada— y la ficha lo confiesa
pintándolas al 55 % con filete punteado. Esto convierte esas 37 en datos.

DE DÓNDE SALEN LOS DATOS
Del fichero que baja el botón «Download Histogram Data» de un barchart de
eBird. El endpoint que alimenta el gráfico dejó de ser público: pedirlo por
programa devuelve la pantalla de acceso del Cornell Lab. El TSV descargado a
mano es el mismo dato y no obliga a nadie a dar sus credenciales a un script.

    ebird.org → Explore → hotspot → Bar Charts → Download Histogram Data

Cada fichero trae, por especie, 48 columnas: cuatro «semanas» por mes con la
frecuencia (proporción de listas que incluyen esa especie), y una fila
«Sample Size:» con cuántas listas hay detrás de cada semana. Esa fila es
imprescindible: una frecuencia del 100 % sobre dos listas de junio no es una
máxima, es ruido.

CÓMO SE PASA DE FRECUENCIA A LOS CUATRO ESTADOS
La app pinta 0 ausente, 1 presente, 2 máxima, 3 cría. La conversión es
deliberadamente conservadora:

  · Se agregan los hotspots ponderando por número de listas, no promediando
    frecuencias: si Calatilla tiene 400 listas en marzo y Bacuta 12, marzo no
    puede decidirse a medias entre los dos.
  · Los meses con menos de MIN_LISTAS listas no se tocan: se conserva lo que
    hubiera y se anota. Sin esfuerzo no hay dato, y un cero por falta de
    observadores no es una ausencia.
  · 2 (máxima) si el mes llega al UMBRAL_MAXIMA de la frecuencia del mejor mes.
  · 0 (ausente) si no llega al UMBRAL_AUSENTE de esa misma frecuencia y además
    queda por debajo de PISO_AUSENTE en términos absolutos.
  · 1 (presente) el resto.
  · 3 (cría) NUNCA se deduce de aquí. Un barchart dice si el ave está, no si
    cría. Los 3 que ya hubiera en la matriz se respetan tal cual.

CUÁNDO SUBE A «VERIFICADO»
Solo si los doce meses tienen esfuerzo suficiente y la especie se detecta lo
bastante como para que el patrón signifique algo (ver `patron_solido`). Si no,
la matriz mejora pero la especie sigue marcada como estimada: es preferible
una matriz mejor con la etiqueta honesta que una etiqueta bonita sin respaldo.

Las 23 ya verificadas NO se tocan, pero sí se comparan: las discrepancias
salen en el informe. Si el barchart contradice al plan en una especie
transcrita a mano, eso es justo lo que hay que mirar con ojos humanos.

Uso:
    contrastar-fenologia.py --barcharts datos-ebird/        # informe, no escribe
    contrastar-fenologia.py --barcharts datos-ebird/ --escribir
    contrastar-fenologia.py --barcharts datos-ebird/ --informe fenologia.md

Sin dependencias: solo la biblioteca estándar.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

SEMANAS_MES = 4                 # el barchart parte cada mes en 4 columnas
MIN_LISTAS = 20                 # listas por mes por debajo de las cuales no se decide
UMBRAL_MAXIMA = 0.60            # ≥60 % de la frecuencia del mejor mes → máxima
UMBRAL_AUSENTE = 0.05           # <5 % de la del mejor mes → candidata a ausente
PISO_AUSENTE = 0.005            # …y además por debajo del 0,5 % de las listas
MIN_FREC_PICO = 0.01            # si ni en su mejor mes llega al 1 %, no hay patrón
LLANO = 0.75                    # si el peor mes ya llega al 75 % del mejor, no hay
                                # estación que marcar: es residente y se pinta
                                # presente los doce meses. Doce «máximas» seguidas
                                # ocupan el mismo sitio y no dicen nada.
CRIA = 3

# El barchart nombra en inglés: «Eurasian Spoonbill», «Dunlin». especies.json
# trae el campo `ingles`, que es la clave de unión. Estas son las diferencias
# de nomenclatura que no resuelve una comparación literal.
ALIAS = {
    # especies.json usa nomenclatura IOC/británica; eBird usa la de Clements.
    # Donde difieren hay que decirlo, porque una unión literal falla en
    # silencio y la especie se quedaría sin contrastar sin que se note.
    "red throated diver": ["red throated loon", "red throated diver"],
    "grey heron": ["gray heron", "grey heron"],
    "grey plover": ["black bellied plover", "grey plover"],
    "common moorhen": ["eurasian moorhen", "common moorhen"],
    "western barn owl": ["barn owl", "western barn owl"],
    "common house martin": ["common house martin"],
    "common blackbird": ["eurasian blackbird", "common blackbird"],
    "common scoter": ["common scoter", "black scoter"],
    "western yellow wagtail": ["western yellow wagtail", "yellow wagtail"],
    "leachs storm petrel": ["leachs storm petrel"],
    "european stonechat": ["european stonechat", "stonechat"],
    "eurasian spoonbill": ["eurasian spoonbill", "spoonbill"],
    "european robin": ["european robin", "robin"],
    "european goldfinch": ["european goldfinch", "goldfinch"],
    "audouins gull": ["audouins gull"],
}


class FuenteRota(RuntimeError):
    """El TSV no tiene la forma esperada. Nunca escribir en este caso."""


def normalizar(s: str) -> str:
    """Minúsculas sin acentos y sin las coletillas de subespecie o grupo.

    eBird escribe «Yellow Wagtail (Western)» o «Dunlin (hudsonia)». Para unir
    con especies.json sobra todo lo que va entre paréntesis. Las filas de
    taxones sin identificar («gull sp.», «Larus x») se descartan aparte.
    """
    s = re.sub(r"\([^)]*\)", " ", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.replace("\u2019", "").replace("'", "")     # Audouin's / Leach's
    return re.sub(r"[\s-]+", " ", s).strip().lower()


def leer_barchart(ruta: Path) -> tuple[list[float], dict[str, list[float]]]:
    """Devuelve (listas por semana, {especie normalizada: frecuencia semanal}).

    El fichero trae una cabecera de varias líneas antes de los datos, así que
    en vez de contar líneas se busca la primera fila cuyo nombre sea «Sample
    Size:» y, a partir de ahí, cualquier fila con 48 números.
    """
    filas = [l.rstrip("\n").split("\t")
             for l in ruta.read_text(encoding="utf-8", errors="replace").splitlines()]
    listas: list[float] | None = None
    taxa: dict[str, list[float]] = {}

    for f in filas:
        if not f or not f[0].strip():
            continue
        nombre = f[0].strip()
        try:
            nums = [float(x) for x in f[1:1 + 12 * SEMANAS_MES] if x.strip() != ""]
        except ValueError:
            continue
        if len(nums) != 12 * SEMANAS_MES:
            continue
        if nombre.lower().startswith("sample size"):
            listas = nums
        elif not re.search(r"\bsp\.$|\bx\b|/", nombre):     # fuera híbridos y «sp.»
            taxa[normalizar(nombre)] = nums

    if listas is None:
        raise FuenteRota(f"{ruta.name}: no encuentro la fila «Sample Size:»")
    if not taxa:
        raise FuenteRota(f"{ruta.name}: ninguna fila de especie con 48 columnas")
    return listas, taxa


def agregar(barcharts: list[tuple[list[float], dict[str, list[float]]]]
            ) -> tuple[list[float], dict[str, list[float]]]:
    """Funde varios hotspots ponderando por listas, semana a semana.

    Ponderar importa: una frecuencia del 80 % sobre 5 listas no puede pesar lo
    mismo que un 20 % sobre 500. Se reconstruye el número de listas con la
    especie (frecuencia × listas), se suman, y se divide por el total.
    """
    n = 12 * SEMANAS_MES
    listas_tot = [0.0] * n
    con_especie: dict[str, list[float]] = {}
    for listas, taxa in barcharts:
        for i in range(n):
            listas_tot[i] += listas[i]
        for nombre, frec in taxa.items():
            acum = con_especie.setdefault(nombre, [0.0] * n)
            for i in range(n):
                acum[i] += frec[i] * listas[i]
    frecuencias = {nombre: [(a / listas_tot[i] if listas_tot[i] else 0.0)
                            for i, a in enumerate(acum)]
                   for nombre, acum in con_especie.items()}
    return listas_tot, frecuencias


def por_mes(semanal: list[float], listas: list[float]) -> list[float]:
    """Media mensual ponderada por listas: 12 valores a partir de 48."""
    fuera = []
    for m in range(12):
        tr = slice(m * SEMANAS_MES, (m + 1) * SEMANAS_MES)
        peso = sum(listas[tr])
        fuera.append(sum(f * l for f, l in zip(semanal[tr], listas[tr])) / peso if peso else 0.0)
    return fuera


def listas_por_mes(listas: list[float]) -> list[float]:
    return [sum(listas[m * SEMANAS_MES:(m + 1) * SEMANAS_MES]) for m in range(12)]


def a_estados(frec: list[float], esfuerzo: list[float], previos: list[int]
              ) -> tuple[list[int], list[str]]:
    """Frecuencias mensuales → [0..3], conservando la cría y los meses sin datos."""
    pico = max(frec) if frec else 0.0
    medidos = [frec[m] for m in range(12) if esfuerzo[m] >= MIN_LISTAS]
    llano = bool(medidos) and pico > 0 and min(medidos) >= LLANO * pico
    estados, avisos = [], []
    if llano:
        avisos.append("presente todo el año sin estación marcada: "
                      f"el peor mes llega al {min(medidos) / pico:.0%} del mejor")
    for m in range(12):
        if previos[m] == CRIA:                       # la cría no sale de un barchart
            estados.append(CRIA)
            continue
        if esfuerzo[m] < MIN_LISTAS:
            estados.append(previos[m])
            avisos.append(f"mes {m + 1}: solo {esfuerzo[m]:.0f} listas, se conserva lo anterior")
            continue
        f = frec[m]
        if llano:
            estados.append(1)
        elif pico and f >= UMBRAL_MAXIMA * pico:
            estados.append(2)
        elif f < UMBRAL_AUSENTE * pico and f < PISO_AUSENTE:
            estados.append(0)
        else:
            estados.append(1)
    return estados, avisos


def patron_solido(frec: list[float], esfuerzo: list[float]) -> tuple[bool, str]:
    """¿Da el barchart para marcar la especie como verificada?"""
    flojos = [m + 1 for m in range(12) if esfuerzo[m] < MIN_LISTAS]
    if flojos:
        return False, f"meses con menos de {MIN_LISTAS} listas: {flojos}"
    if max(frec) < MIN_FREC_PICO:
        return False, (f"ni en su mejor mes pasa del {MIN_FREC_PICO:.0%} de las listas "
                       f"(máx {max(frec):.2%}): muestra insuficiente")
    return True, ""


def buscar(nombre_ingles: str, frecuencias: dict[str, list[float]]) -> str | None:
    clave = normalizar(nombre_ingles)
    for cand in ALIAS.get(clave, [clave]):
        if cand in frecuencias:
            return cand
    # Último intento: alguna fila que empiece por el nombre (subespecies).
    for k in frecuencias:
        if k.startswith(clave):
            return k
    return None


def escribir_atomico(destino: Path, payload: dict) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=".especies-", suffix=".tmp")
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


MESES = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]


def pinta(estados: list[int]) -> str:
    return "".join(" ·▓█"[e] for e in estados)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--barcharts", required=True, metavar="DIR",
                    help="carpeta con los .txt/.tsv descargados de eBird")
    ap.add_argument("--datos", default=None, help="carpeta app/datos")
    ap.add_argument("--escribir", action="store_true", help="actualiza especies.json")
    ap.add_argument("--informe", metavar="FICHERO.md")
    args = ap.parse_args()

    raiz = Path(__file__).resolve().parent.parent
    datos = Path(args.datos) if args.datos else raiz / "app" / "datos"
    f_esp = datos / "especies.json"
    if not f_esp.exists():
        return _fallo(f"no encuentro {f_esp}")

    dir_bc = Path(args.barcharts)
    ficheros = sorted([p for p in dir_bc.glob("*")
                       if p.suffix.lower() in (".txt", ".tsv", ".csv")])
    if not ficheros:
        return _fallo(f"no hay ficheros de barchart en {dir_bc}/ "
                      f"(baja el TSV con «Download Histogram Data» en eBird)")

    cargados = []
    for p in ficheros:
        try:
            cargados.append(leer_barchart(p))
            print(f"[ok] {p.name}: {sum(cargados[-1][0]):.0f} listas · "
                  f"{len(cargados[-1][1])} taxones", file=sys.stderr)
        except FuenteRota as e:
            return _fallo(str(e))

    listas, frecuencias = agregar(cargados)
    esfuerzo = listas_por_mes(listas)
    print(f"[ok] agregado: {sum(esfuerzo):.0f} listas · "
          f"mes más flojo {min(esfuerzo):.0f}, mejor {max(esfuerzo):.0f}", file=sys.stderr)

    doc = json.loads(f_esp.read_text(encoding="utf-8"))
    filas, cambios = [], {"subidas": 0, "matriz": 0, "sin_datos": 0, "discrepan": 0}

    for esp in doc["especies"]:
        clave = buscar(esp["ingles"], frecuencias)
        if clave is None:
            filas.append((esp, None, None, None, ["sin fila en el barchart"], False))
            cambios["sin_datos"] += 1
            continue
        frec = por_mes(frecuencias[clave], listas)
        nuevos, avisos = a_estados(frec, esfuerzo, esp["meses"])
        solido, porque = patron_solido(frec, esfuerzo)
        if porque:
            avisos.append(porque)

        ya = esp["confianza"] == "verificado"
        if ya:
            if nuevos != esp["meses"]:
                cambios["discrepan"] += 1
            filas.append((esp, frec, nuevos, clave, avisos, False))
            continue                                   # transcrita a mano: no se toca

        if nuevos != esp["meses"]:
            cambios["matriz"] += 1
        sube = solido
        if sube:
            cambios["subidas"] += 1
        filas.append((esp, frec, nuevos, clave, avisos, sube))
        if args.escribir:
            esp["meses"] = nuevos
            if sube:
                esp["confianza"] = "verificado"
                esp["fuenteFenologia"] = (
                    f"barcharts de eBird de {len(ficheros)} hotspots del Odiel, "
                    f"{sum(esfuerzo):.0f} listas, contrastado el {date.today():%d/%m/%Y}")

    for esp, frec, nuevos, clave, avisos, sube in filas:
        marca = "SUBE" if sube else ("—   " if nuevos else "????")
        antes = pinta(esp["meses"])
        ahora = pinta(nuevos) if nuevos else " " * 12
        print(f"{marca} {esp['id']:<28} {antes} → {ahora}"
              + (f"   · {'; '.join(avisos)}" if avisos else ""))

    print(f"\n{cambios['subidas']} suben a verificado · {cambios['matriz']} matrices "
          f"cambiadas · {cambios['sin_datos']} sin fila en el barchart · "
          f"{cambios['discrepan']} verificadas que el barchart contradice", file=sys.stderr)

    if args.informe:
        Path(args.informe).write_text(_informe(filas, esfuerzo, ficheros), encoding="utf-8")
        print(f"[ok] informe en {args.informe}", file=sys.stderr)

    if not args.escribir:
        print("[informe] no se ha escrito especies.json (usa --escribir)", file=sys.stderr)
        return 0
    doc["nota"] = (doc.get("nota", "") + " · Las estimadas se han contrastado con los "
                   f"barcharts de eBird del Odiel el {date.today():%d/%m/%Y} con "
                   "herramientas/contrastar-fenologia.py.")
    escribir_atomico(f_esp, doc)
    print(f"[ok] escrito {f_esp}", file=sys.stderr)
    return 0


def _informe(filas, esfuerzo, ficheros) -> str:
    out = ["# Fenología contrastada con los barcharts de eBird", "",
           f"Fuente: {', '.join(p.name for p in ficheros)}. "
           f"Listas por mes: {', '.join(f'{MESES[i]}{e:.0f}' for i, e in enumerate(esfuerzo))}.",
           "", "Estados: espacio ausente · `·` presente · `▓` máxima · `█` cría "
           "(la cría nunca se deduce del barchart).", "",
           "| Especie | Confianza | Antes | Después | Frecuencia máxima | Notas |",
           "| --- | --- | --- | --- | ---: | --- |"]
    for esp, frec, nuevos, clave, avisos, sube in filas:
        out.append(f"| {esp['nombre']} (`{esp['id']}`) | "
                   f"{'verificado' if sube else esp['confianza']}{' ↑' if sube else ''} | "
                   f"`{pinta(esp['meses'])}` | `{pinta(nuevos) if nuevos else '—'}` | "
                   f"{max(frec):.1%} | {'; '.join(avisos)} |" if frec else
                   f"| {esp['nombre']} (`{esp['id']}`) | {esp['confianza']} | "
                   f"`{pinta(esp['meses'])}` | — | — | {'; '.join(avisos)} |")
    return "\n".join(out) + "\n"


def _fallo(msg: str) -> int:
    print(f"[FALLO] {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
