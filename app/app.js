"use strict";
/* Aves del Odiel — lógica de la aplicación.
   Fichero externo a propósito: la CSP del sitio es script-src 'self',
   sin 'unsafe-inline'. Sigue siendo una sola página sin dependencias. */
/* ============================================================================
   Aves del Odiel — lógica de la aplicación
   Sin dependencias. Todo el estado del cuaderno vive en el dispositivo.
   ========================================================================= */

/* --- utilidades ----------------------------------------------------------- */
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
               'septiembre','octubre','noviembre','diciembre'];
const MES_C = ['E','F','M','A','M','J','J','A','S','O','N','D'];
const TZ = 'Europe/Madrid';

const cap = s => s ? s[0].toUpperCase() + s.slice(1) : s;
const dosD = n => String(n).padStart(2, '0');

function el(tag, attrs = {}, ...hijos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else if (k === 'html') n.innerHTML = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else if (k === 'dataset') Object.assign(n.dataset, v);
    else n.setAttribute(k, v);
  }
  for (const h of hijos.flat()) if (h !== null && h !== undefined && h !== false)
    n.append(h.nodeType ? h : document.createTextNode(String(h)));
  return n;
}
const vaciar = n => { while (n.firstChild) n.removeChild(n.firstChild); return n; };

/** Fecha/hora locales de Huelva, independientes del reloj del dispositivo. */
function ahoraLocal() {
  const p = new Intl.DateTimeFormat('es-ES', {
    timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date()).reduce((a, x) => (a[x.type] = x.value, a), {});
  const h = p.hour === '24' ? '00' : p.hour;   // hourCycle h23 devuelve '24' en algunos motores
  return { fecha: `${p.year}-${p.month}-${p.day}`, hora: `${h}:${p.minute}`,
           mes: Number(p.month) - 1, dia: Number(p.day) };
}
const minutos = hhmm => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m; };
function dur(min) {
  if (min < 0) min = -min;
  const h = Math.floor(min / 60), m = min % 60;
  return h ? `${h} h ${dosD(m)} min` : `${m} min`;
}

/* --- almacenamiento ------------------------------------------------------- */
/* localStorage: preferencias (síncrono, pequeño).  IndexedDB: salidas y cola. */
const Pref = {
  leer(k, def) { try { const v = localStorage.getItem('odiel.' + k); return v === null ? def : JSON.parse(v); }
                 catch { return def; } },
  esc(k, v) { try { localStorage.setItem('odiel.' + k, JSON.stringify(v)); } catch {} },
};

const DB = (() => {
  let p = null;
  const abrir = () => p || (p = new Promise((res, rej) => {
    const r = indexedDB.open('odiel', 1);
    r.onupgradeneeded = () => {
      const d = r.result;
      if (!d.objectStoreNames.contains('salidas')) d.createObjectStore('salidas', { keyPath: 'id' });
      if (!d.objectStoreNames.contains('cola'))    d.createObjectStore('cola',    { keyPath: 'id' });
      if (!d.objectStoreNames.contains('cache'))   d.createObjectStore('cache',   { keyPath: 'k' });
    };
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  }));
  const tx = async (store, modo, fn) => {
    const d = await abrir();
    return new Promise((res, rej) => {
      const t = d.transaction(store, modo), s = t.objectStore(store);
      const pet = fn(s);
      t.oncomplete = () => res(pet && 'result' in pet ? pet.result : undefined);
      t.onerror = () => rej(t.error);
    });
  };
  return {
    todo:   s => tx(s, 'readonly',  o => o.getAll()),
    obtener:(s, k) => tx(s, 'readonly',  o => o.get(k)),
    poner:  (s, v) => tx(s, 'readwrite', o => o.put(v)),
    borrar: (s, k) => tx(s, 'readwrite', o => o.delete(k)),
  };
})();

/* --- estado global -------------------------------------------------------- */
const E = {
  especies: [], grupos: [], zonas: [], puntos: [], mareas: null, sinonimos: null,
  salidas: [], cola: [],
  salida: null,                       // salida en curso
  vista: 'esperable',
  filtros: { mes: null, zona: null, marea: null, tamano: null, grupo: null },
  ubicacion: { estado: 'off', coords: null },
  mapa: { zoom: 1, centro: [-6.9, 37.3], capas: { observatorio: true, sendero: true, zona: true }, sel: null },
  pantalla: 'hoy',
  datosOk: false,
};
const porId = id => E.especies.find(e => e.id === id);
const zonaId = id => E.zonas.find(z => z.id === id);

/* --- carga de datos ------------------------------------------------------- */
async function traer(ruta) {
  const r = await fetch(ruta, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${ruta}: HTTP ${r.status}`);
  return r.json();
}
async function cargarDatos() {
  // Los datos incrustados permiten abrir el fichero sin servidor; los de disco mandan.
  const semilla = $('#datos-incrustados');
  if (semilla) aplicarDatos(JSON.parse(semilla.textContent));
  // Sobre file:// no hay fetch posible: con los datos incrustados ya basta.
  if (E.datosOk && !location.protocol.startsWith('http')) return;
  try {
    const [esp, zon, pun, mar, sin] = await Promise.all([
      traer('datos/especies.json'), traer('datos/zonas.json'), traer('datos/puntos.geojson'),
      traer('datos/mareas.json').catch(() => null), traer('datos/sinonimos.json').catch(() => null),
    ]);
    aplicarDatos({ especies: esp, zonas: zon, puntos: pun, mareas: mar, sinonimos: sin });
  } catch (err) {
    if (!E.datosOk) throw err;
    console.warn('[datos] se usan los incrustados:', err.message);
  }
}
function aplicarDatos(d) {
  if (d.especies) { E.especies = d.especies.especies; E.grupos = d.especies.grupos; E.metaEsp = d.especies; }
  if (d.zonas)    E.zonas = d.zonas.zonas;
  if (d.puntos)   E.puntos = d.puntos.features.map(f =>
                    ({ ...f.properties, lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] }));
  if (d.mareas)   E.mareas = d.mareas;
  if (d.sinonimos) E.sinonimos = d.sinonimos;
  E.datosOk = E.especies.length > 0;
}

/* --- tema ----------------------------------------------------------------- */
function ponerTema(t) {
  document.documentElement.dataset.tema = t;
  // El basemap lee sus colores del CSS, así que hay que reconstruir el estilo
  // al cambiar de modo. Si no, el mapa se queda en modo día dentro de una app
  // en modo noche, que en el campo es justo lo que no quieres.
  if (typeof mapa !== 'undefined' && mapa) { try { mapa.setStyle(estiloMapa()); } catch (e) { /* aún cargando */ } }
  Pref.esc('tema', t);
  $$('#aj-tema button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tema === t)));
  const c = { claro: '#EFEDE7', oscuro: '#14140F', exterior: '#ffffff' }[t];
  $('meta[name=theme-color]').setAttribute('content', c);
}

/* --- banda de estado ------------------------------------------------------ */
let bandaFijada = null;
function banda(txt, { aviso = false, accion = null, alPulsar = null, fijar = false } = {}) {
  const b = $('#banda'), bt = $('#banda-btn');
  if (!txt) { b.classList.remove('on'); bandaFijada = null; return; }
  if (bandaFijada && !fijar) return;         // no se pisa un aviso persistente
  $('#banda-txt').textContent = txt;
  b.classList.toggle('aviso', aviso);
  b.classList.add('on');
  bt.classList.toggle('oculto', !accion);
  if (accion) { bt.textContent = accion; bt.onclick = alPulsar; }
  if (fijar) bandaFijada = txt;
}
function repasarRed() {
  if (navigator.onLine) {
    if (bandaFijada) { bandaFijada = null; banda(null); }
    else banda(null);
    if (E.cola.length) banda(`${E.cola.length} reporte(s) en cola`, { accion: 'Enviar', alPulsar: vaciarCola });
  } else {
    banda('Sin conexión · trabajando con lo descargado', { fijar: true });
  }
}
const vibrar = ms => { try { navigator.vibrate && navigator.vibrate(ms); } catch {} };

/* --- brindis con deshacer ------------------------------------------------- */
let brindisT = null, brindisFn = null;
function brindis(txt, deshacer = null, ms = 5000) {
  clearTimeout(brindisT);
  $('#brindis-txt').textContent = txt;
  $('#brindis-btn').classList.toggle('oculto', !deshacer);
  brindisFn = deshacer;
  $('#brindis').classList.add('on');
  brindisT = setTimeout(() => { $('#brindis').classList.remove('on'); brindisFn = null; }, ms);
}
$('#brindis-btn').addEventListener('click', () => {
  if (brindisFn) brindisFn();
  brindisFn = null; clearTimeout(brindisT);
  $('#brindis').classList.remove('on');
});

/* --- navegación ----------------------------------------------------------- */
function ir(p, { porSistema = false } = {}) {
  E.pantalla = p;
  $$('.pantalla').forEach(s => s.classList.toggle('activa', s.id === 'p-' + p));
  $$('#tabs button').forEach(b => b.dataset.p === p
    ? b.setAttribute('aria-current', 'page') : b.removeAttribute('aria-current'));
  $('#main').scrollTop = 0;
  if (p === 'guia') pintarGuia();
  if (p === 'mapa') pintarMapa();
  if (p === 'cuaderno') pintarCuaderno();
  if (p === 'ajustes') pintarAjustes();
  if (p === 'hoy') pintarHoy();
  if (!porSistema) Pref.esc('pantalla', p);
}
$$('#tabs button').forEach(b => b.addEventListener('click', () => ir(b.dataset.p)));
/* --- mareas --------------------------------------------------------------- */
function estacionDe(zid) {
  const z = zonaId(zid) || E.zonas[0];
  const eid = (z && z.estacionMarea) || 'huelva-5';
  return E.mareas && E.mareas.estaciones ? E.mareas.estaciones[eid] : null;
}
function diaMarea(fecha, zid) {
  const est = estacionDe(zid);
  if (!est) return null;
  const d = est.dias.find(x => x.fecha === fecha);
  if (!d) return null;
  const z = zonaId(zid);
  const desfase = (z && typeof z.desfaseMinutos === 'number') ? z.desfaseMinutos : 0;
  // El desfase de la zona respecto al mareógrafo se aplica sobre la hora mostrada.
  return {
    ...d, estacion: est, desfase,
    eventos: d.eventos.map(e => {
      const m = (minutos(e.local) + desfase + 1440) % 1440;
      return { ...e, local: `${dosD(Math.floor(m / 60))}:${dosD(m % 60)}`, min: m };
    }),
  };
}
/** Días de predicción que quedan por delante. Menos de 1 = caducado. */
function diasRestantes() {
  const est = estacionDe(E.salida ? E.salida.zona : null);
  if (!est || !est.dias.length) return -1;
  const hoy = ahoraLocal().fecha;
  return est.dias.filter(d => d.fecha >= hoy).length;
}
function proximaMarea(zid) {
  const a = ahoraLocal(), d = diaMarea(a.fecha, zid);
  if (!d) return null;
  const m = minutos(a.hora);
  const sig = d.eventos.find(e => e.min >= m);
  return sig ? { ...sig, faltan: sig.min - m, dia: d } : { ...d.eventos[d.eventos.length - 1], faltan: null, dia: d, pasada: true };
}

/* --- probabilidad --------------------------------------------------------- */
const estadoMes = (esp, mes) => esp.meses[mes] ?? 0;
// Las que no tienen fenología no pueden entrar en ninguna afirmación sobre un
// mes concreto. Su matriz es doce unos, que no significa «está todo el año»
// sino «no se sabe»: colarlas en el cuaderno precargado de julio o en el
// filtro de «especies de este mes» sería inventarse el dato por la puerta de
// atrás, justo después de haber quitado el gráfico por lo mismo.
const sinFenologia = esp => !!esp.notaFenologia;
function esperables(mes, zid, marea) {
  return E.especies.filter(e => {
    if (sinFenologia(e)) return false;
    if (estadoMes(e, mes) < 1) return false;
    if (zid && !e.zonas.includes(zid)) return false;
    if (marea && marea !== 'indiferente' && e.marea !== 'indiferente' && e.marea !== marea) return false;
    return true;
  });
}

/* --- fragmentos reutilizables --------------------------------------------- */
function fenMini(esp) {
  // Sin dato no se dibuja nada. Doce barras iguales no dicen «no sé»: dicen
  // «está los doce meses», que para un colimbo chico es falso y además
  // contradice al texto de su propia ficha. Un hueco es más honesto que un
  // gráfico verosímil, y deja el sitio ocupado para que la lista no baile.
  const f = el('div', { class: 'fen mini', 'aria-hidden': 'true' });
  if (esp.notaFenologia) { f.classList.add('sin-dato'); return f; }
  esp.meses.forEach(m => f.append(el('i', { dataset: { m: String(m) } })));
  if (esp.confianza !== 'verificado') { f.style.opacity = '.55'; }
  return f;
}
function etEstatus(esp) { return esp.estatus.join(' + '); }

function filaEspecie(esp, { conMas = false, alPulsar = null } = {}) {
  const cont = el('button', { class: 'fila', type: 'button' });
  const mini = el('div', { class: 'miniatura' + (esp.foto.estado === 'pendiente' ? ' pend' : '') },
                  esp.foto.estado === 'pendiente' ? el('span', { text: 'FOTO PEND.' }) : el('span', { text: 'FOTO' }));
  const txt = el('div', { class: 'txt' },
    el('span', { class: 'nom', text: esp.nombre }),
    el('span', { class: 'sci' }, esp.cientifico, ' · ', el('span', { class: 'est', text: etEstatus(esp) })));
  cont.append(mini, txt, fenMini(esp));
  cont.addEventListener('click', () => (alPulsar || abrirFicha)(esp));
  if (!conMas) return cont;
  const caja = el('div', { class: 'fila', style: 'padding:0;border:none;min-height:0' });
  cont.style.borderBottom = 'none';
  cont.style.flex = '1';
  const puesto = !!(E.salida && E.salida.avistamientos.some(a => a.especie === esp.id));
  const mas = el('button', {
    class: 'mas' + (puesto ? ' puesto' : ''), type: 'button',
    'aria-label': `Añadir ${esp.nombre} al cuaderno`, text: puesto ? '✓' : '+',
    onclick: ev => { ev.stopPropagation(); anadirASalida(esp); mas.className = 'mas puesto'; mas.textContent = '✓'; },
  });
  const env = el('div', { style: 'display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--linea)' }, cont, mas);
  return env;
}

/* --- pantalla HOY --------------------------------------------------------- */
function pintarHoy() {
  const a = ahoraLocal();
  const zid = (E.salida && E.salida.zona) || Pref.leer('zona', 'odiel');
  const z = zonaId(zid);
  $('#hoy-sub').textContent = `${a.dia} ${MESES[a.mes].slice(0, 3)} · ${z ? z.nombre : '—'}`;

  // --- marea
  const caja = $('#tarj-marea'), restan = diasRestantes();
  const d = diaMarea(a.fecha, zid), prox = proximaMarea(zid);
  caja.classList.toggle('caducada', !d || restan < 1);
  const est = estacionDe(zid);
  $('#marea-est').textContent = est ? (est.nombre || `estación ${est.codigo}`) : 'sin datos';
  $('#marea-datum').textContent = E.mareas ? E.mareas.datum : '—';

  if (d && prox) {
    $('#marea-tipo').textContent = prox.pasada ? 'última' : prox.tipo;
    $('#marea-hora').textContent = prox.local;
    $('#marea-alt').textContent = `${prox.altura.toFixed(2).replace('.', ',')} m`;
    $('#marea-cuenta').textContent = prox.faltan === null
      ? 'Sin más extremos hoy.'
      : `Faltan ${dur(prox.faltan)} para la ${prox.tipo}.`;
    const cont = vaciar($('#marea-hoy'));
    d.eventos.forEach(e => cont.append(el('div', { class: (e.tipo === 'bajamar' ? 'baja' : '') + (e.min < minutos(a.hora) ? ' pasado' : '') },
      el('b', { text: e.local }),
      el('small', { text: `${e.tipo} · ${e.altura.toFixed(2).replace('.', ',')} m` }))));
    const desf = d.desfase ? ` · desfase estimado de la zona +${d.desfase} min` : '';
    $('#marea-proc').textContent =
      `${E.mareas.fuente} · hora local (${E.mareas.zonaHoraria}) · descargado ${(E.mareas.generado || '').slice(0, 16).replace('T', ' ')}${desf}`;
  } else {
    $('#marea-tipo').textContent = '—'; $('#marea-hora').textContent = '—';
    $('#marea-alt').textContent = ''; vaciar($('#marea-hoy'));
    $('#marea-cuenta').textContent = restan < 1
      ? 'Las predicciones descargadas se han agotado.' : 'No hay datos para hoy.';
    $('#marea-proc').textContent = E.mareas ? `Última descarga: ${(E.mareas.generado || '').slice(0, 16).replace('T', ' ')}` : '';
  }

  // --- probabilidad y destacadas
  const esp = esperables(a.mes, zid, null);
  const alta = esp.filter(e => estadoMes(e, a.mes) >= 2);
  const cria = esp.filter(e => estadoMes(e, a.mes) === 3);
  $('#hoy-n').textContent = alta.length;
  $('#hoy-n-sub').textContent = `de ${E.especies.length} en la guía · ${cria.length} en cría`;
  const lista = vaciar($('#hoy-destacadas'));
  alta.slice().sort((x, y) => (x.foto.estado === 'pendiente') - (y.foto.estado === 'pendiente'))
      .slice(0, 4).forEach(e => lista.append(filaEspecie(e)));
  if (!alta.length) lista.append(el('p', { class: 'proc', text: 'Nada con probabilidad alta este mes en esta zona.' }));
}

/* --- pantalla GUÍA -------------------------------------------------------- */
const ETIQ_TAM = { pequeno: 'Pequeña', mediano: 'Mediana', grande: 'Grande' };
const ETIQ_MAREA = { bajamar: 'Bajamar', pleamar: 'Pleamar', indiferente: 'Indiferente' };
function etiquetaFiltro(k, v) {
  if (k === 'mes') return cap(MESES[v]);
  if (k === 'zona') return (zonaId(v) || {}).nombre || v;
  if (k === 'marea') return ETIQ_MAREA[v] || v;
  if (k === 'tamano') return ETIQ_TAM[v] || v;
  if (k === 'grupo') return (E.grupos.find(g => g.id === v) || {}).nombre || v;
  return v;
}
function aplicaFiltros(omitir = null) {
  const f = E.filtros;
  return E.especies.filter(e => {
    if (f.mes !== null && omitir !== 'mes' && (sinFenologia(e) || estadoMes(e, f.mes) < 1)) return false;
    if (f.zona && omitir !== 'zona' && !e.zonas.includes(f.zona)) return false;
    if (f.marea && omitir !== 'marea' && f.marea !== 'indiferente'
        && e.marea !== 'indiferente' && e.marea !== f.marea) return false;
    if (f.tamano && omitir !== 'tamano' && e.tamano !== f.tamano) return false;
    if (f.grupo && omitir !== 'grupo' && e.grupo !== f.grupo) return false;
    return true;
  });
}
function pintarGuia() {
  const chips = vaciar($('#guia-chips'));
  Object.entries(E.filtros).forEach(([k, v]) => {
    if (v === null || v === undefined) return;
    chips.append(el('button', { class: 'chip', type: 'button', onclick: () => { E.filtros[k] = null; pintarGuia(); } },
      etiquetaFiltro(k, v), el('span', { class: 'x', text: '✕' })));
  });
  chips.append(el('button', { class: 'chip add', type: 'button', onclick: () => abrirHoja('h-filtros') }, '+ Filtro'));

  const res = aplicaFiltros();
  const activos = Object.entries(E.filtros).filter(([, v]) => v !== null && v !== undefined);
  $('#guia-sub').textContent = activos.length ? `Filtrado · ${res.length} especies` : `${res.length} especies`;

  // Al filtrar por mes desaparecen las que no tienen fenología. Callárselo
  // haría pensar que no existen; decirlo cuesta una línea.
  const ocultas = E.filtros.mes !== null ? E.especies.filter(sinFenologia).length : 0;
  $('#guia-sinfen').textContent = ocultas
    ? `${ocultas} especies sin fenología no se muestran al filtrar por mes.` : '';
  $('#guia-sinfen').classList.toggle('oculto', !ocultas);

  const cont = vaciar($('#guia-lista'));
  $('#guia-vacia').classList.toggle('oculto', res.length > 0);
  $('#guia-lista').classList.toggle('oculto', res.length === 0);

  if (!res.length) {
    // Propone quitar el filtro concreto que vacía la lista, con el recuento.
    let mejor = null;
    for (const [k] of activos) {
      const n = aplicaFiltros(k).length;
      if (n > 0 && (!mejor || n > mejor.n)) mejor = { k, n };
    }
    $('#guia-vacia-txt').textContent = mejor
      ? `Con estos filtros no queda ninguna especie. Sin el filtro «${etiquetaFiltro(mejor.k, E.filtros[mejor.k])}» quedarían ${mejor.n}.`
      : 'Con estos filtros no queda ninguna especie.';
    const b = $('#btn-quitar-uno');
    b.classList.toggle('oculto', !mejor);
    if (mejor) { b.textContent = `Quitar «${etiquetaFiltro(mejor.k, E.filtros[mejor.k])}» → ${mejor.n}`;
                 b.onclick = () => { E.filtros[mejor.k] = null; pintarGuia(); }; }
    return;
  }
  E.grupos.forEach(g => {
    const dentro = res.filter(e => e.grupo === g.id);
    if (!dentro.length) return;
    const sec = el('div', { class: 'grupo' },
      el('h2', {}, el('b', { text: g.nombre }), el('span', { text: String(dentro.length) })));
    const lista = el('div', { class: 'lista' });
    dentro.forEach(e => lista.append(filaEspecie(e, { conMas: !!E.salida })));
    sec.append(lista);
    cont.append(sec);
  });
}
$('#btn-quitar-todos').addEventListener('click', () => {
  E.filtros = { mes: null, zona: null, marea: null, tamano: null, grupo: null }; pintarGuia();
});
function pintarHojaFiltros() {
  const a = ahoraLocal();
  const grupos = [
    ['hf-mes', 'mes', MESES.map((m, i) => [i, cap(m)])],
    ['hf-zona', 'zona', E.zonas.map(z => [z.id, z.nombre])],
    ['hf-marea', 'marea', [['bajamar', 'Bajamar'], ['pleamar', 'Pleamar'], ['indiferente', 'Indiferente']]],
    ['hf-tam', 'tamano', [['pequeno', 'Pequeña'], ['mediano', 'Mediana'], ['grande', 'Grande']]],
    ['hf-grupo', 'grupo', E.grupos.map(g => [g.id, g.nombre])],
  ];
  grupos.forEach(([id, clave, ops]) => {
    const c = vaciar($('#' + id));
    ops.forEach(([v, et]) => c.append(el('button', {
      class: 'chip' + (E.filtros[clave] === v ? ' on' : ''), type: 'button',
      onclick: () => { E.filtros[clave] = E.filtros[clave] === v ? null : v; pintarHojaFiltros(); pintarGuia(); },
    }, et)));
  });
}
/* --- hojas y capas (profundidad máxima 2) --------------------------------- */
let hojaAbierta = null, capaAbierta = null;
function abrirHoja(id) {
  cerrarHoja();
  hojaAbierta = $('#' + id);
  hojaAbierta.classList.add('on');
  $('#velo').classList.add('on');
  if (id === 'h-filtros') pintarHojaFiltros();
  if (id === 'h-reporte') reporteAbiertoEn = Date.now();
}
function cerrarHoja() {
  if (!hojaAbierta) return;
  hojaAbierta.classList.remove('on');
  hojaAbierta.style.transform = '';
  hojaAbierta = null;
  if (!capaAbierta) $('#velo').classList.remove('on');
}
function abrirCapa(id) { capaAbierta = $('#' + id); capaAbierta.classList.add('on'); }
function cerrarCapa() {
  if (!capaAbierta) return;
  capaAbierta.classList.remove('on');
  capaAbierta.style.transform = '';
  capaAbierta = null;
}
$('#velo').addEventListener('click', cerrarHoja);
$$('[data-cerrar-hoja]').forEach(b => b.addEventListener('click', cerrarHoja));
$$('[data-cerrar-capa]').forEach(b => b.addEventListener('click', cerrarCapa));
// «Atrás» del sistema cierra el detalle; nunca deshace un conteo.
history.replaceState({ n: 0 }, '');
window.addEventListener('popstate', () => {
  if (capaAbierta) { cerrarCapa(); history.pushState({ n: 1 }, ''); }
  else if (hojaAbierta) { cerrarHoja(); history.pushState({ n: 1 }, ''); }
});
history.pushState({ n: 1 }, '');

/* Arrastre hacia abajo para cerrar hojas y capas. */
function arrastrable(nodo, asa, cerrar) {
  let y0 = null, dy = 0;
  asa.addEventListener('pointerdown', ev => {
    if (ev.pointerType === 'mouse' && ev.button !== 0) return;
    y0 = ev.clientY; dy = 0; nodo.classList.add('arrastrando');
    asa.setPointerCapture(ev.pointerId);
  });
  asa.addEventListener('pointermove', ev => {
    if (y0 === null) return;
    dy = Math.max(0, ev.clientY - y0);
    nodo.style.transform = `translateY(${dy}px)`;
  });
  const fin = () => {
    if (y0 === null) return;
    nodo.classList.remove('arrastrando');
    nodo.style.transform = '';
    if (dy > 90) cerrar();
    y0 = null;
  };
  asa.addEventListener('pointerup', fin);
  asa.addEventListener('pointercancel', fin);
}
$$('.hoja').forEach(h => arrastrable(h, $('[data-arrastre]', h), cerrarHoja));
$$('.capa').forEach(c => { const a = $('[data-arrastre]', c); if (a) arrastrable(c, a, cerrarCapa); });

/* --- ficha de especie ----------------------------------------------------- */
let fichaActual = null;
function abrirFicha(esp) {
  fichaActual = esp;
  $('#cf-nom').textContent = esp.nombre;
  $('#cf-sci').textContent = `${esp.cientifico} · ${etEstatus(esp)}`;

  const foto = $('#cf-foto');
  vaciar(foto);
  if (esp.foto.estado === 'pendiente') {
    foto.className = 'foto pendiente';
    const sin = E.sinonimos && E.sinonimos.entradas.find(s => s.id === esp.id);
    const cat = encodeURIComponent((sin && sin.categoriaCommons) || esp.cientifico);
    foto.append(el('a', {
      class: 'et', target: '_blank', rel: 'noopener',
      href: `https://commons.wikimedia.org/w/index.php?search=deepcategory%3A%22${cat}%22&ns6=1`,
      style: 'text-decoration:none',
    }, 'Foto pendiente', el('br'), el('span', { style: 'font-weight:400;text-transform:none;letter-spacing:0', text: 'Buscar en Commons ↗' })));
    $('#cf-credito').textContent = sin && !sin.commonsVerificado
      ? 'Categoría de Commons por verificar.'
      : (sin ? `Categoría verificada: ${sin.categoriaCommons}${sin.archivos ? ` · ${sin.archivos} archivos`
         : (sin.subcategorias ? ` · ${sin.subcategorias} subcategorías` : '')}` : '');
    $('#cf-propon').classList.remove('oculto');
  } else {
    foto.className = 'foto';
    foto.append(el('img', { src: `fotos/${esp.foto.archivo}`, alt: esp.nombre, style: 'width:100%;height:100%;object-fit:cover' }));
    $('#cf-credito').textContent = `${esp.foto.autor} · ${esp.foto.licencia}`;
    $('#cf-propon').classList.add('oculto');
  }

  const verificado = esp.confianza === 'verificado';
  const sinDato = !!esp.notaFenologia;
  $('#cf-fencaja').classList.toggle('estimada', !verificado);
  $('#cf-fencaja').classList.toggle('sin-dato', sinDato);
  $('#cf-marca').className = sinDato ? 'marca est' : (verificado ? 'marca ver' : 'marca est');
  $('#cf-marca').textContent = sinDato ? '— Sin fenología'
    : (verificado ? '✓ Fenología verificada' : '≈ Fenología estimada');
  // La marca es binaria, y con eso una matriz sacada de 789 listas de eBird se
  // leía igual que doce meses genéricos. Esta línea dice de dónde sale cada
  // una. Se prefirió a un tercer estado visual: la barra ya codifica cuatro
  // estados por altura y trama, y tres niveles de confianza encima son doce
  // combinaciones que aprender para leerla con el sol de cara.
  $('#cf-fenfuente').textContent = verificado
    ? 'Matriz transcrita del plan de la guía.'
    : (esp.fuenteFenologia || esp.notaFenologia || 'Presencia genérica, sin datos.');
  const fen = vaciar($('#cf-fen'));
  const mesHoy = ahoraLocal().mes;
  if (!sinDato) esp.meses.forEach((m, i) => fen.append(el('i', {
    dataset: { m: String(m) }, title: `${cap(MESES[i])}: ${['ausente', 'presente', 'máxima probabilidad', 'época de cría'][m]}`,
    style: i === mesHoy ? 'outline:2px solid var(--azul);outline-offset:1px' : null,
  })));

  $('#cf-ident').textContent = esp.identificacion;
  $('#cf-cond').textContent = esp.conducta;

  const conf = vaciar($('#cf-conf'));
  $('#cf-confsec').classList.toggle('oculto', !esp.confusiones.length);
  esp.confusiones.forEach(c => {
    const otra = porId(c.especie);
    conf.append(el('button', { class: 'conf', type: 'button', onclick: () => otra && abrirFicha(otra) },
      el('div', { class: 'txt' },
        el('span', { class: 'nom', text: otra ? otra.nombre : c.especie }),
        el('span', { class: 'cl', text: c.clave })),
      el('span', { class: 'fl', text: '→' })));
  });

  const dl = vaciar($('#cf-datos'));
  const filas = [
    ['Zonas', esp.zonas.map(z => (zonaId(z) || {}).nombre || z).join(' · ')],
    ['Hábitat', esp.habitat.join(' · ')],
    ['Marea óptima', ETIQ_MAREA[esp.marea]],
    ['Tamaño', ETIQ_TAM[esp.tamano]],
    ['Inglés', esp.ingles],
  ];
  filas.forEach(([k, v]) => { dl.append(el('dt', { text: k }), el('dd', { text: v })); });

  $('#cf-anadir').classList.toggle('oculto', !E.salida);
  abrirCapa('c-ficha');
  $('.capa-cuerpo', $('#c-ficha')).scrollTop = 0;
}
$('#cf-anadir').addEventListener('click', () => {
  if (!fichaActual) return;
  anadirASalida(fichaActual);
  cerrarCapa(); ir('cuaderno');
});
$('#cf-reportar').addEventListener('click', () => { abrirHoja('h-reporte'); });
$('#cf-proponer').addEventListener('click', () => { $('#hr-tipo').value = 'foto'; abrirHoja('h-reporte'); });

/* --- ficha de zona -------------------------------------------------------- */
let zonaActual = null;
function abrirZona(z) {
  zonaActual = z;
  $('#cz-nom').textContent = z.nombre;
  $('#cz-prot').textContent = z.proteccion;
  const av = vaciar($('#cz-avisos'));
  (z.avisos || []).forEach(a => av.append(el('div', {
    class: 'tarj', style: 'background:var(--azul-sup);border-color:var(--azul)' },
    el('span', { class: 'rot', style: 'color:var(--azul)', text: 'Aviso' }),
    el('p', { style: 'font-size:14px;margin-top:6px', text: a }))));
  if (z.autorizacion) av.append(el('div', { class: 'tarj', style: 'background:var(--alarma-sup);border-color:var(--alarma)' },
    el('span', { class: 'rot', style: 'color:var(--alarma)', text: 'Autorización' }),
    el('p', { style: 'font-size:14px;margin-top:6px', text: 'Algunos accesos de esta zona tienen cupo. Comprobar antes de ir.' })));
  $('#cz-ventana').textContent = z.ventana;
  $('#cz-itin').textContent = z.itinerario;
  const dl = vaciar($('#cz-marea'));
  const est = z.estacionMarea && E.mareas ? E.mareas.estaciones[z.estacionMarea] : null;
  [['Estación', est ? (est.nombre || `código ${est.codigo}`) : 'no aplica'],
   ['Marea óptima', ETIQ_MAREA[z.mareaOptima]],
   ['Desfase', z.desfaseMinutos === null || z.desfaseMinutos === undefined ? 'no aplica'
      : (z.desfaseMinutos ? `+${z.desfaseMinutos} min sobre el mareógrafo · estimado` : 'sin desfase')],
  ].forEach(([k, v]) => dl.append(el('dt', { text: k }), el('dd', { text: v })));

  const ps = vaciar($('#cz-puntos'));
  E.puntos.filter(p => p.zona === z.id).forEach(p => ps.append(el('button', {
    class: 'fila', type: 'button', style: 'min-height:56px',
    onclick: () => { E.mapa.sel = p.id; cerrarCapa(); ir('mapa'); },
  }, el('div', { class: 'txt' },
      el('span', { class: 'nom', text: p.nombre }),
      el('span', { class: 'sci', style: 'font-style:normal;font-family:var(--mono);font-size:10px;letter-spacing:.06em',
                   text: `${p.tipo.toUpperCase()} · marea ${p.mareaOptima}` })))));

  const es = vaciar($('#cz-esp'));
  const mes = ahoraLocal().mes;
  esperables(mes, z.id, null).filter(e => estadoMes(e, mes) >= 2).slice(0, 6)
    .forEach(e => es.append(filaEspecie(e)));
  abrirCapa('c-zona');
}
$('#cz-salida').addEventListener('click', () => {
  if (zonaActual) { Pref.esc('zona', zonaActual.id); cerrarCapa(); prepararSalida(zonaActual.id); }
});
/* --- salida: crear, anotar, cerrar ---------------------------------------- */
function prepararSalida(zid) {
  const z = zonaId(zid || Pref.leer('zona', 'odiel')) || E.zonas[0];
  $('#he-zona').textContent = z.nombre;
  $('#he-zona').dataset.id = z.id;
  const sel = vaciar($('#he-punto'));
  E.puntos.filter(p => p.zona === z.id)
    .forEach(p => sel.append(el('option', { value: p.id, text: p.nombre })));
  if (!sel.options.length) sel.append(el('option', { value: '', text: 'Sin punto concreto' }));
  const a = ahoraLocal(), prox = proximaMarea(z.id);
  const fase = prox ? prox.tipo : z.mareaOptima;
  const chips = vaciar($('#he-filtros'));
  [cap(MESES[a.mes]), z.nombre, cap(fase)].forEach(t => chips.append(el('span', { class: 'chip', text: t })));
  chips.dataset.mes = a.mes; chips.dataset.zona = z.id; chips.dataset.marea = fase;
  abrirHoja('h-empezar');
}
$('#he-cambiar').addEventListener('click', () => {
  const ids = E.zonas.map(z => z.id);
  const act = $('#he-zona').dataset.id;
  prepararSalida(ids[(ids.indexOf(act) + 1) % ids.length]);
});
$('#he-ok').addEventListener('click', () => {
  const a = ahoraLocal(), zid = $('#he-zona').dataset.id;
  const c = $('#he-filtros').dataset;
  const prox = proximaMarea(zid);
  E.salida = {
    id: `${a.fecha}-${a.hora.replace(':', '')}`,
    fecha: a.fecha, horaInicio: a.hora, horaFin: null,
    zona: zid, punto: $('#he-punto').value || null,
    coords: E.ubicacion.coords,
    marea: prox ? { fase: prox.tipo, hora: prox.local, altura: prox.altura,
                    origen: `portus-${(estacionDe(zid) || {}).codigo || '3329'}` } : null,
    meteo: {}, observadores: Pref.leer('observador', ''), notas: '',
    avistamientos: [],
  };
  // La Guía hereda los filtros de la salida.
  E.filtros = { mes: Number(c.mes), zona: c.zona, marea: c.marea, tamano: null, grupo: null };
  Pref.esc('zona', zid);
  Pref.esc('salida', E.salida);
  cerrarHoja();
  ir('cuaderno');           // la pestaña activa solo salta sola al empezar o cerrar salida
});

function anadirASalida(esp, n = 1) {
  if (!E.salida) { brindis('No hay ninguna salida en curso'); return; }
  let a = E.salida.avistamientos.find(x => x.especie === esp.id);
  if (!a) { a = { especie: esp.id, n: 0, exacto: true, plumaje: [], nota: '' }; E.salida.avistamientos.push(a); }
  a.n += n;
  guardarBorrador();
  if (E.pantalla === 'cuaderno') pintarCuaderno();
  brindis(`${esp.nombre} · ${a.exacto ? a.n : '~' + a.n}`);
}
const guardarBorrador = () => Pref.esc('salida', E.salida);

/* --- contador con pulsación larga ----------------------------------------- */
function controlConteo(esp, av) {
  const num = el('div', { class: 'num' + (av.n ? '' : ' cero'), role: 'button', tabindex: '0',
                          'aria-label': `${esp.nombre}: ${av.n}. Mantener pulsado para cambiar de modo` });
  const pinta = () => {
    num.textContent = (av.exacto ? '' : '~') + av.n;
    num.classList.toggle('cero', !av.n);
    fila.classList.toggle('estimando', !av.exacto);
  };
  const paso = () => (av.exacto ? 1 : 10);
  const menos = el('button', { type: 'button', 'aria-label': `Restar ${esp.nombre}`, text: '−',
    onclick: () => { av.n = Math.max(0, av.n - paso()); pinta(); guardarBorrador(); } });
  const mas = el('button', { type: 'button', 'aria-label': `Sumar ${esp.nombre}`, text: '+',
    onclick: () => { av.n += paso(); pinta(); guardarBorrador(); } });

  // Pulsación larga de 500 ms sobre el número: exacto ⇄ estimación. Con vibración.
  let t = null, movido = false;
  const abrir = () => {
    vibrar(18);
    num.classList.add('largo');
    $('#h-modo-t').textContent = esp.nombre;
    $$('#h-modo [data-modo]').forEach(b => {
      b.classList.toggle('pri', b.dataset.modo === (av.exacto ? 'exacto' : 'estimado'));
      b.onclick = () => {
        av.exacto = b.dataset.modo === 'exacto';   // el conteo no se toca: solo cambia el paso
        pinta(); guardarBorrador(); cerrarHoja(); num.classList.remove('largo');
      };
    });
    abrirHoja('h-modo');
  };
  num.addEventListener('pointerdown', () => { movido = false; t = setTimeout(abrir, 500); });
  num.addEventListener('pointermove', ev => {
    if (Math.abs(ev.movementY) > 6 || Math.abs(ev.movementX) > 6) { movido = true; clearTimeout(t); }
  });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(e =>
    num.addEventListener(e, () => { clearTimeout(t); num.classList.remove('largo'); }));
  num.addEventListener('keydown', ev => {
    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); abrir(); }
    if (ev.key === 'ArrowUp')   { ev.preventDefault(); av.n += paso(); pinta(); guardarBorrador(); }
    if (ev.key === 'ArrowDown') { ev.preventDefault(); av.n = Math.max(0, av.n - paso()); pinta(); guardarBorrador(); }
  });
  const fila = el('div', { class: 'cuenta-fila' },
    el('div', { class: 'txt' },
      el('span', { class: 'nom', style: 'font:600 15px/1.2 var(--sans);display:block', text: esp.nombre }),
      el('span', { class: 'sci', style: 'font:italic 12px/1.3 var(--serif);color:var(--mudo);display:block', text: esp.cientifico }),
      av.plumaje.length ? el('span', { class: 'plum', text: av.plumaje.join(' + ') }) : null),
    el('div', { class: 'ctl' }, menos, num, mas));
  pinta();
  return fila;
}

/* --- pantalla CUADERNO ---------------------------------------------------- */
function pintarCuaderno() {
  const hayS = !!E.salida;
  $('#cuad-curso').classList.toggle('oculto', !hayS);
  $('#cuad-hist').classList.toggle('oculto', hayS);
  hayS ? pintarCurso() : pintarHistorico();
}
function pintarCurso() {
  // La pista de la pulsación larga desaparece tras la tercera salida.
  $('#curso-pista').classList.toggle('oculto', E.salidas.length > 2);
  const s = E.salida, z = zonaId(s.zona), p = E.puntos.find(x => x.id === s.punto);
  const n = s.avistamientos.filter(a => a.n > 0).length;
  $('#curso-sub').textContent = `${p ? p.nombre : (z ? z.nombre : '')} · ${s.horaInicio} · ${n} especies`;
  const prox = proximaMarea(s.zona);
  $('#curso-marea').textContent = prox && prox.faltan !== null
    ? `${cap(prox.tipo)} ${prox.local} · faltan ${dur(prox.faltan)}`
    : (prox ? `Última marea del día: ${prox.tipo} ${prox.local}` : 'Sin datos de marea');

  const a = ahoraLocal();
  let lista;
  if (E.vista === 'anotadas') lista = s.avistamientos.filter(x => x.n > 0).map(x => porId(x.especie)).filter(Boolean);
  else if (E.vista === 'todas') lista = E.especies;
  else lista = esperables(a.mes, s.zona, s.marea ? s.marea.fase : null)
                 .sort((x, y) => estadoMes(y, a.mes) - estadoMes(x, a.mes));

  // Lo ya anotado sube arriba para no perderlo de vista.
  const puestos = new Set(s.avistamientos.filter(x => x.n > 0).map(x => x.especie));
  lista = lista.slice().sort((x, y) => (puestos.has(y.id) ? 1 : 0) - (puestos.has(x.id) ? 1 : 0));

  const cont = vaciar($('#curso-lista'));
  if (E.vista === 'esperable') cont.append(el('div', { class: 'rot', style: 'padding:2px 0 8px',
    text: `Esperable hoy aquí · precargado · ${lista.length}` }));
  if (!lista.length) cont.append(el('p', { class: 'proc', text: 'Nada que precargar con estos criterios. Prueba la vista «Todas».' }));
  lista.forEach(esp => {
    let av = s.avistamientos.find(x => x.especie === esp.id);
    if (!av) { av = { especie: esp.id, n: 0, exacto: true, plumaje: [], nota: '' }; s.avistamientos.push(av); }
    cont.append(controlConteo(esp, av));
  });
  // registros sin identificar
  (s.avistamientos.filter(x => x.sinIdentificar)).forEach(av => {
    cont.append(el('div', { class: 'cuenta-fila' },
      el('div', { class: 'txt' },
        el('span', { style: 'font:600 15px/1.2 var(--sans);display:block', text: 'Ave sin identificar' }),
        el('span', { style: 'font:400 12px/1.3 var(--sans);color:var(--mudo);display:block',
                     text: (av.sinIdentificar.rasgos || []).join(' · ') || 'sin rasgos' })),
      el('div', { class: 'ctl' }, el('div', { class: 'num', text: String(av.n) }))));
  });
}
$$('#curso-tabs button').forEach(b => b.addEventListener('click', () => {
  E.vista = b.dataset.vista;
  $$('#curso-tabs button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  pintarCurso();
}));

function pintarHistorico() {
  const cont = vaciar($('#hist-lista'));
  const vacio = !E.salidas.length;
  $('#hist-vacio').classList.toggle('oculto', !vacio);
  $('#btn-nueva-salida').classList.toggle('oculto', vacio);
  $('#hist-sub').textContent = vacio ? 'Sin salidas'
    : `${E.salidas.length} salida${E.salidas.length === 1 ? '' : 's'} · ${E.salidas.reduce((n, s) => n + s.avistamientos.filter(a => a.n > 0).length, 0)} registros`;
  E.salidas.slice().sort((a, b) => b.id.localeCompare(a.id)).forEach(s => cont.append(filaSalida(s)));
}
function filaSalida(s) {
  const z = zonaId(s.zona), p = E.puntos.find(x => x.id === s.punto);
  const n = s.avistamientos.filter(a => a.n > 0).length;
  const cara = el('button', { class: 'fila', type: 'button', style: 'min-height:74px',
    onclick: () => abrirDetalleSalida(s) },
    el('div', { class: 'txt' },
      el('span', { class: 'nom', text: `${s.fecha.split('-').reverse().join('/')} · ${p ? p.nombre : (z ? z.nombre : '—')}` }),
      el('span', { class: 'sci', style: 'font-style:normal;font-family:var(--mono);font-size:11px',
        text: `${s.horaInicio}–${s.horaFin || '—'} · ${n} especies${s.marea ? ` · ${s.marea.fase} ${s.marea.hora}` : ''}` })),
    el('span', { class: 'fl', style: 'font:700 18px/1 var(--sans);color:var(--mudo)', text: '›' }));
  return deslizable(cara, 'Exportar', () => exportar('csv', s));
}
/* Arrastre hacia la izquierda sobre una fila: acción lateral. */
function deslizable(cara, etiqueta, alSoltar, rojo = false) {
  const caja = el('div', { class: 'deslizable' },
    el('div', { class: 'accion' + (rojo ? ' rojo' : ''), text: etiqueta }),
    el('div', { class: 'cara' }, cara));
  const c = $('.cara', caja);
  let x0 = null, dx = 0;
  c.addEventListener('pointerdown', ev => { x0 = ev.clientX; dx = 0; });
  c.addEventListener('pointermove', ev => {
    if (x0 === null) return;
    dx = Math.min(0, ev.clientX - x0);
    if (dx < -6) { c.style.transition = 'none'; c.style.transform = `translateX(${Math.max(dx, -104)}px)`; }
  });
  const fin = () => {
    if (x0 === null) return;
    c.style.transition = ''; c.style.transform = '';
    if (dx < -70) { vibrar(12); alSoltar(); }
    x0 = null;
  };
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(e => c.addEventListener(e, fin));
  return caja;
}
$('#btn-nueva-salida').addEventListener('click', () => prepararSalida());
$('#btn-vacio-empezar').addEventListener('click', () => prepararSalida());
$('#btn-vacio-importar').addEventListener('click', () => $('#fichero-importar').click());
$('#btn-empezar').addEventListener('click', () => prepararSalida());
$('#btn-sinid').addEventListener('click', () => abrirSinId());

/* --- cerrar y guardar ----------------------------------------------------- */
$('#btn-cerrar-salida').addEventListener('click', () => {
  const s = E.salida, a = ahoraLocal();
  s.horaFin = a.hora;
  const dl = vaciar($('#hc-resumen'));
  const anot = s.avistamientos.filter(x => x.n > 0);
  const z = zonaId(s.zona), p = E.puntos.find(x => x.id === s.punto);
  [['Duración', dur(minutos(s.horaFin) - minutos(s.horaInicio))],
   ['Especies', String(anot.length)],
   ['Ejemplares', String(anot.reduce((n, x) => n + x.n, 0))],
   ['Zona', `${z ? z.nombre : '—'}${p ? ' · ' + p.nombre : ''}`],
   ['Marea', s.marea ? `${s.marea.fase} ${s.marea.hora} · ${s.marea.altura.toFixed(2).replace('.', ',')} m` : '—'],
  ].forEach(([k, v]) => dl.append(el('dt', { text: k }), el('dd', { text: v })));
  const reg = vaciar($('#hc-registros'));
  if (!anot.length) reg.append(el('p', { class: 'proc', text: 'Ningún registro todavía.' }));
  anot.forEach(av => {
    const esp = porId(av.especie);
    const cara = el('div', { class: 'fila', style: 'min-height:52px' },
      el('div', { class: 'txt' }, el('span', { class: 'nom',
        text: esp ? esp.nombre : 'Ave sin identificar' })),
      el('span', { style: 'font:700 15px/1 var(--mono)', text: (av.exacto ? '' : '~') + av.n }));
    reg.append(deslizable(cara, 'Borrar', () => {
      const copia = { ...av };
      av.n = 0; guardarBorrador(); $('#btn-cerrar-salida').click();
      brindis('Registro borrado', () => { Object.assign(av, copia); guardarBorrador(); $('#btn-cerrar-salida').click(); });
    }, true));
  });
  abrirHoja('h-cerrar');
});
$('#hc-guardar').addEventListener('click', async () => {
  const s = E.salida;
  s.avistamientos = s.avistamientos.filter(a => a.n > 0 || a.sinIdentificar);
  await DB.poner('salidas', s);
  E.salidas = await DB.todo('salidas');
  E.salida = null; Pref.esc('salida', null);
  cerrarHoja();
  const dl = vaciar($('#hg-resumen'));
  const z = zonaId(s.zona);
  [['Fecha', s.fecha.split('-').reverse().join('/')],
   ['Horario', `${s.horaInicio}–${s.horaFin}`],
   ['Zona', z ? z.nombre : '—'],
   ['Especies', String(s.avistamientos.length)],
  ].forEach(([k, v]) => dl.append(el('dt', { text: k }), el('dd', { text: v })));
  $$('#h-guardada [data-exp]').forEach(b => b.onclick = () => exportar(b.dataset.exp, s));
  abrirHoja('h-guardada');           // sin diálogo de éxito: el resumen ES la confirmación
  ir('cuaderno');
  if (E.salidas.length % 10 === 0) brindis('Van 10 salidas. Buen momento para exportar una copia.', null, 7000);
});

function abrirDetalleSalida(s) {
  const z = zonaId(s.zona), p = E.puntos.find(x => x.id === s.punto);
  $('#cs-nom').textContent = s.fecha.split('-').reverse().join('/');
  $('#cs-sub').textContent = `${p ? p.nombre : (z ? z.nombre : '')} · ${s.horaInicio}–${s.horaFin || '—'}`;
  const dl = vaciar($('#cs-resumen'));
  [['Duración', s.horaFin ? dur(minutos(s.horaFin) - minutos(s.horaInicio)) : '—'],
   ['Marea', s.marea ? `${s.marea.fase} ${s.marea.hora} · ${s.marea.altura.toFixed(2).replace('.', ',')} m` : '—'],
   ['Origen marea', s.marea ? s.marea.origen : '—'],
   ['Coordenadas', s.coords ? s.coords.map(n => n.toFixed(4)).join(', ') : 'no registradas'],
  ].forEach(([k, v]) => dl.append(el('dt', { text: k }), el('dd', { text: v })));
  const reg = vaciar($('#cs-registros'));
  s.avistamientos.forEach(av => {
    const esp = porId(av.especie);
    reg.append(el('div', { class: 'fila', style: 'min-height:52px' },
      el('div', { class: 'txt' },
        el('span', { class: 'nom', text: esp ? esp.nombre : 'Ave sin identificar' }),
        av.nota ? el('span', { class: 'sci', style: 'font-style:normal', text: av.nota }) : null),
      el('span', { style: 'font:700 15px/1 var(--mono)', text: (av.exacto === false ? '~' : '') + av.n })));
  });
  $$('#c-salida [data-exp]').forEach(b => b.onclick = () => exportar(b.dataset.exp, s));
  $('#cs-borrar').onclick = async () => {
    await DB.borrar('salidas', s.id);
    E.salidas = await DB.todo('salidas');
    cerrarCapa(); pintarCuaderno();
    brindis('Salida borrada', async () => { await DB.poner('salidas', s); E.salidas = await DB.todo('salidas'); pintarCuaderno(); });
  };
  abrirCapa('c-salida');
}
/* --- exportación (se genera en el dispositivo, sin red) -------------------- */
function bajar(nombre, texto, mime) {
  const url = URL.createObjectURL(new Blob(['﻿' + texto], { type: mime + ';charset=utf-8' }));
  const a = el('a', { href: url, download: nombre });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
const csvCampo = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
function aCSV(salidas) {
  const cab = ['salida_id', 'fecha', 'hora_inicio', 'hora_fin', 'zona', 'punto', 'lat', 'lon',
               'marea_fase', 'marea_hora', 'marea_altura', 'especie_id', 'nombre', 'cientifico',
               'n', 'exacto', 'plumaje', 'nota'];
  const filas = [cab.map(csvCampo).join(',')];
  salidas.forEach(s => {
    const z = zonaId(s.zona), p = E.puntos.find(x => x.id === s.punto);
    s.avistamientos.forEach(a => {
      const e = porId(a.especie);
      filas.push([s.id, s.fecha, s.horaInicio, s.horaFin || '', z ? z.nombre : s.zona, p ? p.nombre : '',
        s.coords ? s.coords[1] : '', s.coords ? s.coords[0] : '',
        s.marea ? s.marea.fase : '', s.marea ? s.marea.hora : '', s.marea ? s.marea.altura : '',
        a.especie, e ? e.nombre : 'Ave sin identificar', e ? e.cientifico : '',
        a.n, a.exacto === false ? 'estimado' : 'exacto',
        (a.plumaje || []).join(' '), a.nota || ''].map(csvCampo).join(','));
    });
  });
  return filas.join('\r\n');
}
function exportar(formato, una = null) {
  const datos = una ? [una] : E.salidas;
  if (!datos.length) { brindis('No hay nada que exportar'); return; }
  const sello = una ? una.id : ahoraLocal().fecha;
  if (formato === 'csv') bajar(`odiel-${sello}.csv`, aCSV(datos), 'text/csv');
  else bajar(`odiel-${sello}.json`, JSON.stringify({
    app: 'pajaritos.josearcos.me', exportado: new Date().toISOString(),
    versionDatos: (E.metaEsp || {}).version || null, salidas: datos,
  }, null, 1), 'application/json');
  brindis(`Exportado ${formato.toUpperCase()} · ${datos.length} salida(s)`);
}
$$('[data-exp]').forEach(b => { if (!b.closest('.hoja') && !b.closest('.capa')) b.addEventListener('click', () => exportar(b.dataset.exp)); });
$('#btn-importar').addEventListener('click', () => $('#fichero-importar').click());
$('#fichero-importar').addEventListener('change', async ev => {
  const f = ev.target.files[0]; if (!f) return;
  try {
    const t = await f.text();
    const d = JSON.parse(t);
    const ss = Array.isArray(d) ? d : d.salidas;
    if (!Array.isArray(ss)) throw new Error('formato');
    for (const s of ss) await DB.poner('salidas', s);
    E.salidas = await DB.todo('salidas');
    pintarCuaderno(); pintarAjustes();
    brindis(`Importadas ${ss.length} salidas`);
  } catch { brindis('No se ha podido leer ese archivo'); }
  ev.target.value = '';
});

/* --- ave sin identificar (croquis) ---------------------------------------- */
const RASGOS = ['Limícola', 'Rapaz', 'Anátida', 'Gaviota', 'Garza', 'Paseriforme',
                'Pequeña', 'Mediana', 'Grande', 'En el agua', 'En el fango', 'En vuelo',
                'Posada', 'Pico largo', 'Pico curvado', 'Patas largas', 'Obispillo blanco', 'Bando'];
let siRasgos = new Set(), siN = 1, trazos = [], trazo = null, ctx = null;
function abrirSinId() {
  if (!E.salida) { brindis('Empieza una salida antes'); return; }
  siRasgos = new Set(); siN = 1; trazos = [];
  $('#si-num').textContent = '1'; $('#si-nota').value = '';
  const c = vaciar($('#si-rasgos'));
  RASGOS.forEach(r => c.append(el('button', { class: 'chip', type: 'button', onclick: e => {
    siRasgos.has(r) ? siRasgos.delete(r) : siRasgos.add(r);
    e.currentTarget.classList.toggle('on', siRasgos.has(r));
  } }, r)));
  abrirCapa('c-sinid');
  requestAnimationFrame(prepararLienzo);
}
function prepararLienzo() {
  const cv = $('#croquis'), r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  cv.width = Math.max(1, r.width * dpr); cv.height = Math.max(1, r.height * dpr);
  ctx = cv.getContext('2d'); ctx.scale(dpr, dpr);
  repintarCroquis();
}
function repintarCroquis() {
  if (!ctx) return;
  const cv = $('#croquis'), r = cv.getBoundingClientRect();
  ctx.clearRect(0, 0, r.width, r.height);
  ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--tinta').trim() || '#1A1A18';
  ctx.lineWidth = 2.4; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  trazos.forEach(t => {
    ctx.beginPath();
    t.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.stroke();
  });
}
(() => {
  const cv = $('#croquis');
  const pos = ev => { const r = cv.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top]; };
  cv.addEventListener('pointerdown', ev => {
    ev.preventDefault(); cv.setPointerCapture(ev.pointerId);
    trazo = [pos(ev)]; trazos.push(trazo);
  });
  cv.addEventListener('pointermove', ev => { if (!trazo) return; trazo.push(pos(ev)); repintarCroquis(); });
  ['pointerup', 'pointercancel'].forEach(e => cv.addEventListener(e, () => { trazo = null; }));
})();
$('#croquis-deshacer').addEventListener('click', () => { trazos.pop(); repintarCroquis(); });
$('#croquis-borrar').addEventListener('click', () => { trazos = []; repintarCroquis(); });
$('#si-mas').addEventListener('click', () => { siN++; $('#si-num').textContent = siN; });
$('#si-menos').addEventListener('click', () => { siN = Math.max(1, siN - 1); $('#si-num').textContent = siN; });
$('#si-guardar').addEventListener('click', () => {
  const croquis = trazos.length ? $('#croquis').toDataURL('image/png') : null;
  E.salida.avistamientos.push({
    especie: '?', n: siN, exacto: true, plumaje: [], nota: $('#si-nota').value.trim(),
    sinIdentificar: { rasgos: [...siRasgos], croquis },
  });
  guardarBorrador(); cerrarCapa(); pintarCuaderno();
  brindis('Guardada para resolver en casa');
});

/* --- mapa: MapLibre + PMTiles ---------------------------------------------
   Sustituye al esquema por coordenadas. El basemap es el .pmtiles de Huelva
   servido desde el propio NAS con peticiones Range: sin claves, sin terceros
   y sin que nadie sepa dónde mira el usuario.

   LAS LIBRERÍAS SE CARGAN AL ABRIR EL MAPA, NO AL ARRANCAR. Son 388 KB
   comprimidos, y quien abre la app para mirar la marea no tiene por qué
   pagarlos. El Service Worker sí las precarga, así que en el campo ya están
   en caché aunque no haya red: el coste se paga en casa, con wifi, y el
   beneficio se cobra en la marisma.

   El build `-csp` de MapLibre existe justamente para cabeceras como la
   nuestra: script clásico, sin eval, y el worker declarado a mano desde el
   propio origen con setWorkerUrl. */
const MAPLIBRE = {
  css: 'vendor/maplibre-gl-5.24.0.css',
  js: 'vendor/maplibre-gl-5.24.0-csp.js',
  worker: 'vendor/maplibre-gl-5.24.0-csp-worker.js',
  pmtiles: 'vendor/pmtiles-4.5.0.js',
  basemap: 'mapas/actual.pmtiles',
};
let cargando = null;
function cargarMapLibre() {
  if (cargando) return cargando;
  const meter = (tag, at) => new Promise((ok, mal) => {
    const n = el(tag, { ...at, onload: () => ok(), onerror: () => mal(new Error(at.src || at.href)) });
    document.head.append(n);
  });
  cargando = (async () => {
    await meter('link', { rel: 'stylesheet', href: MAPLIBRE.css });
    await meter('script', { src: MAPLIBRE.js });
    await meter('script', { src: MAPLIBRE.pmtiles });
    maplibregl.setWorkerUrl(MAPLIBRE.worker);          // CSP: nada de blob:
    maplibregl.addProtocol('pmtiles', new pmtiles.Protocol().tile);
  })();
  return cargando;
}

/* Colores del mapa = colores de la app. Se leen del CSS en vez de repetirlos
   aquí, para que los tres modos de pantalla (día, exterior, noche) arrastren
   también al basemap y no quede una isla con su propia paleta. */
function tinta(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }

/* Estilo mínimo, escrito a mano contra lo que el .pmtiles trae de verdad en
   el Odiel: landuse/wetland es la marisma, water/basin son las salinas y
   roads/footway son los senderos. Un tema genérico traería comercios,
   gasolineras y etiquetas urbanas, que aquí son ruido y además pesan. */
function estiloMapa() {
  const papel = tinta('--papel'), relleno = tinta('--relleno'), linea = tinta('--linea');
  const linea2 = tinta('--linea-2'), texto = tinta('--tinta-2'), mudo = tinta('--mudo');
  const azul = tinta('--azul'), verde = tinta('--ok');
  const fuente = { type: 'vector', url: `pmtiles://${MAPLIBRE.basemap}`, attribution: '© OpenStreetMap · Protomaps' };
  const capa = (id, tipo, capaFuente, filtro, paint, extra = {}) =>
    ({ id, type: tipo, source: 'basemap', 'source-layer': capaFuente, ...(filtro ? { filter: filtro } : {}), paint, ...extra });

  return {
    version: 8,
    // Sin `glyphs`. La clave no admite null --el estilo entero se rechaza con
    // «glyphs: string expected, null found» y el mapa se queda en blanco-- y
    // omitirla es lo correcto aquí: no hay capas de texto porque las etiquetas
    // las ponen los marcadores HTML, con la tipografía de la app. El precio es
    // que el basemap no rotula ríos ni parajes; si algún día hace falta,
    // Protomaps publica un paquete de glifos que habría que autoalojar.
    sources: { basemap: fuente },
    layers: [
      { id: 'fondo', type: 'background', paint: { 'background-color': papel } },
      capa('tierra', 'fill', 'earth', null, { 'fill-color': relleno }),

      // Vegetación y arena, muy apagadas: son contexto, no protagonistas.
      capa('bosque', 'fill', 'landuse', ['in', ['get', 'kind'], ['literal', ['wood', 'forest', 'scrub', 'meadow', 'grass']]],
           { 'fill-color': verde, 'fill-opacity': 0.10 }),
      capa('playa', 'fill', 'landuse', ['==', ['get', 'kind'], 'beach'],
           { 'fill-color': '#D9CFB4', 'fill-opacity': 0.55 }),

      // LA MARISMA. Es el motivo de la guía, así que se distingue del resto
      // del verde con su propia tinta y un borde tenue.
      capa('marisma', 'fill', 'landuse', ['==', ['get', 'kind'], 'wetland'],
           { 'fill-color': azul, 'fill-opacity': 0.13 }),
      capa('marisma-borde', 'line', 'landuse', ['==', ['get', 'kind'], 'wetland'],
           { 'line-color': azul, 'line-opacity': 0.35, 'line-width': 0.8 }),

      // Lo construido, en gris de fondo: el polígono industrial de Huelva es
      // una referencia visual enorme para orientarse desde los observatorios.
      capa('urbano', 'fill', 'landuse', ['in', ['get', 'kind'], ['literal', ['residential', 'industrial', 'commercial', 'retail']]],
           { 'fill-color': linea2, 'fill-opacity': 0.45 }),

      // Agua. Las balsas de salinas (basin) van un punto más claras que el
      // río, que es como se ven desde arriba y ayuda a situarse.
      capa('agua', 'fill', 'water', ['!=', ['get', 'kind'], 'basin'], { 'fill-color': azul, 'fill-opacity': 0.45 }),
      capa('salinas', 'fill', 'water', ['==', ['get', 'kind'], 'basin'], { 'fill-color': azul, 'fill-opacity': 0.26 }),
      capa('salinas-borde', 'line', 'water', ['==', ['get', 'kind'], 'basin'],
           { 'line-color': azul, 'line-opacity': 0.5, 'line-width': 0.6 }),
      capa('canales', 'line', 'water', ['==', ['geometry-type'], 'LineString'],
           { 'line-color': azul, 'line-opacity': 0.55, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.6, 15, 2.5] }),

      capa('carretera', 'line', 'roads', ['in', ['get', 'kind'], ['literal', ['motorway', 'major_road']]],
           { 'line-color': linea2, 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.8, 15, 4] }),
      capa('calle', 'line', 'roads', ['==', ['get', 'kind'], 'minor_road'],
           { 'line-color': linea, 'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.5, 15, 2] }),

      // SENDEROS. Discontinuos y en tinta, no en gris: son por donde se anda,
      // y en una marisma saber si hay paso o no cambia la salida entera.
      capa('sendero', 'line', 'roads', ['in', ['get', 'kind'], ['literal', ['footway', 'path', 'cycleway', 'track']]],
           { 'line-color': mudo, 'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.8, 16, 2],
             'line-dasharray': [2, 2], 'line-opacity': 0.8 }),

      capa('edificio', 'fill', 'buildings', null,
           { 'fill-color': linea2, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 14, 0, 16, 0.5] }),
    ].filter(Boolean),
  };
}

/* Los 17 puntos NO son una capa del basemap: son marcadores HTML. Así llevan
   su etiqueta con la tipografía de la app y sin necesitar un servidor de
   glifos —que sería otra dependencia y otro par de MB en la precarga—, y de
   paso siguen siendo botones de verdad, con foco y tamaño de toque. */
let mapa = null, marcadores = [], marcaPos = null;

function marcadorPunto(p) {
  const sel = E.mapa.sel === p.id;
  const n = el('button', {
    class: 'pin' + (sel ? ' sel' : '') + ' t-' + p.tipo, type: 'button',
    'aria-label': p.nombre, title: p.nombre,
  }, el('i'), el('span', { text: p.nombre }));
  n.addEventListener('click', ev => {
    ev.stopPropagation();
    E.mapa.sel = p.id;
    pintarMapa();
  });
  return n;
}

function pintarMapa() {
  const caps = vaciar($('#mapa-capas'));
  [['observatorio', 'Observatorios'], ['sendero', 'Senderos'], ['zona', 'Zonas']].forEach(([k, et]) =>
    caps.append(el('button', { class: 'chip' + (E.mapa.capas[k] ? ' on' : ''), type: 'button',
      onclick: () => { E.mapa.capas[k] = !E.mapa.capas[k]; pintarMapa(); } }, et)));

  pintarTarjetaMapa();

  cargarMapLibre().then(() => {
    if (!mapa) {
      const lons = E.puntos.map(p => p.lon), lats = E.puntos.map(p => p.lat);
      mapa = new maplibregl.Map({
        container: 'mapa-gl',
        style: estiloMapa(),
        bounds: [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
        fitBoundsOptions: { padding: 36 },
        attributionControl: false,       // la atribución ya está en el HTML
        maxZoom: 15,                     // el techo del .pmtiles; más allá no hay dato
        dragRotate: false,               // el norte se queda arriba: en el campo
        pitchWithRotate: false,          // se compara con el mapa de papel
        touchZoomRotate: true,
      });
      mapa.touchZoomRotate.disableRotation();
      mapa.on('error', e => {
        // Un basemap que no carga no puede dejar la pantalla en blanco sin decirlo.
        console.warn('[mapa]', e && e.error && e.error.message);
        $('#mapa-aviso').textContent = 'El basemap no ha cargado. Los puntos siguen en su sitio.';
        $('#mapa-aviso').classList.remove('oculto');
      });
      mapa.on('load', () => $('#mapa-aviso').classList.add('oculto'));
      // Con 17 puntos juntos, las etiquetas se solapan al alejarse y el mapa
      // se vuelve ilegible justo en la vista de conjunto. Por debajo de z12
      // solo queda el punto; el nombre lo lleva la tarjeta de abajo.
      const ajustarEtiquetas = () => $('#lienzo-mapa').classList.toggle('lejos', mapa.getZoom() < 12);
      mapa.on('zoom', ajustarEtiquetas); mapa.on('load', ajustarEtiquetas);
    }
    marcadores.forEach(m => m.remove());
    marcadores = E.puntos
      .filter(p => E.mapa.capas.observatorio || p.tipo !== 'observatorio')
      .filter(p => E.mapa.capas.sendero || p.tipo !== 'sendero')
      .map(p => new maplibregl.Marker({ element: marcadorPunto(p), anchor: 'bottom' })
        .setLngLat([p.lon, p.lat]).addTo(mapa));

    if (E.ubicacion.coords) {
      if (marcaPos) marcaPos.remove();
      marcaPos = new maplibregl.Marker({ element: el('div', { class: 'pos-yo', 'aria-label': 'Tu posición' }) })
        .setLngLat(E.ubicacion.coords).addTo(mapa);
    }
    const sel = E.puntos.find(p => p.id === E.mapa.sel);
    if (sel) mapa.easeTo({ center: [sel.lon, sel.lat], duration: 400 });
  }).catch(err => {
    console.warn('[mapa] no se pudieron cargar las librerías', err);
    $('#mapa-aviso').textContent = 'No se ha podido cargar el mapa. Prueba con conexión y quedará guardado.';
    $('#mapa-aviso').classList.remove('oculto');
  });
}

function pintarTarjetaMapa() {
  const sel = E.puntos.find(p => p.id === E.mapa.sel);
  const z0 = sel ? zonaId(sel.zona) : null;
  $('#mapa-sub').textContent = z0 ? `${z0.nombre} · ${E.puntos.filter(p => p.zona === z0.id).length} puntos`
                                  : `${E.puntos.length} puntos`;
  $('#mapa-cercano-rot').textContent = sel
    ? (E.ubicacion.coords ? `Más cercano · ${Math.round(distancia(E.ubicacion.coords, [sel.lon, sel.lat]))} m` : sel.tipo.toUpperCase())
    : 'Selecciona un punto';
  $('#mapa-cercano-nom').textContent = sel ? sel.nombre : '—';
  $('#mapa-cercano-nota').textContent = sel
    ? `${sel.nota || ''}${sel.nota ? ' · ' : ''}Marea óptima: ${sel.mareaOptima}. Coordenadas ${sel.precision}.`
    : 'Toca un punto del mapa para ver su ficha y empezar una salida ahí.';
  $('#btn-ver-zona').disabled = !sel; $('#btn-salida-aqui').disabled = !sel;
}

function distancia([lo1, la1], [lo2, la2]) {
  const R = 6371000, r = Math.PI / 180;
  const dφ = (la2 - la1) * r, dλ = (lo2 - lo1) * r;
  const a = Math.sin(dφ / 2) ** 2 + Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin(dλ / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
$('#mapa-mas').addEventListener('click', () => mapa && mapa.zoomIn());
$('#mapa-menos').addEventListener('click', () => mapa && mapa.zoomOut());
$('#mapa-pos').addEventListener('click', pedirUbicacion);
$('#btn-ver-zona').addEventListener('click', () => {
  const p = E.puntos.find(x => x.id === E.mapa.sel); if (p) abrirZona(zonaId(p.zona));
});
$('#btn-salida-aqui').addEventListener('click', () => {
  const p = E.puntos.find(x => x.id === E.mapa.sel);
  if (!p) return;
  Pref.esc('zona', p.zona); prepararSalida(p.zona);
  setTimeout(() => { $('#he-punto').value = p.id; }, 0);
});
/* El pellizco lo lleva ahora MapLibre, que además hace inercia y doble toque
   como se espera de un mapa. El manejador a mano que había aquí escalaba un
   SVG; dejarlo puesto habría significado dos cosas peleándose por el mismo
   gesto. El wireframe sigue cumpliéndose: pellizco SOLO en el mapa, porque
   MapLibre solo existe dentro de #lienzo-mapa. */

/* --- geolocalización (opt-in, nunca sale del dispositivo) ----------------- */
let vigilando = null;
function pedirUbicacion() {
  if (!navigator.geolocation) { brindis('Este navegador no tiene geolocalización'); return; }
  E.ubicacion.estado = 'pidiendo';
  navigator.geolocation.getCurrentPosition(pos => {
    E.ubicacion = { estado: 'on', coords: [pos.coords.longitude, pos.coords.latitude] };
    Pref.esc('ubicacion', true);
    // Punto más cercano => precarga de la zona.
    let mejor = null;
    E.puntos.forEach(p => {
      const d = distancia(E.ubicacion.coords, [p.lon, p.lat]);
      if (!mejor || d < mejor.d) mejor = { p, d };
    });
    if (mejor) { E.mapa.sel = mejor.p.id; Pref.esc('zona', mejor.p.zona); }
    if (E.pantalla === 'mapa') pintarMapa();
    pintarAjustes();
    // watchPosition solo mientras el mapa está abierto, para no gastar batería.
    if (E.pantalla === 'mapa' && vigilando === null) {
      vigilando = navigator.geolocation.watchPosition(
        p2 => { E.ubicacion.coords = [p2.coords.longitude, p2.coords.latitude]; if (E.pantalla === 'mapa') pintarMapa(); },
        () => {}, { enableHighAccuracy: true, maximumAge: 10000 });
    }
  }, err => {
    E.ubicacion = { estado: err.code === 1 ? 'denegada' : 'error', coords: null };
    Pref.esc('ubicacion', false);
    pintarAjustes();
    // Denegada: aviso persistente con salida manual, nunca un muro.
    banda('Ubicación denegada · elige el observatorio a mano', {
      aviso: true, accion: 'Elegir', alPulsar: () => { ir('mapa'); banda(null); }, fijar: true });
  }, { enableHighAccuracy: true, timeout: 10000 });
}
function pararVigilancia() {
  if (vigilando !== null) { navigator.geolocation.clearWatch(vigilando); vigilando = null; }
}
/* --- reportes (cola local, se envían al recuperar red) -------------------- */
let reporteAbiertoEn = 0;
$('#hr-enviar').addEventListener('click', async () => {
  if ($('#hr-hp').value) { cerrarHoja(); return; }        // honeypot
  const msg = $('#hr-msg').value.trim();
  if (msg.length < 10) { brindis('Escribe un poco más: al menos diez caracteres'); return; }
  const r = {
    id: 'r' + Date.now(),
    tipo: $('#hr-tipo').value,
    especie: fichaActual ? fichaActual.id : null,
    mensaje: msg.slice(0, 2000),
    telefono: $('#hr-hp').value,                 // honeypot, vacío en un envío legítimo
    abiertoEn: reporteAbiertoEn,                 // el servidor exige MIN_FILL_SECONDS
    contacto: $('#hr-con').value.trim().slice(0, 120),
    contexto: { versionDatos: (E.metaEsp || {}).version || null,
                pantalla: capaAbierta ? 'ficha-especie' : E.pantalla,
                zonaActiva: (E.salida && E.salida.zona) || Pref.leer('zona', 'odiel') },
  };
  await DB.poner('cola', r);
  E.cola = await DB.todo('cola');
  $('#hr-msg').value = ''; $('#hr-con').value = '';
  cerrarHoja(); pintarAjustes();
  if (navigator.onLine) vaciarCola(); else brindis('Sin red: se enviará al recuperar cobertura');
});
async function vaciarCola() {
  if (!navigator.onLine || !E.cola.length) return;
  for (const r of [...E.cola]) {
    try {
      const res = await fetch('/api/reporte', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(r) });
      if (res.ok) { await DB.borrar('cola', r.id); }
    } catch { break; }                       // sin notificación de éxito
  }
  E.cola = await DB.todo('cola');
  pintarAjustes(); repasarRed();
}

/* --- pantalla AJUSTES ----------------------------------------------------- */
const TRAMOS = [
  { k: 'app', nom: 'Interfaz y datos de la guía', mb: 0.45, fijo: true },
  { k: 'fotos', nom: 'Fotos de especie', mb: 0 },
  { k: 'mapa', nom: 'Teselas del mapa', mb: 0 },
  { k: 'mareas', nom: 'Mareas descargadas', mb: 0.04, fijo: true },
];
function pintarAjustes() {
  const pend = E.especies.filter(e => e.foto.estado === 'pendiente').length;
  $('#aj-descarga-txt').textContent =
    `${E.especies.length - pend} fotos · mapa de Huelva · mareas de ${diasRestantes()} días · ${pend} fichas con foto pendiente`;

  const desc = Pref.leer('descargado', {});
  TRAMOS[1].mb = (desc.fotos || 0) * 0.12;
  TRAMOS[2].mb = desc.mapa || 0;
  const total = TRAMOS.reduce((n, t) => n + t.mb, 0);
  $('#aj-total').textContent = total >= 1 ? `${total.toFixed(0)} MB` : `${Math.round(total * 1024)} KB`;
  const cont = vaciar($('#aj-tramos'));
  TRAMOS.forEach(t => cont.append(el('div', { class: 'tramo' },
    el('div', { class: 'txt' }, el('div', { class: 'nom', text: t.nom }),
      el('div', { class: 'mb', text: t.mb >= 1 ? `${t.mb.toFixed(0)} MB` : `${Math.round(t.mb * 1024)} KB` })),
    t.fijo || !t.mb ? el('span', { class: 'mb', text: t.fijo ? 'imprescindible' : 'sin descargar' })
      : el('button', { type: 'button', text: 'Borrar', onclick: () => {
          const d = Pref.leer('descargado', {}); delete d[t.k === 'fotos' ? 'fotos' : 'mapa'];
          Pref.esc('descargado', d); pintarAjustes(); brindis(`${t.nom}: borrado`); } }))));

  $('#aj-ubi').setAttribute('aria-checked', String(E.ubicacion.estado === 'on'));
  $('#aj-ubi-est').textContent = { on: 'Activada', off: 'Desactivada', denegada: 'Denegada por el navegador',
                                   pidiendo: 'Pidiendo permiso…', error: 'No disponible' }[E.ubicacion.estado];
  $('#aj-ubi-denegada').classList.toggle('oculto', E.ubicacion.estado !== 'denegada');

  const nReg = E.salidas.reduce((n, s) => n + s.avistamientos.length, 0);
  $('#aj-datos').textContent = `${E.salidas.length} salida${E.salidas.length === 1 ? '' : 's'} · ${nReg} avistamientos en este dispositivo`;
  $('#aj-cola-txt').textContent = E.cola.length
    ? `${E.cola.length} reporte(s) esperando cobertura. Se envían solos.` : 'Nada en cola.';

  const dl = vaciar($('#aj-meta'));
  const ver = E.especies.filter(e => e.confianza === 'verificado').length;
  [['Versión datos', (E.metaEsp || {}).version || '—'],
   ['Especies', `${E.especies.length} · ${ver} con fenología verificada`],
   ['Fotos pendientes', String(pend)],
   ['Mareas', E.mareas ? `${(E.mareas.generado || '').slice(0, 10)} · ${diasRestantes()} días por delante` : 'sin datos'],
   ['Sinónimos', E.sinonimos ? `${E.sinonimos.entradas.filter(s => s.commonsVerificado).length} de ${E.sinonimos.entradas.length} verificados en Commons` : '—'],
  ].forEach(([k, v]) => dl.append(el('dt', { text: k }), el('dd', { text: v })));
}
$('#aj-ubi').addEventListener('click', () => {
  if (E.ubicacion.estado === 'on') {
    E.ubicacion = { estado: 'off', coords: null }; pararVigilancia();
    Pref.esc('ubicacion', false); pintarAjustes();
    if (E.pantalla === 'mapa') pintarMapa();
  } else pedirUbicacion();
});
$('#btn-elegir-obs').addEventListener('click', () => ir('mapa'));
$$('#aj-tema button').forEach(b => b.addEventListener('click', () => ponerTema(b.dataset.tema)));
$('#btn-remarea').addEventListener('click', async () => {
  if (!navigator.onLine) { $('#sc-txt').textContent =
    'Las mareas se descargan del NAS y ahora mismo no hay cobertura. Lo descargado sigue disponible.';
    abrirCapa('c-sincache'); return; }
  try { E.mareas = await traer('datos/mareas.json'); pintarHoy(); brindis('Mareas actualizadas'); }
  catch { brindis('No se ha podido actualizar'); }
});
$('#sc-volver').addEventListener('click', () => { cerrarCapa(); ir('hoy'); });

/* --- descarga previa por trozos ------------------------------------------- */
/* Por trozos y no en un único GET: los túneles cortan las descargas largas. */
let descarga = null;
$('#btn-descargar').addEventListener('click', () => {
  if (descarga) { pararDescarga(); return; }
  const totalMB = 268;                          // por medir con el .pmtiles real
  let hechoMB = 0;
  $('#aj-progreso').classList.remove('oculto');
  $('#btn-descargar').textContent = 'Descargando…';
  $('#btn-pausar').textContent = 'Pausar';
  const tramo = () => {
    hechoMB = Math.min(totalMB, hechoMB + 6);
    $('#aj-barra').style.width = `${(hechoMB / totalMB) * 100}%`;
    $('#aj-progreso-txt').textContent = `${hechoMB} de ${totalMB} MB · mapa de Huelva`;
    if (hechoMB >= totalMB) {
      pararDescarga();
      Pref.esc('descargado', { ...Pref.leer('descargado', {}), mapa: totalMB, fotos: E.especies.length });
      pintarAjustes(); brindis('Descarga completa · listo para el campo');
    }
  };
  descarga = setInterval(tramo, 220);
});
function pararDescarga() {
  clearInterval(descarga); descarga = null;
  $('#btn-descargar').textContent = 'Descargar';
  $('#btn-pausar').textContent = 'Reanudar';
}
$('#btn-pausar').addEventListener('click', () => {
  if (descarga) { pararDescarga(); brindis('Descarga pausada · sigue donde la dejaste'); }
  else $('#btn-descargar').click();
});

/* --- arranque -------------------------------------------------------------- */
async function arrancar() {
  ponerTema(Pref.leer('tema', matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro'));
  try { await cargarDatos(); }
  catch (err) {
    document.body.innerHTML =
      `<div style="padding:40px;font:16px/1.5 system-ui"><h1 style="font:700 22px Georgia,serif">No se han podido cargar los datos</h1>
       <p style="margin-top:10px;color:#6E6A60">${err.message}. Sirve la carpeta por HTTP: <code>python3 -m http.server</code></p></div>`;
    return;
  }
  E.salidas = await DB.todo('salidas').catch(() => []);
  E.cola    = await DB.todo('cola').catch(() => []);
  const borrador = Pref.leer('salida', null);
  if (borrador && borrador.id) E.salida = borrador;
  // La ubicación siempre arranca apagada: el permiso se pide al pulsar, nunca al arrancar.
  E.ubicacion = { estado: 'off', coords: null };

  const a = ahoraLocal();
  E.filtros.mes = a.mes;
  E.filtros.zona = Pref.leer('zona', 'odiel');

  ir(Pref.leer('pantalla', 'hoy'), { porSistema: true });
  repasarRed();
  if (diasRestantes() < 3 && diasRestantes() >= 0)
    banda(`Quedan ${diasRestantes()} días de mareas descargadas`, { aviso: true, accion: 'Actualizar',
      alPulsar: () => $('#btn-remarea').click() });

  // Refresco de reloj: la cuenta atrás de marea tiene que ser fiable.
  setInterval(() => { if (E.pantalla === 'hoy') pintarHoy(); if (E.pantalla === 'cuaderno' && E.salida) pintarCurso(); }, 60000);
  window.addEventListener('online', () => { repasarRed(); vaciarCola(); });
  window.addEventListener('offline', repasarRed);
  window.addEventListener('resize', () => { if (capaAbierta && capaAbierta.id === 'c-sinid') prepararLienzo(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) pararVigilancia(); });

  if ('serviceWorker' in navigator && location.protocol.startsWith('http'))
    navigator.serviceWorker.register('sw.js').catch(() => {});
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
}
arrancar();
