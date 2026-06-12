/*
 * El Checador — snapshot de geolocalización al checar/registrar visita + reloj.
 *
 * Cualquier <button data-checar-geo> dentro de un <form> captura la ubicación
 * (navigator.geolocation) al hacer click, llena los hidden lat/lng/precision/
 * sin_geo del form y lo envía. Si el GPS falla, deniega o expira, marca
 * sin_geo=1 y envía igual (la checada NUNCA se bloquea). Delegado vía
 * htmx:afterSwap para que funcione también en el modal de visita inyectado.
 */
(function () {
  "use strict";

  function uuid() {
    try { return crypto.randomUUID(); }
    catch (e) { return "c-" + Date.now() + "-" + Math.round(Math.random() * 1e9); }
  }

  function setVal(form, name, value) {
    var el = form.querySelector("[name=" + name + "]");
    if (el) el.value = value;
  }

  function wire(btn) {
    if (btn.__checadorWired) return;
    btn.__checadorWired = true;
    btn.addEventListener("click", function () {
      var form = btn.closest("form");
      if (!form) return;
      btn.disabled = true;
      btn.classList.add("opacity-60");
      var estado = form.querySelector("[data-geo-estado]");
      var uf = form.querySelector("[name=uuid]");
      if (uf && !uf.value) uf.value = uuid();
      if (estado) estado.textContent = "Tomando tu ubicación…";

      function finalizar() {
        // Offline → encola en IndexedDB; online → envía el form normal.
        if (!navigator.onLine) {
          encolar(itemDeForm(form)).then(function () {
            if (estado) estado.textContent = "Guardado sin conexión. Se enviará al reconectar.";
            actualizarBadge();
            btn.disabled = false;
            btn.classList.remove("opacity-60");
          });
          return;
        }
        form.submit();
      }
      function sinGeo(msg) {
        setVal(form, "sin_geo", "1");
        if (estado && msg) estado.textContent = msg;
        finalizar();
      }

      if (!navigator.geolocation) { sinGeo("Sin ubicación — se registrará igual."); return; }
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          setVal(form, "lat", pos.coords.latitude);
          setVal(form, "lng", pos.coords.longitude);
          setVal(form, "precision", pos.coords.accuracy || "");
          finalizar();
        },
        function () { sinGeo("Sin ubicación — se registrará igual."); },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
      );
    });
  }

  // ── Cola offline (IndexedDB) ──────────────────────────────────────────
  var DB_NOMBRE = "checador", STORE = "cola", SYNC_URL = "/checador/api/sync";

  function abrirDB() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) { reject(new Error("sin IndexedDB")); return; }
      var req = indexedDB.open(DB_NOMBRE, 1);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "uuid" });
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function conStore(modo, fn) {
    return abrirDB().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, modo);
        var store = tx.objectStore(STORE);
        var out = fn(store);
        tx.oncomplete = function () { resolve(out && out.result !== undefined ? out.result : out); };
        tx.onerror = function () { reject(tx.error); };
      });
    });
  }

  function itemDeForm(form) {
    var get = function (n) { var el = form.querySelector("[name=" + n + "]"); return el ? el.value : ""; };
    var item = {
      uuid: get("uuid") || uuid(),
      registrado_en: new Date().toISOString(),
      lat: get("lat") || null, lng: get("lng") || null,
      precision: get("precision") || null, sin_geo: get("sin_geo") === "1",
    };
    if (form.querySelector("[name=accion]")) {
      item.tipo = get("accion") || "entrada";
    } else {
      item.tipo = "visita";
      var tipoSel = form.querySelector("[name=tipo]:checked") || form.querySelector("[name=tipo]");
      item.visita_tipo = tipoSel ? tipoSel.value : "cliente";
      item.cliente = get("cliente") || null;
      item.proveedor = get("proveedor") || null;
      item.nota = get("nota") || "";
    }
    return item;
  }

  function encolar(item) {
    return conStore("readwrite", function (store) { store.put(item); }).catch(function () {});
  }

  function leerCola() {
    return conStore("readonly", function (store) { return store.getAll(); })
      .then(function (r) { return r || []; }).catch(function () { return []; });
  }

  function borrar(uuid) {
    return conStore("readwrite", function (store) { store.delete(uuid); }).catch(function () {});
  }

  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function actualizarBadge() {
    return leerCola().then(function (items) {
      document.querySelectorAll("[data-checador-pendientes]").forEach(function (el) {
        var n = items.length;
        el.textContent = n;
        el.closest("[data-checador-badge]") && (el.closest("[data-checador-badge]").style.display = n ? "" : "none");
      });
      return items;
    });
  }

  function sincronizar() {
    if (!navigator.onLine) return;
    leerCola().then(function (items) {
      if (!items.length) return;
      fetch(SYNC_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
        credentials: "same-origin",
        body: JSON.stringify({ items: items }),
      })
        .then(function (r) { return r.ok ? r.json() : { resultados: [] }; })
        .then(function (data) {
          var dels = (data.resultados || []).filter(function (x) { return x.ok; }).map(function (x) { return borrar(x.uuid); });
          return Promise.all(dels);
        })
        .then(actualizarBadge)
        .catch(function () {});
    });
  }

  function montar(root) {
    (root || document).querySelectorAll("[data-checar-geo]").forEach(wire);
  }

  function reloj() {
    var el = document.getElementById("reloj");
    if (!el) return;
    var d = new Date();
    el.textContent = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }

  // Cronómetro del timer de proyecto: cuenta hacia arriba desde data-inicio
  // (ISO del servidor — la fuente de verdad es la DB, esto es solo visual).
  function cronometro() {
    var el = document.getElementById("cronometro");
    if (!el || !el.dataset.inicio) return;
    var inicio = new Date(el.dataset.inicio).getTime();
    if (isNaN(inicio)) return;
    var segs = Math.max(0, Math.floor((Date.now() - inicio) / 1000));
    var h = Math.floor(segs / 3600), m = Math.floor((segs % 3600) / 60), s = segs % 60;
    el.textContent = String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  function init() {
    montar();
    reloj();
    setInterval(reloj, 10000);
    cronometro();
    setInterval(cronometro, 1000);
    actualizarBadge();
    sincronizar();  // intenta vaciar la cola al abrir
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  document.body.addEventListener("htmx:afterSwap", function (e) { montar(e.target); });
  window.addEventListener("online", sincronizar);
})();
