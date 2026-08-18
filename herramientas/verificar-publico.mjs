// Verificación de pajaritos.josearcos.me con navegador real, desde fuera.
// Comprueba lo único que no se puede probar sin HTTPS: registro del Service
// Worker, contexto seguro y Geolocation API. Y de paso que la CSP no rompa
// nada ahora que el JS va en fichero aparte.
//
//   node herramientas/verificar-publico.mjs
import { chromium } from '/Users/josearcos/Sites/microsites/node_modules/playwright/index.mjs';

const URL = 'https://pajaritos.josearcos.me/';
const errores = [];
const csp = [];

const nav = await chromium.launch({ channel: 'chrome' }).catch(() => chromium.launch());
const ctx = await nav.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 2, isMobile: true, hasTouch: true,
  locale: 'es-ES', timezoneId: 'Europe/Madrid',
});
const p = await ctx.newPage();
p.on('pageerror', e => errores.push('PAGEERROR: ' + e.message));
p.on('console', m => {
  const t = m.text();
  if (/Content Security Policy|Refused to/i.test(t)) csp.push(t);
  else if (m.type() === 'error') errores.push('CONSOLA: ' + t);
});

const r = await p.goto(URL, { waitUntil: 'networkidle', timeout: 45000 });
console.log('=== respuesta del borde ===');
console.log('  status:', r.status());
const h = r.headers();
for (const k of ['content-security-policy', 'cache-control', 'cf-cache-status',
                 'permissions-policy', 'x-frame-options', 'content-encoding'])
  console.log(`  ${k}: ${h[k] ?? '(ausente)'}`);

await p.waitForTimeout(2500);

console.log('=== contexto seguro y APIs ===');
console.log(await p.evaluate(() => ({
  isSecureContext: window.isSecureContext,
  geolocation: typeof navigator.geolocation?.getCurrentPosition === 'function',
  serviceWorkerAPI: 'serviceWorker' in navigator,
  storagePersistAPI: typeof navigator.storage?.persist === 'function',
  indexedDB: typeof indexedDB !== 'undefined',
})));

console.log('=== service worker ===');
const sw = await p.evaluate(async () => {
  if (!('serviceWorker' in navigator)) return { soportado: false };
  const reg = await Promise.race([
    navigator.serviceWorker.ready,
    new Promise(res => setTimeout(() => res(null), 15000)),
  ]);
  if (!reg) return { soportado: true, registrado: false };
  return {
    soportado: true, registrado: true,
    scope: reg.scope,
    estado: reg.active?.state ?? null,
    script: reg.active?.scriptURL ?? null,
  };
});
console.log(' ', sw);

console.log('=== cachés que ha creado ===');
console.log(' ', await p.evaluate(async () => {
  const nombres = await caches.keys();
  const out = {};
  for (const n of nombres) out[n] = (await (await caches.open(n)).keys()).length;
  return out;
}));

console.log('=== estado de la app ===');
console.log(' ', await p.evaluate(() => ({
  especies: E?.especies?.length ?? null,
  verificadas: E?.especies?.filter(e => e.confianza === 'verificado').length ?? null,
  zonas: E?.zonas?.length ?? null,
  puntos: E?.puntos?.length ?? null,
  mareasDias: E?.mareas?.estaciones?.['huelva-5']?.dias?.length ?? null,
  estacion: E?.mareas?.estaciones?.['huelva-5']?.nombre ?? null,
})));

console.log('=== lo que se ve en Hoy ===');
console.log(' ', await p.evaluate(() => ({
  cabecera: document.querySelector('#hoy-sub')?.textContent,
  marea: [document.querySelector('#marea-tipo')?.textContent,
          document.querySelector('#marea-hora')?.textContent,
          document.querySelector('#marea-alt')?.textContent].join(' '),
  cuenta: document.querySelector('#marea-cuenta')?.textContent,
  probabilidad: document.querySelector('#hoy-n')?.textContent + ' ' +
                document.querySelector('#hoy-n-sub')?.textContent,
  destacadas: document.querySelectorAll('#hoy-destacadas .fila').length,
  caducada: document.querySelector('#tarj-marea')?.classList.contains('caducada'),
})));

console.log('=== manifest / PWA ===');
console.log(' ', await p.evaluate(async () => {
  const l = document.querySelector('link[rel=manifest]');
  if (!l) return 'sin manifest';
  const m = await (await fetch(l.href)).json();
  return { name: m.name, display: m.display, start_url: m.start_url, iconos: m.icons.length };
}));

await p.screenshot({ path: '/Users/josearcos/Sites/pajaritos/herramientas/publico-hoy.png' });

console.log('=== violaciones de CSP ===');
console.log(csp.length ? csp : '  ninguna');
console.log('=== errores ===');
console.log(errores.length ? errores : '  ninguno');

await ctx.close();
await nav.close();
