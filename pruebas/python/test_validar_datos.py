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
                 "confianza": "verificado", "zonas": ["odiel"],
                 "foto": {"estado": "pendiente", "archivo": None}},
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

    def __init__(self, datos: dict, version_html: str, version_sw: str,
                 logica_html: str | None = "", logica_sw: str | None = ""):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        (raiz / "app" / "datos").mkdir(parents=True)
        for nombre, contenido in datos.items():
            (raiz / "app" / "datos" / nombre).write_text(
                json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
        # logica_* a "" significa «la misma que app.js», que es el caso sano.
        # A None significa «no está», para poder probar el olvido.
        l_html = version_html if logica_html == "" else logica_html
        l_sw = version_sw if logica_sw == "" else logica_sw
        etiqueta_l = f'<script src="logica.js?v={l_html}"></script>' if l_html else ""
        armazon_l = f"'logica.js?v={l_sw}', " if l_sw else ""
        (raiz / "app" / "index.html").write_text(
            etiqueta_l + f'<script src="app.js?v={version_html}"></script>',
            encoding="utf-8")
        (raiz / "app" / "sw.js").write_text(
            f"const ARMAZON = ['/', {armazon_l}'app.js?v={version_sw}'];",
            encoding="utf-8")
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


def escenario(mutar=None, version_html="7", version_sw="7",
              logica_html="", logica_sw="") -> Escenario:
    datos = _datos_validos()
    if mutar:
        mutar(datos)
    return Escenario(datos, version_html, version_sw, logica_html, logica_sw)


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

    def test_logica_js_no_declarada_en_index(self):
        """logica.js es el segundo fichero de la app. Si no se declara, el
        navegador carga app.js sola, `Logica` es undefined y la app muere en
        la primera marea. La versión doble de app.js ya nos mordió una vez:
        el segundo fichero entra con su comprobación puesta, no después."""
        with escenario(logica_html=None) as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("logica.js", r.stderr)

    def test_logica_js_no_precargada_en_el_sw(self):
        """Declarada en index.html pero fuera de ARMAZON: la app funciona con
        red y se rompe sin ella, que es justo donde se usa — en la marisma."""
        with escenario(logica_sw=None) as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("logica.js", r.stderr)

    def test_version_de_logica_desincronizada(self):
        """Mismo agujero que con app.js, en el fichero nuevo."""
        with escenario(logica_html="9") as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("logica.js", r.stderr)

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


class ValidarFotos(unittest.TestCase):
    """Criterio t39.1 (29-09-2026): CC0, dominio público, CC BY y CC BY-SA, con
    autor, licencia y enlace a la página del archivo en Commons.

    CC BY y CC BY-SA obligan a atribuir. Una foto «lista» a la que le falta el
    autor o la licencia incumple la licencia con la que se descargó, y una foto
    cuyo fichero no está sube a producción como un icono roto. Cada test de
    aquí rompe UNA cosa de una foto sana y comprueba que el guion lo ve."""

    @staticmethod
    def _foto(**cambios) -> dict:
        foto = {
            "estado": "lista", "archivo": "avoceta-1a2b3c4d.webp",
            "autor": "El Golli Mohamed", "licencia": "CC BY-SA 4.0",
            "licenciaUrl": "https://creativecommons.org/licenses/by-sa/4.0/",
            "paginaArchivo": "https://commons.wikimedia.org/wiki/File:Avoceta.jpg",
            "origen": "commons", "modificada": True, "revisada": "2026-09-29",
        }
        foto.update(cambios)
        return foto

    def _correr(self, foto, con_fichero=True, nombre_fichero="avoceta-1a2b3c4d.webp"):
        def mutar(d):
            d["especies.json"]["especies"][0]["foto"] = foto
        with escenario(mutar) as e:
            if con_fichero:
                (e.raiz / "app" / "fotos").mkdir(exist_ok=True)
                (e.raiz / "app" / "fotos" / nombre_fichero).write_bytes(b"x")
            return e.correr()

    def test_foto_completa_pasa(self):
        """El caso bueno. Sin él, los demás podrían ser falsos positivos."""
        r = self._correr(self._foto())
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_las_licencias_aceptadas_pasan(self):
        for lic in ("CC0 1.0", "Public domain", "CC BY 4.0", "CC BY 3.0",
                    "CC BY-SA 4.0", "CC BY-SA 2.5"):
            with self.subTest(licencia=lic):
                r = self._correr(self._foto(licencia=lic))
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_especie_sin_campo_foto(self):
        """app.js lee `esp.foto.estado` sin comprobar nada: sin el campo, la
        ficha muere."""
        def mutar(d):
            del d["especies.json"]["especies"][0]["foto"]
        with escenario(mutar) as e:
            r = e.correr()
        self.assertEqual(r.returncode, 1)
        self.assertIn("foto", r.stderr)
        self.assertIn("avoceta", r.stderr)

    def test_estado_desconocido(self):
        r = self._correr(self._foto(estado="casi"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("estado", r.stderr)

    def test_foto_lista_sin_autor(self):
        for autor in ("", None):
            with self.subTest(autor=autor):
                r = self._correr(self._foto(autor=autor))
                self.assertEqual(r.returncode, 1)
                self.assertIn("autor", r.stderr)

    def test_foto_lista_sin_licencia(self):
        r = self._correr(self._foto(licencia=""))
        self.assertEqual(r.returncode, 1)
        self.assertIn("licencia", r.stderr)

    def test_licencia_no_aceptada(self):
        """Commons solo admite libres, pero un dato mal copiado o una licencia
        con NC o ND no cumple el criterio y tiene que parar."""
        for lic in ("CC BY-NC 4.0", "CC BY-ND 4.0", "Copyrighted free use", "todos"):
            with self.subTest(licencia=lic):
                r = self._correr(self._foto(licencia=lic))
                self.assertEqual(r.returncode, 1)
                self.assertIn("licencia", r.stderr)

    def test_foto_lista_sin_enlace_a_commons_o_de_otra_web(self):
        for pagina in ("", None, "https://example.com/File:Avoceta.jpg",
                       "https://commons.wikimedia.org/wiki/Category:Avoceta"):
            with self.subTest(pagina=pagina):
                r = self._correr(self._foto(paginaArchivo=pagina))
                self.assertEqual(r.returncode, 1)
                self.assertIn("paginaArchivo", r.stderr)

    def test_foto_lista_sin_fecha_de_revision(self):
        """La revisión humana es la que dice que la identificación es buena;
        sin fecha nadie sabe si se hizo."""
        for fecha in ("", None, "ayer", "29/09/2026"):
            with self.subTest(fecha=fecha):
                r = self._correr(self._foto(revisada=fecha))
                self.assertEqual(r.returncode, 1)
                self.assertIn("revisada", r.stderr)

    def test_foto_lista_cuyo_fichero_no_existe(self):
        r = self._correr(self._foto(), con_fichero=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no existe", r.stderr)
        self.assertIn("avoceta-1a2b3c4d.webp", r.stderr)

    def test_archivo_con_ruta(self):
        """El nombre va tal cual a `fotos/<archivo>`; con una ruta se sale de
        la carpeta."""
        r = self._correr(self._foto(archivo="../datos/especies.json"), con_fichero=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("archivo", r.stderr)

    def test_archivo_sin_huella_en_el_nombre(self):
        """nginx sirve /fotos/ como inmutable un año. Un nombre sin huella del
        contenido significa que cambiar la foto por otra no llega a nadie que
        ya tenga la vieja en caché, ni al service worker, que es cache-first."""
        for nombre in ("avoceta.webp", "avoceta-1a2b3c.webp", "avoceta-zzzzzzzz.webp"):
            with self.subTest(archivo=nombre):
                r = self._correr(self._foto(archivo=nombre), nombre_fichero=nombre)
                self.assertEqual(r.returncode, 1)
                self.assertIn("huella", r.stderr)

    def test_foto_pendiente_con_archivo_a_medias(self):
        """Un estado que dice una cosa y unos campos que dicen otra es un
        trabajo a medias: o está lista o está pendiente."""
        r = self._correr({"estado": "pendiente", "archivo": "avoceta-1a2b3c4d.webp"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("pendiente", r.stderr)


class DatosRealesDelRepo(unittest.TestCase):
    """Los datos que hay ahora mismo en `app/datos/` tienen que pasar."""

    def test_el_repo_esta_coherente(self):
        r = subprocess.run(
            [sys.executable, str(GUION)],
            cwd=RAIZ, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
