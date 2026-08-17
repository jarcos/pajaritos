#!/usr/bin/env python3
"""
Lee los reportes. Se ejecuta EN EL NAS, nunca por HTTP: el sitio no tiene
ninguna ruta de lectura de reportes y no debe tenerla.

    docker compose exec api python /scripts/ver-reportes.py resumen

Usa el módulo sqlite3 de la biblioteca estándar en lugar del binario `sqlite3`,
que no está garantizado ni en la imagen alpine ni en DSM. Una dependencia menos
y un modo de fallo menos.

    ver-reportes.py                → pendientes de atender
    ver-reportes.py resumen        → recuento por tipo y por especie
    ver-reportes.py todos          → todo el histórico
    ver-reportes.py ver 7          → un reporte completo
    ver-reportes.py atender 7      → marcar como atendido
"""
from __future__ import annotations

import os
import sqlite3
import sys
import textwrap

DB = os.environ.get("REPORTES_DB", "/reportes/reportes.db")


def abrir(escritura: bool = False) -> sqlite3.Connection:
    uri = f"file:{DB}" + ("" if escritura else "?mode=ro")
    con = sqlite3.connect(uri, uri=True, timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    return con


def tabla(filas, cols: list[str]) -> None:
    """Tabla de texto alineada, sin dependencias."""
    if not filas:
        print("(nada)")
        return
    anchos = [max([len(c)] + [len(str(f[c])) for f in filas]) for c in cols]
    print("  ".join(c.ljust(a) for c, a in zip(cols, anchos)))
    print("  ".join("-" * a for a in anchos))
    for f in filas:
        print("  ".join(str(f[c]).ljust(a) for c, a in zip(cols, anchos)))
    print(f"\n{len(filas)} fila(s)")


def listar(solo_pendientes: bool) -> None:
    q = ("SELECT id, substr(recibido,1,16) AS recibido, tipo, especie, "
         "       substr(replace(mensaje, char(10), ' '),1,64) AS mensaje "
         "  FROM reportes")
    if solo_pendientes:
        q += " WHERE atendido = 0"
    q += " ORDER BY id"
    con = abrir()
    try:
        tabla(con.execute(q).fetchall(), ["id", "recibido", "tipo", "especie", "mensaje"])
    finally:
        con.close()


def resumen() -> None:
    con = abrir()
    try:
        print("-- por tipo --")
        tabla(con.execute(
            "SELECT tipo, count(*) AS total, sum(atendido = 0) AS pendientes "
            "  FROM reportes GROUP BY tipo ORDER BY total DESC").fetchall(),
            ["tipo", "total", "pendientes"])
        print("\n-- especies mas reportadas --")
        tabla(con.execute(
            "SELECT especie, count(*) AS total FROM reportes "
            " WHERE especie <> '' GROUP BY especie ORDER BY total DESC LIMIT 15").fetchall(),
            ["especie", "total"])
    finally:
        con.close()


def ver(rid: int) -> None:
    con = abrir()
    try:
        f = con.execute("SELECT * FROM reportes WHERE id = ?", (rid,)).fetchone()
    finally:
        con.close()
    if not f:
        sys.exit(f"no existe el reporte {rid}")
    for k in f.keys():
        if k == "mensaje":
            print(f"{k:14s} |")
            print(textwrap.indent(textwrap.fill(f[k], 74), " " * 17))
        else:
            print(f"{k:14s} | {f[k]}")


def atender(rid: int) -> None:
    con = abrir(escritura=True)
    try:
        cur = con.execute("UPDATE reportes SET atendido = 1 WHERE id = ?", (rid,))
        n = cur.rowcount
    finally:
        con.close()
    print(f"reporte {rid} marcado como atendido" if n else f"no existe el reporte {rid}")


def main() -> None:
    accion = sys.argv[1] if len(sys.argv) > 1 else "pendientes"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if accion == "pendientes":
        listar(True)
    elif accion == "todos":
        listar(False)
    elif accion == "resumen":
        resumen()
    elif accion in ("ver", "atender"):
        if not (arg and arg.isdigit()):
            sys.exit(f"uso: ver-reportes.py {accion} <id>")
        (ver if accion == "ver" else atender)(int(arg))
    else:
        sys.exit("uso: ver-reportes.py [pendientes|todos|resumen|ver <id>|atender <id>]")


if __name__ == "__main__":
    main()
