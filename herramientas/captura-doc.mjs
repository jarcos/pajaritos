// Captura las secciones nuevas de la especificación para revisarlas de un vistazo.
import { chromium } from '/Users/josearcos/Sites/microsites/node_modules/playwright/index.mjs';

const F = 'file:///Users/josearcos/Sites/pajaritos/docs/especificacion-app-guia-odiel.html';
const nav = await chromium.launch({ channel: 'chrome' }).catch(() => chromium.launch());
const p = await (await nav.newContext({ viewport: { width: 1180, height: 1000 }, deviceScaleFactor: 2 })).newPage();
const errs = [];
p.on('pageerror', e => errs.push(e.message));
await p.goto(F, { waitUntil: 'load' });

const secciones = await p.evaluate(() =>
  [...document.querySelectorAll('h2')].map(h => h.textContent.trim()));
console.log('secciones:', secciones.length);

// Cabecera
await p.screenshot({ path: '/Users/josearcos/Sites/pajaritos/herramientas/doc-cabecera.png' });

// Sección 11
const h11 = await p.$('h2:has(.sec:text-is("11"))').catch(() => null);
for (const [n, sel] of [['11', '11'], ['12', '12']]) {
  const h = await p.evaluateHandle(sel => {
    const hs = [...document.querySelectorAll('h2')];
    return hs.find(x => x.querySelector('.sec')?.textContent === sel);
  }, sel);
  const el = h.asElement();
  if (!el) { console.log('no encuentro la seccion', n); continue; }
  await el.scrollIntoViewIfNeeded();
  await p.waitForTimeout(300);
  await p.screenshot({ path: `/Users/josearcos/Sites/pajaritos/herramientas/doc-sec${n}.png` });
}

console.log('errores:', errs.length ? errs : 'ninguno');
await nav.close();
