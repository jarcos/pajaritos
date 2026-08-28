/* Service Worker · Aves del Odiel
   Estrategias de la sección 08 de la especificación:
     · armazón y datos  → precarga en la instalación, después «cache first» con
       refresco en segundo plano (la app avisa, no sobrescribe en silencio)
     · mareas           → «network first» con reserva en caché (dato perecedero)
     · fotos y teselas  → «cache first», se acumulan según se usan
     · /api/            → nunca se cachea
*/
// Al cambiar V se purgan las cachés viejas en `activate`. Súbelo siempre que
// cambie la lista de abajo o la versión de app.js.
const V = 'odiel-v13';
// El mapa vive en su propia caché, sin versión: son 41 MB que el usuario ha
// descargado a mano y no se tiran por subir V. `activate` la deja en paz.
const C_MAPA = 'odiel-mapa';
const ARMAZON = [
  './', 'index.html', 'logica.js?v=2026-08-28a', 'app.js?v=2026-08-28a',
  'manifest.webmanifest', 'icono.svg',
  'datos/especies.json', 'datos/zonas.json', 'datos/puntos.geojson', 'datos/sinonimos.json',
  // El motor del mapa entra en la precarga a propósito: 388 KB comprimidos que
  // se pagan en casa con wifi. Una app para la marisma sin cobertura no puede
  // depender de bajarse MapLibre justo cuando no hay red. El .pmtiles NO está
  // aquí: son 41 MB y tienen su propia descarga, con su barra y su permiso.
  'vendor/maplibre-gl-5.24.0-csp.js', 'vendor/maplibre-gl-5.24.0-csp-worker.js',
  'vendor/maplibre-gl-5.24.0.css', 'vendor/pmtiles-4.5.0.js',
];

self.addEventListener('install', ev => {
  ev.waitUntil((async () => {
    const c = await caches.open(V);
    await Promise.allSettled(ARMAZON.map(u => c.add(u)));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', ev => {
  ev.waitUntil((async () => {
    const claves = await caches.keys();
    await Promise.all(claves.filter(k => k !== V && k !== C_MAPA).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

const esFoto = u => u.pathname.includes('/fotos/');
const esTesela = u => u.pathname.endsWith('.pmtiles');

/* El .pmtiles se guarda entero, en una sola entrada y como 200, porque la
   Cache API rechaza por especificación guardar una respuesta 206. Aquí se
   sirven los rangos que pide pmtiles cortando ese cuerpo: Blob.slice es
   perezoso, no copia los 41 MB en memoria. Si no está guardado, a la red. */
async function servirMapa(req, url) {
  const guardada = await (await caches.open(C_MAPA)).match(url.pathname);
  if (!guardada) return fetch(req);              // sin descargar: rango a la red

  const rango = req.headers.get('range');
  if (!rango) return guardada;

  const m = /bytes=(\d+)-(\d*)/.exec(rango);
  if (!m) return guardada;
  const cuerpo = await guardada.blob();
  const ini = Number(m[1]);
  const fin = m[2] ? Math.min(Number(m[2]), cuerpo.size - 1) : cuerpo.size - 1;
  if (ini >= cuerpo.size || fin < ini) {
    return new Response(null, { status: 416,
      headers: { 'Content-Range': `bytes */${cuerpo.size}` } });
  }
  return new Response(cuerpo.slice(ini, fin + 1), { status: 206, headers: {
    'Content-Type': 'application/octet-stream',
    'Content-Range': `bytes ${ini}-${fin}/${cuerpo.size}`,
    'Content-Length': String(fin - ini + 1),
    'Accept-Ranges': 'bytes' } });
}

self.addEventListener('fetch', ev => {
  const req = ev.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/')) return;          // los reportes no se cachean

  // Mareas: dato perecedero. Red primero, caché como red de seguridad.
  if (url.pathname.endsWith('mareas.json')) {
    ev.respondWith((async () => {
      try {
        const r = await fetch(req);
        if (r.ok) (await caches.open(V)).put(req, r.clone());
        return r;
      } catch { return (await caches.match(req)) || Response.error(); }
    })());
    return;
  }

  // Mapa: entrada única guardada por la descarga previa, servida por rangos.
  if (esTesela(url)) { ev.respondWith(servirMapa(req, url)); return; }

  // Fotos: caché primero; se acumulan con el uso.
  if (esFoto(url)) {
    ev.respondWith((async () => {
      const hit = await caches.match(req);
      if (hit) return hit;
      const r = await fetch(req);
      if (r.ok) ev.waitUntil((await caches.open(V)).put(req, r.clone()));
      return r;
    })());
    return;
  }

  // Resto: caché primero + revalidación en segundo plano.
  ev.respondWith((async () => {
    const hit = await caches.match(req);
    const red = fetch(req).then(r => {
      if (r.ok) caches.open(V).then(c => c.put(req, r.clone()));
      return r;
    }).catch(() => null);
    if (hit) { ev.waitUntil(red); return hit; }
    const r = await red;
    if (r) return r;
    if (req.mode === 'navigate') return (await caches.match('index.html')) || Response.error();
    return Response.error();
  })());
});
