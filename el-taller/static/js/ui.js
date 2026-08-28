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
  function realzarFechas(root) {
  (root || document).querySelectorAll('input[type="date"]:not([data-hoy-listo])').forEach(function (input) {
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
      // LC revisión buzón: "Hoy" SOLO aplica la fecha; no enfocar el input para
      // no reabrir el mini-calendario nativo (como "Fin de mes" del otro lado).
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
  }
  realzarFechas(document);
  // Re-realza inputs date inyectados por HTMX (modales del #modal-slot, etc.).
  document.body.addEventListener('htmx:afterSwap', function (e) { realzarFechas(e.target || document); });

  // --- Mini-calendario inline [data-minical] ---
  // Init GLOBAL (antes vivía en un <script> inline con document.currentScript,
  // frágil al inyectarse por HTMX). Aquí es idempotente y corre también en
  // htmx:afterSwap, así funciona dentro de los modales del #modal-slot.
  // El <input hidden data-mc-input> lleva el valor ISO (fuente de verdad).
  var MC_MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  function mcHoyISO() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  // Normaliza cualquier valor a ISO YYYY-MM-DD. Defensivo: una fecha localizada
  // ("19 de julio de 2026") producía NaN y dejaba el calendario vacío/ancho.
  function mcNormalizarISO(v) {
    v = (v || '').trim();
    if (/^\d{4}-\d{2}-\d{2}/.test(v)) return v.slice(0, 10);
    var m = v.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/);  // dd/mm/yyyy
    if (m) return m[3] + '-' + m[2].padStart(2, '0') + '-' + m[1].padStart(2, '0');
    return '';  // formato no reconocido → sin valor (cae a hoy o queda vacío)
  }
  function initMinical(root) {
    (root || document).querySelectorAll('[data-minical]:not([data-minical-listo])').forEach(function (mc) {
      mc.setAttribute('data-minical-listo', '1');
      var input = mc.querySelector('[data-mc-input]');
      var grid = mc.querySelector('[data-mc-grid]');
      var titulo = mc.querySelector('[data-mc-titulo]');
      if (!input || !grid || !titulo) return;
      input.value = mcNormalizarISO(input.value);
      // Por default arranca en HOY si viene vacío; data-mc-default-hoy="0" lo evita.
      if (!input.value && mc.getAttribute('data-mc-default-hoy') !== '0') input.value = mcHoyISO();
      var base = (input.value || mcHoyISO()).split('-').map(Number);
      var vy = base[0], vm = base[1];
      function render() {
        var sel = input.value;
        titulo.textContent = MC_MESES[vm - 1] + ' ' + vy;
        var primero = new Date(vy, vm - 1, 1);
        var offset = (primero.getDay() + 6) % 7;  // semana inicia lunes
        var dias = new Date(vy, vm, 0).getDate();
        grid.innerHTML = '';
        for (var i = 0; i < offset; i++) grid.appendChild(document.createElement('span'));
        for (var d = 1; d <= dias; d++) {
          var iso = vy + '-' + String(vm).padStart(2, '0') + '-' + String(d).padStart(2, '0');
          var b = document.createElement('button');
          b.type = 'button'; b.textContent = d; b.dataset.iso = iso;
          b.className = 'h-8 rounded-lg text-sm transition ' + (iso === sel
            ? 'bg-brand-500 font-semibold text-white'
            : 'text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800')
            + (iso === mcHoyISO() && iso !== sel ? ' ring-1 ring-brand-300' : '');
          (function (isoDia) {
            b.addEventListener('click', function () { input.value = (input.value === isoDia) ? '' : isoDia; render(); });
          })(iso);
          grid.appendChild(b);
        }
      }
      var prev = mc.querySelector('[data-mc-prev]'); if (prev) prev.addEventListener('click', function () { vm--; if (vm < 1) { vm = 12; vy--; } render(); });
      var next = mc.querySelector('[data-mc-next]'); if (next) next.addEventListener('click', function () { vm++; if (vm > 12) { vm = 1; vy++; } render(); });
      var hoy = mc.querySelector('[data-mc-hoy]'); if (hoy) hoy.addEventListener('click', function () { input.value = mcHoyISO(); var p = input.value.split('-').map(Number); vy = p[0]; vm = p[1]; render(); });
      var manana = mc.querySelector('[data-mc-manana]'); if (manana) manana.addEventListener('click', function () { var t = new Date(); t.setDate(t.getDate() + 1); input.value = t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0'); var p = input.value.split('-').map(Number); vy = p[0]; vm = p[1]; render(); });
      var quitar = mc.querySelector('[data-mc-quitar]'); if (quitar) quitar.addEventListener('click', function () { input.value = ''; render(); });
      render();
    });
  }
  initMinical(document);
  document.body.addEventListener('htmx:afterSwap', function (e) { initMinical(e.target || document); });

  // --- Pills de acceso rápido que fijan un <select> (modales de acciones
  //     rápidas): <button data-set-select="valor" data-set-select-target="#sel">.
  //     Delegado → funciona en contenido inyectado por HTMX sin re-init.
  document.body.addEventListener('click', function (e) {
    var pill = e.target.closest && e.target.closest('[data-set-select]');
    if (!pill) return;
    var sel = document.querySelector(pill.getAttribute('data-set-select-target'));
    if (!sel) return;
    sel.value = pill.getAttribute('data-set-select');
    sel.dispatchEvent(new Event('change', { bubbles: true }));
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

// ===========================================================================
// Auto-grow de los cuadros de texto del chat (El Chalán + Los Recados).
// Reporte de Oscar: "los cuadros de texto de chalán y recados, muy chico".
// El textarea arranca en ~3 renglones y crece con el contenido hasta un tope
// (data-autogrow-max, px); arriba del tope hace scroll interno. Vanilla, sin
// libs (regla #1). Delegación para tolerar la conversación inyectada por HTMX.
// ===========================================================================
(function () {
  // Donde el navegador sabe hacerlo solo, este JS no se monta: dos mecanismos
  // peleando por el mismo alto es cómo volvería el «se hace grande y chico solo».
  var NATIVO = !!(window.CSS && CSS.supports && CSS.supports('field-sizing', 'content'));
  if (NATIVO) return;
  function ajustar(ta) {
    if (!ta) return;
    var max = parseInt(ta.getAttribute('data-autogrow-max') || '200', 10);
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, max) + 'px';
    ta.style.overflowY = ta.scrollHeight > max ? 'auto' : 'hidden';
  }
  function ajustarTodas(raiz) {
    var nodo = (raiz && raiz.querySelectorAll) ? raiz : document;
    nodo.querySelectorAll('textarea[data-autogrow]').forEach(ajustar);
  }
  // NADA se mide MIENTRAS SE TECLEA. Ni con guarda de `isComposing`.
  //
  // Los acentos y la ñ se escriben en dos pulsaciones (´ + a · Option+n + n) y
  // entre una y otra el navegador está componiendo la letra. Leer `scrollHeight`
  // ahí fuerza un recálculo del diseño que en Mac corta la composición: el
  // acento se pierde. La guarda de `isComposing` se puso el 28 de agosto y NO
  // bastó — Oscar lo siguió reportando con el arreglo ya desplegado, y su
  // instrucción fue clara: «prefiero que sirva a la funcionalidad».
  //
  // Así que el camino de teclear queda LIMPIO: crecer al escribir lo hace el
  // navegador solo con `field-sizing: content` (ver `input.css`), que es la
  // herramienta que ya existe para esto. Aquí sólo se mide cuando NADIE está
  // escribiendo: al cargar, al llegar por HTMX y al vaciarse tras enviar.
  document.addEventListener('DOMContentLoaded', function () { ajustarTodas(); });
  document.body.addEventListener('htmx:afterSwap', function (e) { ajustarTodas(e.target); });
  // Tras enviar, el inline hx-on vacía el textarea; re-encoge en el siguiente tick.
  document.body.addEventListener('htmx:afterRequest', function () { setTimeout(function () { ajustarTodas(); }, 0); });
})();

/* Rickroll placeholder (decisión Oscar): el botón "Enviar" del recuadro de
   Cotizaciones aún no manda correo. Mientras tanto abre este modal con autoplay.
   La "X" se ve grande pero su área clickeable real es de 1×1 px; solo Esc o
   refrescar cierran (el backdrop NO cierra). */
window.abrirRickroll = function () {
  if (document.getElementById('rickroll-overlay')) return;
  var ov = document.createElement('div');
  ov.id = 'rickroll-overlay';
  ov.style.cssText = 'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.92);';
  ov.innerHTML =
    '<div style="position:relative;width:92%;max-width:900px;aspect-ratio:16/9;">'
    + '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0&modestbranding=1&playsinline=1" '
    +   'allow="autoplay; encrypted-media; fullscreen" allowfullscreen '
    +   'referrerpolicy="strict-origin-when-cross-origin" '
    +   'style="position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:14px;box-shadow:0 24px 70px rgba(0,0,0,.6);"></iframe>'
    + '<span aria-hidden="true" style="position:absolute;top:-16px;right:-12px;font-size:46px;line-height:1;font-weight:700;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.85);pointer-events:none;user-select:none;">&times;</span>'
    + '<button type="button" aria-label="Cerrar" data-rickroll-close '
    +   'style="position:absolute;top:0;right:0;width:1px;height:1px;padding:0;margin:0;border:0;background:transparent;cursor:pointer;overflow:hidden;"></button>'
    + '</div>';
  function cerrar() {
    document.removeEventListener('keydown', onKey);
    var n = document.getElementById('rickroll-overlay');
    if (n) n.remove();
  }
  function onKey(e) { if (e.key === 'Escape') cerrar(); }
  ov.querySelector('[data-rickroll-close]').addEventListener('click', cerrar);
  document.addEventListener('keydown', onKey);
  document.body.appendChild(ov);
};


/* Aviso de cambios sin guardar (LC 2026-07-26, Oscar).

   Marca un `<form data-avisar-cambios>` como "sucio" en cuanto el usuario toca
   un campo, y si intenta salirse de la página sin guardar, el navegador le
   pregunta. También lo puede marcar otro componente escribiendo
   `form.dataset.cambiosSinGuardar = "1"` (así lo hace el borrado diferido de la
   foto del producto, en imagen_pegar.js).

   Se limpia al enviar el formulario — guardar no debe disparar el aviso.

   LC 2026-08-13 (Oscar): «el aviso de cambios o "✓ Guardado" hay que aplicarlo
   a TODAS las páginas — productos, proyectos, todo». Así que ya no hace falta
   marcar `data-avisar-cambios` a mano: se monta solo en cualquier formulario
   que tenga un botón de GUARDAR (los mismos verbos que la barra flotante). Se
   saltan los modales —se cierran sin salirse de la página, ahí no aplica— y
   cualquier form con `data-sin-avisar-cambios`. Además del aviso al salir, el
   estado se ve: la barra flotante muestra «Sin guardar» mientras haya algo
   pendiente y «✓ Guardado» al terminar. */
(function () {
  'use strict';
  /* Mismos verbos que la barra flotante: «Filtrar» o «Confirmar» no guardan. */
  var RE_GUARDA = /^(guardar|crear|actualizar|registrar|emitir)\b/i;

  function esFormDeGuardar(form) {
    if (form.hasAttribute('data-avisar-cambios')) return true;
    if (form.hasAttribute('data-sin-avisar-cambios')) return false;
    if (form.closest('#modal-slot')) return false;
    return Array.prototype.some.call(
      form.querySelectorAll('button[type="submit"], input[type="submit"]'),
      function (b) {
        var t = (b.tagName === 'INPUT' ? b.value : b.textContent) || '';
        return RE_GUARDA.test(t.replace(/\s+/g, ' ').trim());
      }
    );
  }
  function formularios() {
    return Array.prototype.slice.call(document.querySelectorAll('form')).filter(esFormDeGuardar);
  }
  function sucio() {
    return Array.prototype.slice.call(document.querySelectorAll('form'))
      .some(function (f) { return f.dataset.cambiosSinGuardar === '1'; });
  }
  function avisar(estado) {
    if (window.__guardarEstado) window.__guardarEstado(estado);
  }
  function montar(form) {
    if (form.dataset.avisoMontado) return;
    form.dataset.avisoMontado = '1';
    ['input', 'change'].forEach(function (ev) {
      form.addEventListener(ev, function (e) {
        // Los controles de solo-lectura o los que no viajan en el POST no cuentan.
        var t = e.target;
        if (!t || t.disabled || t.type === 'hidden') return;
        form.dataset.cambiosSinGuardar = '1';
        avisar('sucio');
      });
    });
    form.addEventListener('submit', function () {
      delete form.dataset.cambiosSinGuardar;
      avisar('guardando');
    });
  }
  function escanear() {
    formularios().forEach(montar);
    avisar(sucio() ? 'sucio' : 'limpio');
  }
  window.addEventListener('beforeunload', function (e) {
    if (!sucio()) return;
    e.preventDefault();
    e.returnValue = '';  // requerido por Chrome para mostrar el aviso
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', escanear);
  } else {
    escanear();
  }
  document.body.addEventListener('htmx:afterSwap', escanear);
  /* Guardado por HTMX (autoguardado del proyecto, celdas, modales): el aviso se
     apaga y la barra dice «✓ Guardado» un momento. */
  document.body.addEventListener('htmx:afterRequest', function (e) {
    var t = e.target;
    var form = t && t.closest ? t.closest('form') : null;
    if (!form || !form.dataset.avisoMontado) return;
    if (!(e.detail && e.detail.successful)) return;
    delete form.dataset.cambiosSinGuardar;
    avisar(sucio() ? 'sucio' : 'guardado');
  });
})();

/* ── Guardar flotante (LC 2026-08-04 R3 · fijo desde 2026-08-07, Oscar) ──────
   «En todas las páginas, el botón de Guardar debe de existir en la esquina
   superior derecha. Si trae consigo otros botones, moverlos esos ahí también.»

   En vez de mover el botón en ~25 plantillas, se monta arriba a la derecha una
   barra con un PROXY por cada botón del grupo; al picar el proxy se hace click
   en el original. Así el form, HTMX, el `form=` y cualquier hx-post siguen
   funcionando igual (clonar el botón o moverlo de sitio sí los rompería).

   Dos modos, según `data-guardar-fijo` en el <body>:
   - CON el atributo (El Taller): la barra vive siempre visible y el grupo de
     botones original se esconde, para no verlos duplicados.
   - SIN el atributo (La Gerencia): como antes — la barra sólo aparece cuando el
     Guardar de verdad se sale de la pantalla, y nada se esconde.
   `ui.js` es dual-copy (regla §18): el archivo es idéntico en las dos apps y lo
   que cambia es el interruptor del <body>.

   Reglas:
   - Sólo botones que GUARDAN (Guardar / Crear / Actualizar / Registrar / Emitir).
     Filtrar, Confirmar, Enviar, Casar, «Volver a mi cuenta»… no cuentan: si no,
     la barra secuestraría el botón de un filtro o del banner de impersonación.
   - Los modales (`#modal-slot`) no participan — ya traen su pie de botones.
   - Opt-out: `data-sin-guardar-flotante` en el botón o en su form.
   - Se esconde mientras hay un modal abierto y refleja el `disabled` del original.
   - Se re-escanea en cada swap de HTMX (el botón puede llegar por OOB, como el
     Deshacer/Guardar del detalle de proyecto). */
(function () {
  'use strict';
  var SEL = 'button[type="submit"], input[type="submit"]';
  /* Lo que sí es un "guardar". Se compara contra el texto del botón. */
  var RE_GUARDA = /^(guardar|crear|actualizar|registrar|emitir)\b/i;
  var ACCIONES = /^(BUTTON|A|INPUT)$/;
  var barra = null, lista = null, original = null, grupo = null;
  var observer = null, proxies = [];
  var ultimoFuera = false;  // ¿el Guardar original está fuera de la pantalla?

  function fijo() {
    return document.body.hasAttribute('data-guardar-fijo');
  }

  function texto(el) {
    var t = (el.tagName === 'INPUT' ? el.value : el.textContent) || '';
    return t.replace(/\s+/g, ' ').trim();
  }

  function etiqueta(el) {
    var t = texto(el);
    return t.length > 24 ? t.slice(0, 24) + '…' : (t || 'Guardar');
  }

  function esCandidato(el) {
    if (el.closest('#modal-slot') || el.closest('[data-modal-slot-close]')) return false;
    if (el.hasAttribute('data-sin-guardar-flotante')) return false;
    var f = el.closest('form');
    if (f && f.hasAttribute('data-sin-guardar-flotante')) return false;
    if (!RE_GUARDA.test(texto(el))) return false;
    // El grupo que nosotros escondimos sigue contando: si no, el siguiente
    // escaneo elegiría otro botón y la barra saltaría al equivocado.
    if (el.closest('[data-guardar-flotante-origen]')) return true;
    // Un botón escondido (display:none) no cuenta como el Guardar de la página.
    return !!(el.offsetParent || el.getClientRects().length);
  }

  /* El Guardar y los botones que lo acompañan (Deshacer, Cancelar…). Sólo se
     toma el grupo cuando el contenedor no tiene nada más que botones. */
  function grupoDe(el) {
    var p = el.parentElement;
    if (!p) return { contenedor: el, botones: [el] };
    var hijos = Array.prototype.slice.call(p.children);
    var soloAcciones = hijos.length > 1 && hijos.every(function (h) {
      return ACCIONES.test(h.tagName);
    });
    if (soloAcciones) return { contenedor: p, botones: hijos };
    return { contenedor: el, botones: [el] };
  }

  function montarBarra() {
    if (barra) return;
    barra = document.createElement('div');
    // Debajo del header sticky (z-20) y por debajo de los modales (z-50).
    barra.className = 'fixed right-4 top-[4.75rem] z-40 hidden sm:right-6';
    barra.setAttribute('data-guardar-flotante', '');
    lista = document.createElement('div');
    lista.className = 'flex items-center gap-2';
    barra.appendChild(lista);
    document.body.appendChild(barra);
  }

  /* Estado de guardado, al lado del botón (LC 2026-08-13, Oscar: «el aviso de
     cambios o ✓ Guardado, en todas las páginas»). Lo alimenta el guard de
     cambios sin guardar de arriba. */
  var estadoEl = null, estadoTimer = null, ultimoEstado = 'limpio';
  var ESTADOS = {
    sucio: ['● Sin guardar', 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-300'],
    guardando: ['Guardando…', 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'],
    guardado: ['✓ Guardado', 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-300'],
  };
  function pintarEstado() {
    if (!lista) return;   // en esta página no hay nada que guardar
    if (!estadoEl || !estadoEl.isConnected) {
      estadoEl = document.createElement('span');
      estadoEl.setAttribute('data-guardar-estado', '');
    }
    if (estadoEl.parentNode !== lista) lista.insertBefore(estadoEl, lista.firstChild);
    var def = ESTADOS[ultimoEstado];
    if (!def) { estadoEl.className = 'hidden'; return; }
    estadoEl.textContent = def[0];
    estadoEl.className = 'rounded-full px-2.5 py-1 text-xs font-medium shadow-theme-xs ' + def[1];
  }
  window.__guardarEstado = function (estado) {
    ultimoEstado = estado;
    if (estadoTimer) { clearTimeout(estadoTimer); estadoTimer = null; }
    pintarEstado();
    if (estado === 'guardado') {
      estadoTimer = setTimeout(function () { window.__guardarEstado('limpio'); }, 2500);
    }
  };

  function hayModal() {
    var slot = document.getElementById('modal-slot');
    return !!(slot && slot.children.length);
  }

  function pintar(visible) {
    if (!barra || !original) return;
    proxies.forEach(function (par) {
      par.proxy.disabled = !!par.real.disabled;
      par.proxy.classList.toggle('cursor-not-allowed', !!par.real.disabled);
      par.proxy.classList.toggle('opacity-40', !!par.real.disabled);
    });
    barra.classList.toggle('hidden', !(visible && !hayModal()));
  }

  function soltarOriginal() {
    if (!grupo) return;
    var c = grupo.contenedor;
    if (c.hasAttribute('data-guardar-flotante-origen')) {
      c.removeAttribute('data-guardar-flotante-origen');
      c.style.display = c.dataset.gfDisplay || '';
      delete c.dataset.gfDisplay;
    }
    grupo = null;
  }

  function esconderOriginal() {
    if (!grupo) return;
    var c = grupo.contenedor;
    c.dataset.gfDisplay = c.style.display || '';
    c.setAttribute('data-guardar-flotante-origen', '');
    c.style.display = 'none';
  }

  function escanear() {
    var candidatos = Array.prototype.slice.call(document.querySelectorAll(SEL)).filter(esCandidato);
    var nuevo = candidatos[0] || null;
    if (nuevo === original) return;
    if (observer) { observer.disconnect(); observer = null; }
    soltarOriginal();
    proxies = [];
    original = nuevo;
    if (!original) { if (barra) barra.classList.add('hidden'); return; }
    montarBarra();
    grupo = grupoDe(original);
    lista.textContent = '';
    grupo.botones.forEach(function (real) {
      var proxy = document.createElement('button');
      proxy.type = 'button';
      proxy.className = (real === original ? 'btn-primario' : 'btn-secundario') + ' shadow-theme-lg';
      proxy.textContent = etiqueta(real);
      proxy.addEventListener('click', function () {
        if (!real.disabled) real.click();
      });
      lista.appendChild(proxy);
      proxies.push({ proxy: proxy, real: real });
    });
    pintarEstado();   // el `textContent = ''` de arriba se llevó el chip
    if (fijo()) {
      esconderOriginal();
      ultimoFuera = true;
      pintar(true);
      return;
    }
    // Modo clásico: aparece justo cuando el original deja de verse.
    observer = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) { ultimoFuera = !e.isIntersecting; pintar(ultimoFuera); });
    }, { rootMargin: '-72px 0px 0px 0px' });
    observer.observe(original);
  }

  /* Un swap de HTMX puede reemplazar un botón del grupo dejando el proxy
     apuntando a un nodo que ya no está en la página (pasa con el «↶ Deshacer»
     del detalle de proyecto, que llega por OOB en cada autoguardado). Si eso
     ocurre, se re-montan los proxies. */
  function grupoVigente() {
    return proxies.length > 0 && proxies.every(function (p) { return p.real.isConnected; });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', escanear);
  } else {
    escanear();
  }
  document.body.addEventListener('htmx:afterSettle', function () {
    if (!grupoVigente()) original = null;   // fuerza re-montar la barra
    escanear();
    pintar(ultimoFuera);
  });
  // Un modal abierto tapa la barra (y al revés); el slot avisa cuándo cambia.
  var slot = document.getElementById('modal-slot');
  if (slot && window.MutationObserver) {
    new MutationObserver(function () { pintar(ultimoFuera); }).observe(slot, { childList: true });
  }
})();

/* ── LC 2026-08-23 (Oscar): en el celular y en la PWA las tarjetas nacen
   PLEGADAS ─────────────────────────────────────────────────────────────────
   «Hay mucho scroll.» El pliegue inicial NO se hace aquí: lo hace input.css con
   una media query, porque cerrar desde el JS después del primer pintado se ve
   como un brinco (la página aparece larga y se encoge). Aquí sólo vive el
   toggle, la flecha y la memoria de la sesión.

   La memoria es `sessionStorage` a propósito: al entrar fresco todo está
   plegado —que es lo que se pidió— pero si abres una sección, picas algo y
   regresas con Atrás, sigue abierta. Sin ella la app te vuelve a cerrar lo que
   acabas de abrir en cada navegación. Al cerrar la app se olvida y vuelve al
   default plegado.

   En escritorio no hace nada: `esMovil()` corta el toggle y la media query de
   la hoja no aplica, así que estas pantallas se ven igual que siempre. */
(function () {
  var CORTE = '(max-width: 767px)';        // teléfonos; una tablet ya tiene aire
  var LLAVE = 'despacho-movil-abiertas';

  function esMovil() {
    try { return window.matchMedia(CORTE).matches; } catch (_) { return false; }
  }
  function leerMemoria() {
    try { return JSON.parse(sessionStorage.getItem(LLAVE) || '{}'); } catch (_) { return {}; }
  }
  function guardarMemoria(m) {
    try { sessionStorage.setItem(LLAVE, JSON.stringify(m)); } catch (_) { /* privado o lleno */ }
  }
  /* La ruta va en la llave para que dos pantallas con una sección del mismo
     nombre no se pisen el estado. */
  function clave(sec) {
    return location.pathname + '#' + (sec.getAttribute('data-movil-plegable') || '');
  }
  function pintarFlecha(sec) {
    var f = sec.querySelector('[data-movil-flecha]');
    if (f) f.textContent = sec.hasAttribute('data-abierto') ? '▾' : '▸';
  }

  function escanear() {
    var memoria = leerMemoria();
    document.querySelectorAll('[data-movil-plegable]').forEach(function (sec) {
      if (sec.dataset.movilListo !== '1') {
        sec.dataset.movilListo = '1';
        /* Los avisos que sólo salen cuando hay algo que atender nacen abiertos:
           plegarlos sería esconder el aviso. */
        if (sec.hasAttribute('data-movil-abierto')) sec.setAttribute('data-abierto', '');
      }
      var k = clave(sec);
      if (k in memoria) {
        if (memoria[k]) sec.setAttribute('data-abierto', '');
        else sec.removeAttribute('data-abierto');
      }
      pintarFlecha(sec);
    });
  }

  document.addEventListener('click', function (e) {
    if (!esMovil()) return;
    var asa = e.target.closest('[data-movil-asa]');
    if (!asa) return;
    var sec = asa.closest('[data-movil-plegable]');
    if (!sec) return;
    /* Cuando el asa es el encabezado completo y adentro hay un enlace o un
       botón propio (el título de «Tareas pendientes» lleva a Tareas, el
       encabezado del calendario a la página del calendario), ese control gana:
       se navega, no se pliega. */
    var dentro = e.target.closest('a, button, input, select, label, [data-dropdown-trigger]');
    if (dentro && dentro !== asa && asa.contains(dentro)) return;

    e.preventDefault();
    var abrir = !sec.hasAttribute('data-abierto');
    if (abrir) sec.setAttribute('data-abierto', ''); else sec.removeAttribute('data-abierto');
    var m = leerMemoria();
    m[clave(sec)] = abrir;
    guardarMemoria(m);
    pintarFlecha(sec);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', escanear);
  } else {
    escanear();
  }
  /* Una sección puede llegar por swap (el tablero de resultados del Dashboard,
     un panel que se repinta): necesita su flecha y su estado. */
  document.body.addEventListener('htmx:afterSettle', escanear);
})();

// ===========================================================================
// Cuadros de texto que crecen AL ENFOCAR, no al teclear.
// LC 2026-08-28 (Oscar): «que siempre esté del mismo tamaño, y cuando se le
// haga click para editar, que se extienda al tamaño del contenedor completo
// para todo el contenido; al salir, que regrese a su tamaño original».
//
// Es lo contrario del auto-grow de arriba, y a propósito: aquel mide en cada
// tecla, y eso trae dos males —el alto acaba dependiendo de cuándo se midió
// (de ahí el «se hace grande y chico solo») y puede cortar la escritura de un
// acento o una ñ, que se componen en dos pulsaciones—. Aquí el alto de reposo
// lo fija el CSS (`rows`) y sólo se mide al entrar, al salir, y al escribir
// **cuando ya se está adentro** (nunca a media composición).
//
//   <textarea data-crece-al-enfocar data-crece-max="260" rows="2">
// ===========================================================================
(function () {
  if (window.CSS && CSS.supports && CSS.supports('field-sizing', 'content')) return;
  var SEL = 'textarea[data-crece-al-enfocar]';
  function expandir(ta) {
    var max = parseInt(ta.getAttribute('data-crece-max') || '260', 10);
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, max) + 'px';
  }
  function encoger(ta) { ta.style.height = ''; }   // vuelve al alto del CSS

  document.addEventListener('focusin', function (e) {
    if (e.target && e.target.matches && e.target.matches(SEL)) expandir(e.target);
  });
  document.addEventListener('focusout', function (e) {
    if (e.target && e.target.matches && e.target.matches(SEL)) encoger(e.target);
  });
  // Al entrar y al salir, nunca mientras se teclea — ver la nota de arriba.
  // Crecer conforme se escribe lo hace `field-sizing: content` en `input.css`.
})();
