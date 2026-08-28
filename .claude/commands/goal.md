---
description: Bucle autónomo sobre FEATURES.json. Una tarea cada vez, verde o nada.
argument-hint: "[id de tarea | vacío para la siguiente pendiente]"
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, Task
---

# Bucle `/goal`

Trabajas solo, probablemente de noche, sin nadie que te corrija. Todo lo que
sigue existe porque el modo de fallo caro de un bucle desatendido no es
romper cosas: es **decir que ha hecho algo que no ha hecho**. Un agente que
para y explica por qué vale mucho más que uno que amanece con cinco tareas
marcadas y ninguna hecha.

Tarea objetivo: `$ARGUMENTS` — si viene vacía, la primera de `FEATURES.json`
con `"hecha": false` y todas sus `depende_de` ya hechas.

## Antes de tocar nada

1. `git rev-parse --abbrev-ref HEAD` tiene que decir `main`.
2. `git status --porcelain` tiene que salir vacío. Si hay cambios sin
   commitear no son tuyos: **para**.
3. Corre `sh pruebas/puerta.sh`. Si sale roja **antes** de empezar, el repo ya
   estaba roto: **para** y di qué paso falla.
4. Corre el `check` de la tarea. Tiene que salir **distinto de 0**. Si ya pasa,
   el check está roto, no la tarea hecha: **para** y dilo.

## El ciclo, y en este orden

1. **Test primero.** Escribe la prueba que hoy falla y mañana pasará. Córrela y
   **mírala fallar**. Un test que nunca has visto en rojo no prueba nada.
2. Implementa lo mínimo para ponerla en verde.
3. Refactoriza con la suite en verde.
4. `sh pruebas/puerta.sh` entera.
5. Marca la tarea `"hecha": true` con la fecha en `FEATURES.json`, y solo
   entonces — el paso 6 de la puerta comprobará que su `check` pasa de verdad.
6. `sh pruebas/commit-en-verde.sh "mensaje"`. Ese guion vuelve a correr la
   puerta y mira qué entra en el commit. No hagas `git commit` a mano.

## Cláusulas de parada

Para, escribe en la bitácora y espera a José si se cumple **cualquiera**:

- **Rojo dos veces.** La puerta falla dos veces seguidas en la misma tarea por
  la misma causa. Al segundo intento ya no estás arreglando, estás adivinando.
- **Hay que decidir.** Cualquier cosa con más de una respuesta defendible:
  nombres de una API pública, formato de datos que otro consume, borrar algo,
  tocar el NAS, credenciales, dependencias nuevas. No elijas por él.
- **Una tarea y fuera.** Por defecto haces **una** tarea y paras. Solo encadenas
  más si José lo pidió explícitamente al lanzarte.
- **No queda nada elegible.** Ninguna pendiente con dependencias satisfechas.
- **El check ya pasaba.** Ver punto 4 de arriba.
- **Te has visto tocando el check.** Si para poner una tarea en verde estás
  editando su `check`, para. Eso es mover la portería, no marcar gol.
- **Fuera del alcance.** El diff toca ficheros que la tarea no menciona.
  Un bucle que se expande solo es un bucle que nadie revisa.

## Bitácora

Al parar, por la razón que sea, añade a `docs/bitacora-bucle.md`:

```
## <fecha y hora> · <id> · <HECHA | PARADA>
- qué se ha hecho (comandos y su salida, no adjetivos)
- qué NO se ha hecho
- commit, si lo hay
- por qué paraste
```

Lo que **nunca** haces: `git push --force`, tocar `herramientas/verificar.sh`
(es un humo contra el NAS, no la puerta), commitear rojo, borrar entradas de
`FEATURES.json`, ni informar de un paso como hecho sin la salida del comando
que lo demuestra.
