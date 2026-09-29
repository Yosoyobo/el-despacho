// El toggle de tema (claro/oscuro). El script anti-FOUC vive inline en
// base.html (debe correr antes que cualquier render). Este archivo solo
// gestiona el click del botón.
(function () {
  'use strict';
  const btn = document.getElementById('toggle-tema');
  if (!btn) return;
  btn.addEventListener('click', function () {
    const esOscuro = document.documentElement.classList.toggle('dark');
    try {
      localStorage.setItem('despacho-tema', esOscuro ? 'dark' : 'light');
    } catch (e) {
      // localStorage puede estar bloqueado (Safari privado); ignorar.
    }
    // Notificar a otros componentes (ej. site_charts.js repinta).
    try {
      window.dispatchEvent(new CustomEvent('despacho:tema', { detail: { dark: esOscuro } }));
    } catch (e) { /* CustomEvent siempre existe en navegadores soportados */ }
  });
})();
