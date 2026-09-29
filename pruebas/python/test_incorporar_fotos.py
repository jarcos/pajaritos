# -*- coding: utf-8 -*-
"""
Tests de `herramientas/incorporar-fotos.py`.

El guion baja fotos de Commons y reescribe `especies.json`, que es el fichero
del que vive toda la app. Lo que tiene que quedar demostrado aquí es que NO
inventa nada (una foto que no se bajó no se declara lista), que NO toca lo que
no le toca, y que lo que escribe pasa el mismo validador que corre en CI.

La descarga real no se prueba: necesita red y Commons no es nuestro. Lo que se
prueba es todo lo que decide qué se descarga y qué se escribe después.
"""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import unittest
from pathlib import Path

from pruebas.python.test_validar_datos import Escenario, _datos_validos

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "incorporar_fotos", RAIZ / "herramientas" / "incorporar-fotos.py")
F = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F)


def _item(**cambios) -> dict:
    item = {
        "archivo": "Avocette élégante Thyna022.jpg",
        "autor": "El Golli Mohamed", "licencia": "CC BY-SA 4.0",
        "licenciaUrl": "https://creativecommons.org/licenses/by-sa/4.0/",
        "paginaArchivo": "https://commons.wikimedia.org/wiki/File:Avocette_élégante_Thyna022.jpg",
        "original": "https://upload.wikimedia.org/x.jpg",
    }
    item.update(cambios)
    return item


def _especies() -> dict:
    return {"especies": [
        {"id": "avoceta", "nombre": "Avoceta", "foto": {"estado": "pendiente", "archivo": None,
                                                        "autor": None, "licencia": None, "origen": None}},
        {"id": "garza", "nombre": "Garza", "foto": {"estado": "pendiente", "archivo": None,
                                                     "autor": None, "licencia": None, "origen": None}},
    ]}


class Piezas(unittest.TestCase):

    def test_nombre_local_lleva_el_id_y_la_huella_del_contenido(self):
        """El nombre de Commons trae espacios, tildes y paréntesis; el local
        es el id de la especie más la huella del contenido. nginx sirve
        /fotos/ como inmutable durante un año: si una foto se cambia por otra
        con el mismo nombre, los navegadores y Cloudflare siguen enseñando la
        vieja. Con la huella en el nombre, otra foto es otra URL."""
        self.assertEqual(F.nombre_local("avoceta", "webp", "1a2b3c4d"),
                         "avoceta-1a2b3c4d.webp")

    def test_la_huella_depende_del_contenido_y_no_del_nombre(self):
        self.assertEqual(F.huella(b"una foto"), F.huella(b"una foto"))
        self.assertNotEqual(F.huella(b"una foto"), F.huella(b"otra foto"))
        self.assertRegex(F.huella(b"x"), r"^[0-9a-f]{8}$")

    def test_url_de_miniatura_escapa_lo_que_hay_que_escapar(self):
        u = F.url_miniatura("Aigrette garzette (site RAMSAR) é.jpg", 1280)
        self.assertTrue(u.startswith("https://commons.wikimedia.org/wiki/Special:FilePath/"))
        self.assertNotIn(" ", u)
        self.assertIn("%C3%A9", u)
        self.assertTrue(u.endswith("?width=1280"))

    def test_entrada_foto_declara_lo_que_exige_el_criterio(self):
        f = F.entrada_foto(_item(), "avoceta-1a2b3c4d.webp", "2026-09-29")
        self.assertEqual(f["estado"], "lista")
        self.assertEqual(f["archivo"], "avoceta-1a2b3c4d.webp")
        self.assertEqual(f["autor"], "El Golli Mohamed")
        self.assertEqual(f["licencia"], "CC BY-SA 4.0")
        self.assertEqual(f["origen"], "commons")
        self.assertEqual(f["archivoCommons"], "Avocette élégante Thyna022.jpg")
        self.assertIs(f["modificada"], True)     # siempre se redimensiona
        self.assertEqual(f["revisada"], "2026-09-29")

    def test_entrada_foto_sin_autor_o_licencia_se_niega(self):
        """Antes de bajar nada: una foto sin atribución no vale la pena."""
        for campo in ("autor", "licencia", "paginaArchivo"):
            with self.subTest(campo=campo):
                with self.assertRaises(ValueError):
                    F.entrada_foto(_item(**{campo: ""}), "avoceta-1a2b3c4d.webp", "2026-09-29")


class Aplicar(unittest.TestCase):

    def test_solo_toca_las_especies_bajadas(self):
        datos = _especies()
        nuevo = F.aplicar(datos, {"avoceta": _item()}, {"avoceta": "avoceta-1a2b3c4d.webp"}, "2026-09-29")
        por_id = {e["id"]: e for e in nuevo["especies"]}
        self.assertEqual(por_id["avoceta"]["foto"]["estado"], "lista")
        self.assertEqual(por_id["garza"]["foto"]["estado"], "pendiente")

    def test_una_foto_que_no_se_bajo_no_se_declara_lista(self):
        """El fallo que más duele: declarar lista una foto cuyo fichero no
        está. La ficha enseñaría un icono roto en producción."""
        nuevo = F.aplicar(_especies(), {"avoceta": _item()}, {}, "2026-09-29")
        self.assertEqual(nuevo["especies"][0]["foto"]["estado"], "pendiente")

    def test_especie_que_no_existe_se_niega(self):
        with self.assertRaises(KeyError):
            F.aplicar(_especies(), {"fantasma": _item()}, {"fantasma": "fantasma-1a2b3c4d.webp"}, "2026-09-29")

    def test_no_modifica_el_original_que_recibe(self):
        datos = _especies()
        F.aplicar(datos, {"avoceta": _item()}, {"avoceta": "avoceta-1a2b3c4d.webp"}, "2026-09-29")
        self.assertEqual(datos["especies"][0]["foto"]["estado"], "pendiente")

    def test_lo_que_escribe_pasa_el_validador_de_ci(self):
        """La prueba que importa: el resultado del guion es una foto que el
        validador da por buena. Si los dos se desincronizan, esto lo dice."""
        datos = _datos_validos()
        datos["especies.json"] = F.aplicar(
            {"grupos": datos["especies.json"]["grupos"],
             "especies": datos["especies.json"]["especies"]},
            {"avoceta": _item()}, {"avoceta": "avoceta-1a2b3c4d.webp"}, "2026-09-29")
        with Escenario(datos, "7", "7") as e:
            (e.raiz / "app" / "fotos").mkdir()
            (e.raiz / "app" / "fotos" / "avoceta-1a2b3c4d.webp").write_bytes(b"x")
            r = e.correr()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 con foto", r.stdout)


class Serializar(unittest.TestCase):

    def test_reproduce_byte_a_byte_el_especies_json_real(self):
        """Si al reescribir el fichero cambia un solo carácter, el diff de git
        deja de decir qué foto se añadió y pasa a decir «cambió todo»."""
        texto = (RAIZ / "app" / "datos" / "especies.json").read_text(encoding="utf-8")
        self.assertEqual(F.serializar(json.loads(texto)), texto)


class Atribucion(unittest.TestCase):

    def test_csv_solo_lleva_las_listas_y_escapa_bien(self):
        datos = F.aplicar(_especies(),
                          {"avoceta": _item(autor='Nombre, con "comas"')},
                          {"avoceta": "avoceta-1a2b3c4d.webp"}, "2026-09-29")
        filas = list(csv.DictReader(io.StringIO(F.atribucion_csv(datos))))
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["especie"], "avoceta")
        self.assertEqual(filas[0]["autor"], 'Nombre, con "comas"')
        self.assertEqual(filas[0]["licencia"], "CC BY-SA 4.0")
        self.assertEqual(filas[0]["archivo"], "avoceta-1a2b3c4d.webp")

    def test_csv_sin_fotos_solo_tiene_cabecera(self):
        filas = F.atribucion_csv(_especies()).strip().splitlines()
        self.assertEqual(len(filas), 1)


if __name__ == "__main__":
    unittest.main()
