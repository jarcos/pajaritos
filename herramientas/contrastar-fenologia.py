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

Cada fichero trae, por taxón, 48 columnas: cuatro «semanas» por mes con la
frecuencia (proporción de listas que incluyen esa especie), y una fila
«Sample Size:» con cuántas listas hay detrás de cada semana. Esa fila es
imprescindible: una frecuencia del 100 % sobre dos listas de junio no es una
máxima, es ruido.

EL NOMBRE VIENE EN ESPAÑOL Y CON EL CIENTÍFICO DENTRO, así:

    Ánsar Común (<em class="sci">Anser anser</em>)\t0.0\t0.0\t…

Eso permite unir por taxón en vez de por nombre común, que es la parte que se
rompe sola: especies.json usa nomenclatura IOC y eBird la de Clements. Cuando
el científico tampoco coincide —Larus melanocephalus contra Ichthyaetus
melanocephalus— se prueba con los nombres que ya guarda sinonimos.json, que
para eso se verificaron contra Commons.

Se descartan los taxones que no son especie: híbridos (`Aythya ferina x
nyroca`), pares indistinguibles (`Apus apus/pallidus`) y agregados (`Limosa
sp.`, `Charadriidae sp.`). Las filas de subespecie sí cuentan: si no hay fila
a nivel de especie, se toma el máximo semana a semana entre ellas, que no
infla como haría sumarlas.

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

POR QUÉ NADA SUBE A «VERIFICADO»
Porque eBird y el plan de la guía no miden lo mismo, y al contrastarlos se vio
de golpe: el barchart contradice 21 de las 22 fenologías transcritas a mano, y
siempre en la misma dirección. Todas las limícolas se desplazan al paso
postnupcial. El correlimos común, que inverna por millares en el Odiel, sale
en la mitad de las listas de enero y en el 87 % de las de agosto.

Eso no mide cuántos hay: mide la probabilidad de que alguien lo apunte, que se
dispara cuando la gente va expresamente a mirar limícolas y hace listas
completas del fango. La «máxima» del plan es máxima ABUNDANCIA; la de eBird es
máxima DETECTABILIDAD. Para las limícolas se separan medio año.

Así que este script MEJORA la matriz —pasar de doce meses genéricos a un
patrón con listas detrás es una mejora real— pero no toca `confianza`: las
estimadas siguen estimadas, al 55 % de opacidad y con filete punteado. Se les
añade `fuenteFenologia` para que conste de dónde sale. Mezclar las dos bajo la
misma etiqueta sería exactamente el pecado que el principio 4 quiere evitar.

Solo se escribe la matriz si el patrón es sólido: doce meses con esfuerzo
suficiente y una frecuencia de pico que signifique algo (ver `patron_solido`).
Un alcatraz al 1,5 % o una lechuza al 0 % no dan para nada; esos se quedan
como estaban.

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
# UMBRALES, Y POR QUÉ NO SON RELATIVOS AL PICO A SECAS.
# La primera versión marcaba «máxima» cualquier mes que llegara al 60 % del
# mejor. Con Larus michahellis —residente que oscila entre el 41 % y el 73 %
# de las listas— eso daba diez máximas seguidas, que no es una fenología sino
# ruido con forma de dato. Ahora el listón se pone a medio camino entre la
# MEDIANA del año y el pico: así solo destaca lo que de verdad sobresale sobre
# el propio nivel de fondo de la especie.
UMBRAL_MAXIMA = 0.50            # a mitad de camino entre mediana y pico
SUELO_MAXIMA = 0.60             # y nunca por debajo del 60 % del pico
UMBRAL_AUSENTE = 0.10           # <10 % de la del mejor mes → candidata a ausente
PISO_AUSENTE = 0.02             # …y además por debajo del 2 % de las listas
MIN_FREC_PICO = 0.03            # si ni en su mejor mes llega al 3 %, no hay patrón
MAX_MESES_MAXIMA = 7            # más que esto no es una estación, es un residente
LLANO = 0.75                    # si el peor mes ya llega al 75 % del mejor, no hay
                                # estación que marcar: es residente y se pinta
                                # presente los doce meses. Doce «máximas» seguidas
                                # ocupan el mismo sitio y no dicen nada.

def suavizar(m: list[float]) -> list[float]:
    """Media móvil circular de tres meses.

    Con 34–97 listas al mes el error de muestreo son varios puntos, y sin
    suavizar aparecen dientes de sierra que se leen como estacionalidad. El
    año es circular: diciembre es vecino de enero.
    """
    return [(m[(i - 1) % 12] + m[i] + m[(i + 1) % 12]) / 3 for i in range(12)]
CRIA = 3

# El barchart nombra en inglés: «Eurasian Spoonbill», «Dunlin». especies.json
# trae el campo `ingles`, que es la clave de unión. Estas son las diferencias
# de nomenclatura que no resuelve una comparación literal.


class FuenteRota(RuntimeError):
    """El TSV no tiene la forma esperada. Nunca escribir en este caso."""


SCI = re.compile(r'<em class="sci">(.*?)</em>')


def comun(nombre_fila: str) -> str:
    """Nombre en español de la fila, sin el científico ni los acentos.

    Segunda vía de unión, y la que salva los cambios de género recientes: la
    ficha dice Charadrius alexandrinus y eBird ya dice Anarhynchus, pero los
    dos lo llaman chorlitejo patinegro.
    """
    base = SCI.sub("", nombre_fila).replace("(", " ").replace(")", " ")
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", base).strip().lower()


def taxon(nombre_fila: str) -> str | None:
    """Científico de una fila del barchart, o None si no es una especie.

    Descarta lo que no se puede contrastar: híbridos, pares indistinguibles y
    agregados de género o familia. Un `Limosa sp.` no dice nada de la aguja
    colinegra ni de la colipinta.
    """
    m = SCI.search(nombre_fila)
    if not m:
        return None
    t = re.sub(r"\s+", " ", m.group(1)).strip()
    if " x " in t or "/" in t or "sp." in t or t.endswith("dae") or t.endswith("mes"):
        return None
    return t


def clave(cientifico: str) -> str:
    """Género + especie en minúsculas: junta la especie con sus subespecies."""
    partes = cientifico.lower().split()
    return " ".join(partes[:2])


def leer_barchart(ruta: Path) -> tuple[list[float], dict[str, list[float]]]:
    """Devuelve (listas por semana, {género especie: frecuencia semanal}).

    La cabecera ocupa una docena de líneas, así que en vez de contarlas se
    busca la fila «Sample Size:» y, a partir de ahí, cualquier fila con 48
    números. Las filas traen 50 campos: nombre, 48 semanas y una columna vacía
    al final.
    """
    filas = [l.rstrip("\n").split("\t")
             for l in ruta.read_text(encoding="utf-8", errors="replace").splitlines()]
    listas: list[float] | None = None
    taxa: dict[str, list[float]] = {}
    descartados = 0
    por_comun: dict[str, str] = {}

    for f in filas:
        if not f or not f[0].strip():
            continue
        nombre = f[0].strip()
        try:
            nums = [float(x) for x in f[1:1 + 12 * SEMANAS_MES]]
        except ValueError:
            continue
        if len(nums) != 12 * SEMANAS_MES:
            continue
        if nombre.lower().startswith("sample size"):
            listas = nums
            continue
        t = taxon(nombre)
        if t is None:
            descartados += 1
            continue
        # Especie y subespecies comparten clave: máximo semana a semana. Sumar
        # las inflaría, porque una misma lista puede traer las dos filas.
        k = clave(t)
        por_comun.setdefault(comun(nombre), k)
        if k in taxa:
            taxa[k] = [max(a, b) for a, b in zip(taxa[k], nums)]
        else:
            taxa[k] = nums

    if listas is None:
        raise FuenteRota(f"{ruta.name}: no encuentro la fila «Sample Size:»")
    if not taxa:
        raise FuenteRota(f"{ruta.name}: ninguna fila de especie con 48 columnas")
    print(f"[ok] {ruta.name}: {len(taxa)} especies · {descartados} taxones "
          f"descartados (híbridos, pares y agregados)", file=sys.stderr)
    leer_barchart.comunes = {**getattr(leer_barchart, "comunes", {}), **por_comun}
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
    frec = suavizar(frec)
    pico = max(frec) if frec else 0.0
    ordenados = sorted(frec)
    mediana = (ordenados[5] + ordenados[6]) / 2
    corte = max(mediana + UMBRAL_MAXIMA * (pico - mediana), SUELO_MAXIMA * pico)
    if sum(1 for f in frec if f >= corte) > MAX_MESES_MAXIMA:
        corte = float("inf")          # sin estación destacable: ninguna máxima
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
        elif pico and f >= corte:
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


def buscar(esp: dict, sin: dict | None, frecuencias: dict[str, list[float]]) -> str | None:
    """Une la ficha con su fila del barchart por nombre científico.

    Se prueban, por este orden, el científico de la ficha y los nombres que
    sinonimos.json ya verificó: el vigente según Wikidata, el del PDF y el de
    la categoría de Commons. Es la cadena sinónimo→vigente que hace falta
    cuando eBird categoriza bajo Ichthyaetus lo que la ficha llama Larus.
    """
    candidatos = [esp["cientifico"]]
    if sin:
        candidatos += [sin.get("vigente"), sin.get("enPdfSeo"), sin.get("categoriaCommons")]
    for c in candidatos:
        if c and clave(c) in frecuencias:
            return clave(c)
    # Última vía: el nombre en español. Salva los cambios de género que ni la
    # ficha ni sinonimos.json han visto todavía.
    comunes = getattr(leer_barchart, "comunes", {})
    n = unicodedata.normalize("NFKD", esp["nombre"]).encode("ascii", "ignore").decode().lower()
    k = comunes.get(n)
    return k if k and k in frecuencias else None


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
    ap.add_argument("--extra", metavar="DIR",
                    help="fuente secundaria (p. ej. el barchart de la provincia) que "
                         "SOLO se usa para las especies sin fila en la principal")
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

    # Fuente secundaria: los tres hotspots del Odiel son marisma y laguna, así
    # que el negrón, el colimbo, la pardela, el paíño, el págalo y el alca no
    # salen en ninguno.
    #
    # OJO: sirve para SABER QUE ESTÁN, no para fechar cuándo. Se probó con el
    # barchart de la provincia (27 000 listas) y la fenología que sale no vale:
    # el denominador va lleno de listas de interior y marisma donde un ave
    # pelágica no puede aparecer, así que la frecuencia se diluye hasta el
    # ruido. El alca salía con pico en mayo y junio —un par de salidas
    # pelágicas -- cuando es invernante. Por eso lo que venga de aquí se
    # informa pero NUNCA se escribe. Para fecharlas hace falta un barchart de
    # un hotspot de seawatch, con denominador de gente mirando al mar.
    listas_x: list[float] | None = None
    frec_x: dict[str, list[float]] = {}
    if args.extra:
        f_x = sorted([q for q in Path(args.extra).glob("*")
                      if q.suffix.lower() in (".txt", ".tsv", ".csv")])
        if not f_x:
            return _fallo(f"--extra {args.extra}: no hay ficheros de barchart")
        try:
            listas_x, frec_x = agregar([leer_barchart(q) for q in f_x])
        except FuenteRota as e:
            return _fallo(str(e))
        print(f"[ok] secundaria: {sum(listas_x):.0f} listas · {len(frec_x)} especies",
              file=sys.stderr)
    esfuerzo = listas_por_mes(listas)
    print(f"[ok] agregado: {sum(esfuerzo):.0f} listas · "
          f"mes más flojo {min(esfuerzo):.0f}, mejor {max(esfuerzo):.0f}", file=sys.stderr)

    doc = json.loads(f_esp.read_text(encoding="utf-8"))
    f_sin = datos / "sinonimos.json"
    sinonimos = ({e["id"]: e for e in json.loads(f_sin.read_text(encoding="utf-8"))["entradas"]}
                 if f_sin.exists() else {})
    filas, cambios = [], {"subidas": 0, "matriz": 0, "sin_datos": 0, "discrepan": 0}

    for esp in doc["especies"]:
        antes = list(esp["meses"])
        fuente, l_uso, f_uso = "los hotspots del Odiel", listas, frecuencias
        clave_esp = buscar(esp, sinonimos.get(esp["id"]), frecuencias)
        if clave_esp is None and frec_x:
            clave_esp = buscar(esp, sinonimos.get(esp["id"]), frec_x)
            if clave_esp is not None:
                fuente, l_uso, f_uso = "el barchart de la provincia", listas_x, frec_x
                avisos_extra = True
        if clave_esp is None:
            filas.append((esp, antes, None, None, None, ["sin fila en el barchart"], False))
            cambios["sin_datos"] += 1
            continue
        esf_uso = listas_por_mes(l_uso)
        frec = por_mes(f_uso[clave_esp], l_uso)
        nuevos, avisos = a_estados(frec, esf_uso, esp["meses"])
        solido, porque = patron_solido(frec, esf_uso)
        if f_uso is not frecuencias:
            solido = False
            avisos.insert(0, "solo aparece en la fuente secundaria, cuyo denominador "
                             "incluye listas de interior: confirma que está, no cuándo. "
                             "Necesita un hotspot de seawatch")
        if porque:
            avisos.append(porque)

        ya = esp["confianza"] == "verificado"
        if ya:
            if nuevos != esp["meses"]:
                cambios["discrepan"] += 1
            filas.append((esp, antes, frec, nuevos, clave_esp, avisos, False))
            continue                                   # transcrita a mano: no se toca

        # `solido` ya no sube nada de categoría: decide si la matriz derivada
        # es lo bastante fiable como para sustituir a la genérica.
        if solido and nuevos != esp["meses"]:
            cambios["matriz"] += 1
        if solido:
            cambios["subidas"] += 1
        filas.append((esp, antes, frec, nuevos, clave_esp, avisos, solido))
        if args.escribir and solido:
            esp["meses"] = nuevos
            esp["fuenteFenologia"] = (
                f"eBird, {fuente}, {sum(listas_por_mes(l_uso)):.0f} listas, "
                f"contrastado el {date.today():%d/%m/%Y}. "
                f"Mide detectabilidad, no abundancia: sigue siendo estimación.")

    for esp, antes, frec, nuevos, clave, avisos, sube in filas:
        marca = "ESCR" if sube else ("—   " if nuevos else "????")
        pinta_antes = pinta(antes)
        ahora = pinta(nuevos) if nuevos else " " * 12
        print(f"{marca} {esp['id']:<28} {pinta_antes} → {ahora}"
              + (f"   · {'; '.join(avisos)}" if avisos else ""))

    print(f"\n{cambios['subidas']} con patrón sólido · {cambios['matriz']} matrices "
          f"cambiadas · {cambios['sin_datos']} sin fila en el barchart · "
          f"{cambios['discrepan']} verificadas que el barchart contradice", file=sys.stderr)

    if args.informe:
        Path(args.informe).write_text(_informe(filas, esfuerzo, ficheros), encoding="utf-8")
        print(f"[ok] informe en {args.informe}", file=sys.stderr)

    if not args.escribir:
        print("[informe] no se ha escrito especies.json (usa --escribir)", file=sys.stderr)
        return 0
    doc["nota"] = (doc.get("nota", "") + " · Las estimadas con patrón sólido llevan "
                   f"matriz derivada de los barcharts de eBird del Odiel ({date.today():%d/%m/%Y}, "
                   "herramientas/contrastar-fenologia.py). Siguen marcadas como estimadas a "
                   "propósito: el barchart mide detectabilidad y la matriz del plan, abundancia.")
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
    for esp, antes, frec, nuevos, clave, avisos, sube in filas:
        out.append(f"| {esp['nombre']} (`{esp['id']}`) | "
                   f"{esp['confianza']}{' · matriz nueva' if sube else ''} | "
                   f"`{pinta(antes)}` | `{pinta(nuevos) if nuevos else '—'}` | "
                   f"{max(frec):.1%} | {'; '.join(avisos)} |" if frec else
                   f"| {esp['nombre']} (`{esp['id']}`) | {esp['confianza']} | "
                   f"`{pinta(antes)}` | — | — | {'; '.join(avisos)} |")
    return "\n".join(out) + "\n"


def _fallo(msg: str) -> int:
    print(f"[FALLO] {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
