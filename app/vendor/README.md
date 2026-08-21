# Librerías del mapa, autoalojadas

No vienen de un CDN y no es por gusto: la CSP del sitio es
`script-src 'self'; worker-src 'self'; connect-src 'self'`, así que todo el
código que ejecuta el navegador tiene que salir de este mismo origen.

| Fichero | Qué es | Licencia |
| --- | --- | --- |
| `maplibre-gl-5.24.0-csp.js` | MapLibre GL JS 5.24.0, build **CSP** | BSD 3-Clause |
| `maplibre-gl-5.24.0-csp-worker.js` | su worker, en fichero suelto | BSD 3-Clause |
| `maplibre-gl-5.24.0.css` | estilos del control del mapa | BSD 3-Clause |
| `pmtiles-4.5.0.js` | protocolo PMTiles para MapLibre | BSD 3-Clause |

**Por qué la 5 y no la 6.** MapLibre 6 se publica solo como ESM y arranca su
worker desde un `blob:`, que `worker-src 'self'` bloquea. La rama 5 mantiene
el build `-csp`, pensado justo para esto: script clásico, sin `eval`, y el
worker se declara a mano con `maplibregl.setWorkerUrl(...)` apuntando a un
fichero del propio origen. Sin paso de build, que es la regla de la casa.

**Lo que pesa.** 388 KB comprimidos entre las cuatro. Suena mucho al lado de
los ~150 KB que ocupa hoy la app entera, pero hay que mirarlo contra lo que
sirven: el basemap de Huelva son 41 MB. La librería es el 1 % de lo que hay
que descargar para tener mapa en el campo, así que va en la precarga del
Service Worker: una app que se lleva a la marisma sin cobertura no puede
depender de bajarse el motor del mapa justo cuando no hay red.

**Cómo actualizarlas.** `npm pack maplibre-gl@5 pmtiles` en una carpeta
temporal, extraer, y copiar `dist/maplibre-gl-csp.js`,
`dist/maplibre-gl-csp-worker.js`, `dist/maplibre-gl.css` y `dist/pmtiles.js`
con el número de versión en el nombre. El nombre lleva la versión a
propósito: son inmutables y cacheables un año, igual que el `.pmtiles`. Al
cambiarlas hay que subir `V` en `sw.js`.
