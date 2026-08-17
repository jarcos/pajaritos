/* Service Worker · Aves del Odiel
   Estrategias de la sección 08 de la especificación:
     · armazón y datos  → precarga en la instalación, después «cache first» con
       refresco en segundo plano (la app avisa, no sobrescribe en silencio)
     · mareas           → «network first» con reserva en caché (dato perecedero)
     · fotos y teselas  → «cache first», se acumulan según se usan
     · /api/            → nunca se cachea
*/
const V = 'odiel-v1';
const ARMAZON = [
  './', 'index.html', 'app.js', 'manifest.webmanifest', 'icono.svg',
  'datos/especies.json', 'datos/zonas.json', 'datos/puntos.geojson', 'datos/sinonimos.json',
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
    await Promise.all(claves.filter(k => k !== V).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

const esFoto = u => u.pathname.includes('/fotos/');
const esTesela = u => u.pathname.endsWith('.pmtiles');

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

  // Fotos y teselas: caché primero; se acumulan con el uso.
  if (esFoto(url) || esTesela(url)) {
    ev.respondWith((async () => {
      const hit = await caches.match(req);
      if (hit) return hit;
      const r = await fetch(req);
      if (r.ok || r.status === 206) (await caches.open(V)).put(req, r.clone()).catch(() => {});
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
