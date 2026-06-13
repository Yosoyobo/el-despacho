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
  (function construirCarpetas() {
    var nav = document.querySelector('[data-ta-sidebar] nav');
    if (!nav) return;
    var conGrupo = nav.querySelectorAll('[data-sidebar-grupo]');
    if (!conGrupo.length) return;
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
          '<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
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

// ── Indicador global "Procesando…" (LC logo girando) — S-LC-Feedback-V7 ──
// V9: el spinner SOLO aparece tras una acción deliberada del usuario (enviar,
// submit, clic de navegación / cambio de sección). NO debe salir al teclear ni
// por autoguardados ni por polling de fondo. Por eso ignoramos las peticiones
// HTMX disparadas por eventos de texto/cambio de campo (input/keyup/keydown/
// change), las que no tienen evento disparador (hx-trigger="load"/"every Ns")
// y las marcadas con [data-sin-indicador="1"]. Rastreamos las peticiones
// "ruidosas" en un WeakSet para que una silenciosa que termina no apague el
// spinner de una ruidosa en curso. Debounce de 180 ms para no parpadear.
(function () {
  var el = document.getElementById('proc-indicador');
  if (!el) return;
  var enVuelo = 0;
  var timer = null;
  var ruidosas = (typeof WeakSet !== 'undefined') ? new WeakSet() : null;
  function mostrar() {
    if (timer) return;
    timer = setTimeout(function () {
      if (enVuelo > 0) { el.classList.remove('hidden'); el.classList.add('flex'); }
    }, 180);
  }
  function ocultarSiVacio() {
    if (enVuelo > 0) return;
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

  document.body.addEventListener('htmx:beforeRequest', function (evt) {
    if (esSilenciosa(evt)) return;
    var xhr = evt.detail && evt.detail.xhr;
    if (ruidosas && xhr) ruidosas.add(xhr);
    inicia();
  });
  function fin(evt) {
    var xhr = evt.detail && evt.detail.xhr;
    if (!ruidosas) { return; }
    if (xhr && ruidosas.has(xhr)) { ruidosas.delete(xhr); termina(); }
  }
  document.body.addEventListener('htmx:afterRequest', fin);
  document.body.addEventListener('htmx:responseError', fin);
  document.body.addEventListener('htmx:sendError', fin);

  // Formularios clásicos (POST de página completa): mostrar hasta que navegue.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.hasAttribute('hx-post') || form.hasAttribute('hx-get')) return;
    if (form.getAttribute('data-sin-indicador') === '1') return;
    enVuelo++; mostrar();
  }, true);
  // Si el usuario regresa con el botón atrás (bfcache), limpia el estado.
  window.addEventListener('pageshow', function () { enVuelo = 0; ocultarSiVacio(); });
})();
