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

/* --- estacionDeclarada ---------------------------------------------------- */

/* Ojo con la diferencia respecto a `estacionDe`, que NO es un descuido y por eso
   son dos funciones y no una: `estacionDe` contesta «qué mareógrafo uso para
   calcular la marea de esta zona», y ahí un valor por defecto es lo correcto.
   `estacionDeclarada` contesta «qué mareógrafo dice esta zona que tiene», y ahí
   inventarse Huelva sería escribir en la ficha un dato que el JSON no da. Es la
   misma familia de mentira que las doce unidades de las especies sin fenología. */

test('estacionDeclarada: la zona que declara una estación, la devuelve', () => {
  const z = ESTADO.zonas.find(x => x.id === 'odiel');
  assert.strictEqual(L.estacionDeclarada(ESTADO, z).nombre, 'Huelva');
});

test('estacionDeclarada: la zona SIN estación devuelve null, no huelva-5', () => {
  const z = ESTADO.zonas.find(x => x.id === 'sinest');
  assert.strictEqual(L.estacionDeclarada(ESTADO, z), null);
});

test('estacionDeclarada: y estacionDe, para esa misma zona, SÍ devuelve huelva-5', () => {
  // La ficha de zona dirá «no aplica» y el cálculo de mareas seguirá usando
  // Huelva. Las dos cosas a la vez, que es justo lo que se quiere.
  const z = ESTADO.zonas.find(x => x.id === 'sinest');
  assert.strictEqual(L.estacionDeclarada(ESTADO, z), null);
  assert.strictEqual(L.estacionDe(ESTADO, 'sinest').nombre, 'Huelva');
});

test('estacionDeclarada: sin datos de mareas devuelve null', () => {
  const z = ESTADO.zonas.find(x => x.id === 'odiel');
  assert.strictEqual(L.estacionDeclarada({ ...ESTADO, mareas: null }, z), null);
});

test('estacionDeclarada: una estación que no existe devuelve null, no undefined', () => {
  // `estaciones['fantasma']` es undefined, y `undefined` colado en la ficha
  // imprime «código undefined». null al menos cae en el «no aplica».
  assert.strictEqual(L.estacionDeclarada(ESTADO, { id: 'x', estacionMarea: 'fantasma' }), null);
});

test('estacionDeclarada: sin zona devuelve null y no revienta', () => {
  assert.strictEqual(L.estacionDeclarada(ESTADO, null), null);
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

/* --- procedencia del texto de identificación -------------------------------
   Los 60 textos de identificación los redactamos aquí; sólo una parte está
   cotejada contra la guía publicada de la Autoridad Portuaria. La ficha tiene
   que decir cuál es cuál, igual que ya hace con la fenología, porque si no un
   párrafo escrito de memoria se lee con la misma autoridad que uno contrastado.
   Es una función pura de un objeto a una cadena: aquí se prueba, no en el DOM. */

test('una ficha cotejada sin matices lo dice y nombra la fuente', () => {
  const l = L.procedenciaIdent({ fuenteIdentificacion: 'guia-seo' });
  assert.match(l, /Cotejada con la guía de la ría de Huelva/);
  assert.match(l, /Autoridad Portuaria/);
});

test('una ficha cotejada con matiz antepone la fuente y añade el matiz', () => {
  const l = L.procedenciaIdent({ fuenteIdentificacion: 'guia-seo',
                                 notaIdentificacion: 'Del PDF viene el antifaz negro.' });
  assert.match(l, /^Cotejada con la guía de la ría de Huelva\./);
  assert.match(l, /antifaz negro/);
  // La coletilla larga de la fuente sobra cuando hay matiz: la línea ya es densa.
  assert.doesNotMatch(l, /Autoridad Portuaria/);
});

test('una ficha propia NO dice que esté cotejada', () => {
  const l = L.procedenciaIdent({ fuenteIdentificacion: 'propia',
                                 notaIdentificacion: 'El PDF no describe el ave.' });
  assert.match(l, /Redacción propia, sin cotejar/);
  assert.doesNotMatch(l, /Cotejada/);
  assert.match(l, /no describe el ave/);
});

test('una ficha propia sin nota no deja un espacio colgando', () => {
  const l = L.procedenciaIdent({ fuenteIdentificacion: 'propia' });
  assert.strictEqual(l, l.trim());
  assert.doesNotMatch(l, /undefined|null/);
});

test('sin procedencia declarada no se inventa un respaldo', () => {
  // El validador lo impide en los datos, pero si alguna vez se cuela, el fallo
  // seguro es callar, nunca afirmar que está cotejada.
  for (const e of [{}, { fuenteIdentificacion: '' }, { fuenteIdentificacion: 'otra-cosa' }]) {
    assert.doesNotMatch(L.procedenciaIdent(e), /Cotejada/);
  }
});

/* --- fotos ------------------------------------------------------------------
   Criterio t39.1 (29-09-2026): CC0, dominio público, CC BY y CC BY-SA, con
   autor y licencia visibles bajo la foto y enlace a la página del archivo en
   Commons. CC BY y CC BY-SA obligan a atribuir; una foto que se enseña sin
   decir de quién es incumple la licencia con la que se descargó.
   El fallo seguro es el placeholder, nunca una foto a medias. */

const FOTO = {
  estado: 'lista', archivo: 'ciconia-ciconia.webp', autor: 'Carlos Delgado',
  licencia: 'CC BY-SA 3.0', licenciaUrl: 'https://creativecommons.org/licenses/by-sa/3.0/',
  paginaArchivo: 'https://commons.wikimedia.org/wiki/File:Ciconia_ciconia_-_01.jpg',
  modificada: true, revisada: '2026-09-29',
};

test('una foto pendiente no se muestra y no tiene crédito', () => {
  assert.strictEqual(L.fotoMostrable({ estado: 'pendiente', archivo: null }), false);
  assert.strictEqual(L.creditoFoto({ estado: 'pendiente', archivo: null }), null);
});

test('sin foto declarada tampoco rompe', () => {
  assert.strictEqual(L.fotoMostrable(undefined), false);
  assert.strictEqual(L.creditoFoto(undefined), null);
});

test('una foto completa se muestra con autor, licencia y enlace a Commons', () => {
  assert.strictEqual(L.fotoMostrable(FOTO), true);
  const c = L.creditoFoto(FOTO);
  assert.strictEqual(c.texto, 'Foto: Carlos Delgado · CC BY-SA 3.0');
  assert.strictEqual(c.enlace, FOTO.paginaArchivo);
  assert.strictEqual(c.licenciaUrl, FOTO.licenciaUrl);
});

test('una foto recortada o redimensionada lo dice', () => {
  assert.match(L.creditoFoto(FOTO).nota, /redimensionada/i);
  assert.strictEqual(L.creditoFoto(Object.assign({}, FOTO, { modificada: false })).nota, '');
});

test('una foto lista sin autor NO se muestra: incumpliría la licencia', () => {
  assert.strictEqual(L.fotoMostrable(Object.assign({}, FOTO, { autor: '' })), false);
  assert.strictEqual(L.fotoMostrable(Object.assign({}, FOTO, { autor: null })), false);
});

test('una foto lista sin licencia, sin archivo o sin enlace a Commons NO se muestra', () => {
  assert.strictEqual(L.fotoMostrable(Object.assign({}, FOTO, { licencia: '' })), false);
  assert.strictEqual(L.fotoMostrable(Object.assign({}, FOTO, { archivo: null })), false);
  assert.strictEqual(L.fotoMostrable(Object.assign({}, FOTO, { paginaArchivo: '' })), false);
});

test('el estado manda: con todos los campos pero pendiente, no se muestra', () => {
  assert.strictEqual(L.fotoMostrable(Object.assign({}, FOTO, { estado: 'pendiente' })), false);
});
