# -*- coding: utf-8 -*-
"""
Tests de `herramientas/comprobar-desplegado.sh`.

Este guión existe porque el 28-08-2026 la única forma de saber si el NAS estaba
sirviendo el `logica.js` recién desplegado fue un `curl` y un `md5` a mano. Un
guardia que solo funciona cuando alguien se acuerda de llamarlo no es un
guardia. Y uno que nadie ha visto fallar tampoco.

Levanta un servidor de mentira sobre un árbol temporal y le da al guión un
`--base` que apunta ahí. Sin red, sin NAS, sin tocar producción.
"""
from __future__ import annotations

import functools
import http.server
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
GUION = RAIZ / "herramientas" / "comprobar-desplegado.sh"

CONTENIDO = {
    "index.html": '<script src="logica.js?v=7"></script><script src="app.js?v=7"></script>',
    "logica.js": "var Logica = {};\n",
    "app.js": "// app\n",
    "sw.js": "const V = 'v1';\n",
    "manifest.webmanifest": '{"name":"x"}',
}


class Silencioso(http.server.SimpleHTTPRequestHandler):
    """El servidor de pruebas no tiene por qué ensuciar la salida del test."""

    def log_message(self, *_):
        pass


class Escenario:
    """Un repo y un «producción» que empiezan idénticos, para poder separarlos."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.repo = base / "repo" / "app"
        self.prod = base / "prod"
        for d in (self.repo, self.prod):
            d.mkdir(parents=True)
            for nombre, texto in CONTENIDO.items():
                (d / nombre).write_text(texto, encoding="utf-8")

        manejador = functools.partial(Silencioso, directory=str(self.prod))
        socketserver.TCPServer.allow_reuse_address = True
        self._srv = socketserver.TCPServer(("127.0.0.1", 0), manejador)
        self.url = f"http://127.0.0.1:{self._srv.server_address[1]}"
        self._hilo = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._hilo.start()

    def correr(self, ficheros=None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sh", str(GUION), self.url, str(self.repo), *(ficheros or CONTENIDO)],
            capture_output=True, text=True, timeout=60,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._srv.shutdown()
        self._srv.server_close()
        self._tmp.cleanup()


class ComprobarDesplegado(unittest.TestCase):

    def test_todo_coincide(self):
        """El caso bueno pasa. Sin esto, los demás podrían ser falsos positivos:
        un guión que falla siempre también «detecta» todo."""
        with Escenario() as e:
            r = e.correr()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("DESPLIEGUE AL DIA", r.stdout)

    def test_un_fichero_desplegado_es_viejo(self):
        """El caso real: se despliega y el NAS se queda con el fichero anterior."""
        with Escenario() as e:
            (e.prod / "logica.js").write_text("var Logica = {viejo:1};\n", encoding="utf-8")
            r = e.correr()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("logica.js", r.stdout)
        self.assertIn("difiere", r.stdout)

    def test_un_fichero_no_se_sirve(self):
        """Un 404 devuelve una página de error con su hash tan tranquila. Sin
        `curl --fail` esto saldría como «difiere», que es un diagnóstico
        distinto y manda a mirar al sitio equivocado."""
        with Escenario() as e:
            (e.prod / "logica.js").unlink()
            r = e.correr()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no se sirve", r.stdout)

    def test_el_index_desplegado_es_de_otra_version(self):
        """Si el index viejo pide `?v=6`, hay que comparar lo que produccion
        sirve DE VERDAD, no pedirle la version que nos conviene oir."""
        with Escenario() as e:
            (e.prod / "index.html").write_text(
                '<script src="logica.js?v=6"></script><script src="app.js?v=6"></script>',
                encoding="utf-8")
            r = e.correr()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("version que sirve produccion: 6", r.stdout)
        self.assertIn("index.html", r.stdout)

    def test_produccion_caida(self):
        """Sin servidor no se puede afirmar nada. Lo que no vale es decir que
        todo coincide porque no se ha podido comparar."""
        with Escenario() as e:
            e._srv.shutdown()
            e._srv.server_close()
            r = e.correr()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("NO SE PUEDE COMPROBAR", r.stdout)
        self.assertNotIn("AL DIA", r.stdout)

    def test_sin_ficheros_no_dice_que_todo_esta_bien(self):
        """Comparar nada y salir 0 parece una comprobación y no lo es. Es el
        mismo agujero que un `for` sobre una lista vacía en un guión de copias:
        cero fallos porque cero intentos."""
        with Escenario() as e:
            r = subprocess.run(
                ["sh", str(GUION), e.url, str(e.repo)],
                capture_output=True, text=True, timeout=60)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("AL DIA", r.stdout)

    def test_el_index_sin_version_no_pasa_por_alto(self):
        with Escenario() as e:
            (e.prod / "index.html").write_text("<html>sin scripts</html>", encoding="utf-8")
            r = e.correr()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no declara ninguna version", r.stdout)


if __name__ == "__main__":
    unittest.main()
