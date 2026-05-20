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
      cerrarModales();
    }
  });

  // --- Modales (S-TailAdmin-Sweep wave 1) ---
  function abrirModal(modal) {
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }
  function cerrarModal(modal) {
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }
  function cerrarModales() {
    document.querySelectorAll('[data-modal]').forEach(cerrarModal);
  }
  document.querySelectorAll('[data-modal-target]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      abrirModal(document.querySelector(btn.getAttribute('data-modal-target')));
    });
  });
  document.querySelectorAll('[data-modal]').forEach(function (modal) {
    modal.addEventListener('click', function (e) {
      if (e.target === modal) cerrarModal(modal);  // backdrop
    });
  });
  document.body.addEventListener('click', function (e) {
    var close = e.target.closest('[data-modal-close]');
    if (close) cerrarModal(close.closest('[data-modal]'));
  });

  // --- Modal slot HTMX (S-TailAdmin-Sweep wave 5) ---
  // Modales inyectados vía hx-get hacia #modal-slot. Cerrar = vaciar slot.
  function cerrarSlotModal() {
    var slot = document.getElementById('modal-slot');
    if (slot) slot.innerHTML = '';
  }
  document.body.addEventListener('click', function (e) {
    if (e.target.closest('[data-modal-slot-close]')) cerrarSlotModal();
    var slot = document.getElementById('modal-slot');
    if (slot && e.target === slot.firstElementChild) cerrarSlotModal();  // backdrop
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') cerrarSlotModal();
  });
  document.body.addEventListener('htmx:afterRequest', function (e) {
    var xhr = e.detail && e.detail.xhr;
    if (!xhr) return;
    var redirect = xhr.getResponseHeader && xhr.getResponseHeader('HX-Redirect');
    if (redirect) return;  // htmx maneja el redirect; no toques el slot
  });

  // --- Dropdowns canónicos S-TailAdmin-Sweep (_dropdown.html) ---
  document.querySelectorAll('[data-dropdown]').forEach(function (root) {
    var trigger = root.querySelector('[data-dropdown-trigger]');
    var menu = root.querySelector('[data-dropdown-menu]');
    if (!trigger || !menu) return;
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      document.querySelectorAll('[data-dropdown-menu]').forEach(function (m) {
        if (m !== menu) m.hidden = true;
      });
      menu.hidden = !menu.hidden;
    });
  });
  document.addEventListener('click', function () {
    document.querySelectorAll('[data-dropdown-menu]').forEach(function (m) { m.hidden = true; });
  });

  // --- Toasts: auto-dismiss 4s ---
  document.querySelectorAll('[data-toast]').forEach(function (t) {
    setTimeout(function () { t.style.transition = 'opacity .3s'; t.style.opacity = '0'; setTimeout(function () { t.remove(); }, 300); }, 4000);
  });
  document.body.addEventListener('click', function (e) {
    var close = e.target.closest('[data-toast-close]');
    if (close) close.closest('[data-toast]').remove();
  });
})();
