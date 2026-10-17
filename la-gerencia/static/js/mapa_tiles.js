/* mapa_tiles.js — ÚNICO lugar donde se nombra el proveedor de mosaicos de los mapas.
 *
 * Todo mapa Leaflet del sistema (geo-picker, geocerca de sedes, tablero del
 * checador, rutas de mandados) crea su capa con `despachoTileLayer()`. Cambiar
 * de proveedor gratuito es cambiar `TILE_URL` aquí y nada más («gratis o
 * abortamos»: nada con costo recurrente). `tests/test_mapa_tiles.py` impide
 * volver a escribir un `L.tileLayer(` suelto.
 *
 * Por qué `referrerPolicy: 'origin'` (S-Tickets-Oct14): los servidores de
 * OpenStreetMap bloquean (403 «Access blocked — App is not following the tile
 * usage policy») a quien pide mosaicos SIN `Referer`. Django manda por defecto
 * `Referrer-Policy: same-origin`, y con ésa el navegador NO envía Referer a
 * otro origen. Con `origin` cada mosaico lleva `https://taller.learningcenter.mx/`
 * (sólo el origen, nunca la ruta) sin importar la política del sitio.
 *
 * Sin subdominios `{s}`: la política de OSM los desaconseja (HTTP/2 ya
 * multiplexa). Dual-copy (regla §18): idéntico en El Taller y La Gerencia.
 */
(function () {
  "use strict";
  if (window.despachoTileLayer) return;

  var TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  var ATRIBUCION = '&copy; <a href="https://www.openstreetmap.org/copyright" ' +
    'target="_blank" rel="noopener">OpenStreetMap</a> contributors';

  window.DESPACHO_TILES = { url: TILE_URL, attribution: ATRIBUCION, maxZoom: 19, referrerPolicy: "origin" };

  window.despachoTileLayer = function (extra) {
    var opciones = {};
    var base = window.DESPACHO_TILES;
    for (var k in base) if (k !== "url") opciones[k] = base[k];
    if (extra) for (var j in extra) opciones[j] = extra[j];
    return window.L.tileLayer(base.url, opciones);
  };
})();
