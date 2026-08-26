# AGENTS.md

Guía para agentes y contribuidores de **pajaritos.josearcos.me**, la guía de
observación de aves de las Marismas del Odiel. Este fichero es el canónico;
`CLAUDE.md` es sólo un puntero para Claude Code.

Todo en este repo está en español, nombres de función incluidos. Mantenlo así.

## Qué es

Una PWA que se usa **con el móvil en la mano, en la marisma, con sol de cara y
puede que sin cobertura**. Eso decide casi todo lo demás:

- **Sin build.** `app/app.js` es un fichero de 1.558 líneas que el navegador
  carga tal cual. No hay bundler, no hay transpilador, no hay `node_modules`
  en producción. Cualquier propuesta de meter un framework tiene que justificar
  por qué merece la pena perder eso.
- **Service Worker** (`app/sw.js`) para que funcione sin red.
- **Servicios Python de biblioteca estándar**, sin una sola dependencia:
  - `services/api/app.py` (282 líneas) — endpoint de reportes. SQLite.
  - `services/mareas/fetch_mareas.py` (230 líneas) — predicción de mareas.
- **`herramientas/`** — utilidades de mantenimiento en Python y shell.
- **`app/datos/`** — los cuatro JSON que son el contenido real:
  `especies.json`, `zonas.json`, `puntos.geojson`, `sinonimos.json`.

Despliegue: NAS Synology detrás de un Cloudflare Tunnel, sin puertos entrantes.
El detalle completo está en `SETUP.md`, que **está en `.gitignore` a
propósito**: es el runbook de infraestructura y no va al repo público. Existe
en la copia local; si trabajas desde un clon limpio, no lo tendrás.

## La puerta

Antes de empujar, en local:

```
pruebas/puerta.sh
```

Corre lo mismo que el job `comprobar` de CI, más la suite:

1. `python3 herramientas/validar-datos.py` — coherencia de los datos.
2. `node --check app/app.js` — que el JS parsea.
3. `sh -n` sobre todos los `.sh` de `herramientas/`, `scripts/` y `pruebas/`.
4. Que no haya basura de macOS (`.DS_Store`, `._*`) commiteada.
5. `pruebas/correr.sh` — la suite de tests (desde 26-08-2026).

**No confundir con `herramientas/verificar.sh`**, que es otra cosa: un humo
contra el contenedor **ya desplegado** en el NAS, lanzado desde dentro de la
red `tunnel`. Necesita Docker y el NAS; no sirve como puerta antes del push.

## Las trampas conocidas

- **La versión de `app.js` está en dos sitios**: el `?v=` de `index.html` y la
  lista `ARMAZON` de `sw.js`. Si se desincronizan, el Service Worker precarga
  una URL que la página no pide y quien tenga la app instalada se queda con el
  JS viejo **de forma permanente**. `validar-datos.py` lo comprueba; no
  desactives esa comprobación.
- **Toda especie necesita entrada en `sinonimos.json`.** Durante meses sólo 8
  de 60 la tenían y las demás caían en el `|| esp.cientifico` de `app.js`: la
  ficha no decía ni «verificada» ni «por verificar». Categoría sin comprobar y
  sin avisar de ello.
- **`services/api/app.py` es la única superficie de escritura de todo el
  sitio**, y su seguridad es *incapacidad*, no autenticación: una sola ruta
  acepta POST, sólo hace INSERT, no hay ruta de lectura ni de borrado, la base
  de datos vive en un volumen que nginx no monta, y no se almacena la IP de
  nadie. Añadirle una ruta de lectura, un borrado o un log de IPs desmonta el
  modelo entero. Si el cambio va por ahí, es una decisión, no una tarea.
- **El despliegue está detrás de `AUTODEPLOY_ENABLED`.** Si la variable del
  repo no está en `true`, el job de despliegue no corre y el push parece verde
  sin haber desplegado nada.
- **Un hueco es más honesto que un gráfico verosímil.** La app dibuja doce
  barras de fenología sólo cuando hay dato. Doce barras iguales no dicen «no
  se sabe», dicen «está los doce meses», y para un colimbo chico eso es falso.
  Esa decisión está tomada y comentada en el código; no la revierta nadie por
  hacer que «se vea mejor».

## Estándares de ingeniería (toda la cartera)

Aplican a todos los proyectos propios. La copia canónica está en
`~/Sites/hq/ESTANDARES.md`; esta sección es la copia local del repo. Si
divergen, manda la canónica.

### El punto de partida honesto

**Este proyecto no tenía un solo test.** El CI comprueba que los JSON son
coherentes y que el JS parsea: eso es un `lint` largo, no una suite. Aquí TDD
no es «seguir aplicándolo», es empezarlo. El resto de esta sección dice cómo, y
no finge que ya esté hecho.

### TDD — el test primero

- **Sin código de producción sin un test que lo pidiera antes.** Rojo → verde →
  refactor. El test y la implementación entran en el mismo commit, pero el test
  se escribió antes y se le vio fallar.
- **Un fallo reportado empieza por un test que lo reproduce.** Todas las
  trampas de la sección anterior están ahí porque algo se rompió de verdad;
  cada una merece un test que impida que vuelva a pasar.
- **Un test describe comportamiento, no implementación.**
- **Verde antes de commitear, siempre.** Rojo no se commitea.

Las herramientas están puestas y no añaden dependencias de producción:

- **Python** — `pruebas/python/`, con `unittest` de la biblioteca estándar.
  Cubre `herramientas/validar-datos.py`, `services/api/app.py` y
  `services/mareas/fetch_mareas.py`.
- **JavaScript** — `pruebas/js/`, con `node --test` (viene en Node, aquí
  v26.3.1). No hay `package.json` y no hace falta.

Se corren juntas con `pruebas/correr.sh`.

### DDD — el dominio primero y aislado

El dominio de este proyecto es concreto: **mareas, fenología y probabilidad de
avistamiento**. Hoy vive mezclado con el DOM dentro de `app.js`.

- `estacionDe`, `diaMarea`, `diasRestantes`, `proximaMarea` — mareas.
- `estadoMes`, `sinFenologia`, `esperables` — fenología y probabilidad.
- `aplicaFiltros` — selección.

Ninguna de esas funciones toca el DOM: son puras y son lo que de verdad tiene
valor en la app. Están enterradas entre `pintarHoy()` y `abrirFicha()`, que sí
lo tocan.

**El trabajo pendiente**: extraer las funciones puras a `app/logica.js`, que
`app.js` cargue antes, y que `pruebas/js/` las importe. Es la separación
dominio / presentación posible en un proyecto sin build, y es el primer paso
para que TDD signifique algo aquí. Mientras no esté hecho, todo test de JS
tiene que duplicar lógica o tocar el DOM, y las dos cosas son peores.

Cuando esté hecho: **`app/logica.js` no toca `document`, `window` ni la red.**
Es un grep y tiene que salir vacío.

### SOLID — las cinco

- **S** — responsabilidad única. `app.js` tiene 1.558 líneas y hace de todo;
  el objetivo no es partirlo por partirlo, sino que cada extracción nueva salga
  ya con una sola razón para cambiar.
- **O** — abierto/cerrado. Una zona nueva o una estación de mareas nueva se
  añade por datos (`zonas.json`), no editando `app.js`.
- **L** — sustitución de Liskov. Aplica poco aquí; no lo fuerces.
- **I** — segregación de interfaces. Funciones con pocos argumentos y objetos
  de opciones explícitos, como ya hacen `banda()` y `filaEspecie()`.
- **D** — inversión de dependencias. La lógica pura recibe los datos por
  argumento; no lee `E` (el estado global) por dentro. Hoy `esperables()` y
  `estacionDe()` sí lo hacen: al extraerlas, se les pasa el estado.

### Cobertura — trinquete, no aspiración

- Suelo actual: **no hay**, porque no hay suite todavía.
- En cuanto `pruebas/correr.sh` cubra algo de forma estable, se declara el
  suelo en el propio repo y **sólo sube**. Bajarlo es una decisión explícita
  con su commit y su motivo.
- **Código nuevo: 100%.** El suelo global será el trinquete de la deuda vieja;
  para lo que se escriba a partir de hoy no hay excusa.
- La cobertura no sustituye a las aserciones. Un test que ejecuta la línea sin
  comprobar nada sube el número y compra tranquilidad falsa.

### Deuda declarada

- [ ] Extraer `app/logica.js` con las funciones puras de mareas, fenología y
      filtros, y que reciban el estado por argumento.
- [ ] Un test por cada trampa de «Las trampas conocidas».
- [ ] Cobertura de Python (`coverage.py` como dependencia sólo de desarrollo) y
      suelo inicial.
- [ ] Cobertura de JS y suelo inicial.

## Convenciones

- **Sin ramas, sin PRs.** Se commitea y se empuja a `main`; CI es la puerta.
  Nunca se despliega en rojo. Decisión de cartera, 26-08-2026.
- **Antes de commitear, mirar qué entra en el commit** (`git show --stat`).
  `git add -A` es como se cuelan ficheros en el commit equivocado.
- **Cero dependencias en producción.** Ni en los servicios Python ni en la
  app. Lo que se añada para desarrollo o para tests se queda fuera de la imagen
  y fuera del `tar` que sube el despliegue.
- **Los comentarios explican por qué, no qué.** Los que hay en este repo
  documentan decisiones y fallos reales; sigue esa costumbre en vez de
  describir lo que la línea ya dice.
- **Un dato sobre un ave que no se puede defender no entra.** Si la fuente no
  está clara, el hueco es la respuesta correcta.
