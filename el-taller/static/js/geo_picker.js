/* geo_picker.js — Selector de dirección/ubicación unificado (S-Geo-Picker-V1).
 *
 * UN solo componente, data-attr-driven, para TODO lugar donde se ingresa una
 * dirección, ubicación o lugar. Conforme escribes busca en vivo POIs internos
 * (sedes / clientes / proveedores con ubicación) + direcciones de Nominatim y
 * los muestra en una lista; al elegir uno —o al pegar/buscar una dirección—
 * el mapa pone el pin en automático.
 *
 * El componente se arma según lo que traiga el contenedor `.geo-picker`:
 *   - Si trae un `[data-geo-buscar]` (input dedicado) → ese input es el buscador
 *     (sedes, geocerca, destino de mandado). Si NO, el PROPIO campo objetivo
 *     (`data-objetivo-texto`) se vuelve el buscador (un solo campo: clientes,
 *     proveedores, lugar de tarea).
 *   - Si trae un `[data-geo-mapa]` (+ `data-lat-input`/`data-lng-input`) → maneja
 *     un mini-mapa Leaflet con pin (clic/arrastre/«Mi ubicación»/radio opcional).
 *   - Sin mapa y con el campo como buscador (modo "texto") → solo autocompletado.
 *
 * Leaflet se carga PEREZOSAMENTE (sólo al abrir un mapa). Se re-inicializa en
 * `htmx:afterSwap` (modales/tabs). "gratis o abortamos": Nominatim + OSM,
 * debounce 600 ms, sin API key. Dual-copy (regla §18): idéntico en ambas apps.
 */
(function () {
  "use strict";

  var LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
  var LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  var leafletPedido = false;

  var UL_CLASS = "absolute left-0 right-0 z-[1000] mt-1 hidden max-h-56 overflow-y-auto " +
    "rounded-lg border border-gray-200 bg-white text-sm shadow-theme-lg " +
    "dark:border-gray-700 dark:bg-gray-900";

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
  function deburr(s) { return (s == null ? "" : "" + s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, ""); }

  // Conserva el NÚMERO de calle que el usuario escribió (Nominatim devuelve la
  // calle SIN número, y para una entrega el número es indispensable). Si el texto
  // del usuario empieza con la calle de la dirección elegida y trae algo más (el
  // número), conserva su calle+número y le añade el contexto (colonia/ciudad/CP).
  function fusionarNumero(textoUsuario, direccion) {
    textoUsuario = (textoUsuario || "").trim();
    if (!direccion) return textoUsuario;
    if (!textoUsuario) return direccion;
    var segs = direccion.split(",").map(function (s) { return s.trim(); });
    var calle = segs[0] || "";
    var u = deburr(textoUsuario), c = deburr(calle);
    if (c && u.indexOf(c) === 0 && u.length > c.length) {
      return [textoUsuario].concat(segs.slice(1)).join(", ");
    }
    return direccion;
  }

  // Pinta la lista combinada (POIs + direcciones). `autoaplicar` toma el primero.
  // `footer` (opcional) = {label, onClick} → item especial al final (p. ej. el
  // toggle "buscar en el mapa" del modo acotado).
  function pintarLista(lista, data, conPois, onElegir, autoaplicar, footer) {
    lista.innerHTML = "";
    var items = [];
    if (conPois && data && data.pois) {
      data.pois.forEach(function (p) {
        items.push({ nombre: p.label, direccion: p.direccion || p.label, lat: p.lat, lng: p.lng, _poi: p.fuente });
      });
    }
    ((data && data.resultados) || []).forEach(function (r) { items.push(r); });
    if (!items.length && !footer) { lista.classList.add("hidden"); return; }
    items.forEach(function (r) {
      var li = document.createElement("li");
      li.className = "cursor-pointer px-3 py-2 text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-800";
      if (r._poi) {
        li.innerHTML = '<span class="mr-1.5 rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">' + esc(r._poi) + "</span>" + esc(r.nombre);
      } else {
        li.textContent = r.direccion || r.nombre;
      }
      li.addEventListener("click", function () { onElegir(r); });
      lista.appendChild(li);
    });
    if (footer) {
      var lf = document.createElement("li");
      lf.className = "cursor-pointer border-t border-gray-100 px-3 py-2 text-xs font-medium text-brand-600 hover:bg-gray-50 dark:border-gray-800 dark:text-brand-400 dark:hover:bg-gray-800";
      lf.textContent = footer.label;
      lf.addEventListener("click", function (e) { e.stopPropagation(); footer.onClick(); });
      lista.appendChild(lf);
    }
    lista.classList.remove("hidden");
    if (autoaplicar && items.length) onElegir(items[0]);
  }

  // opts.acotado (bool): limita la búsqueda a direcciones guardadas + POIs (sin
  // Nominatim) hasta que el usuario pida "buscar en el mapa" (mapa opcional).
  function hacerBuscador(lista, endpoint, conPois, onElegir, opts) {
    opts = opts || {};
    var t = null, mapaHab = false, ultimaQ = "";
    function url(q) {
      var u = endpoint + "?q=" + encodeURIComponent(q) + (conPois ? "" : "&pois=0");
      if (opts.acotado) { u += "&acotado=1"; if (mapaHab) u += "&mapa=1"; }
      return u;
    }
    function go(q, auto) {
      ultimaQ = q;
      fetch(url(q))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          var footer = (opts.acotado && !mapaHab)
            ? { label: "🌐 Buscar en el mapa…", onClick: function () { mapaHab = true; go(ultimaQ, false); } }
            : null;
          pintarLista(lista, d, conPois, onElegir, auto, footer);
        })
        .catch(function () { lista.classList.add("hidden"); });
    }
    return {
      go: go,
      debounce: function (q) { if (t) clearTimeout(t); t = setTimeout(function () { go(q, false); }, 600); },
      cancel: function () { if (t) clearTimeout(t); },
    };
  }

  // Mini-mapa Leaflet con pin. Devuelve { setCoords, abrir }.
  function montarMapa(root, refs, endpoint) {
    var mapaEl = root.querySelector("[data-geo-mapa]");
    var toggle = root.querySelector("[data-geo-toggle-mapa]");
    var btnLoc = root.querySelector("[data-geo-localizar]");
    var coordsEl = root.querySelector("[data-geo-coords]");
    var latI = refs.latI, lngI = refs.lngI, etiqI = refs.etiqI, radioI = refs.radioI, textoI = refs.textoI;
    var zoom = parseInt(root.getAttribute("data-zoom") || "16", 10);
    var map = null, marker = null, circ = null, listo = false;

    function radioVal() { var r = num(radioI); return (r && r > 0) ? r : 150; }

    function pintar(lat, lng, centrar) {
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
      if (latI) { latI.value = lat.toFixed(6); latI.dispatchEvent(new Event("input", { bubbles: true })); latI.dispatchEvent(new Event("change", { bubbles: true })); }
      if (lngI) { lngI.value = lng.toFixed(6); lngI.dispatchEvent(new Event("input", { bubbles: true })); lngI.dispatchEvent(new Event("change", { bubbles: true })); }
      if (coordsEl) coordsEl.textContent = lat.toFixed(6) + ", " + lng.toFixed(6);
      pintar(lat, lng, centrar);
    }

    function reverse(lat, lng) {
      var destino = etiqI || textoI;
      if (!destino || destino.value.trim()) return;
      fetch(endpoint + "?lat=" + lat.toFixed(6) + "&lng=" + lng.toFixed(6))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.punto && d.punto.nombre && !destino.value.trim()) {
            destino.value = (destino === textoI) ? (d.punto.direccion || d.punto.nombre) : d.punto.nombre;
            destino.dispatchEvent(new Event("input", { bubbles: true }));
            destino.dispatchEvent(new Event("change", { bubbles: true }));
          }
        })
        .catch(function () {});
    }

    function crear() {
      if (listo || !mapaEl) return;
      ensureLeaflet(function () {
        if (listo || !mapaEl || !window.L) return;
        listo = true;
        var lat0 = num(latI), lng0 = num(lngI);
        var tienePin = lat0 !== null && lng0 !== null;
        var centro = tienePin ? [lat0, lng0] : [19.4326, -99.1332];  // CDMX por defecto
        map = L.map(mapaEl).setView(centro, tienePin ? zoom : 11);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
        map.on("click", function (e) { setCoords(e.latlng.lat, e.latlng.lng, false); reverse(e.latlng.lat, e.latlng.lng); });
        if (radioI) radioI.addEventListener("input", function () { if (circ) circ.setRadius(radioVal()); });
        setTimeout(function () { map.invalidateSize(); if (tienePin) pintar(lat0, lng0, true); }, 120);
      });
    }

    function abrir() {
      if (!mapaEl) return;
      mapaEl.classList.remove("hidden");
      crear();
      setTimeout(function () { if (map) map.invalidateSize(); }, 160);
      if (toggle) toggle.textContent = toggle.getAttribute("data-cerrar") || "Ocultar mapa";
    }

    if (toggle) toggle.addEventListener("click", function () {
      var oculto = mapaEl.classList.toggle("hidden");
      if (oculto) { toggle.textContent = toggle.getAttribute("data-abrir") || "Ver / fijar en el mapa"; }
      else { abrir(); }
    });
    if (btnLoc && navigator.geolocation) btnLoc.addEventListener("click", function () {
      btnLoc.disabled = true;
      navigator.geolocation.getCurrentPosition(function (pos) {
        abrir(); setCoords(pos.coords.latitude, pos.coords.longitude, true);
        btnLoc.disabled = false;
      }, function () { btnLoc.disabled = false; }, { enableHighAccuracy: true, timeout: 10000 });
    });
    if (root.getAttribute("data-mapa-abierto") === "1") abrir();

    return { setCoords: setCoords, abrir: abrir };
  }

  function initPicker(root) {
    if (root.getAttribute("data-geo-init") === "1") return;
    root.setAttribute("data-geo-init", "1");
    var endpoint = root.getAttribute("data-endpoint");
    if (!endpoint) return;
    var conPois = root.getAttribute("data-con-pois") === "1";
    var campo = byId(root.getAttribute("data-objetivo-texto"));
    var latI = byId(root.getAttribute("data-lat-input"));
    var lngI = byId(root.getAttribute("data-lng-input"));
    var etiqI = byId(root.getAttribute("data-etiqueta-input"));
    var radioI = byId(root.getAttribute("data-radio-input"));
    var dedicado = root.querySelector("[data-geo-buscar]");
    var tieneMapa = !!root.querySelector("[data-geo-mapa]");

    var box, lista, esCampo = false;
    if (dedicado) {
      box = dedicado;
      lista = root.querySelector("[data-geo-resultados]");
    } else if (campo) {
      esCampo = true; box = campo;
      var wrap = document.createElement("div");
      wrap.className = "relative";
      campo.parentNode.insertBefore(wrap, campo);
      wrap.appendChild(campo);
      lista = document.createElement("ul");
      lista.className = UL_CLASS;
      lista.setAttribute("data-geo-resultados", "");
      wrap.appendChild(lista);
      campo.setAttribute("autocomplete", "off");
    } else { return; }
    if (!box || !lista) return;

    var mapa = tieneMapa
      ? montarMapa(root, { latI: latI, lngI: lngI, etiqI: etiqI, radioI: radioI, textoI: campo }, endpoint)
      : null;

    function onElegir(r) {
      if (mapa && r.lat != null && r.lng != null) { mapa.abrir(); mapa.setCoords(r.lat, r.lng, true); }
      if (esCampo) {
        campo.value = fusionarNumero(campo.value, r.direccion || r.nombre);
        campo.dispatchEvent(new Event("input", { bubbles: true }));
        campo.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        var destino = etiqI || campo;
        if (destino && !destino.value.trim()) {
          destino.value = (destino === campo) ? fusionarNumero(box.value, r.direccion || r.nombre) : (r.nombre || r.direccion || "");
          destino.dispatchEvent(new Event("input", { bubbles: true }));
          destino.dispatchEvent(new Event("change", { bubbles: true }));
        }
        box.value = r.nombre || r.direccion || "";
      }
      lista.classList.add("hidden");
    }

    var acotado = root.getAttribute("data-geo-acotado") === "1";
    var b = hacerBuscador(lista, endpoint, conPois, onElegir, { acotado: acotado });
    var autoPaste = !!mapa;  // con mapa, pegar/Enter aplica el 1er resultado (auto-pin)

    function tryCoords(q) {
      if (!mapa) return false;
      var m = q.match(/^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$/);
      if (m) { mapa.abrir(); mapa.setCoords(parseFloat(m[1]), parseFloat(m[2]), true); lista.classList.add("hidden"); return true; }
      return false;
    }

    box.addEventListener("input", function () {
      var q = box.value.trim();
      if (tryCoords(q)) { b.cancel(); return; }
      if (q.length < 4) { b.cancel(); lista.classList.add("hidden"); return; }
      b.debounce(q);
    });
    box.addEventListener("paste", function () {
      setTimeout(function () {
        var q = box.value.trim();
        if (tryCoords(q) || q.length < 3) return;
        b.cancel(); b.go(q, autoPaste);
      }, 30);
    });
    // Enter aplica el 1er resultado solo en inputs (no en textareas, donde Enter
    // es salto de línea). Sin mapa (modo texto) no se secuestra el Enter.
    if (autoPaste && box.tagName === "INPUT") {
      box.addEventListener("keydown", function (e) {
        if (e.key !== "Enter") return;
        e.preventDefault();
        var q = box.value.trim();
        if (tryCoords(q) || q.length < 3) return;
        b.cancel(); b.go(q, true);
      });
    }

    // Modo texto puro (campo-buscador, sin mapa): el contenedor de config ya no
    // se necesita (el dropdown vive junto al campo). Se elimina para no dejar hueco.
    if (esCampo && !tieneMapa) root.remove();
  }

  function scan() {
    document.querySelectorAll(".geo-picker[data-geo-picker]").forEach(initPicker);
  }

  document.addEventListener("DOMContentLoaded", scan);
  document.addEventListener("htmx:afterSwap", scan);

  // Cierra cualquier lista de resultados al hacer clic afuera de su buscador.
  document.addEventListener("click", function (e) {
    document.querySelectorAll("[data-geo-resultados]").forEach(function (lista) {
      var box = lista.previousElementSibling;
      if (e.target !== box && !lista.contains(e.target)) lista.classList.add("hidden");
    });
  });
})();
