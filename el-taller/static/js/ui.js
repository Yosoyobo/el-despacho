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

  // --- Carpetas personalizadas del usuario (V9) ---
  // El usuario agrupa items del sidebar en carpetas (campo `grupo` por usuario).
  // Reparenteamos por JS: creamos un botón + panel colapsable por carpeta y
  // movemos los items adentro. El toggle lo cablea el handler de
  // [data-sidebar-group] de abajo (corre justo después). Si el usuario no tiene
  // carpetas, no hace nada (cero riesgo para el sidebar existente).
  // Registro de iconos de carpeta (V11). Espejo de cuentas.models.ICONOS_CARPETA.
  // clave -> contenido interno de un <svg viewBox="0 0 24 24" stroke="currentColor">.
  var ICONOS_CARPETA_SVG = {
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke-linecap="round" stroke-linejoin="round"/>',
    star: '<path d="m12 3 2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9L12 3Z" stroke-linecap="round" stroke-linejoin="round"/>',
    rocket: '<path d="M4.5 16.5 3 21l4.5-1.5M14 4c2.5-1 5 0 6 1s2 3.5 1 6c-1.6 4-7 8-7 8l-3-3-3-3s4-5.4 8-7c.6-.2 1.3-.4 2-1Z" stroke-linecap="round" stroke-linejoin="round"/><circle cx="14.5" cy="9.5" r="1.5"/>',
    money: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h.01M18 12h.01" stroke-linecap="round"/>',
    chart: '<path d="M3 3v18h18M8 14v4M13 9v9M18 5v13" stroke-linecap="round" stroke-linejoin="round"/>',
    wrench: '<path d="M14.7 6.3a4 4 0 0 0-5 5l-6 6 3 3 6-6a4 4 0 0 0 5-5l-2.5 2.5-2.5-.5-.5-2.5 2.5-2.5Z" stroke-linecap="round" stroke-linejoin="round"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" stroke-linecap="round" stroke-linejoin="round"/>',
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18" stroke-linecap="round" stroke-linejoin="round"/>',
    bell: '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" stroke-linecap="round" stroke-linejoin="round"/>',
    box: '<path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16ZM3.3 7 12 12l8.7-5M12 22V12" stroke-linecap="round" stroke-linejoin="round"/>',
    tag: '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0l-7.2-7.2A2 2 0 0 1 3 12V4a1 1 0 0 1 1-1h8a2 2 0 0 1 1.4.6l7.2 7.2a2 2 0 0 1 0 2.6Z" stroke-linecap="round" stroke-linejoin="round"/><circle cx="7.5" cy="7.5" r="1"/>',
    chat: '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.2A8.4 8.4 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5Z" stroke-linecap="round" stroke-linejoin="round"/>',
    heart: '<path d="M20.8 5.6a5 5 0 0 0-7.1 0L12 7.3l-1.7-1.7a5 5 0 1 0-7.1 7.1L12 21l8.8-8.3a5 5 0 0 0 0-7.1Z" stroke-linecap="round" stroke-linejoin="round"/>',
    bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" stroke-linecap="round" stroke-linejoin="round"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 6.6 19l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3 13.4H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 6.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 10 4.6V4a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1Z" stroke-linecap="round" stroke-linejoin="round"/>',
    pin: '<path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11Z" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="10" r="2.5"/>'
  };
  function svgCarpeta(clave) {
    var inner = ICONOS_CARPETA_SVG[clave] || ICONOS_CARPETA_SVG.folder;
    return '<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">' + inner + '</svg>';
  }
  function leerCarpetaIconos() {
    try {
      var nodo = document.getElementById('sidebar-carpetas-iconos');
      return nodo ? (JSON.parse(nodo.textContent || '{}') || {}) : {};
    } catch (e) { return {}; }
  }

  (function construirCarpetas() {
    var nav = document.querySelector('[data-ta-sidebar] nav');
    if (!nav) return;
    var conGrupo = nav.querySelectorAll('[data-sidebar-grupo]');
    if (!conGrupo.length) return;
    var iconosCarpeta = leerCarpetaIconos();
    var carpetas = {}; // nombre -> {orden, nodos:[]}
    conGrupo.forEach(function (el) {
      var g = (el.getAttribute('data-sidebar-grupo') || '').trim();
      if (!g) return;
      var ord = parseInt(el.style.order || '999', 10);
      if (isNaN(ord)) ord = 999;
      if (!carpetas[g]) carpetas[g] = { orden: ord, nodos: [] };
      carpetas[g].orden = Math.min(carpetas[g].orden, ord);
      carpetas[g].nodos.push(el);
    });
    Object.keys(carpetas).forEach(function (nombre) {
      var info = carpetas[nombre];
      var key = 'carpeta:' + nombre;
      var activo = info.nodos.some(function (n) {
        return n.classList.contains('menu-item-active') || n.querySelector('.menu-item-active');
      });
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'menu-item menu-item-inactive w-full justify-between';
      btn.style.order = info.orden;
      btn.setAttribute('data-sidebar-group', key);
      btn.setAttribute('aria-expanded', activo ? 'true' : 'false');
      btn.innerHTML =
        '<span class="flex items-center gap-3">' +
          svgCarpeta(iconosCarpeta[nombre]) +
          '<span class="carpeta-nombre"></span>' +
        '</span>' +
        '<svg data-sidebar-group-chevron class="h-4 w-4 transition-transform' + (activo ? ' rotate-180' : '') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>';
      btn.querySelector('.carpeta-nombre').textContent = nombre; // textContent: nombre seguro
      var panel = document.createElement('div');
      panel.setAttribute('data-sidebar-group-panel', key);
      panel.style.order = info.orden;
      panel.className = 'ml-4 flex flex-col gap-1 border-l border-gray-200 pl-3 dark:border-gray-800' + (activo ? '' : ' hidden');
      var ref = info.nodos[0];
      nav.insertBefore(btn, ref);
      nav.insertBefore(panel, ref);
      info.nodos.forEach(function (n) { n.style.order = ''; panel.appendChild(n); });
    });
  })();

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

  // --- Campo de color HEX con popover poco intrusivo (S-Estados-Color-HEX) ---
  // Sincroniza swatch ↔ cuadro de texto ↔ rueda nativa ↔ chips. El cuadro de
  // texto es la fuente de verdad (#RRGGBB). Delegación para tolerar formularios
  // re-renderizados (HTMX) sin re-bindear.
  function _hexValido(v) { return /^#[0-9a-fA-F]{6}$/.test(v); }
  function _aplicarColor(campo, valor) {
    valor = (valor || '').trim();
    if (valor && valor[0] !== '#') valor = '#' + valor;
    var input = campo.querySelector('[data-color-input]');
    var swatch = campo.querySelector('[data-color-swatch]');
    var preview = campo.querySelector('[data-color-preview]');
    var wheel = campo.querySelector('[data-color-wheel]');
    if (input && input.value !== valor) input.value = valor.toUpperCase();
    if (_hexValido(valor)) {
      if (swatch) swatch.style.backgroundColor = valor;
      if (preview) preview.style.setProperty('--ec', valor);
      if (wheel) wheel.value = valor;
    }
  }
  function _cerrarPopovers(excepto) {
    document.querySelectorAll('[data-color-popover]').forEach(function (p) {
      if (p !== excepto) p.hidden = true;
    });
  }
  document.body.addEventListener('click', function (e) {
    var swatch = e.target.closest('[data-color-swatch]');
    if (swatch) {
      e.preventDefault();
      var campo = swatch.closest('[data-campo-color]');
      var pop = campo && campo.querySelector('[data-color-popover]');
      if (pop) { var abrir = pop.hidden; _cerrarPopovers(pop); pop.hidden = !abrir; }
      return;
    }
    var chip = e.target.closest('[data-color-chip]');
    if (chip) {
      e.preventDefault();
      var campoChip = chip.closest('[data-campo-color]');
      _aplicarColor(campoChip, chip.getAttribute('data-color-chip'));
      var popChip = campoChip.querySelector('[data-color-popover]');
      if (popChip) popChip.hidden = true;
      return;
    }
    if (!e.target.closest('[data-campo-color]')) _cerrarPopovers(null);
  });
  document.body.addEventListener('input', function (e) {
    var campo = e.target.closest('[data-campo-color]');
    if (!campo) return;
    if (e.target.matches('[data-color-input]') || e.target.matches('[data-color-wheel]')) {
      _aplicarColor(campo, e.target.value);
    }
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
    // 3) Botón "Quitar" (V6 Bloque 4): limpia la fecha y dispara change. El
    // picker nativo del SO no permite des-seleccionar desde adentro — esta es
    // la afordancia equivalente. Visible solo con valor y en campos opcionales.
    // Opt-out con data-sin-quitar="1".
    var quitarBtn = null;
    if (input.dataset.sinQuitar !== '1' && !input.required) {
      quitarBtn = document.createElement('button');
      quitarBtn.type = 'button';
      quitarBtn.textContent = '✕';
      quitarBtn.title = 'Quitar fecha';
      quitarBtn.className = 'ml-1 inline-flex items-center rounded-md border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-error-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700';
      quitarBtn.setAttribute('data-no-row-click', '');
      quitarBtn.setAttribute('aria-label', 'Quitar fecha');
      quitarBtn.addEventListener('click', function () {
        input.value = '';
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
      var syncQuitar = function () { quitarBtn.style.display = input.value ? '' : 'none'; };
      input.addEventListener('change', syncQuitar);
      input.addEventListener('input', syncQuitar);
      syncQuitar();
    }
    // Inserta el botón después del wrapper relativo (si existe) o del input.
    var anchor = input.closest('.relative') || input;
    if (anchor.parentNode) {
      // Si el padre no es flex, hacemos un span inline; suficiente para alinearse.
      var holder = document.createElement('span');
      holder.className = 'inline-flex items-center align-middle';
      holder.appendChild(hoyBtn);
      if (quitarBtn) holder.appendChild(quitarBtn);
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

  // --- Bottom pop-over de adjuntos (S-Adjuntos-UI) ---
  // Bottom-sheet que sube desde abajo. Usado por el Buzón para listar adjuntos.
  // Delegación para tolerar contenido inyectado vía HTMX.
  function abrirPopover(pop) {
    if (!pop) return;
    pop.hidden = false;
    var panel = pop.querySelector('[data-adjuntos-popover-panel]');
    requestAnimationFrame(function () {
      if (panel) panel.classList.remove('translate-y-full');
    });
  }
  function cerrarPopover(pop) {
    if (!pop) return;
    var panel = pop.querySelector('[data-adjuntos-popover-panel]');
    if (panel) panel.classList.add('translate-y-full');
    setTimeout(function () { pop.hidden = true; }, 220);
  }
  function cerrarPopovers() {
    document.querySelectorAll('[data-adjuntos-popover]:not([hidden])').forEach(cerrarPopover);
  }
  document.body.addEventListener('click', function (e) {
    var trigger = e.target.closest('[data-adjuntos-popover-trigger]');
    if (trigger) {
      e.preventDefault();
      abrirPopover(document.querySelector(trigger.getAttribute('data-adjuntos-popover-trigger')));
      return;
    }
    if (e.target.closest('[data-adjuntos-popover-close]') || e.target.matches('[data-adjuntos-popover-backdrop]')) {
      var pop = e.target.closest('[data-adjuntos-popover]');
      if (pop) cerrarPopover(pop);
    }
  });

  // --- Lightbox de imágenes (S-Adjuntos-UI) ---
  // Cualquier elemento con [data-lightbox="<url>"] abre la imagen a tamaño
  // grande en un overlay full-screen. Si es un <img> sin atributo, usa su src.
  function abrirLightbox(src, alt) {
    if (!src) return;
    var ov = document.createElement('div');
    ov.setAttribute('data-lightbox-overlay', '');
    ov.className = 'fixed inset-0 z-[70] flex items-center justify-center bg-black/80 p-4';
    var img = document.createElement('img');
    img.src = src;
    img.alt = alt || '';
    img.className = 'max-h-[90vh] max-w-[90vw] rounded-lg object-contain shadow-2xl';
    ov.appendChild(img);
    ov.addEventListener('click', function () { ov.remove(); });
    document.body.appendChild(ov);
  }
  function cerrarLightbox() {
    document.querySelectorAll('[data-lightbox-overlay]').forEach(function (o) { o.remove(); });
  }
  document.body.addEventListener('click', function (e) {
    var lb = e.target.closest('[data-lightbox]');
    if (!lb) return;
    e.preventDefault();
    var src = lb.getAttribute('data-lightbox') || (lb.tagName === 'IMG' ? lb.src : '');
    abrirLightbox(src, lb.getAttribute('data-lightbox-alt') || lb.getAttribute('alt'));
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { cerrarLightbox(); cerrarPopovers(); }
  });
})();

// ── Indicador global "Procesando…" (LC logo girando) + anti-doble-clic ──
// S-LC-Feedback-V7 / V9 / S-Chalan-Equipo-UX (este sprint).
//
// Dos responsabilidades, una sola IIFE:
//  1) SPINNER: el logo LC gira SIEMPRE que el usuario dispara una petición
//     deliberada (submit, clic que hace request HTMX o navega un form clásico)
//     o pide algo a El Chalán. NO sale al teclear, ni por autoguardados, ni por
//     polling de fondo, ni en [data-sin-indicador="1"]. Debounce corto (90 ms)
//     para que se sienta inmediato pero sin parpadear en respuestas instantáneas.
//  2) ANTI-DOBLE-CLIC: al enviar un formulario lo marcamos "enviando" y
//     bloqueamos en seco cualquier segundo submit hasta que termine (clave para
//     El Chalán y cualquier POST: el usuario hace doble clic creyendo que no se
//     registró). También deshabilitamos visualmente los botones de submit y los
//     botones HTMX (hx-get/hx-post) mientras la petición está en vuelo.
//     Opt-out por formulario/elemento con [data-sin-bloqueo="1"].
(function () {
  var el = document.getElementById('proc-indicador');
  var enVuelo = 0;
  var timer = null;
  var ruidosas = (typeof WeakSet !== 'undefined') ? new WeakSet() : null;
  function mostrar() {
    if (!el || timer) return;
    timer = setTimeout(function () {
      if (enVuelo > 0) { el.classList.remove('hidden'); el.classList.add('flex'); }
    }, 90);
  }
  function ocultarSiVacio() {
    if (enVuelo > 0 || !el) return;
    if (timer) { clearTimeout(timer); timer = null; }
    el.classList.add('hidden'); el.classList.remove('flex');
  }
  function inicia() { enVuelo++; mostrar(); }
  function termina() { enVuelo = Math.max(0, enVuelo - 1); if (enVuelo === 0) ocultarSiVacio(); }

  // ¿Esta petición HTMX es silenciosa (no debe encender el spinner)?
  function esSilenciosa(evt) {
    var cfg = evt.detail && evt.detail.requestConfig;
    var elt = (evt.detail && evt.detail.elt) || (cfg && cfg.elt);
    if (elt && elt.closest && elt.closest('[data-sin-indicador="1"]')) return true;
    var te = cfg && cfg.triggeringEvent;
    if (!te) return true; // polling / hx-trigger="load"/"every Ns" / revealed
    var t = te.type;
    if (t === 'input' || t === 'keyup' || t === 'keydown' || t === 'change') return true;
    return false; // submit, click, etc. → acción del usuario
  }

  // --- Anti-doble-clic: deshabilita un elemento y lo marca para reactivar. ---
  // Spinner inline en el propio botón mientras la acción está en vuelo. Cubre
  // TODA pantalla (botones de submit clásicos y disparadores HTMX) sin tocar
  // plantillas — el feedback aparece justo donde el usuario picó (reporte de
  // Oscar: "al enviar al Buzón no veo el logo"). Usa currentColor: blanco en
  // botones brand, gris en secundarios.
  function ponerSpinnerBoton(elt) {
    if (!elt || elt.tagName !== 'BUTTON') return;
    if (elt.querySelector('[data-btn-spinner]')) return;
    if (elt.closest && elt.closest('[data-sin-indicador="1"]')) return;
    var s = document.createElement('span');
    s.setAttribute('data-btn-spinner', '1');
    s.className = 'mr-1.5 inline-flex shrink-0 align-[-2px]';
    s.innerHTML = '<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">'
      + '<circle class="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>'
      + '<path class="opacity-90" fill="currentColor" d="M12 2a10 10 0 0 1 10 10h-4a6 6 0 0 0-6-6V2z"></path></svg>';
    elt.insertBefore(s, elt.firstChild);
  }
  function quitarSpinnerBoton(elt) {
    var s = elt && elt.querySelector && elt.querySelector('[data-btn-spinner]');
    if (s) s.remove();
  }
  function bloquear(elt) {
    if (!elt || elt.disabled) return;
    if (elt.closest && elt.closest('[data-sin-bloqueo="1"]')) return;
    elt.disabled = true;
    elt.setAttribute('data-autobloqueo', '1');
    ponerSpinnerBoton(elt);
  }
  function reactivarTodo() {
    document.querySelectorAll('[data-autobloqueo="1"]').forEach(function (b) {
      b.disabled = false; b.removeAttribute('data-autobloqueo');
      quitarSpinnerBoton(b);
    });
    document.querySelectorAll('form[data-enviando="1"]').forEach(function (f) {
      f.removeAttribute('data-enviando');
    });
  }

  document.body.addEventListener('htmx:beforeRequest', function (evt) {
    if (esSilenciosa(evt)) return;
    var xhr = evt.detail && evt.detail.xhr;
    if (ruidosas && xhr) ruidosas.add(xhr);
    // Deshabilita el botón HTMX que disparó (hx-get/hx-post fuera de form) para
    // que un segundo clic no dispare otra petición.
    var elt = evt.detail && evt.detail.elt;
    if (elt && (elt.tagName === 'BUTTON' || (elt.tagName === 'A' && elt.hasAttribute('hx-get')))) {
      bloquear(elt);
    }
    inicia();
  });
  function fin(evt) {
    var xhr = evt.detail && evt.detail.xhr;
    // Solo reactivamos/contamos en peticiones deliberadas — un poll de fondo
    // que termina no debe desbloquear un formulario que apenas se envió.
    if (!ruidosas || !xhr || !ruidosas.has(xhr)) return;
    ruidosas.delete(xhr);
    reactivarTodo();
    termina();
  }
  document.body.addEventListener('htmx:afterRequest', fin);
  document.body.addEventListener('htmx:responseError', fin);
  document.body.addEventListener('htmx:sendError', fin);

  // --- Navegación de página completa (cambiar de sección con un link) ---
  // El usuario hace clic en un item del menú / un link y la página tarda en
  // cargar; queremos que el logo gire de inmediato. El documento nuevo reinicia
  // el spinner solo. Si el clic NO termina en navegación (descarga de CSV/PDF,
  // o nav cancelada) un temporizador de seguridad lo apaga.
  var navTimer = null;
  function esNavegacionReal(a, e) {
    if (!a || a.tagName !== 'A') return false;
    if (e.defaultPrevented) return false;                       // otro handler ya lo tomó
    if (e.button && e.button !== 0) return false;               // no clic izquierdo
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return false;  // abre pestaña nueva
    if (a.target && a.target !== '_self') return false;         // _blank, etc.
    if (a.hasAttribute('download')) return false;
    if (a.hasAttribute('hx-get') || a.hasAttribute('hx-post') || a.hasAttribute('hx-boost')) return false;
    if (a.closest('[data-sin-indicador="1"]')) return false;
    var href = a.getAttribute('href') || '';
    if (!href || href.charAt(0) === '#') return false;
    if (/^(mailto:|tel:|javascript:|blob:|data:)/i.test(href)) return false;
    try {
      var dest = new URL(a.href, window.location.href);
      // Mismo documento, solo cambia el hash → no recarga.
      if (dest.origin === window.location.origin &&
          dest.pathname === window.location.pathname &&
          dest.search === window.location.search && dest.hash) return false;
    } catch (_) { /* href raro → asumimos navegación */ }
    return true;
  }
  function arrancarNav() {
    inicia();
    // Seguridad: si en 4 s no hubo `pagehide` (fue descarga o se canceló),
    // apaga el spinner para no dejarlo pegado.
    if (navTimer) clearTimeout(navTimer);
    navTimer = setTimeout(function () { termina(); navTimer = null; }, 4000);
  }
  document.addEventListener('click', function (e) {
    if (!e.target.closest) return;
    var a = e.target.closest('a[href]');
    if (a) { if (esNavegacionReal(a, e)) arrancarNav(); return; }
    // Filas clickeables [data-href] (navegan vía JS en el otro handler de ui.js).
    var row = e.target.closest('[data-href]');
    if (row && !e.defaultPrevented && e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey
        && !e.target.closest('a, button, input, label, select, textarea, [data-dropdown], [data-no-row-click]')
        && row.getAttribute('href') !== '' && row.getAttribute('data-href')) {
      arrancarNav();
    }
  }, false);
  window.addEventListener('pagehide', function () {
    // Navegación realmente en curso: el temporizador de seguridad ya no aplica
    // (la página se va con el spinner encendido; el documento nuevo lo reinicia).
    if (navTimer) { clearTimeout(navTimer); navTimer = null; }
  });

  // Submit de CUALQUIER formulario (clásico o HTMX): bloquea doble envío +
  // enciende el spinner. El evento `submit` solo dispara cuando el form pasó la
  // validación nativa (required, etc.), así que es seguro marcarlo aquí.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.tagName !== 'FORM') return;
    if (form.getAttribute('data-sin-bloqueo') === '1') return;
    // Segundo submit mientras el primero sigue en vuelo → cancélalo en seco.
    if (form.getAttribute('data-enviando') === '1') {
      e.preventDefault();
      if (e.stopImmediatePropagation) e.stopImmediatePropagation();
      return;
    }
    form.setAttribute('data-enviando', '1');
    var esHtmx = form.hasAttribute('hx-post') || form.hasAttribute('hx-get');
    // Forms de subida con archivos: el IIFE de la barra de progreso (más abajo)
    // hace preventDefault() para mandar por XHR. Eso NO es una validación
    // cancelada — el envío SÍ está en curso. Lo detectamos para igual mostrar
    // el spinner + botones en gris (reporte de Oscar: "al enviar al Buzón con
    // adjunto no veo el logo ni el botón gris").
    function formTieneArchivos(f) {
      var ins = f.querySelectorAll('input[type="file"]');
      for (var i = 0; i < ins.length; i++) { if (ins[i].files && ins[i].files.length) return true; }
      return false;
    }
    var esSubidaXHR = !esHtmx && form.hasAttribute('data-upload-progress') && formTieneArchivos(form);
    var btns = form.querySelectorAll('button:not([type="button"]):not([data-sin-bloqueo="1"]), input[type="submit"]');
    // SPINNER SÍNCRONO para envíos clásicos. Se enciende YA (no diferido):
    // un POST clásico empieza a navegar de inmediato y el setTimeout(0) puede
    // perder la carrera contra el unload — por eso Oscar no veía el logo girar.
    // El debounce de 90 ms de mostrar() evita el parpadeo si el submit se
    // cancela enseguida. HTMX lo maneja por separado en htmx:beforeRequest.
    var spinnerEncendido = false;
    if (!esHtmx && form.getAttribute('data-sin-indicador') !== '1') {
      inicia();
      spinnerEncendido = true;
    }
    // Deshabilitar botones se DIFIERE un tick: así un POST clásico ya serializó
    // el botón-submisor antes de deshabilitarlo, y podemos ver si un validador
    // JS canceló el envío.
    setTimeout(function () {
      if (!esHtmx && e.defaultPrevented && !esSubidaXHR) {
        // Submit clásico cancelado (validación) → no navega: deshaz el bloqueo
        // y apaga el spinner que encendimos.
        form.removeAttribute('data-enviando');
        if (spinnerEncendido) { spinnerEncendido = false; termina(); }
        return;
      }
      btns.forEach(bloquear);
      if (spinnerEncendido) {
        // Red de seguridad: si NO navega (descarga, error de red, subida a
        // Drive lenta), libera botones + spinner. La subida por XHR puede
        // tardar más, así que le damos más margen.
        setTimeout(function () {
          if (form.getAttribute('data-enviando') === '1') { reactivarTodo(); termina(); }
        }, esSubidaXHR ? 60000 : 12000);
      }
    }, 0);
  }, true);

  // Si el usuario regresa con el botón atrás (bfcache), limpia todo el estado.
  window.addEventListener('pageshow', function () {
    enVuelo = 0; ocultarSiVacio(); reactivarTodo();
  });
})();

// ===========================================================================
// Barra de progreso de subida de adjuntos (S-LC-Feedback-V10).
// Muestra arriba del todo el progreso REAL del upload (xhr.upload.progress):
//  • HTMX (Recados chat y cualquier hx-post con archivos): vía htmx:beforeSend.
//  • Forms clásicos opt-in [data-upload-progress] (Buzón, Egreso): XHR propio.
// Reporte de Oscar: "barra de progreso de los adjuntos para verificar que suba".
// ===========================================================================
(function () {
  var barra = document.getElementById('barra-subida');
  var fill = barra && barra.querySelector('[data-barra-subida-fill]');
  if (!barra || !fill) return;
  var ocultarTimer = null;
  function set(p) { fill.style.width = Math.max(0, Math.min(100, p)) + '%'; }
  function mostrar() { if (ocultarTimer) { clearTimeout(ocultarTimer); ocultarTimer = null; } barra.classList.remove('hidden'); }
  function terminar() { set(100); ocultarTimer = setTimeout(function () { barra.classList.add('hidden'); set(0); }, 450); }
  function reset() { if (ocultarTimer) { clearTimeout(ocultarTimer); ocultarTimer = null; } barra.classList.add('hidden'); set(0); }

  function formConArchivos(elt) {
    var form = elt && (elt.tagName === 'FORM' ? elt : (elt.closest && elt.closest('form')));
    if (!form) return false;
    var inputs = form.querySelectorAll('input[type="file"]');
    for (var i = 0; i < inputs.length; i++) { if (inputs[i].files && inputs[i].files.length) return true; }
    return false;
  }

  // --- HTMX: progreso real del upload ---
  document.body.addEventListener('htmx:beforeSend', function (evt) {
    var d = evt.detail || {};
    var xhr = d.xhr;
    if (!xhr || !xhr.upload || !formConArchivos(d.elt)) return;
    mostrar(); set(3);
    xhr.upload.addEventListener('progress', function (e) {
      if (e.lengthComputable) set(Math.round((e.loaded / e.total) * 100));
    });
  });
  document.body.addEventListener('htmx:afterRequest', function (evt) {
    var d = evt.detail || {};
    if (d.elt && formConArchivos(d.elt)) terminar();
  });
  document.body.addEventListener('htmx:sendError', reset);

  // --- Forms clásicos opt-in: XHR con progreso, sigue el redirect de Django ---
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.tagName !== 'FORM') return;
    if (!form.hasAttribute('data-upload-progress')) return;
    if (form.hasAttribute('hx-post') || form.hasAttribute('hx-get')) return;
    if (form.getAttribute('data-upload-omitir') === '1') return; // fallback nativo en curso
    if (!formConArchivos(form)) return; // sin archivos → submit normal del navegador
    e.preventDefault();
    var xhr = new XMLHttpRequest();
    xhr.open(form.method || 'POST', form.action || window.location.href, true);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    mostrar(); set(3);
    xhr.upload.addEventListener('progress', function (ev) {
      if (ev.lengthComputable) set(Math.round((ev.loaded / ev.total) * 100));
    });
    xhr.onload = function () {
      terminar();
      var destino = xhr.responseURL || '';
      var origen = form.action || window.location.href;
      if (destino && destino !== origen) {
        window.location.href = destino;            // POST→redirect→GET (éxito)
      } else {
        document.open(); document.write(xhr.responseText); document.close(); // form con errores
      }
    };
    xhr.onerror = function () {
      reset();
      form.setAttribute('data-upload-omitir', '1');
      form.removeAttribute('data-enviando');
      form.submit();                                // fallback: submit nativo (no re-intercepta)
    };
    xhr.send(new FormData(form));
  }, true);

  window.addEventListener('pageshow', reset);
})();
