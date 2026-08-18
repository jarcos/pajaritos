#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actualiza docs/especificacion-app-guia-odiel.html con el estado real tras
el despliegue del 18/08/2026. Idempotente: si ya está aplicado, avisa y sale."""
import pathlib
import sys

P = pathlib.Path.home() / "Sites/pajaritos/docs/especificacion-app-guia-odiel.html"
s = P.read_text(encoding="utf-8")

if "v3 · en producción" in s:
    sys.exit("ya estaba actualizado")

cambios = []


def rep(viejo, nuevo, etiqueta):
    global s
    if viejo not in s:
        sys.exit(f"NO ENCONTRADO: {etiqueta}")
    s = s.replace(viejo, nuevo, 1)
    cambios.append(etiqueta)


# ---------------------------------------------------------------- 1. estilos
rep(
    ".fase .out{margin-top:9px;font:600 11.5px/1.4 var(--mono);color:var(--sal)}",
    """.fase .out{margin-top:9px;font:600 11.5px/1.4 var(--mono);color:var(--sal)}
.fase.hecha .num{background:var(--verde)}
.fase.parcial .num{background:var(--sal)}
.fase.pendiente .num{background:#fff;color:var(--tinta-3);border:2px solid var(--linea)}
.estado{display:inline-block;font:700 10px/1 var(--mono);letter-spacing:.12em;text-transform:uppercase;
        padding:5px 9px;border-radius:100px;margin-left:10px;vertical-align:2px}
.estado.hecha{background:var(--verde-cl);color:var(--verde)}
.estado.parcial{background:var(--sal-cl);color:#8f5320}
.estado.pendiente{background:var(--papel-2);color:var(--tinta-3)}
.real{margin-top:11px;padding:11px 15px;background:var(--verde-cl);border-left:3px solid var(--verde);
      border-radius:0 6px 6px 0;font-size:14px;line-height:1.5;color:var(--tinta-2)}
.real.ojo{background:var(--sal-cl);border-left-color:var(--sal)}
.real b{color:var(--verde);font-weight:700}
.real.ojo b{color:#8f5320}""",
    "estilos de estado de fase",
)

# ---------------------------------------------------------------- 2. cabecera
rep(
    '<p class="kicker">Especificación funcional y técnica · v2</p>',
    '<p class="kicker">Especificación funcional y técnica · v3 · en producción</p>',
    "kicker a v3",
)
rep(
    '    <span class="pill">Offline híbrido</span>\n'
    '    <span class="pill">12 de agosto de 2026</span>',
    '    <span class="pill">Offline híbrido</span>\n'
    '    <span class="pill" style="background:var(--verde-cl);border-color:var(--verde);color:var(--verde)">'
    'En producción · 18 ago 2026</span>\n'
    '    <span class="pill">PWA instalable</span>\n'
    '    <span class="pill">Fase 1 cerrada</span>',
    "pastillas de cabecera",
)

# ------------------------------------------------- 3. aviso de estado, arriba
rep(
    '<p class="lead">Documento complementario al <em>Plan de la guía de observación</em>.',
    """<div class="nota" style="background:var(--verde-cl);border-left-color:var(--verde)">
  <p><strong style="color:var(--verde)">La aplicación está desplegada y en funcionamiento</strong>
  en <a href="https://pajaritos.josearcos.me">pajaritos.josearcos.me</a> desde el 18 de agosto de 2026.
  Verificado sobre HTTPS con navegador real: Service Worker registrado y activo, contexto seguro,
  Geolocation API disponible, sin violaciones de CSP y sin errores de consola. Sirve 60 especies,
  7 zonas, 17 puntos y 31 días de predicción de marea que el cron publica solo cada madrugada.</p>
  <p>Las fases marcadas en la sección 11 reflejan lo ejecutado, no lo planeado. La sección 12 recoge
  en qué se desvió la realidad de este documento y por qué. El diario técnico completo está en
  <code>pajaritos/SETUP.md</code> §14.</p>
</div>

<p class="lead">Documento complementario al <em>Plan de la guía de observación</em>.""",
    "aviso de produccion",
)

P.write_text(s, encoding="utf-8")
print("aplicados:", ", ".join(cambios))
