#!/usr/bin/env python3
"""
Endpoint de reportes de pajaritos.josearcos.me — la ÚNICA superficie de
escritura de todo el sitio.

Almacenamiento: SQLite (módulo `sqlite3` de la biblioteca estándar).
Frente al JSONL anterior gana tres cosas concretas:

  · Atomicidad real. El append a un fichero de texto desde varios hilos
    funciona "porque el volumen es trivial", no porque sea riguroso. Una
    transacción no deja lugar a dudas.
  · Consultable. `scripts/ver-reportes.sh` responde "¿cuántos reportes de
    fenología llevo y de qué especies" sin escribir un parser.
  · Un solo fichero para Hyper Backup, con instantánea consistente vía
    VACUUM INTO (ver scripts/snapshot-reportes.sh).

Y no añade NADA: sqlite3 viene en la stdlib, así que no hay dependencia nueva,
ni contenedor nuevo, ni RAM reservada. Descartado Mongo justamente por eso.

Nota sobre el hallazgo C2 de la auditoría ("app-layer auth required, even
behind Cloudflare Access"): esta app es pública por diseño y no tiene cuentas,
así que no hay nada que autenticar. La forma de la mitigación cambia: en lugar
de autenticar, se hace que el servidor sea incapaz de hacer daño.

  · Una sola ruta acepta POST. Todo lo demás es 404 o 405.
  · Solo INSERT. No hay ruta de lectura, ni de borrado, ni de consulta.
  · La base de datos vive en un volumen que nginx NO monta: es físicamente
    imposible servirla por HTTP, no depende de acertar con la config.
  · Nada de lo recibido se sirve de vuelta ni se ejecuta. Consultas
    parametrizadas siempre.
  · No se almacena la IP de nadie: coherente con que el servidor no sepa
    quién eres.
  · Rate limit en nginx y en el borde de Cloudflare, no aquí.
"""
from __future__ import annotations

import json
import os
import ssl
import smtplib
import re
from email.message import EmailMessage
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
DB = Path(os.environ.get("REPORTES_DB", "/reportes/reportes.db"))
MAX_BODY = int(os.environ.get("MAX_BODY_BYTES", "8192"))
HONEYPOT = os.environ.get("HONEYPOT_FIELD", "telefono")
MIN_FILL = int(os.environ.get("MIN_FILL_SECONDS", "3"))

TIPOS = {"fenologia", "identificacion", "foto", "zona", "error"}
ID_RE = re.compile(r"^[a-z0-9-]{1,60}$")
LIMITES = {"mensaje": 2000, "contacto": 120, "especie": 60, "pantalla": 40, "zonaActiva": 40}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS reportes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    recibido       TEXT    NOT NULL,
    tipo           TEXT    NOT NULL,
    especie        TEXT    NOT NULL DEFAULT '',
    mensaje        TEXT    NOT NULL,
    contacto       TEXT    NOT NULL DEFAULT '',
    version_datos  TEXT    NOT NULL DEFAULT '',
    pantalla       TEXT    NOT NULL DEFAULT '',
    zona_activa    TEXT    NOT NULL DEFAULT '',
    atendido       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reportes_recibido ON reportes(recibido);
"""


def log(nivel: str, msg: str, **extra) -> None:
    """Una línea JSON por evento a stdout. El driver `db` de Synology no deja
    ficheros de log en disco, así que esto sale por logspout → tcplog."""
    payload = {"ts": datetime.now(timezone.utc).isoformat(), "nivel": nivel,
               "servicio": "pajaritos-api", "msg": msg, **extra}
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def conectar() -> sqlite3.Connection:
    """Una conexión por petición. A este volumen abrir una conexión cuesta
    microsegundos, y así se evita de raíz toda la clase de errores de
    compartir una conexión entre hilos del ThreadingHTTPServer."""
    con = sqlite3.connect(DB, timeout=5.0, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL")      # lectores no bloquean al escritor
    con.execute("PRAGMA synchronous=FULL")      # el dato importa más que la latencia
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def inicializar() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    with closing(conectar()) as con:
        con.executescript(ESQUEMA)
    log("info", "esquema listo", db=str(DB))


def limpiar(valor, maximo: int) -> str:
    """Texto plano acotado, sin caracteres de control. No se escapa HTML aquí:
    esto no se renderiza nunca, y escapar dos veces ensucia el dato."""
    if not isinstance(valor, str):
        return ""
    valor = "".join(c for c in valor if c in "\n\t" or ord(c) >= 32)
    return valor.strip()[:maximo]


def validar(cuerpo: dict) -> tuple[dict | None, str]:
    if cuerpo.get(HONEYPOT):
        return None, "honeypot"                     # bot: se descarta en silencio

    abierto = cuerpo.get("abiertoEn")
    if isinstance(abierto, (int, float)):
        if time.time() - abierto / 1000 < MIN_FILL:
            return None, "demasiado-rapido"

    tipo = cuerpo.get("tipo")
    if tipo not in TIPOS:
        return None, "tipo-invalido"

    especie = limpiar(cuerpo.get("especie"), LIMITES["especie"])
    if especie and not ID_RE.match(especie):
        return None, "especie-invalida"

    mensaje = limpiar(cuerpo.get("mensaje"), LIMITES["mensaje"])
    if len(mensaje) < 10:
        return None, "mensaje-corto"

    ctx = cuerpo.get("contexto") or {}
    return {
        "recibido": datetime.now(TZ).isoformat(timespec="seconds"),
        "tipo": tipo,
        "especie": especie,
        "mensaje": mensaje,
        "contacto": limpiar(cuerpo.get("contacto"), LIMITES["contacto"]),
        "version_datos": limpiar(ctx.get("versionDatos"), 20),
        "pantalla": limpiar(ctx.get("pantalla"), LIMITES["pantalla"]),
        "zona_activa": limpiar(ctx.get("zonaActiva"), LIMITES["zonaActiva"]),
    }, ""


def guardar(r: dict) -> int:
    """INSERT parametrizado. Es la única sentencia de escritura del proyecto."""
    with closing(conectar()) as con:
        cur = con.execute(
            "INSERT INTO reportes "
            "(recibido, tipo, especie, mensaje, contacto, version_datos, pantalla, zona_activa) "
            "VALUES (:recibido, :tipo, :especie, :mensaje, :contacto, "
            ":version_datos, :pantalla, :zona_activa)",
            r,
        )
        return int(cur.lastrowid)


def avisar(r: dict, rid: int) -> None:
    """Aviso por SMTP. Si falla, el reporte YA está en la base de datos: el
    correo es una comodidad, no el almacenamiento.

    POR QUÉ SMTP Y NO LA API DE MAILGUN. La primera versión usaba la API HTTP
    con MAILGUN_API_KEY. Al ir a configurarla apareció que Mailgun solo enseña
    el secreto de una clave en el momento de crearla —el panel guarda el Key
    ID, no el valor— y la cuenta ya tenía sus dos claves gastadas, una de
    ellas en uso. Las credenciales SMTP, en cambio, ya estaban funcionando en
    biblioHack y en monitoring, así que esto no añade ningún secreto nuevo al
    inventario: reutiliza el que ya se mantiene y se rota.

    Se aceptan los dos juegos de nombres que hay en la casa: SMTP_USER/
    SMTP_PASS (monitoring) y SMTP_USERNAME/SMTP_PASSWORD (biblioHack).
    """
    servidor = os.environ.get("SMTP_HOST")
    usuario = os.environ.get("SMTP_USER") or os.environ.get("SMTP_USERNAME")
    clave = os.environ.get("SMTP_PASS") or os.environ.get("SMTP_PASSWORD")
    destino = os.environ.get("ALERT_EMAIL")
    if not (servidor and usuario and clave and destino):
        log("info", "aviso omitido: SMTP sin configurar")
        return
    puerto = int(os.environ.get("SMTP_PORT", "587"))
    remite = os.environ.get("SMTP_FROM", usuario)

    msg = EmailMessage()
    msg["From"] = f"pajaritos <{remite}>"
    msg["To"] = destino
    msg["Subject"] = f"[pajaritos] reporte #{rid}: {r['tipo']} · {r['especie'] or 'general'}"
    msg.set_content(json.dumps(r, ensure_ascii=False, indent=1))

    try:
        # Timeout corto a propósito: esto corre dentro de la petición del
        # usuario y el reporte ya está guardado. Más vale un correo perdido
        # que dejar colgada la respuesta de quien está en el campo.
        with smtplib.SMTP(servidor, puerto, timeout=10) as s:
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
            s.ehlo()
            s.login(usuario, clave)
            s.send_message(msg)
        log("info", "aviso enviado", id=rid, destino=destino)
    except Exception as e:                          # noqa: BLE001
        log("warn", "aviso falló", error=f"{type(e).__name__}: {e}", id=rid)


class Handler(BaseHTTPRequestHandler):
    server_version = "pajaritos"
    sys_version = ""

    def _json(self, code: int, payload: dict) -> None:
        cuerpo = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        # Ni siquiera hay una ruta de lectura de reportes. /healthz y nada más.
        if self.path == "/healthz":
            try:
                with closing(conectar()) as con:
                    con.execute("SELECT 1").fetchone()
                self._json(200, {"ok": True, "db": "ok"})
            except Exception as e:                   # noqa: BLE001
                log("error", "healthz: db inaccesible", error=f"{type(e).__name__}: {e}")
                self._json(503, {"ok": False, "db": "error"})
        else:
            self._json(404, {"error": "no existe"})

    def do_POST(self):
        if self.path != "/reporte":
            self._json(404, {"error": "no existe"})
            return

        try:
            largo = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._json(400, {"error": "longitud invalida"})
            return
        if largo <= 0 or largo > MAX_BODY:
            self._json(413, {"error": "cuerpo fuera de limites"})
            return

        try:
            cuerpo = json.loads(self.rfile.read(largo).decode("utf-8"))
            if not isinstance(cuerpo, dict):
                raise ValueError("se esperaba un objeto")
        except Exception:                            # noqa: BLE001
            self._json(400, {"error": "json invalido"})
            return

        reporte, motivo = validar(cuerpo)
        if reporte is None:
            # 200 también en los descartes: no se le dice a un bot por qué falló.
            log("info", "descartado", motivo=motivo,
                ip=self.headers.get("CF-Connecting-IP", "?"))   # se registra, no se guarda
            self._json(200, {"ok": True})
            return

        try:
            rid = guardar(reporte)
        except Exception as e:                       # noqa: BLE001
            log("error", "no se pudo guardar", error=f"{type(e).__name__}: {e}")
            self._json(500, {"error": "no se pudo guardar"})
            return

        log("info", "reporte guardado", id=rid, tipo=reporte["tipo"],
            especie=reporte["especie"])
        avisar(reporte, rid)
        self._json(201, {"ok": True})

    def log_message(self, fmt, *args):
        log("debug", "http", linea=fmt % args)


if __name__ == "__main__":
    log("info", "arrancando", db=str(DB), maxBody=MAX_BODY)
    inicializar()
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
