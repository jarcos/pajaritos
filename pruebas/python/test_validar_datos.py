# -*- coding: utf-8 -*-
"""
Tests de `herramientas/validar-datos.py`.

Este fichero existe porque `validar-datos.py` es la única red de seguridad del
proyecto y nadie había comprobado nunca que la red tenga agujeros. Cada test de
aquí corresponde a una trampa documentada en AGENTS.md: el guión dice que las
detecta, y esto lo demuestra en vez de creérselo.

Sin dependencias: `unittest` de la biblioteca estándar. Se corre solo con
`pruebas/correr.sh`.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
GUION = RAIZ / "herramientas" / "validar-datos.py"


# ── Datos mínimos que pasan todas las comprobaciones ──────────────────────

def _datos_validos() -> dict:
    return {
        "especies.json": {
            "grupos": [{"id": "limicolas"}],
            "especies": [
                {"id": "avoceta", "grupo": "limicolas",
                 "confianza": "verificado", "zonas": ["odiel"]},
            ],
        },
        "sinonimos.json": {
            "entradas": [{"id": "avoceta", "commonsVerificado": True}],
        },
        "zonas.json": {"zonas": [{"id": "odiel", "puntos": ["p1"]}]},
        "puntos.geojson": {
            "features": [{"properties": {"id": "p1"}}],
        },
    }


class Escenario:
    """Un árbol de proyecto de mentira, con datos que el test puede romper."""

    def __init__(self, datos: dict, version_html: str, version_sw: str):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        (raiz / "app" / "datos").mkdir(parents=True)
        for nombre, contenido in datos.items():
            (raiz / "app" / "datos" / nombre).write_text(
                json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
        (raiz / "app" / "index.html").write_text(
            f'<script src="app.js?v={version_html}"></script>', encoding="utf-8")
        (raiz / "app" / "sw.js").write_text(
            f"const ARMAZON = ['/', 'app.js?v={version_sw}'];", encoding="utf-8")
        self.raiz = raiz

    def correr(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GUION),
             "--datos", str(self.raiz / "app" / "datos"),
             "--app", str(self.raiz / "app")],
            capture_output=True, text=True,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._tmp.cleanup()


def escenario(mutar=None, version_html="7", version_sw="7") -> Escenario:
    datos = _datos_validos()
    if mutar:
        mutar(datos)
    return Escenario(datos, version_html, version_sw)


# ── Los tests ─────────────────────────────────────────────────────────────

class ValidarDatos(unittest.TestCase):

    def test_datos_coherentes_salen_en_verde(self):
        """El caso bueno pasa. Sin esto, todos los demás podrían ser falsos
        positivos: un guión que falla siempre también «detecta» todo."""
        with escenario() as e:
            r = e.correr()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ok ·", r.stdout)

    def test_json_roto_no_revienta_el_guion(self):
        """Un JSON a medias deja la app en blanco. El guión tiene que dar un
        fallo legible, no una traza."""
        with escenario() as e:
            (e.raiz / "app" / "datos" / "zonas.json").write_text("{", encoding="utf-8")
            r = e.correr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no parsea", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_especie_sin_sinonimo(self):
        """La trampa que estuvo viva meses: 52 de 60 especies caían en el
        fallback silencioso de app.js y la ficha no decía ni «verificada» ni
        «por verificar»."""
        def mutar(d):
            d["especies.json"]["especies"].append(
                {"id": "colimbo", "grupo": "limicolas",
                 "confianza": "verificado", "zonas": ["odiel"]})
        with escenario(mutar) as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("sin entrada", r.stderr)
        self.assertIn("colimbo", r.stderr)

    def test_sinonimo_de_especie_que_ya_no_existe(self):
        def mutar(d):
            d["sinonimos.json"]["entradas"].append(
                {"id": "fantasma", "commonsVerificado": False})
        with escenario(mutar) as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("ya no existen", r.stderr)

    def test_ids_de_especie_repetidos(self):
        def mutar(d):
            d["especies.json"]["especies"].append(
                dict(d["especies.json"]["especies"][0]))
        with escenario(mutar) as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("ids repetidos", r.stderr)

    def test_version_de_appjs_desincronizada(self):
        """La peor de todas: si index.html y sw.js no coinciden, quien tenga la
        app instalada se queda con el JS viejo de forma permanente."""
        with escenario(version_html="8", version_sw="7") as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("desincronizada", r.stderr)

    def test_version_ausente(self):
        with escenario() as e:
            (e.raiz / "app" / "sw.js").write_text(
                "const ARMAZON = ['/'];", encoding="utf-8")
            r = e.correr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no encuentro la versión", r.stderr)

    def test_especie_con_grupo_inexistente(self):
        def mutar(d):
            d["especies.json"]["especies"][0]["grupo"] = "inventado"
        with escenario(mutar) as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("grupo inexistente", r.stderr)

    def test_zona_que_apunta_a_un_punto_inexistente(self):
        def mutar(d):
            d["zonas.json"]["zonas"][0]["puntos"] = ["p1", "p99"]
        with escenario(mutar) as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("p99", r.stderr)


class DatosRealesDelRepo(unittest.TestCase):
    """Los datos que hay ahora mismo en `app/datos/` tienen que pasar."""

    def test_el_repo_esta_coherente(self):
        r = subprocess.run(
            [sys.executable, str(GUION)],
            cwd=RAIZ, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
