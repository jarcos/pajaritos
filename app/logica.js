"use strict";
/* Aves del Odiel — lógica pura.
 *
 * Aquí solo entra código que se puede contestar con datos de entrada y nada
 * más: mareas, fenología y filtros. Ni un selector, ni una pintura, ni un
 * acceso al almacenamiento del navegador. Esa es toda la regla, y es
 * comprobable con un grep — lo hace el `check` de p1 en FEATURES.json.
 *
 * Por qué está separado: estas cuatro cosas son lo único de la app con valor
 * propio, y vivían entre pintarHoy() y abrirFicha(). Mientras estuvieron ahí,
 * probarlas exigía montar un DOM falso o duplicar la lógica en el test. Las
 * dos salidas son peores que no probar nada, porque dan confianza sin darla.
 *
 * Se carga como script clásico antes de app.js (por eso `var` y un solo
 * nombre global) y como módulo CommonJS en los tests. Nada de imports: el
 * sitio se sirve con CSP `script-src 'self'` y sin empaquetador.
 */

var Logica = (function () {

  /* --- utilidades ------------------------------------------------------- */

  const dosD = n => String(n).padStart(2, '0');

  /** '06:10' -> 370. Minutos desde medianoche. */
  const minutos = hhmm => {
    const [h, m] = hhmm.split(':').map(Number);
    return h * 60 + m;
  };

  const zonaId = (zonas, id) => (zonas || []).find(z => z.id === id);

  const estadoMes = (esp, mes) => esp.meses[mes] ?? 0;

  /* Una especie sin fenología tiene doce unos en `meses`, y eso NO significa
     «está todo el año»: significa «no se sabe». Colarla en una afirmación
     sobre un mes concreto es inventarse el dato. Por esto se quitó el gráfico
     de las fichas sin fenología, y por lo mismo se filtra aquí. */
  const sinFenologia = esp => !!esp.notaFenologia;

  /* --- mareas ----------------------------------------------------------- */

  /** Estación de mareógrafo que le toca a una zona. `null` si aún no han
   *  llegado los datos de mareas: el estado arranca vacío y se rellena por
   *  fetch, y entre medias la app ya se está pintando. */
  function estacionDe(estado, zid) {
    const z = zonaId(estado.zonas, zid) || (estado.zonas || [])[0];
    const eid = (z && z.estacionMarea) || 'huelva-5';
    return estado.mareas && estado.mareas.estaciones
      ? (estado.mareas.estaciones[eid] || null)
      : null;
  }

  /** Mareógrafo que una zona DECLARA tener, sin ningún valor por defecto.
   *  `null` si la zona no declara ninguno, si no hay datos de mareas todavía o
   *  si el código apunta a una estación que no existe.
   *
   *  No es `estacionDe` con otro nombre, y por eso son dos:
   *    · `estacionDe` responde «con qué mareógrafo calculo la marea de aquí», y
   *      ahí caer en huelva-5 es lo correcto: hay que dar una hora.
   *    · `estacionDeclarada` responde «qué dice el JSON que tiene esta zona», y
   *      ahí inventarse Huelva es escribir en la ficha un dato que nadie ha
   *      dado. Misma familia que las doce unidades de las especies sin
   *      fenología: rellenar un hueco es peor que dejarlo.
   */
  function estacionDeclarada(estado, zona) {
    if (!zona || !zona.estacionMarea) return null;
    if (!estado.mareas || !estado.mareas.estaciones) return null;
    return estado.mareas.estaciones[zona.estacionMarea] || null;
  }

  /** Predicción de un día para una zona, con el desfase de la zona respecto
   *  al mareógrafo ya aplicado. `null` si esa fecha no está en la predicción
   *  descargada, que es lo que pasa cuando caduca. */
  function diaMarea(estado, fecha, zid) {
    const est = estacionDe(estado, zid);
    if (!est) return null;
    const d = est.dias.find(x => x.fecha === fecha);
    if (!d) return null;
    const z = zonaId(estado.zonas, zid);
    const desfase = (z && typeof z.desfaseMinutos === 'number') ? z.desfaseMinutos : 0;
    return {
      ...d,
      estacion: est,
      desfase,
      eventos: d.eventos.map(e => {
        // El módulo 1440 no es cosmético: con +5 h, una bajamar de 20:00 es
        // la 01:00, no «las 25:00». Sin dar la vuelta, además de escribir una
        // hora que no existe, la lista se ordenaría mal.
        const m = (minutos(e.local) + desfase + 1440) % 1440;
        return { ...e, local: `${dosD(Math.floor(m / 60))}:${dosD(m % 60)}`, min: m };
      }),
    };
  }

  /** Días de predicción que quedan por delante. Menos de 1 = caducada. */
  function diasRestantes(estado, zid, hoy) {
    const est = estacionDe(estado, zid);
    if (!est || !est.dias.length) return -1;
    return est.dias.filter(d => d.fecha >= hoy).length;
  }

  /** Siguiente evento de marea a partir de un instante dado. Si ya han pasado
   *  todos, devuelve el último con `pasada: true` — mostrar «la próxima es a
   *  las 06:10» a las 23:30 sería mentir por omisión del día. */
  function proximaMarea(estado, zid, ahora) {
    const d = diaMarea(estado, ahora.fecha, zid);
    if (!d) return null;
    const m = minutos(ahora.hora);
    const sig = d.eventos.find(e => e.min >= m);
    return sig
      ? { ...sig, faltan: sig.min - m, dia: d }
      : { ...d.eventos[d.eventos.length - 1], faltan: null, dia: d, pasada: true };
  }

  /* --- probabilidad ----------------------------------------------------- */

  /** Especies razonablemente esperables en un mes, zona y estado de marea. */
  function esperables(especies, mes, zid, marea) {
    return (especies || []).filter(e => {
      if (sinFenologia(e)) return false;
      if (estadoMes(e, mes) < 1) return false;
      if (zid && !e.zonas.includes(zid)) return false;
      if (marea && marea !== 'indiferente' && e.marea !== 'indiferente' && e.marea !== marea) return false;
      return true;
    });
  }

  /* --- filtros de la guía ------------------------------------------------ */

  /** Aplica los filtros de la guía. `omitir` salta UNO de ellos, y solo uno:
   *  es lo que permite decir «quita el filtro de zona y aparecen 7» con un
   *  número que de verdad sale de contar. */
  function aplicaFiltros(especies, filtros, omitir = null) {
    const f = filtros || {};
    return (especies || []).filter(e => {
      if (f.mes !== null && f.mes !== undefined && omitir !== 'mes'
          && (sinFenologia(e) || estadoMes(e, f.mes) < 1)) return false;
      if (f.zona && omitir !== 'zona' && !e.zonas.includes(f.zona)) return false;
      if (f.marea && omitir !== 'marea' && f.marea !== 'indiferente'
          && e.marea !== 'indiferente' && e.marea !== f.marea) return false;
      if (f.tamano && omitir !== 'tamano' && e.tamano !== f.tamano) return false;
      if (f.grupo && omitir !== 'grupo' && e.grupo !== f.grupo) return false;
      return true;
    });
  }

  return {
    dosD, minutos, zonaId, estadoMes, sinFenologia,
    estacionDe, estacionDeclarada, diaMarea, diasRestantes, proximaMarea,
    esperables, aplicaFiltros,
  };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = Logica;
