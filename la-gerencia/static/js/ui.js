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

  // --- Sidebar groups colapsables (S-LC-Feedback-V2) ---
  // Persisten el estado abierto/cerrado en localStorage. Si el grupo
  // contiene una URL activa, el server ya lo renderiza expandido.
  const SIDEBAR_GRUPOS_KEY = 'despacho-sidebar-grupos';
  function leerSidebarGrupos() {
    try {
      const raw = localStorage.getItem(SIDEBAR_GRUPOS_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) { return {}; }
  }
  function escribirSidebarGrupos(estado) {
    try { localStorage.setItem(SIDEBAR_GRUPOS_KEY, JSON.stringify(estado)); } catch (e) { /* noop */ }
  }
  document.querySelectorAll('[data-sidebar-group]').forEach(function (btn) {
    const grupo = btn.getAttribute('data-sidebar-group');
    const panel = document.querySelector('[data-sidebar-group-panel="' + grupo + '"]');
    const chevron = btn.querySelector('[data-sidebar-group-chevron]');
    if (!panel) return;

    // Si localStorage tiene preferencia explícita, respetarla
    // (sólo si el grupo NO contiene un link activo — server tiene preferencia
    // sobre localStorage cuando el usuario navegó adentro).
    const grupos = leerSidebarGrupos();
    const yaActivo = btn.getAttribute('aria-expanded') === 'true';
    if (!yaActivo && grupos[grupo] === true) {
      panel.classList.remove('hidden');
      btn.setAttribute('aria-expanded', 'true');
      if (chevron) chevron.classList.add('rotate-180');
    }

    btn.addEventListener('click', function () {
      const ahora = panel.classList.toggle('hidden');
      const abierto = !ahora;
      btn.setAttribute('aria-expanded', abierto ? 'true' : 'false');
      if (chevron) chevron.classList.toggle('rotate-180', abierto);
      const g = leerSidebarGrupos();
      g[grupo] = abierto;
      escribirSidebarGrupos(g);
    });
  });

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

  // --- <input type="date">: botón "Hoy" + auto-mostrar calendario al click ---
  // Mejora cosmética: cada <input type=date> recibe un botón "Hoy" hermano
  // que setea el valor al día actual y dispara `change`. Además al hacer
  // focus se invoca showPicker() (soporte en Chrome/Safari modernos) para
  // que el calendario se despliegue sin necesidad de tocar el ícono.
  document.querySelectorAll('input[type="date"]:not([data-hoy-listo])').forEach(function (input) {
    input.dataset.hoyListo = '1';
    // 1) Auto-mostrar el picker al focus / click (graceful si el browser no soporta).
    var openPicker = function () {
      try { if (typeof input.showPicker === 'function') input.showPicker(); } catch (_) { /* noop */ }
    };
    input.addEventListener('focus', openPicker);
    input.addEventListener('click', openPicker);
    // 2) Botón "Hoy" hermano.
    if (input.dataset.sinHoy === '1') return; // opt-out
    var hoyBtn = document.createElement('button');
    hoyBtn.type = 'button';
    hoyBtn.textContent = 'Hoy';
    hoyBtn.className = 'ml-2 inline-flex items-center rounded-md border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700';
    hoyBtn.setAttribute('data-no-row-click', '');
    hoyBtn.setAttribute('aria-label', 'Poner fecha de hoy');
    hoyBtn.addEventListener('click', function () {
      var t = new Date();
      var iso = t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0');
      input.value = iso;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.focus();
    });
    // Inserta el botón después del wrapper relativo (si existe) o del input.
    var anchor = input.closest('.relative') || input;
    if (anchor.parentNode) {
      // Si el padre no es flex, hacemos un span inline; suficiente para alinearse.
      var holder = document.createElement('span');
      holder.className = 'inline-flex items-center align-middle';
      holder.appendChild(hoyBtn);
      anchor.parentNode.insertBefore(holder, anchor.nextSibling);
    }
  });

  // --- Filas <tr data-href="..."> clickeables ---
  // Cualquier <tr> con data-href se vuelve navegable. No dispara cuando el
  // click cae sobre un <a>, <button>, <input>, <label>, <select> u otro
  // elemento interactivo — esos manejan su propio click. Soporta cmd/ctrl
  // click para abrir en pestaña nueva.
  document.body.addEventListener('click', function (e) {
    var row = e.target.closest('[data-href]');
    if (!row) return;
    if (e.target.closest('a, button, input, label, select, textarea, [data-dropdown], [data-no-row-click]')) return;
    var url = row.getAttribute('data-href');
    if (!url) return;
    if (e.metaKey || e.ctrlKey) {
      window.open(url, '_blank');
    } else {
      window.location.href = url;
    }
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
