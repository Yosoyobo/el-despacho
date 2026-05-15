// UI helpers vanilla — sidebar móvil + dropdowns del header.
// Sin Alpine ni librerías: regla #1 + alcance S-TailAdmin-1 (sin libs JS nuevas).
//
// Convenciones HTML:
//   <button data-ta-toggle="sidebar">…</button>   abre/cierra el sidebar móvil
//   <aside data-ta-sidebar>…</aside>              elemento controlado
//   <button data-ta-dropdown="#perfil">…</button> abre el panel #perfil
//   <div id="perfil" data-ta-dropdown-panel>…</div>
(function () {
  'use strict';

  // --- Sidebar móvil ---
  const sidebar = document.querySelector('[data-ta-sidebar]');
  const sidebarBackdrop = document.querySelector('[data-ta-sidebar-backdrop]');
  function abrirSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('translate-x-0');
    sidebar.classList.remove('-translate-x-full');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('hidden');
  }
  function cerrarSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('-translate-x-full');
    sidebar.classList.remove('translate-x-0');
    if (sidebarBackdrop) sidebarBackdrop.classList.add('hidden');
  }
  document.querySelectorAll('[data-ta-toggle="sidebar"]').forEach(function (b) {
    b.addEventListener('click', function () {
      const abierto = sidebar && !sidebar.classList.contains('-translate-x-full');
      abierto ? cerrarSidebar() : abrirSidebar();
    });
  });
  if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', cerrarSidebar);

  // --- Dropdowns del header ---
  const dropdowns = []; // { trigger, panel }
  document.querySelectorAll('[data-ta-dropdown]').forEach(function (trigger) {
    const sel = trigger.getAttribute('data-ta-dropdown');
    const panel = document.querySelector(sel);
    if (!panel) return;
    dropdowns.push({ trigger: trigger, panel: panel });
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      // Cerrar los demás
      dropdowns.forEach(function (d) {
        if (d.panel !== panel) d.panel.classList.add('hidden');
      });
      panel.classList.toggle('hidden');
    });
    panel.addEventListener('click', function (e) { e.stopPropagation(); });
  });
  document.addEventListener('click', function () {
    dropdowns.forEach(function (d) { d.panel.classList.add('hidden'); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      dropdowns.forEach(function (d) { d.panel.classList.add('hidden'); });
      cerrarSidebar();
    }
  });
})();
