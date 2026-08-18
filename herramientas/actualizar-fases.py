#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sustituye la sección 11 de la especificación por el estado real de cada fase."""
import pathlib
import sys

P = pathlib.Path.home() / "Sites/pajaritos/docs/especificacion-app-guia-odiel.html"
s = P.read_text(encoding="utf-8")

INI = '<h2><span class="sec">11</span>Fases de implementación</h2>'
FIN = '<h2><span class="sec">12</span>'

if 'Fases de implementación · estado real' in s:
    sys.exit("la seccion 11 ya estaba actualizada")
if INI not in s or FIN not in s:
    sys.exit("no encuentro los limites de la seccion 11")

a = s.index(INI)
b = s.index(FIN)

NUEVO = """<h2><span class="sec">11</span>Fases de implementación · estado real</h2>

<p class="lead">Actualizado el <strong>18 de agosto de 2026</strong>, después del despliegue. El estado
de cada fase es el ejecutado y verificado, no el previsto. Donde la realidad se apartó de lo escrito
aquí, se dice en qué y por qué.</p>

<div class="fase hecha"><div class="num">1</div><div class="body">
  <h4>Infraestructura en el NAS <span class="estado hecha">Hecha · 18 ago</span></h4>
  <p>Ruta del tunnel en «Published application routes», contenedores según el patrón de la casa y
  comprobación de que el Service Worker se registra y la Geolocation API funciona sobre HTTPS.</p>
  <div class="real"><b>Ejecutado.</b> Los tres contenedores arriba, <code>web</code> y <code>api</code>
  <em>healthy</em>. Solo <code>pajaritos-web</code> en la red <code>tunnel</code>, ningún puerto de host,
  y el 3012 confirmado libre. La ruta se publicó por API e insertó <strong>antes del catch-all</strong>
  sin tocar las seis que ya había. Service Worker registrado y <em>activated</em> con scope <code>/</code>,
  caché de armazón con 9 entradas, contexto seguro y Geolocation disponible: verificado desde fuera con
  navegador real, sin violaciones de CSP y sin errores de consola.</div>
  <div class="real ojo"><b>Tres cosas estaban mal.</b> El NAS había cambiado de IP por DHCP y
  <code>~/.ssh/config</code> apuntaba a una máquina distinta. En nginx, <code>add_header</code>
  <strong>no se hereda</strong> en las <code>location</code> que declaran el suyo, así que la CSP no
  llegaba ni a la raíz ni a <code>sw.js</code>: la mitigación estaba escrita y no se aplicaba. Y el
  rate limit no contabilizaba nada, porque nginx ignora las peticiones cuya clave está vacía y la clave
  era <code>$http_cf_connecting_ip</code>. Los tres arreglados y reverificados. Diario en
  <code>SETUP.md</code> §14.</div>
  <p class="out">→ Origen HTTPS operativo y aislado del resto del NAS</p>
</div></div>

<div class="fase hecha"><div class="num">2</div><div class="body">
  <h4>Esqueleto navegable con datos reales <span class="estado hecha">Hecha · con más alcance</span></h4>
  <p>Las seis pantallas y las ~25 especies ya verificadas. Sin fotos, sin mapa, sin offline.</p>
  <div class="real"><b>Se hizo bastante más.</b> No las ~25 especies sino las <strong>60 de arranque</strong>,
  y no seis pantallas sino las seis más las capas de detalle, las hojas, el croquis y los ocho estados del
  wireframe 2a: sin conexión con y sin caché, marea caducada, ubicación denegada, cuaderno vacío, filtro
  sin resultados —que propone quitar el filtro concreto que vacía la lista, con el recuento—, descarga en
  progreso y reporte encolado. Los filtros de mes, zona y marea los hereda la Guía de la salida en curso.</div>
  <p class="out">→ Prototipo navegable para validar la interacción</p>
</div></div>

<div class="fase hecha"><div class="num">3</div><div class="body">
  <h4>Servicio de mareas <span class="estado hecha">Hecha · publicando sola</span></h4>
  <p>Cron diario, parser de PORTUS con conversión a <code>Europe/Madrid</code>, escritura atómica,
  marca de <code>stale</code> y aviso de fallo.</p>
  <div class="real"><b>En marcha sin intervención.</b> El cron de las 04:05 se disparó por su cuenta la
  primera madrugada: 31 días, 120 eventos, validación superada. El reagrupado por fecha local funciona en
  producción —la bajamar de las 23:17 UTC sale a las <strong>01:17 del día siguiente</strong>, que es
  donde el observador la espera—. La pantalla «Hoy» muestra procedencia, datum y hora de descarga, y la
  cuenta atrás hasta la próxima marea.</div>
  <p class="out">→ mareas.json publicándose solo cada día</p>
</div></div>

<div class="fase parcial"><div class="num">4</div><div class="body">
  <h4>Completar datos y tabla de sinónimos <span class="estado parcial">Parcial</span></h4>
  <p>Las 60 especies con estatus, fenología y marca de confianza. Verificación de las 60 categorías de
  Commons —hoy solo 4 comprobadas— y volcado a <code>sinonimos.json</code>.</p>
  <div class="real"><b>Hecho:</b> las 60 especies con grupo, estatus, fenología, hábitat, marea óptima,
  zonas, criterios de identificación, conducta y pares de confusión. <strong>23 con fenología verificada</strong>
  contra la matriz del plan; las otras <strong>37 entran como estimadas</strong> y la ficha lo dice, con la
  franja al 55 % de opacidad y filete punteado.</div>
  <div class="real ojo"><b>Falta lo que más pesa:</b> verificar las <strong>56 categorías de Commons</strong>
  pendientes y contrastar las 37 fenologías estimadas con los <em>barcharts</em> de eBird de los hotspots del
  Odiel. También hay que revisar los textos de identificación, que hoy son borradores y no material cotejado
  con el PDF de SEO/BirdLife.</div>
  <p class="out">→ especies.json y sinonimos.json completos</p>
</div></div>

<div class="fase parcial"><div class="num">5</div><div class="body">
  <h4>Mapa y geolocalización <span class="estado parcial">Parcial</span></h4>
  <p>Extracción del PMTiles de Huelva, medición del peso por nivel de zoom, servido con HTTP Range, capas
  GeoJSON, ubicación opt-in y detección de la zona más cercana.</p>
  <div class="real"><b>Hecho:</b> geolocalización opt-in, que pide permiso al pulsar y nunca al arrancar,
  con detección del punto más cercano y <code>watchPosition</code> activo solo mientras el mapa está abierto.
  Capas propias de observatorios, senderos y zonas sobre <code>puntos.geojson</code> con los 17 puntos reales,
  conmutables. Pellizco para el zoom, solo en el mapa.</div>
  <div class="real ojo"><b>Falta el basemap.</b> Hoy el mapa dibuja un esquema por coordenadas con retícula
  de medio grado y se etiqueta a sí mismo como «basemap PMTiles pendiente», para no aparentar lo que no es.
  Queda extraer el <code>.pmtiles</code> de Huelva y <strong>medir su peso real a zoom 14</strong> para fijar
  el <code>maxzoom</code> por debajo de los 512 MB del plan gratuito de Cloudflare.</div>
  <p class="out">→ Mapa autoalojado sin claves ni terceros</p>
</div></div>

<div class="fase hecha"><div class="num">6</div><div class="body">
  <h4>Cuaderno con persistencia <span class="estado hecha">Hecha</span></h4>
  <p>IndexedDB, salida en curso, contador de un toque, registro de ave sin identificar, exportación a CSV
  y JSON, importación de respaldo, recordatorio de copia.</p>
  <div class="real"><b>Completo.</b> IndexedDB para salidas y cola de reportes; <code>localStorage</code>
  para preferencias y el borrador de la salida en curso. Contador de un toque, con <strong>pulsación larga
  de 500 ms y vibración</strong> sobre el número para pasar de conteo exacto a estimación de diez en diez;
  la fila se sombrea y el «~» va en la cifra. Ave sin identificar con croquis a dedo, deshacer y borrar, y
  chips de rasgos multiselección. Exportación a CSV —con BOM para que Excel respete los acentos y columna
  propia que distingue <code>exacto</code> de <code>estimado</code>— y a JSON, importación de respaldo y
  recordatorio de copia cada 10 salidas.</div>
  <p class="out">→ Cuaderno funcional con memoria local</p>
</div></div>

<div class="fase parcial"><div class="num">7</div><div class="body">
  <h4>Banco de imágenes y placeholders <span class="estado parcial">Parcial</span></h4>
  <p>Descarga desde Commons e iNaturalist, conversión a WebP, manifiesto de atribución, página de créditos
  generada, placeholders enlazados a la búsqueda para las pendientes.</p>
  <div class="real"><b>Hecho el placeholder,</b> que era la parte con criterio: ocupa el mismo alto que la
  foto y lleva marco continuo para que se lea como decisión y no como fallo de maquetación, y es pulsable
  —enlaza a la búsqueda en Commons usando la categoría de <code>sinonimos.json</code>—. Ajustes muestra el
  recuento de pendientes como lista de trabajo.</div>
  <div class="real ojo"><b>Falta el banco entero:</b> las <strong>60 fichas siguen sin fotografía</strong>.
  Ninguna imagen dudosa ha entrado por rellenar el hueco.</div>
  <p class="out">→ Fotos verificadas + créditos + lista de pendientes</p>
</div></div>

<div class="fase hecha"><div class="num">8</div><div class="body">
  <h4>Offline, PWA y formulario de reporte <span class="estado hecha">Hecha · salvo dos cabos</span></h4>
  <p>Service Worker con las estrategias de la sección 08, manifiesto e icono, descarga previa desde Ajustes,
  <code>storage.persist()</code>, endpoint de reportes con rate limit y honeypot, y cola de envío diferido.</p>
  <div class="real"><b>Funcionando en producción.</b> Service Worker con las tres estrategias: precarga del
  armazón, «red primero» para las mareas por ser dato perecedero, y «caché primero» para fotos y teselas.
  Manifiesto, iconos, <code>storage.persist()</code> y cola de reportes en IndexedDB que se vacía al recuperar
  red. El endpoint <code>POST /api/reporte</code> está desplegado y probado contra el origen real:
  <strong>201</strong> con reporte válido, honeypot aceptado en silencio <strong>sin guardar</strong>,
  <code>tipo</code> con intento de inyección descartado por lista cerrada, y rate limit que deja pasar cuatro
  y responde <strong>429</strong> al resto.</div>
  <div class="real ojo"><b>Dos cabos sueltos.</b> Faltan las credenciales de Mailgun: sin ellas el reporte
  <em>sí</em> se guarda en SQLite, solo no llega el aviso por correo. Y la descarga previa desde Ajustes mueve
  hoy un contador, no bytes: hay que engancharla a peticiones Range reales cuando exista el
  <code>.pmtiles</code>.</div>
  <p class="out">→ App instalable, funcional sin cobertura, con canal de correcciones</p>
</div></div>

<div class="fase pendiente"><div class="num">9</div><div class="body">
  <h4>Prueba de campo <span class="estado pendiente">Pendiente</span></h4>
  <p>Una salida real al Odiel en bajamar, con el móvil, en modo avión y con la app instalada. Es la única
  prueba que cuenta: si no se puede registrar un bando con una mano y prismáticos en la otra, hay que
  rediseñar. Y es también cuando se comprueba si los desfases de marea por zona son correctos.</p>
  <div class="real ojo"><b>Ya se puede hacer.</b> La app está instalable y funciona sin cobertura, así que
  esta fase deja de depender de nadie. Recordatorio de la §10 del <code>SETUP.md</code>: si el sitio no carga
  desde el móvil, comprobar con otra red antes de depurar nada —el bloqueo de DIGI sobre prefijos de
  Cloudflare no es culpa de la app—. En modo avión con la PWA instalada eso deja de importar.</div>
  <p class="out">→ App v1.0</p>
</div></div>

"""

s = s[:a] + NUEVO + s[b:]
P.write_text(s, encoding="utf-8")
print("seccion 11 actualizada")
