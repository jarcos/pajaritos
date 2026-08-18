// Comprueba el tablero: render, cuentas, filtros, arrastre y persistencia.
import { chromium } from '/Users/josearcos/Sites/microsites/node_modules/playwright/index.mjs';

const F = 'file:///Users/josearcos/Sites/pajaritos/docs/tablero.html';
const nav = await chromium.launch({ channel: 'chrome' }).catch(() => chromium.launch());
const ctx = await nav.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
const p = await ctx.newPage();
const errs = [];
p.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
p.on('console', m => { if (m.type() === 'error') errs.push('CONSOLA: ' + m.text()); });

await p.goto(F, { waitUntil: 'load' });
await p.waitForTimeout(400);

const base = await p.evaluate(() => ({
  titulo: document.title,
  pct: document.querySelector('#pct').textContent,
  totales: document.querySelector('#totales').textContent,
  hecho: +document.querySelector('#n-hecho').textContent,
  curso: +document.querySelector('#n-curso').textContent,
  pendiente: +document.querySelector('#n-pendiente').textContent,
  tarjetas: document.querySelectorAll('.tarea').length,
  filtros: document.querySelectorAll('#filtros .filtro').length,
  duplicados: (() => {
    const ids = [...document.querySelectorAll('.tarea')].map(x => x.dataset.id);
    return ids.length - new Set(ids).size;
  })(),
}));
console.log('estado inicial:', base);
console.log('suma columnas =', base.hecho + base.curso + base.pendiente);

// filtro por área
await p.click('#filtros .filtro:nth-child(3)');
await p.waitForTimeout(250);
console.log('con filtro Datos:', await p.evaluate(() => ({
  visibles: document.querySelectorAll('.tarea').length,
  areas: [...new Set([...document.querySelectorAll('.tarea')].map(x => x.dataset.area))],
})));
await p.click('#filtros .filtro:nth-child(3)');
await p.waitForTimeout(200);

// arrastre: mover una pendiente a hecho
const antes = await p.evaluate(() => +document.querySelector('#n-hecho').textContent);
await p.evaluate(() => {
  const t = document.querySelector('#c-pendiente .tarea');
  const dt = new DataTransfer();
  t.dispatchEvent(new DragEvent('dragstart', { dataTransfer: dt, bubbles: true }));
  const col = document.querySelector('.col-hecho');
  col.dispatchEvent(new DragEvent('dragover', { dataTransfer: dt, bubbles: true, cancelable: true }));
  col.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
});
await p.waitForTimeout(300);
const despues = await p.evaluate(() => +document.querySelector('#n-hecho').textContent);
console.log(`arrastre: hecho ${antes} -> ${despues}`);

// persistencia tras recargar
await p.reload({ waitUntil: 'load' });
await p.waitForTimeout(400);
console.log('tras recargar, hecho =', await p.evaluate(() => +document.querySelector('#n-hecho').textContent));

// restablecer
await p.click('#btn-reset');
await p.waitForTimeout(300);
console.log('tras restablecer, hecho =', await p.evaluate(() => +document.querySelector('#n-hecho').textContent));

await p.screenshot({ path: '/Users/josearcos/Sites/pajaritos/herramientas/tablero.png', fullPage: false });

// enlace de ida y vuelta con la especificación
await p.click('.volver');
await p.waitForTimeout(500);
console.log('volver lleva a:', (await p.title()).slice(0, 50));
const haciaTablero = await p.$('a[href="tablero.html"]');
console.log('la especificacion enlaza el tablero:', !!haciaTablero);

console.log('errores:', errs.length ? errs : 'ninguno');
await nav.close();
