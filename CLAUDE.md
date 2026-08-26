# CLAUDE.md

Ver [`AGENTS.md`](./AGENTS.md) — la guía canónica para agentes y para quien
toque este repo. Este puntero existe porque Claude Code busca `CLAUDE.md`.

Recordatorios rápidos, el detalle en `AGENTS.md`:

- **Guía de observación de aves de las Marismas del Odiel.** PWA estática
  (`app/`, JS a pelo, sin build), más dos servicios Python de biblioteca
  estándar (`services/api`, `services/mareas`). Todo en español, código
  incluido.
- **La puerta local antes de empujar**: `pruebas/puerta.sh`. Corre lo mismo que
  el job `comprobar` de CI, más la suite de tests. **`herramientas/verificar.sh`
  no es eso**: es un humo contra el contenedor ya desplegado en el NAS.
- **Sin ramas, sin PRs.** Se trabaja sobre `main` y se empuja; CI despliega al
  NAS por Tailscale. El despliegue está detrás de la variable
  `AUTODEPLOY_ENABLED`; si no está en `true`, el job no corre.
- **La versión de `app.js` vive en dos sitios** — `index.html` y la lista
  `ARMAZON` de `sw.js`. Si se desincronizan, quien tenga la app instalada se
  queda con el JS viejo **para siempre**. `validar-datos.py` lo comprueba.
- **`services/api/app.py` es la única superficie de escritura del sitio** y es
  deliberadamente incapaz: sólo INSERT, una ruta POST, sin lectura, sin IPs.
  No le añadas capacidades sin pensarlo dos veces.
- **Estándares**: TDD, DDD, SOLID, cobertura con trinquete. Este es el proyecto
  de la cartera que **arranca desde cero en tests** — lee la sección
  «Estándares» de `AGENTS.md` antes de escribir código nuevo.
- **Subagentes** (`.claude/agents/`): `verificador` corre la puerta y da
  veredicto VERDE/ROJO/INESTABLE. `naturalista` revisa que lo que la app
  afirma sobre las aves sea defendible; su veredicto sobre un dato inventado
  es BLOQUEANTE.
