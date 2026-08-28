
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

## 2026-08-28 · p7 · HECHA (segunda mitad)

José eligió el CI como sitio, así que el `check` de p7 cambió de destino —
no para poner en verde algo rojo: se comprobó que el nuevo seguía en **rojo**
antes de tocar nada, y la mitad ya hecha no se tocó.

**Lo que el CI comprobaba de verdad hasta hoy**

| comprobación | qué demostraba | agujero |
|---|---|---|
| `curl -o /dev/null` a la ruta versionada de `app.js` | que devuelve 200 | nginx ignora el query string de un estático: pasa sirviendo el fichero **anterior** |
| `grep odiel-vN` en `sw.js` | que la cadena coincide | el resto del fichero puede ser cualquiera |
| contar entradas de `sinonimos.json` | que hay N | los N pueden ser otros |
| `logica.js` | — | no se miraba |

Tres indicios y un olvido. Ahora se compara el **sha256** de nueve ficheros
contra el del repo, con la versión leída del index que sirve producción.

**Cambios sobre la primera mitad**

- La lista de ficheros pasa a ser **argumentos explícitos**, sin lista por
  defecto escondida en el guión: un fichero que falta se ve en el sitio donde
  se llama. Y llamar sin ficheros ahora sale con error — comparar nada y salir
  0 parece una comprobación y no lo es. Mutante matado.

**Lo que cazó el check, y no era el código**

Un comentario mío en `ci.yml` citaba la línea vieja literalmente, y para un
`grep` un comentario que reproduce el código **es** el código. Reescrito en
prosa. El check tenía razón.

**Resultado en producción**: run `33173526537`, job «desplegar al NAS», paso
«Comprobar que lo publicado es lo que se subió» → `success`. Como el guión sale
1 ante cualquier diferencia, ante un 404 y ante un servidor que no responde,
`success` significa que los nueve ficheros coinciden byte a byte.

**Lo que no he podido ver**: el log del run. `gh run view --log` y la API
devuelven una URL de `blob.core.windows.net` que el proxy de la sesión remota
bloquea con `Forbidden` — el mismo tipo de límite que `*.josearcos.me`. Lo que
afirmo sale del código de salida del paso, no de haber leído los hashes.

**Lo que sigue sin haberse visto fallar**: el cableado en sí. Los cinco mutantes
que maté eran contra el guión, no contra el paso del CI. Que el paso se ponga
en rojo con un despliegue a medias es la única parte que no se ha demostrado, y
provocarla a propósito significa romper producción. Se sabrá el día que pase.

## 2026-08-28 · p6 · HECHA

La salida obvia era sustituir la copia por `Logica.estacionDe` y cerrar. Habría
sido un error: **las dos copias no hacían lo mismo.**

| | `estacionDe(estado, zid)` | la copia de `pintarZona()` |
|---|---|---|
| zona sin `estacionMarea` | cae en `huelva-5` | `null` |
| `zid` desconocido | cae en `E.zonas[0]` | no aplica |
| para qué se usa | **calcular** una hora de marea | **escribir** un dato en la ficha |

Unificarlas habría puesto «Estación: Huelva» en la ficha de una zona que no
declara mareógrafo. Es la misma familia de mentira que las doce unidades de las
especies sin fenología: rellenar un hueco es peor que dejarlo, porque el hueco
se ve y el relleno no.

Así que **dos funciones con dos nombres**, cada una respondiendo a su pregunta:
`estacionDe` («con qué mareógrafo calculo») sigue cayendo, y hace bien;
`estacionDeclarada` («qué dice el JSON que tiene esta zona») no cae nunca.

- 6 tests, uno de ellos afirmando **la diferencia entre las dos** para la misma
  zona, para que nadie las «arregle» unificándolas dentro de seis meses.
- 3 mutantes: caer en `huelva-5`, devolver `undefined` en vez de `null` (que en
  la ficha imprime «código undefined»), y quitar la guarda de `mareas`.

**Un mutante mal planteado**: el primer intento de matar la guarda la
*sustituía* por un estado falso en vez de *quitarla*, y sobrevivía — pero es
que era un mutante equivalente, no un agujero del test. Rehecho quitándola de
verdad, cayó. Un mutante que sobrevive obliga a mirar dos cosas: el test, y si
el mutante prueba lo que crees.

Versión a `2026-08-28b`, caché del SW a `odiel-v14`.

## 2026-08-28 · PARADA · dos checks que no pueden pasar nunca

Al ir a por p2, el bucle se para antes de empezar. Los `check` de **p2 y p3**
invocan `node --test pruebas/js/`, que es **la invocación rota** que corregí en
`correr.sh` esta misma mañana: node 22 intenta resolver el directorio como
módulo y muere con `MODULE_NOT_FOUND`. El comando falla pase lo que pase en el
repo.

```
# Error: Cannot find module '.../pruebas/js'
#   code: 'MODULE_NOT_FOUND',
```

Con la invocación que sí funciona, los dos checks estarían **en verde ya**: 14
menciones de `diaMarea`/`proximaMarea` y 14 de `esperables`/fenología en la
suite. El trabajo de p2 y p3 entró de rebote con p1.

**Lo que esto dice del tablero.** `comprobar-features.sh` verifica dos
invariantes: una tarea pendiente no puede tener el check en verde, y una hecha
no puede tenerlo en rojo. No cubre el tercer caso: **un check rojo por un
motivo que no tiene nada que ver con la tarea**. Un check que no puede pasar
nunca es tan inútil como uno que pasa siempre, y además es invisible: parece
disciplina.

**Por qué paro en vez de arreglarlo.** Arreglar el check y marcar las dos
tareas como hechas es, mecánicamente, editar un `check` para que pase — la
cláusula de parada más importante que tiene este bucle. Que yo esté convencido
de tener razón es exactamente la situación para la que existe la cláusula.
Decide José.

## 2026-08-28 · p2 y p3 · HECHAS (checks arreglados con autorización)

José autorizó arreglar los dos `check` rotos. El anterior queda guardado en
`check_anterior_roto` dentro de cada entrada: el historial de lo que se creía
que se estaba comprobando vale tanto como el de lo comprobado.

**Un check nuevo no vale hasta que se le ha visto ponerse rojo.** Cuatro
comprobaciones, y las dos últimas son las que importan porque prueban que los
checks son **independientes** y no dos formas de decir «la suite pasa»:

| situación | p2 | p3 |
|---|---|---|
| un test roto | rojo | rojo |
| ningún `.test.js` | rojo | rojo |
| suite **sin** tests de mareas | **rojo** | verde |
| suite **sin** fenología ni filtros | verde | **rojo** |

**Lo que cazó el tercer mutante, y era mío.** La primera versión del check de
p2 buscaba `marea` a secas, y eso casaba con `esperables: «indiferente» en la
especie pasa cualquier marea` — un test de filtros. p2 se ponía verde sin un
solo test de mareas. Afinado a nombres de función: `diaMarea|proximaMarea|
diasRestantes|estacionDe`.

**Y un corte mal hecho, también mío.** El primer intento de quitar «todo lo de
mareas» cortaba por `estacionDeclarada` y dejaba dentro los tests de
`estacionDe`. p2 seguía verde y con razón. El mutante no probaba lo que yo
creía: hay que mirar la salida, no la intención.

Queda **p8**: que `comprobar-features.sh` distinga un check rojo por el estado
del repo de uno rojo porque el comando ni siquiera arranca.
