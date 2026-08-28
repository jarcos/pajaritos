
## 2026-08-28 · p1 · HECHA

**Qué se ha hecho**

- `app/logica.js` nuevo: once funciones puras (`estacionDe`, `diaMarea`,
  `diasRestantes`, `proximaMarea`, `esperables`, `aplicaFiltros` y los cinco
  ayudantes). `grep -cE '\b(document|window|localStorage)\b' app/logica.js` → `0`.
- `pruebas/js/logica.test.js`: 21 tests. Escritos **antes** que el fichero y
  vistos en rojo (`MODULE_NOT_FOUND`).
- `app/app.js`: los diez sitios que tenían la lógica pasan a ser delegaciones
  de una línea. Se conservan como `function` y no como `const` a propósito,
  para no perder el hoisting del que dependen los puntos de llamada.
- `app/index.html` y `app/sw.js`: `logica.js` declarada y precargada, misma
  versión que `app.js`, subida a `2026-08-28a`; caché del SW a `odiel-v13`.
- `herramientas/validar-datos.py`: comprobación 3b, la de `app.js` aplicada a
  `logica.js`. Tres tests nuevos, los tres vistos en rojo primero.

**Mutantes matados (4 sobre logica.js)**

| mutante | test que cayó |
|---|---|
| quitar el `% 1440` | «un desfase que cruza medianoche…» |
| dejar pasar las especies sin fenología | 5 tests de `esperables` |
| que `omitir` se cuele en todos los filtros | «omitir ignora ese filtro y solo ese» |
| devolver siempre la primera marea del día | 2 tests de `proximaMarea` |

**Tres cosas que estaban rotas y no lo sabía nadie**

1. `puerta.sh` decía `PUERTA EN VERDE` con `app.js` sintácticamente roto:
   `node --check app/app.js && echo "ok"` deja el fallo a la izquierda de un
   `&&`, donde `set -e` no mira. `herramientas/levantar.sh` tenía lo mismo con
   `docker compose config`. Los dos corregidos.
2. `pruebas/correr.sh` llamaba a `node --test pruebas/js/`, que en node 22
   muere con `MODULE_NOT_FOUND`. Nunca se notó porque no había ni un `.test.js`
   que lo ejecutara. Ahora pasa la lista de ficheros.
3. Un test mío estaba mal, no el código: esperaba que `aplicaFiltros` con
   `omitir: 'tamano'` escondiera la especie sin fenología. Sin filtro de mes
   no la esconde, y hace bien. Corregida la expectativa.

**Qué NO se ha hecho**

- `app.js` conserva una segunda copia de «qué mareógrafo le toca a esta zona»
  en `pintarZona()`, con semántica distinta (sin los dos fallbacks). Unificarla
  cambia comportamiento, así que queda como **p6** con su propio check.
- Nadie ha abierto la app en un navegador. Lo verificado es estático: que
  `logica.js` no toca el navegador, que todo `Logica.x` que usa `app.js`
  existe, y que ambos ficheros parsean.
- El `push` no ha salido: esta VM no tiene salida a GitHub.

**Cláusula de parada aplicada**: «una tarea y fuera». p6 queda sin empezar.
