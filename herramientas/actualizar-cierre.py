#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Añade la sección 12 «Lo que cambió al implementar», renumera la antigua 12
a 13 y actualiza su tabla de estados y el pie."""
import pathlib
import sys

P = pathlib.Path.home() / "Sites/pajaritos/docs/especificacion-app-guia-odiel.html"
s = P.read_text(encoding="utf-8")

if "Lo que cambió al implementar" in s:
    sys.exit("ya estaba aplicado")


def rep(viejo, nuevo, etiqueta):
    global s
    if viejo not in s:
        sys.exit(f"NO ENCONTRADO: {etiqueta}")
    s = s.replace(viejo, nuevo, 1)


NUEVA = """<h2><span class="sec">12</span>Lo que cambió al implementar</h2>

<p class="lead">Seis desviaciones respecto a lo escrito en este documento. Ninguna es cosmética: cada una
salió de ejecutar algo y ver que no se comportaba como decía el papel.</p>

<div class="grid g2">
  <div class="card acc">
    <span class="tag">Desviación 1</span>
    <h4>El JS ya no vive dentro del index.html</h4>
    <p>Este documento pedía «un solo <code>index.html</code>» con todo dentro. La CSP del sitio es
    <code>script-src 'self'</code> <strong>sin</strong> <code>'unsafe-inline'</code>, así que el JS en línea
    sencillamente no se ejecuta. Se separó en <code>app.js</code>.</p>
    <p>Sigue siendo una sola página, sin framework y sin dependencias, que es lo que buscaba la decisión
    original. Añadir <code>'unsafe-inline'</code> para salvar la letra habría sido debilitar la seguridad
    por comodidad.</p>
  </div>
  <div class="card acc">
    <span class="tag">Desviación 2</span>
    <h4>app.js lleva versión en la URL</h4>
    <p>Consecuencia de lo anterior, y un fallo que se introdujo al separarlo: <code>index.html</code> se
    sirve con <code>no-cache</code>, pero <code>/app.js</code> se cachea <strong>cuatro horas en el borde</strong>.
    Sin versión en la URL, un redespliegue habría servido JS viejo con HTML nuevo durante horas — el tipo de
    fallo que se manifiesta como «a veces va y a veces no».</p>
    <p>Resuelto con <code>app.js?v=2026-08-18</code>, la misma cadena en el <code>ARMAZON</code> del Service
    Worker y <code>V</code> subido para purgar la caché anterior. <strong>Al tocar <code>app.js</code> hay que
    subir las dos.</strong> Mismo criterio que el <code>.pmtiles</code> versionado por nombre.</p>
  </div>
  <div class="card acc">
    <span class="tag">Desviación 3</span>
    <h4>Las cabeceras de seguridad van en un include</h4>
    <p>En nginx, cualquier <code>location</code> que declare su propio <code>add_header</code>
    <strong>descarta todos los heredados</strong> del bloque <code>server</code>. Como casi todas fijan su
    <code>Cache-Control</code>, la CSP desaparecía justo en <code>/</code>, <code>index.html</code>,
    <code>sw.js</code> y <code>app.js</code>.</p>
    <p>Ahora viven en <code>nginx/cabeceras.conf</code>, incluido explícitamente en cada bloque. Se verificó
    ruta por ruta, no leyendo el fichero.</p>
  </div>
  <div class="card acc">
    <span class="tag">Desviación 4</span>
    <h4>El rate limit necesita clave de respaldo</h4>
    <p><code>limit_req_zone $http_cf_connecting_ip</code> no limita nada cuando la cabecera no llega: nginx
    <strong>ignora las peticiones cuya clave está vacía</strong>. Doce POST seguidos pasaron con 201.</p>
    <p>Con un <code>map</code> que cae a <code>$binary_remote_addr</code> cuando falta la cabecera, el límite
    también protege el acceso por LAN o WireGuard. Reverificado: pasan cuatro y el resto son 429.</p>
  </div>
  <div class="card acc">
    <span class="tag">Desviación 5</span>
    <h4>El contrato del reporte lo manda el servidor</h4>
    <p>El cliente se ajustó a lo que valida <code>services/api/app.py</code>: campo honeypot llamado
    <code>telefono</code> —el valor de <code>HONEYPOT_FIELD</code>—, marca <code>abiertoEn</code> en
    milisegundos para el mínimo de <code>MIN_FILL_SECONDS</code>, mensaje de 10 a 2000 caracteres e
    <code>id</code> de especie contra <code>^[a-z0-9-]{1,60}$</code>.</p>
  </div>
  <div class="card acc">
    <span class="tag">Desviación 6</span>
    <h4>El arranque son 60 especies, no 25</h4>
    <p>La fase 2 preveía las ~25 verificadas. Se cargaron las <strong>60 completas</strong>, con 23 de
    fenología verificada y 37 marcadas como estimadas. Es más honesto que una guía corta que aparente
    certeza: el hueco se ve y se sabe dónde está.</p>
  </div>
</div>

<div class="nota">
  <p><strong>La lección que se repite.</strong> Las cuatro primeras desviaciones tienen la misma forma: algo
  estaba escrito correctamente, se leía correcto, y no se estaba aplicando. La CSP existía y no llegaba. El
  rate limit existía y no contaba. El <code>add_header</code> estaba puesto y no se heredaba. Ninguna se
  habría detectado revisando la configuración: hicieron falta peticiones reales contra el origen real. Es la
  misma lección que el servicio de mareas de la v1, cuando «comprobado en el navegador» resultó no ser
  comprobado.</p>
</div>

"""

rep('<h2><span class="sec">12</span>Decisiones cerradas y cuestiones abiertas</h2>',
    NUEVA + '<h2><span class="sec">13</span>Decisiones cerradas y cuestiones abiertas</h2>',
    "seccion 12 nueva + renumerado")

# ------------------------------------------------------------ tabla de estados
rep('<td class="warn">Abierto — confirmar que el 3012 sigue libre (reservado solo para acceso LAN/WireGuard de depuración) y anotar la fila en el registro del runbook</td>',
    '<td class="ok">Cerrado — <strong>3012 confirmado libre</strong> en el NAS el 17/08/2026. La pila no publica ningún puerto de host; queda reservado y comentado en el override</td>',
    "fila puertos")

rep('<td class="ok">Cerrado y <strong>funcionando</strong> — API JSON de PORTUS, estación 3329, cron diario. Ejecutado contra la fuente en vivo: 31 días, 120 eventos, validación superada. Pendiente: revisar condiciones de reutilización y medir los desfases por zona</td>',
    '<td class="ok">Cerrado y <strong>en producción</strong> — API JSON de PORTUS, estación 3329. El cron de las 04:05 publica solo: 31 días, 120 eventos, validación superada. Pendiente: revisar condiciones de reutilización y medir los desfases por zona en el campo</td>',
    "fila mareas")

rep('<td class="ok">Cerrado — activada, opt-in, sin salir del dispositivo</td>',
    '<td class="ok">Cerrado y <strong>verificado sobre HTTPS</strong> — activada, opt-in, sin salir del dispositivo</td>',
    "fila geolocalizacion")

rep('<td class="ok">Cerrado — MapLibre + PMTiles de Protomaps autoalojado. Pendiente: medir el peso real y fijar <code>maxzoom</code></td>',
    '<td class="warn">Decidido, <strong>sin implementar</strong> — MapLibre + PMTiles de Protomaps autoalojado. Hoy hay un esquema por coordenadas que se etiqueta como tal. Pendiente: extraer el <code>.pmtiles</code>, medir el peso a zoom 14 y fijar <code>maxzoom</code></td>',
    "fila mapa")

rep('<tr><td><strong>Quién más lo usa</strong></td>',
    '''<tr><td><strong>Cabeceras de seguridad</strong></td><td class="ok">Cerrado — CSP, <code>X-Frame-Options</code>, <code>Referrer-Policy</code> y <code>Permissions-Policy</code> en <code>nginx/cabeceras.conf</code>, incluido en cada <code>location</code>. Verificadas ruta por ruta y en el borde</td></tr>
<tr><td><strong>Caché del borde</strong></td><td class="ok">Cerrado — Cloudflare respeta el <code>no-store</code> de <code>/sw.js</code> (<code>cf-cache-status: BYPASS</code>), así que no hace falta regla para el Service Worker. <code>/app.js</code> se cachea 4 h y por eso va versionado en la URL</td></tr>
<tr><td><strong>Rate limiting en el borde</strong></td><td class="warn">Abierto — nginx ya limita a 6/min con clave de respaldo, verificado. Falta la regla en Cloudflare para parar el tráfico antes de que cruce el tunnel</td></tr>
<tr><td><strong>Aviso de reportes</strong></td><td class="warn">Abierto — <code>MAILGUN_API_KEY</code> y <code>MAILGUN_DOMAIN</code> vacíos en el <code>.env</code> del NAS. Sin ellos el reporte se guarda igual y solo se pierde el correo</td></tr>
<tr><td><strong>Quién más lo usa</strong></td>''',
    "filas nuevas de la tabla")

# ------------------------------------------------------------------------ pie
rep('<li><strong>Puesta en marcha en el NAS</strong> — <code>pajaritos/SETUP.md</code>,',
    '<li><strong>La aplicación, en funcionamiento</strong> — <a href="https://pajaritos.josearcos.me">pajaritos.josearcos.me</a>. Copia canónica del código en <code>~/Sites/pajaritos</code>, versionada en git y desplegada en <code>/volume1/docker/pajaritos</code>.</li>\n'
    '    <li><strong>Diario del despliegue</strong> — <code>pajaritos/SETUP.md</code> §14: las trampas que aparecieron al ejecutar, con las comprobaciones y sus resultados.</li>\n'
    '    <li><strong>Puesta en marcha en el NAS</strong> — <code>pajaritos/SETUP.md</code>,',
    "pie: documentos relacionados")

P.write_text(s, encoding="utf-8")
print("seccion 12 nueva, tabla y pie actualizados")
