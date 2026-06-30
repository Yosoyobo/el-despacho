/* geo_picker.js — Selector de dirección/ubicación unificado (S-Geo-Picker-V1).
 *
 * UN solo componente, data-attr-driven, para TODO lugar donde se ingresa una
 * dirección, ubicación o lugar. Conforme escribes busca en vivo POIs internos
 * (sedes / clientes / proveedores con ubicación) + direcciones de Nominatim y
 * los muestra en una lista; al elegir uno —o al pegar/buscar una dirección—
 * el mapa pone el pin en automático.
 *
 * Dos modos (atributo `data-modo`):
 *   - "completo": rellena lat/lng (hidden) + etiqueta + mapa Leaflet con pin
 *     arrastrable, clic en el mapa, "mi ubicación" y círculo de radio opcional.
 *   - "texto": sólo rellena un campo de dirección (sin coordenadas ni mapa).
 *
 * Leaflet se carga PEREZOSAMENTE (sólo cuando se abre un mapa) para no inflar
 * las páginas sin mapa. Se re-inicializa en `htmx:afterSwap` (modales/tabs).
 * "gratis o abortamos": Nominatim + OSM, debounce 600 ms, sin API key.
 *
 * Dual-copy (regla §18): este archivo es idéntico en el-taller y la-gerencia.
 */
(function () {
  "use strict";

  var LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
  var LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  var leafletPedido = false;

  function ensureLeaflet(cb) {
    if (window.L) { cb(); return; }
    if (!leafletPedido) {
      leafletPedido = true;
      if (!document.querySelector("link[data-leaflet]")) {
        var l = document.createElement("link");
        l.rel = "stylesheet"; l.href = LEAFLET_CSS; l.setAttribute("data-leaflet", "1");
        document.head.appendChild(l);
      }
      if (!document.querySelector("script[data-leaflet]")) {
        var s = document.createElement("script");
        s.src = LEAFLET_JS; s.setAttribute("data-leaflet", "1");
        document.head.appendChild(s);
      }
    }
    var intentos = 0;
    var iv = setInterval(function () {
      intentos += 1;
      if (window.L) { clearInterval(iv); cb(); }
      else if (intentos > 130) { clearInterval(iv); }  // ~8 s; el buscador sigue sin mapa
    }, 60);
  }

  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }
  function byId(id) { return id ? document.getElementById(id) : null; }
  function num(i) { var v = i ? parseFloat(i.value) : NaN; return isNaN(v) ? null : v; }

  function initPicker(root) {
    if (root.getAttribute("data-geo-init") === "1") return;
    root.setAttribute("data-geo-init", "1");

    var modo = root.getAttribute("data-modo") || "texto";
    var endpoint = root.getAttribute("data-endpoint");
    var box = root.querySelector("[data-geo-buscar]");
    var lista = root.querySelector("[data-geo-resultados]");
    if (!box || !lista || !endpoint) return;

    var conPois = root.getAttribute("data-con-pois") === "1";
    var latI = byId(root.getAttribute("data-lat-input"));
    var lngI = byId(root.getAttribute("data-lng-input"));
    var etiqI = byId(root.getAttribute("data-etiqueta-input"));
    var radioI = byId(root.getAttribute("data-radio-input"));
    var textoI = byId(root.getAttribute("data-objetivo-texto"));
    var coordsEl = root.querySelector("[data-geo-coords]");
    var mapaEl = root.querySelector("[data-geo-mapa]");
    var toggle = root.querySelector("[data-geo-toggle-mapa]");
    var btnLoc = root.querySelector("[data-geo-localizar]");
    var zoom = parseInt(root.getAttribute("data-zoom") || "16", 10);

    var map = null, marker = null, circ = null, mapaListo = false;

    function radioVal() { var r = num(radioI); return (r && r > 0) ? r : 150; }

    function pintarMapa(lat, lng, centrar) {
      if (!map || !window.L) return;
      if (!marker) {
        marker = L.marker([lat, lng], { draggable: true }).addTo(map);
        marker.on("dragend", function () { var p = marker.getLatLng(); setCoords(p.lat, p.lng, false); });
      } else { marker.setLatLng([lat, lng]); }
      if (radioI) {
        if (!circ) {
          circ = L.circle([lat, lng], { radius: radioVal(), color: "#465fff", fillColor: "#465fff", fillOpacity: 0.12, weight: 2 }).addTo(map);
        } else { circ.setLatLng([lat, lng]); circ.setRadius(radioVal()); }
      }
      if (centrar) map.setView([lat, lng], zoom);
    }

    function setCoords(lat, lng, centrar) {
      lat = Number(lat); lng = Number(lng);
      if (latI) { latI.value = lat.toFixed(6); latI.dispatchEvent(new Event("input", { bubbles: true })); }
      if (lngI) { lngI.value = lng.toFixed(6); lngI.dispatchEvent(new Event("input", { bubbles: true })); }
      if (coordsEl) coordsEl.textContent = lat.toFixed(6) + ", " + lng.toFixed(6);
      pintarMapa(lat, lng, centrar);
    }

    function reverseEtiqueta(lat, lng) {
      var destino = etiqI || (modo !== "texto" ? textoI : null);
      if (!destino || destino.value.trim()) return;
      fetch(endpoint + "?lat=" + lat.toFixed(6) + "&lng=" + lng.toFixed(6))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.punto && d.punto.nombre && !destino.value.trim()) {
            destino.value = (destino === textoI) ? (d.punto.direccion || d.punto.nombre) : d.punto.nombre;
            destino.dispatchEvent(new Event("input", { bubbles: true }));
          }
        })
        .catch(function () {});
    }

    function crearMapa() {
      if (mapaListo || !mapaEl) return;
      ensureLeaflet(function () {
        if (mapaListo || !mapaEl || !window.L) return;
        mapaListo = true;
        var lat0 = num(latI), lng0 = num(lngI);
        var tienePin = lat0 !== null && lng0 !== null;
        var centro = tienePin ? [lat0, lng0] : [19.4326, -99.1332];  // CDMX por defecto
        map = L.map(mapaEl).setView(centro, tienePin ? zoom : 11);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
        map.on("click", function (e) { setCoords(e.latlng.lat, e.latlng.lng, false); reverseEtiqueta(e.latlng.lat, e.latlng.lng); });
        if (radioI) radioI.addEventListener("input", function () { if (circ) circ.setRadius(radioVal()); });
        setTimeout(function () { map.invalidateSize(); if (tienePin) pintarMapa(lat0, lng0, true); }, 120);
      });
    }

    function abrirMapa() {
      if (!mapaEl) return;
      mapaEl.classList.remove("hidden");
      crearMapa();
      setTimeout(function () { if (map) map.invalidateSize(); }, 160);
      if (toggle) toggle.textContent = toggle.getAttribute("data-cerrar") || "Ocultar mapa";
    }

    if (root.getAttribute("data-mapa-abierto") === "1") abrirMapa();
    if (toggle && mapaEl) toggle.addEventListener("click", function () {
      var oculto = mapaEl.classList.toggle("hidden");
      if (oculto) { toggle.textContent = toggle.getAttribute("data-abrir") || "Ver / fijar en el mapa"; }
      else { abrirMapa(); }
    });

    if (btnLoc && navigator.geolocation) btnLoc.addEventListener("click", function () {
      btnLoc.disabled = true;
      navigator.geolocation.getCurrentPosition(function (pos) {
        if (modo !== "texto") { abrirMapa(); setCoords(pos.coords.latitude, pos.coords.longitude, true); }
        btnLoc.disabled = false;
      }, function () { btnLoc.disabled = false; }, { enableHighAccuracy: true, timeout: 10000 });
    });

    function elegir(r) {
      if (modo === "texto") {
        if (textoI) {
          textoI.value = r.direccion || r.nombre || "";
          textoI.dispatchEvent(new Event("input", { bubbles: true }));
          textoI.dispatchEvent(new Event("change", { bubbles: true }));
        }
      } else {
        if (r.lat != null && r.lng != null) { abrirMapa(); setCoords(r.lat, r.lng, true); }
        var destino = etiqI || textoI;
        if (destino && !destino.value.trim()) {
          destino.value = (destino === textoI) ? (r.direccion || r.nombre || "") : (r.nombre || r.direccion || "");
          destino.dispatchEvent(new Event("input", { bubbles: true }));
        }
      }
      lista.classList.add("hidden");
      box.value = r.nombre || r.direccion || "";
    }

    function pintar(data, autoaplicar) {
      lista.innerHTML = "";
      var items = [];
      if (conPois && data && data.pois) {
        data.pois.forEach(function (p) {
          items.push({ nombre: p.label, direccion: p.label, lat: p.lat, lng: p.lng, _poi: p.fuente });
        });
      }
      ((data && data.resultados) || []).forEach(function (r) { items.push(r); });
      if (!items.length) { lista.classList.add("hidden"); return; }
      items.forEach(function (r) {
        var li = document.createElement("li");
        li.className = "cursor-pointer px-3 py-2 text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-800";
        if (r._poi) {
          li.innerHTML = '<span class="mr-1.5 rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">' + esc(r._poi) + "</span>" + esc(r.nombre);
        } else {
          li.textContent = r.direccion || r.nombre;
        }
        li.addEventListener("click", function () { elegir(r); });
        lista.appendChild(li);
      });
      lista.classList.remove("hidden");
      // Pegar/buscar una dirección: el mapa pone el pin en automático (1er match).
      if (autoaplicar && items.length) { elegir(items[0]); }
    }

    function buscar(q, autoaplicar) {
      fetch(endpoint + "?q=" + encodeURIComponent(q) + (conPois ? "" : "&pois=0"))
        .then(function (r) { return r.json(); })
        .then(function (d) { pintar(d, autoaplicar); })
        .catch(function () { lista.classList.add("hidden"); });
    }

    // "lat, lng" pegado → fija el pin directo (sólo modo completo).
    function tryCoords(q) {
      var m = q.match(/^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$/);
      if (m && modo !== "texto") {
        abrirMapa(); setCoords(parseFloat(m[1]), parseFloat(m[2]), true);
        lista.classList.add("hidden"); return true;
      }
      return false;
    }

    var t = null;
    box.addEventListener("input", function () {
      var q = box.value.trim();
      if (t) clearTimeout(t);
      if (tryCoords(q)) return;
      if (q.length < 4) { lista.classList.add("hidden"); return; }
      t = setTimeout(function () { buscar(q, false); }, 600);  // debounce Nominatim
    });
    box.addEventListener("keydown", function (e) {
      if (e.key !== "Enter") return;
      e.preventDefault();
      var q = box.value.trim();
      if (tryCoords(q) || q.length < 3) return;
      if (t) clearTimeout(t);
      buscar(q, true);  // Enter = aplica el primer resultado (auto-pin)
    });
    box.addEventListener("paste", function () {
      setTimeout(function () {
        var q = box.value.trim();
        if (tryCoords(q) || q.length < 3) return;
        if (t) clearTimeout(t);
        buscar(q, true);  // pegar dirección = auto-pin
      }, 30);
    });
  }

  function scan() {
    document.querySelectorAll(".geo-picker[data-geo-picker]").forEach(initPicker);
  }

  document.addEventListener("DOMContentLoaded", scan);
  document.addEventListener("htmx:afterSwap", scan);

  // Cierra cualquier lista de resultados al hacer clic afuera de su picker.
  document.addEventListener("click", function (e) {
    document.querySelectorAll(".geo-picker[data-geo-picker]").forEach(function (root) {
      var box = root.querySelector("[data-geo-buscar]");
      var lista = root.querySelector("[data-geo-resultados]");
      if (lista && e.target !== box && !lista.contains(e.target)) lista.classList.add("hidden");
    });
  });
})();
