#!/usr/bin/env python3
"""
Descarga las mareas de Puertos del Estado y publica mareas.json.

FUENTE: la API JSON de PORTUS, la misma que consume su propia web.

    https://poem.puertos.es/portus/Foreman/Data
        ?code=<estacion>&from=YYYYMMDD@HHMM&to=YYYYMMDD@HHMM&mode=ext

Estación por defecto: 3329 = Mareógrafo de Huelva 5.
`mode=ext` devuelve los extremos (pleamares y bajamares). Respuesta:

    [{"date": 1786609200, "data": 0.5511, "hL": 1}, ...]
      date → epoch UTC en segundos     hL → 0 pleamar, 1 bajamar
      data → altura en metros sobre el Cero del Puerto

CÓMO SE LLEGÓ AQUÍ (para que nadie repita el error):
La primera versión raspaba el HTML de portus.puertos.es/PortusData/tablasMareas.
Funcionaba al leerlo con un navegador, pero al ejecutarlo de verdad devolvía
2 KB: esa página es un shell de JavaScript y la tabla se monta en cliente. El
endpoint de arriba es el que llama su propio `tablasMareas.js`, y es JSON puro.
Menos código, sin regex sobre maquetación y muchísimo menos frágil.

DOS COSAS QUE IMPORTAN Y QUE SON FÁCILES DE EQUIVOCAR:

 1. LAS HORAS SON UTC. En verano España va en GMT+2. Sin convertir, la app
    mandaría al observador dos horas antes de la bajamar real: llegaría con el
    fango cubierto y sin limícolas. Se convierte con zoneinfo, no con un
    desplazamiento fijo, para que los cambios de hora no lo rompan.

 2. HAY QUE AGRUPAR POR FECHA LOCAL, NO UTC. Una bajamar a las 22:42 UTC del
    día 8 es 00:42 del día 9 en hora local. Agrupando por UTC, la pantalla de
    «hoy» mostraría una marea que pertenece a mañana.

Este script VALIDA antes de escribir y sale con código != 0 sin tocar nada si
algo no cuadra, en lugar de publicar mareas corruptas en silencio.

Uso:
    fetch_mareas.py               # descarga y escribe
    fetch_mareas.py --dry-run     # descarga, valida e imprime, sin escribir
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://poem.puertos.es/portus/Foreman/Data"
PAGINA = "https://portus.puertos.es/PortusData/tablasMareas"
TZ_LOCAL = ZoneInfo("Europe/Madrid")
UA = "pajaritos.josearcos.me/1.0 (guia de observacion de aves; contacto: {})"

# ── Límites de cordura. Si la fuente cambia, esto es lo que lo delata. ──
MIN_DIAS = 5
MAX_ALTURA_M = 6.0        # la carrera de marea en Huelva no llega a tanto
MIN_ALTURA_M = -1.0
EVENTOS_POR_DIA = (2, 5)  # semidiurna: normalmente 4, a veces 3


class FuenteRota(RuntimeError):
    """La fuente no tiene la forma esperada. Nunca escribir en este caso."""


def _pedir(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA.format(os.environ.get("ALERT_EMAIL", "n/a")),
        "Accept": "application/json, text/html",
        "Accept-Language": "es",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                raise FuenteRota(f"HTTP {r.status}")
            return r.read()
    except urllib.error.URLError as e:
        raise FuenteRota(f"red: {e}") from e


def descargar_extremos(codigo: str, desde: date, hasta: date) -> list[dict]:
    url = (f"{API}?code={codigo}"
           f"&from={desde:%Y%m%d}@0000&to={hasta:%Y%m%d}@0000&mode=ext")
    obj = json.loads(_pedir(url))
    if not isinstance(obj, list) or not obj:
        raise FuenteRota(f"se esperaba una lista no vacía, llegó {type(obj).__name__}")
    for e in obj:
        if not (isinstance(e, dict) and {"date", "data", "hL"} <= set(e)):
            raise FuenteRota(f"elemento con forma inesperada: {e!r}")
    return obj


def descargar_metadatos(codigo: str) -> dict:
    """Nombre y coordenadas de la estación, del `var details` de la página.
    Es un extra: si falla, no se aborta la descarga de mareas."""
    try:
        html = _pedir(f"{PAGINA}?code={codigo}&locale=es", timeout=15).decode("utf-8", "replace")
        m = re.search(r"var\s+details\s*=\s*(\{.*?\});", html, re.S)
        if not m:
            return {}
        d = json.loads(m.group(1))
        return {"nombre": d.get("name"), "lat": d.get("latitude"), "lon": d.get("longitude")}
    except Exception as e:                            # noqa: BLE001
        print(f"[aviso] metadatos de {codigo} no disponibles: {e}", file=sys.stderr)
        return {}


def agrupar_por_fecha_local(extremos: list[dict]) -> list[dict]:
    """Convierte epoch UTC → Europe/Madrid y agrupa por la fecha LOCAL, que es
    la que tiene en la cabeza quien va a salir al campo."""
    dias: dict[str, list[dict]] = {}
    for e in sorted(extremos, key=lambda x: x["date"]):
        utc = datetime.fromtimestamp(int(e["date"]), timezone.utc)
        loc = utc.astimezone(TZ_LOCAL)
        dias.setdefault(loc.date().isoformat(), []).append({
            "tipo": "pleamar" if int(e["hL"]) == 0 else "bajamar",
            "local": loc.strftime("%H:%M"),
            "utc": utc.strftime("%H:%M"),
            "altura": round(float(e["data"]), 2),
        })
    return [{"fecha": f, "eventos": dias[f]} for f in sorted(dias)]


def validar(dias: list[dict]) -> None:
    if len(dias) < MIN_DIAS:
        raise FuenteRota(f"solo {len(dias)} días, mínimo {MIN_DIAS}")
    for d in dias:
        n = len(d["eventos"])
        if not (EVENTOS_POR_DIA[0] <= n <= EVENTOS_POR_DIA[1]):
            raise FuenteRota(f"{d['fecha']}: {n} eventos, fuera de {EVENTOS_POR_DIA}")
        for ev in d["eventos"]:
            if not (MIN_ALTURA_M <= ev["altura"] <= MAX_ALTURA_M):
                raise FuenteRota(f"{d['fecha']} {ev['local']}: altura {ev['altura']} m absurda")
    tipos = {ev["tipo"] for d in dias for ev in d["eventos"]}
    if tipos != {"pleamar", "bajamar"}:
        raise FuenteRota(f"clasificación sospechosa, tipos: {tipos}")
    # Coherencia física: una pleamar debe ser más alta que las bajamares vecinas.
    plano = [ev for d in dias for ev in d["eventos"]]
    for a, b in zip(plano, plano[1:]):
        if a["tipo"] == b["tipo"]:
            raise FuenteRota(f"dos {a['tipo']} consecutivas en {a['local']}/{b['local']}")
        if a["tipo"] == "pleamar" and a["altura"] <= b["altura"]:
            raise FuenteRota(f"pleamar {a['altura']} m no supera a la bajamar {b['altura']} m")


def escribir_atomico(destino: Path, payload: dict) -> None:
    """temp + rename en el mismo volumen: nginx nunca ve un JSON a medias."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=".mareas-", suffix=".tmp")
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
    dry = "--dry-run" in sys.argv
    destino = Path(os.environ.get("MAREAS_PATH", "/datos/mareas.json"))
    horizonte = int(os.environ.get("DIAS_HORIZONTE", "30"))
    spec = os.environ.get("PORTUS_ESTACIONES", "huelva-5:3329")

    ahora = datetime.now(TZ_LOCAL)
    hoy = ahora.date()
    # Se pide un día de más por cada extremo para que el primero y el último
    # queden completos tras reagrupar por fecha local, y luego se recortan.
    desde, hasta = hoy - timedelta(days=1), hoy + timedelta(days=horizonte + 1)

    estaciones: dict[str, dict] = {}
    errores: list[str] = []

    for par in spec.split(","):
        slug, _, codigo = par.strip().partition(":")
        if not codigo:
            errores.append(f"{par}: formato esperado slug:codigo")
            continue
        try:
            dias = agrupar_por_fecha_local(descargar_extremos(codigo, desde, hasta))
            dias = [d for d in dias
                    if hoy <= date.fromisoformat(d["fecha"]) <= hoy + timedelta(days=horizonte)]
            validar(dias)
            estaciones[slug] = {"codigo": codigo, **descargar_metadatos(codigo), "dias": dias}
            nom = estaciones[slug].get("nombre") or codigo
            # Los mensajes van a stderr: así stdout queda limpio para el JSON
            # de --dry-run y se puede encadenar con jq sin filtrar nada.
            print(f"[ok] {slug} ({codigo}) · {nom} · {len(dias)} días",
                  file=sys.stderr, flush=True)
        except Exception as e:                        # noqa: BLE001
            errores.append(f"{slug} ({codigo}): {type(e).__name__}: {e}")
            print(f"[FALLO] {slug}: {e}", file=sys.stderr, flush=True)

    if not estaciones:
        # Sin nada válido se conserva el mareas.json anterior. Salir != 0 para
        # que cron avise; la app sigue sirviendo lo viejo y lo marca "stale".
        print("[FALLO] ninguna estación válida; no se sobrescribe nada",
              file=sys.stderr, flush=True)
        return 1

    payload = {
        "generado": ahora.isoformat(timespec="seconds"),
        "fuente": "Puertos del Estado · PORTUS · poem.puertos.es/portus/Foreman/Data (mode=ext)",
        "origenPredicciones": "Instituto Hidrográfico de la Marina",
        "datum": "Cero del Puerto",
        "zonaHoraria": "Europe/Madrid",
        "stale": False,
        "errores": errores,
        "estaciones": estaciones,
    }

    if dry:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0 if not errores else 1

    escribir_atomico(destino, payload)
    print(f"[ok] escrito {destino}", flush=True)
    return 0 if not errores else 1


if __name__ == "__main__":
    sys.exit(main())
