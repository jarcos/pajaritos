'use strict';
/* Tests de app/logica.js — las funciones puras que antes vivían enterradas
   en app.js entre llamadas al DOM.

   Cada test de aquí es una trampa concreta que la app puede sufrir, no una
   comprobación de que JavaScript sabe sumar. Si alguno se puede borrar sin
   que nadie note nada, es que sobra. */

const { test } = require('node:test');
const assert = require('node:assert');
const L = require('../../app/logica.js');

/* --- fixtures -------------------------------------------------------------
   Pequeños a propósito: si un test necesita los 60 registros reales para
   decir algo, lo que falla no es el dato, es el diseño de la función. */

const ESTADO = {
  zonas: [
    { id: 'odiel',   nombre: 'Odiel',   estacionMarea: 'huelva-5', desfaseMinutos: 0 },
    { id: 'piedras', nombre: 'Piedras', estacionMarea: 'huelva-5', desfaseMinutos: 300 },
    { id: 'sinest',  nombre: 'Sin estación' },
  ],
  mareas: {
    estaciones: {
      'huelva-5': {
        nombre: 'Huelva',
        dias: [
          { fecha: '2026-08-28', eventos: [
            { tipo: 'bajamar',  local: '06:10' },
            { tipo: 'pleamar',  local: '12:30' },
            { tipo: 'bajamar',  local: '20:00' },
          ] },
        ],
      },
    },
  },
};

const ESP = [
  { id: 'a', grupo: 'limicolas', zonas: ['odiel'],            tamano: 'pequeno', marea: 'bajamar',
    meses: [0,0,0,1,1,1,0,0,0,0,0,0] },
  { id: 'b', grupo: 'anatidas',  zonas: ['odiel','piedras'],  tamano: 'mediano', marea: 'indiferente',
    meses: [1,1,1,1,1,1,1,1,1,1,1,1] },
  { id: 'c', grupo: 'anatidas',  zonas: ['piedras'],          tamano: 'grande',  marea: 'pleamar',
    meses: [1,1,1,1,1,1,1,1,1,1,1,1] },
  // Sin fenología: sus doce unos significan «no se sabe», no «todo el año».
  { id: 'z', grupo: 'colimbos',  zonas: ['odiel','piedras'],  tamano: 'mediano', marea: 'indiferente',
    meses: [1,1,1,1,1,1,1,1,1,1,1,1], notaFenologia: 'sin datos suficientes' },
];

/* --- estacionDe ----------------------------------------------------------- */

test('estacionDe: sin datos de mareas devuelve null en vez de reventar', () => {
  // El estado arranca con `mareas: null` y se rellena por fetch. Entre una
  // cosa y otra la app se pinta. Si esto tira, la app se queda en blanco.
  assert.strictEqual(L.estacionDe({ zonas: ESTADO.zonas, mareas: null }, 'odiel'), null);
});

test('estacionDe: zona desconocida cae en la primera zona, no en undefined', () => {
  const est = L.estacionDe(ESTADO, 'no-existe');
  assert.strictEqual(est.nombre, 'Huelva');
});

test('estacionDe: zona sin estacionMarea usa huelva-5 por defecto', () => {
  assert.strictEqual(L.estacionDe(ESTADO, 'sinest').nombre, 'Huelva');
});

/* --- diaMarea ------------------------------------------------------------- */

test('diaMarea: sin desfase deja las horas como vienen', () => {
  const d = L.diaMarea(ESTADO, '2026-08-28', 'odiel');
  assert.deepStrictEqual(d.eventos.map(e => e.local), ['06:10', '12:30', '20:00']);
  assert.strictEqual(d.desfase, 0);
});

test('diaMarea: el desfase de la zona se suma a la hora mostrada', () => {
  const d = L.diaMarea(ESTADO, '2026-08-28', 'piedras');   // +300 min = +5 h
  assert.strictEqual(d.eventos[0].local, '11:10');
  assert.strictEqual(d.eventos[0].min, 11 * 60 + 10);
});

test('diaMarea: un desfase que cruza medianoche da la vuelta, no las 25:00', () => {
  // 20:00 + 5 h = 01:00 del día siguiente. Sin el módulo saldría «25:00»,
  // que además ordenaría mal la lista de eventos.
  const d = L.diaMarea(ESTADO, '2026-08-28', 'piedras');
  assert.strictEqual(d.eventos[2].local, '01:00');
  assert.strictEqual(d.eventos[2].min, 60);
});

test('diaMarea: fecha sin predicción devuelve null (predicción caducada)', () => {
  assert.strictEqual(L.diaMarea(ESTADO, '2027-01-01', 'odiel'), null);
});

/* --- proximaMarea --------------------------------------------------------- */

test('proximaMarea: elige el primer evento que aún no ha pasado y cuánto falta', () => {
  const p = L.proximaMarea(ESTADO, 'odiel', { fecha: '2026-08-28', hora: '10:00' });
  assert.strictEqual(p.tipo, 'pleamar');
  assert.strictEqual(p.faltan, 150);          // 12:30 - 10:00
  assert.notStrictEqual(p.pasada, true);
});

test('proximaMarea: si ya han pasado todas devuelve la última marcada como pasada', () => {
  const p = L.proximaMarea(ESTADO, 'odiel', { fecha: '2026-08-28', hora: '23:30' });
  assert.strictEqual(p.pasada, true);
  assert.strictEqual(p.faltan, null);
  assert.strictEqual(p.local, '20:00');
});

test('proximaMarea: sin día de predicción devuelve null', () => {
  assert.strictEqual(L.proximaMarea(ESTADO, 'odiel', { fecha: '2027-01-01', hora: '10:00' }), null);
});

/* --- esperables ----------------------------------------------------------- */

test('esperables: las especies sin fenología nunca entran', () => {
  // La trampa por la que se quitó el gráfico: doce unos no son «todo el año».
  const r = L.esperables(ESP, 4, null, null);
  assert.ok(!r.some(e => e.id === 'z'), 'la especie sin fenología se ha colado');
});

test('esperables: un mes en cero excluye la especie', () => {
  assert.deepStrictEqual(L.esperables(ESP, 0, null, null).map(e => e.id), ['b', 'c']);
});

test('esperables: filtra por zona', () => {
  assert.deepStrictEqual(L.esperables(ESP, 4, 'odiel', null).map(e => e.id), ['a', 'b']);
});

test('esperables: «indiferente» en la especie pasa cualquier marea', () => {
  assert.deepStrictEqual(L.esperables(ESP, 4, null, 'bajamar').map(e => e.id), ['a', 'b']);
});

test('esperables: marea «indiferente» pedida no filtra nada', () => {
  assert.deepStrictEqual(L.esperables(ESP, 4, null, 'indiferente').map(e => e.id), ['a', 'b', 'c']);
});

/* --- aplicaFiltros -------------------------------------------------------- */

const VACIO = { mes: null, zona: null, marea: null, tamano: null, grupo: null };

test('aplicaFiltros: sin filtros devuelve todo, incluida la que no tiene fenología', () => {
  assert.strictEqual(L.aplicaFiltros(ESP, VACIO).length, 4);
});

test('aplicaFiltros: filtrar por mes esconde las que no tienen fenología', () => {
  const r = L.aplicaFiltros(ESP, { ...VACIO, mes: 4 });
  assert.deepStrictEqual(r.map(e => e.id), ['a', 'b', 'c']);
});

test('aplicaFiltros: mes 0 deja fuera a la que no vuela en enero', () => {
  assert.deepStrictEqual(L.aplicaFiltros(ESP, { ...VACIO, mes: 0 }).map(e => e.id), ['b', 'c']);
});

test('aplicaFiltros: combina zona y grupo', () => {
  const r = L.aplicaFiltros(ESP, { ...VACIO, zona: 'piedras', grupo: 'anatidas' });
  assert.deepStrictEqual(r.map(e => e.id), ['b', 'c']);
});

test('aplicaFiltros: «omitir» ignora ese filtro y solo ese', () => {
  // Es lo que usa la guía para poder decir «quita el filtro de zona y
  // aparecen 7». Si omitir se colara en los demás, el recuento mentiría.
  const f = { ...VACIO, zona: 'odiel', tamano: 'grande' };
  assert.deepStrictEqual(L.aplicaFiltros(ESP, f).map(e => e.id), []);
  assert.deepStrictEqual(L.aplicaFiltros(ESP, f, 'zona').map(e => e.id), ['c']);
  // Sin filtro de mes, la especie sin fenología SÍ sale: solo desaparece
  // cuando se afirma algo sobre un mes concreto. Escribí ['a','b'] aquí y el
  // test cazó mi expectativa, no el código.
  assert.deepStrictEqual(L.aplicaFiltros(ESP, f, 'tamano').map(e => e.id), ['a', 'b', 'z']);
});

test('aplicaFiltros: no muta la lista que recibe', () => {
  const copia = ESP.slice();
  L.aplicaFiltros(ESP, { ...VACIO, mes: 4 });
  assert.deepStrictEqual(ESP, copia);
});
