
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
- Nadie ha abierto la app en un navegador. Lo verificado es estático más el
  despliegue: `logica.js` no toca el navegador, todo `Logica.x` que usa
  `app.js` existe, ambos parsean, y **producción sirve los dos scripts en
  orden con el md5 idéntico al del repo** (`f922886c…`, comprobado desde el
  Mac porque el proxy de la sesión remota bloquea `*.josearcos.me`). Lo que
  sigue sin probar es la interacción: que la ficha de mareas pinte bien.
- El `push` sí salió, con `gh`: clave SSH propia de la VM dada de alta con
  `gh ssh-key add`, sin cambiar los remotos a HTTPS. CI en verde y desplegado.

**Cláusula de parada aplicada**: «una tarea y fuera». p6 queda sin empezar.

## 2026-08-28 · p7 · PARADA (mitad hecha)

**Qué se ha hecho**

- `herramientas/comprobar-desplegado.sh`: compara el `sha256` de lo que sirve
  una URL con el del repo, fichero a fichero. La versión de `app.js` y
  `logica.js` se lee del **index que sirve producción**, no del repo: pedirle
  al servidor justo la versión que queremos oír no comprueba nada.
- `pruebas/python/test_comprobar_desplegado.py`: 6 tests contra un
  `http.server` sobre un árbol temporal. Sin red, sin NAS, sin tocar nada.

**Mutantes matados (4)**

| mutante | test que cayó |
|---|---|
| `curl` sin `--fail` | «un fichero no se sirve» (el 404 salía como «difiere») |
| leer la versión del repo, no la de producción | «el index desplegado es de otra versión» + 1 |
| salir 0 aunque haya fallos | 3 tests |
| «no responde» contado como «todo bien» | «producción caída» |

**Por qué paro aquí**

Enchufarlo en `herramientas/verificar.sh` exige saber qué hay dentro de
`/volume1/docker/pajaritos` en el NAS y cuál es la raíz de documentos del
contenedor `pajaritos-web`. Desde la sesión remota no se puede mirar: el proxy
bloquea `*.josearcos.me` y el NAS está en la LAN. Puedo inferirlo del `cd` que
ya hace `verificar.sh`, pero inferir la infraestructura es exactamente cómo se
pierde una tarde. **Cláusula aplicada: «hay que decidir».**

`p7` queda **pendiente**, con su `check` en rojo. Que la mitad esté hecha no la
convierte en hecha.
