# Referencias FUA

La única imagen activa de la aplicación es
`frontend/src/assets/fua-v02-referencia.png`. El diálogo de impresión la usa tanto
para la vista previa como para la salida PDF con referencia. Mantenga ese archivo
en su ruta, pues el componente lo importa y Vite lo incluye en el build.

`fua-historica.webp` se conserva aquí solo como archivo documental. Antes estaba
en `frontend/src/assets/fua-referencia.webp` y se mostraba en calibraciones antiguas.
La aplicación ya no la carga; tampoco admite fondos alternativos.

La referencia activa es la extracción del anexo 1, página 11, de la Directiva
002-2024-SIS/GREP-V.02. Su origen y geometría están descritos en
`docs/FUA_REVISION_20261014.md`. Las posiciones calibradas se guardan como geometría
en el navegador y no dentro de estas imágenes.
