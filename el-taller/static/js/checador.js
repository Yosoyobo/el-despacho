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

      function enviar() { form.submit(); }
      function sinGeo(msg) {
        setVal(form, "sin_geo", "1");
        if (estado && msg) estado.textContent = msg;
        enviar();
      }

      if (!navigator.geolocation) { sinGeo("Sin ubicación — se registrará igual."); return; }
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          setVal(form, "lat", pos.coords.latitude);
          setVal(form, "lng", pos.coords.longitude);
          setVal(form, "precision", pos.coords.accuracy || "");
          enviar();
        },
        function () { sinGeo("Sin ubicación — se registrará igual."); },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
      );
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
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  document.body.addEventListener("htmx:afterSwap", function (e) { montar(e.target); });
})();
