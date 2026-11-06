# -*- coding: utf-8 -*-
"""
Tests de la analítica de uso (Umami, 06-11-2026, pedido por José).

Umami vive en el NAS (`frienddraft-umami`, en la red `tunnel`, panel en
umami.josearcos.me). Aquí se sirve desde el propio dominio, bajo `/u/`, por
tres motivos que estos tests fijan:

  · La CSP sigue siendo `'self'` para scripts y conexiones: no se abre a nadie.
  · Los bloqueadores no cortan una ruta del propio sitio como cortan un host
    de analítica.
  · Sólo se mide en pajaritos.josearcos.me: ni en local ni por la LAN.

Y dos trampas que no se ven hasta que pasan:

  · Con `proxy_pass http://frienddraft-umami:3000` a pelo, nginx resuelve el
    nombre AL ARRANCAR; si Umami está caído en ese momento, nginx no arranca y
    se cae la guía entera por culpa de las estadísticas. Por eso va por
    variable y con el resolver de Docker: se resuelve en cada petición.
  · El service worker cachea «todo lo demás» con caché primero. Sin excluir
    `/u/`, el script de Umami se quedaría guardado y viejo en los móviles.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
WEBSITE_ID = "e94f49df-d235-4702-b860-bd3017268677"


def _leer(ruta: str) -> str:
    return (RAIZ / ruta).read_text(encoding="utf-8")


def _etiqueta_umami(html: str) -> str:
    etiquetas = re.findall(r"<script\b[^>]*>", html)
    deumami = [e for e in etiquetas if 'src="/u/script.js"' in e]
    if len(deumami) != 1:
        raise AssertionError(f"esperaba un único <script> de /u/script.js, hay {len(deumami)}")
    return deumami[0]


def _bloque(conf: str, cabecera: str) -> str:
    """El cuerpo de `location <cabecera> { ... }`, contando llaves: dentro
    puede haber un `if (...) { ... }`."""
    m = re.search(re.escape(cabecera) + r"\s*\{", conf)
    if not m:
        raise AssertionError(f"no encuentro «{cabecera}» en nginx/pajaritos.conf")
    nivel, i = 1, m.end()
    while nivel and i < len(conf):
        nivel += {"{": 1, "}": -1}.get(conf[i], 0)
        i += 1
    if nivel:
        raise AssertionError(f"«{cabecera}» no cierra sus llaves")
    return conf[m.end():i - 1]


class ScriptEnIndex(unittest.TestCase):
    def setUp(self):
        self.etiqueta = _etiqueta_umami(_leer("app/index.html"))

    def test_carga_el_script_del_propio_dominio_sin_bloquear_la_pagina(self):
        self.assertIn("defer", self.etiqueta)

    def test_lleva_el_id_de_la_web_en_umami(self):
        self.assertIn(f'data-website-id="{WEBSITE_ID}"', self.etiqueta)

    def test_solo_mide_en_el_dominio_publico(self):
        self.assertIn('data-domains="pajaritos.josearcos.me"', self.etiqueta)

    def test_no_guarda_query_ni_hash(self):
        self.assertIn('data-exclude-search="true"', self.etiqueta)
        self.assertIn('data-exclude-hash="true"', self.etiqueta)


class ProxyEnNginx(unittest.TestCase):
    def setUp(self):
        self.conf = _leer("nginx/pajaritos.conf")

    def test_el_script_y_el_envio_van_a_umami_por_variable(self):
        for ruta, destino in (("/u/script.js", "/script.js"), ("/u/api/send", "/api/send")):
            with self.subTest(ruta=ruta):
                cuerpo = _bloque(self.conf, f"location = {ruta}")
                self.assertRegex(cuerpo, r"resolver\s+127\.0\.0\.11\b")
                self.assertRegex(cuerpo, r"set\s+\$umami\s+http://frienddraft-umami:3000\s*;")
                self.assertRegex(cuerpo, r"proxy_pass\s+\$umami" + re.escape(destino) + r"\s*;")

    def test_umami_recibe_la_ip_real_para_contar_visitantes(self):
        cuerpo = _bloque(self.conf, "location = /u/api/send")
        self.assertRegex(cuerpo, r"proxy_set_header\s+CF-Connecting-IP\s+\$http_cf_connecting_ip\s*;")

    def test_el_envio_solo_acepta_post(self):
        cuerpo = _bloque(self.conf, "location = /u/api/send")
        self.assertRegex(cuerpo, r"if\s*\(\$request_method\s*!=\s*POST\)\s*\{\s*return\s+405")

    def test_nada_mas_de_umami_se_publica_por_aqui(self):
        cuerpo = _bloque(self.conf, "location /u/")
        self.assertRegex(cuerpo, r"return\s+404\s*;")

    def test_la_csp_sigue_cerrada_al_propio_origen(self):
        csp = _leer("nginx/cabeceras.conf")
        self.assertIn("script-src 'self';", csp)
        self.assertIn("connect-src 'self';", csp)
        self.assertNotIn("umami", csp)


class ServiceWorker(unittest.TestCase):
    def test_no_intercepta_la_analitica(self):
        sw = _leer("app/sw.js")
        self.assertRegex(sw, r"if \(url\.pathname\.startsWith\('/u/'\)\) return;")


if __name__ == "__main__":
    unittest.main()
