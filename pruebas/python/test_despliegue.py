# -*- coding: utf-8 -*-
"""
Tests del job de despliegue (`.github/workflows/ci.yml`).

Fallo real del 06-11-2026: el push de la analítica cambió
`nginx/pajaritos.conf`, el CI dijo «cambia la infraestructura: se recrean los
contenedores», salió verde... y nginx siguió con la configuración vieja.
`/u/script.js` devolvía index.html.

Dos cosas se juntan:

  · `docker compose up -d --build` sólo recrea un contenedor si cambia su
    definición en el compose. El contenido de un fichero montado no cuenta: el
    servicio `web` se quedaba como estaba.
  · La configuración de nginx es un bind mount de UN fichero, y `tar xzf` lo
    sustituye por otro (inodo nuevo). El contenedor sigue viendo el viejo hasta
    que se vuelve a arrancar; ni un `nginx -s reload` lo arreglaría.

Así que todo cambio en `nginx/` tiene que recrear `web` a la fuerza, y la
comprobación posterior tiene que demostrar que la configuración nueva está
viva: los ficheros estáticos ya se comparaban por hash, la configuración no se
miraba.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CI = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _paso(nombre: str) -> str:
    """El texto de un paso del workflow, desde su `- name:` hasta el siguiente."""
    m = re.search(r"- name: " + re.escape(nombre) + r"\n(.*?)(?=\n      - name: |\Z)", CI, re.S)
    if not m:
        raise AssertionError(f"no encuentro el paso «{nombre}» en ci.yml")
    return m.group(1)


class CambiosEnNginx(unittest.TestCase):
    def test_se_detecta_aparte_un_cambio_en_nginx(self):
        paso = _paso("¿Hace falta tocar los contenedores?")
        self.assertIn('echo "nginx=si" >> "$GITHUB_OUTPUT"', paso)
        self.assertRegex(paso, r"grep -q '\^nginx/'")

    def test_un_cambio_en_nginx_recrea_web_a_la_fuerza(self):
        paso = _paso("Levantar los contenedores")
        self.assertIn("steps.infra.outputs.nginx", paso)
        self.assertRegex(paso, r"up -d --no-deps --force-recreate web")

    def test_la_comprobacion_demuestra_que_la_configuracion_nueva_esta_viva(self):
        # /u/api/send responde 405 a un GET desde el propio nginx, antes de
        # proxear: no depende de que Umami esté arriba. Con la configuración
        # vieja esa ruta cae en index.html y da 200.
        paso = _paso("Comprobar que lo publicado es lo que se subió")
        self.assertRegex(paso, r'\$base/u/api/send')
        self.assertIn("405", paso)


if __name__ == "__main__":
    unittest.main()
