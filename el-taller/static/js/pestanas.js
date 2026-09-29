/* Las pestañas de El Taller — S-Pendientes-Sep28 (camino B del análisis de agosto).
 *
 * Cada pestaña es un documento propio dentro de un marco (<iframe>) de la página
 * `/pestanas/`. Se eligió así porque el front supone UNA página viva a la vez (un
 * solo #modal-slot, identificadores únicos, autoguardados que buscan «el» formulario
 * del proyecto): dos pantallas en el mismo documento se pisarían en silencio. Con
 * marcos, cada pestaña tiene su documento y nadie se entera de que hay otras.
 *
 * Decisiones de Oscar (9 rondas, docs/SPRINT-Pendientes-Sep28.md):
 *   - Sólo El Taller y sólo escritorio (en el celular este guion no hace nada).
 *   - Tope de 6. Las que no se usan se descargan (se vuelven a cargar al picarlas),
 *     menos las que tienen cambios sin guardar.
 *   - Se abren con «+», con Ctrl/⌘+clic y con clic derecho → «Abrir en pestaña».
 *     El clic con el botón de en medio NO se toca: sigue siendo del navegador.
 *   - Se recuerdan en ESTE navegador (localStorage).
 *   - Si lo que se abre ya está en otra pestaña, se salta a ésa.
 *
 * Tres modos, según dónde corre:
 *   - marco:   dentro de una pestaña. Pide al contenedor que abra lo que se le pida
 *              y le avisa a dónde navegó.
 *   - normal:  una página cualquiera. Es la pestaña activa; la barra muestra las
 *              demás y picar otra lleva al contenedor.
 *   - shell:   el contenedor. Arma un marco por pestaña.
 */
(function () {
  'use strict';

  var CLAVE = 'despacho-pestanas';
  var TOPE = 6;
  var CARGADAS_MAX = 3;          // marcos vivos a la vez: la activa y las 2 más recientes
  var ORIGEN = location.origin;
  var MSG = 'despacho-pestana';

  var escritorio = window.matchMedia
    ? window.matchMedia('(min-width: 1024px) and (pointer: fine)')
    : { matches: true };

  var enMarco = (function () {
    try { return window.self !== window.top && window.top.location.origin === ORIGEN; }
    catch (e) { return false; }
  })();
  var esShell = !!(document.body && document.body.hasAttribute('data-pestanas-shell'));

  // ── Estado ────────────────────────────────────────────────────────────────

  function leer() {
    try {
      var e = JSON.parse(localStorage.getItem(CLAVE) || 'null');
      if (e && Array.isArray(e.tabs)) {
        e.tabs = e.tabs.filter(function (t) { return t && t.id && typeof t.url === 'string'; });
        return e;
      }
    } catch (err) { /* sin localStorage o JSON roto: se empieza limpio */ }
    return { v: 1, tabs: [], activa: null };
  }
  function guardar(e) {
    try { localStorage.setItem(CLAVE, JSON.stringify(e)); } catch (err) { /* modo privado */ }
  }
  function nuevaId() {
    return 'p' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  }

  /** Ruta interna normalizada, o null si no es una pantalla de El Taller. */
  function normalizar(url) {
    var u;
    try { u = new URL(url, location.href); } catch (e) { return null; }
    if (u.origin !== ORIGEN) return null;
    if (u.pathname.indexOf('/pestanas') === 0) return '/';
    if (/^\/(static|medios|media)\//.test(u.pathname)) return null;
    // Entrar y salir de la sesión es de la ventana completa, nunca de una pestaña.
    if (/^\/(sign-in|sign-out|auth)(\/|$)/.test(u.pathname)) return null;
    return u.pathname + u.search + u.hash;
  }
  function sinHash(ruta) { return (ruta || '').split('#')[0]; }
  function mismaPantalla(a, b) { return sinHash(a) === sinHash(b); }

  function tituloLimpio(t) {
    t = (t || '').replace(/\s*[—·|-]\s*(El Taller|El Despacho).*$/i, '').trim();
    return t || 'Pantalla';
  }
  function buscar(e, id) {
    for (var i = 0; i < e.tabs.length; i++) if (e.tabs[i].id === id) return e.tabs[i];
    return null;
  }
  function buscarPorRuta(e, ruta) {
    for (var i = 0; i < e.tabs.length; i++) if (mismaPantalla(e.tabs[i].url, ruta)) return e.tabs[i];
    return null;
  }
  function aqui() { return location.pathname + location.search + location.hash; }

  // ── Aviso chico (tope, errores) ───────────────────────────────────────────

  function avisar(texto) {
    var el = document.getElementById('pestanas-aviso');
    if (!el) {
      el = document.createElement('div');
      el.id = 'pestanas-aviso';
      el.setAttribute('role', 'status');
      el.className = 'fixed right-4 top-4 z-[70] max-w-sm rounded-lg bg-gray-900 px-4 py-2.5 text-sm text-white shadow-theme-lg dark:bg-gray-100 dark:text-gray-900';
      document.body.appendChild(el);
    }
    el.textContent = texto;
    el.hidden = false;
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.hidden = true; }, 3500);
  }

  // ── ¿Tiene cambios sin guardar? (lo marca el guardián de ui.js) ───────────

  function marcoSucio(marco) {
    try {
      var d = marco && marco.contentDocument;
      return !!(d && d.querySelector('form[data-cambios-sin-guardar="1"]'));
    } catch (e) { return false; }
  }

  // ═════════════════════════════════════════════════════════════════════════
  // Abrir: lo que hacen Ctrl/⌘+clic, el menú y el «+», en cualquier modo.
  // ═════════════════════════════════════════════════════════════════════════

  /**
   * Abre `url` en una pestaña. `enFrente`: activarla (el «+»); si no, queda
   * atrás, como Ctrl+clic en el navegador. Si ya existe, se salta a ella —
   * salvo con `siempreNueva` (el «+»: pedir una pestaña nueva es pedir otra,
   * aunque el Dashboard ya esté abierto).
   */
  function abrir(url, enFrente, siempreNueva) {
    var ruta = normalizar(url);
    if (!ruta) { window.open(url, '_blank', 'noopener'); return; }
    if (enMarco) {
      window.top.postMessage({ tipo: MSG, accion: 'abrir', url: ruta, enFrente: !!enFrente }, ORIGEN);
      return;
    }
    if (esShell && Shell.listo) { Shell.abrir(ruta, enFrente, siempreNueva); return; }

    // Modo normal: la página actual es la pestaña activa.
    var e = leer();
    Normal.asegurarActiva(e);
    var ya = siempreNueva ? null : buscarPorRuta(e, ruta);
    if (ya) {
      if (ya.id === e.activa) { avisar('Esa pantalla ya es la que tienes abierta.'); return; }
      e.activa = ya.id;
      guardar(e);
      location.href = '/pestanas/';
      return;
    }
    if (e.tabs.length >= TOPE) {
      avisar('Llegaste al tope de ' + TOPE + ' pestañas. Cierra una para abrir otra.');
      return;
    }
    var nueva = { id: nuevaId(), url: ruta, titulo: 'Cargando…', uso: Date.now() };
    e.tabs.push(nueva);
    if (enFrente) {
      e.activa = nueva.id;
      guardar(e);
      location.href = '/pestanas/';
      return;
    }
    guardar(e);
    Barra.pintar(e);
    Barra.destellar(nueva.id);
  }

  // ═════════════════════════════════════════════════════════════════════════
  // La barra
  // ═════════════════════════════════════════════════════════════════════════

  var Barra = {
    el: null,
    montar: function () {
      this.el = document.getElementById('barra-pestanas');
      if (!this.el) return false;
      this.el.classList.remove('hidden');
      this.el.className = 'flex items-end gap-1 overflow-x-auto border-b border-gray-200 bg-white px-3 pt-1.5 dark:border-gray-800 dark:bg-gray-950';
      this.el.setAttribute('role', 'tablist');
      this.el.setAttribute('aria-label', 'Pestañas');
      return true;
    },
    pintar: function (e) {
      if (!this.el) return;
      var frag = document.createDocumentFragment();
      var varias = e.tabs.length > 1;
      e.tabs.forEach(function (t) {
        var activa = t.id === e.activa;
        var tab = document.createElement('div');
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-selected', activa ? 'true' : 'false');
        tab.dataset.pestana = t.id;
        tab.title = t.titulo + '\n' + sinHash(t.url);
        tab.className = 'group flex max-w-[15rem] shrink-0 cursor-pointer items-center gap-1.5 rounded-t-lg border border-b-0 px-3 py-1.5 text-xs '
          + (activa
            ? 'border-gray-200 bg-gray-50 font-medium text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white'
            : 'border-transparent text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-gray-200');
        var nombre = document.createElement('span');
        nombre.className = 'truncate';
        nombre.textContent = t.titulo || 'Pantalla';
        tab.appendChild(nombre);
        if (varias) {
          var x = document.createElement('button');
          x.type = 'button';
          x.dataset.cerrarPestana = t.id;
          x.setAttribute('aria-label', 'Cerrar «' + (t.titulo || 'pestaña') + '»');
          x.className = 'rounded px-1 leading-none text-gray-400 hover:bg-gray-200 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-200';
          x.textContent = '×';
          tab.appendChild(x);
        }
        frag.appendChild(tab);
      });
      var mas = document.createElement('button');
      mas.type = 'button';
      mas.dataset.nuevaPestana = '1';
      mas.title = 'Pestaña nueva (abre el Dashboard). También: Ctrl/⌘ + clic en cualquier enlace.';
      mas.setAttribute('aria-label', 'Pestaña nueva');
      mas.className = 'mb-0.5 ml-1 shrink-0 rounded-md px-2 py-1 text-sm leading-none text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-gray-200';
      mas.textContent = '+';
      frag.appendChild(mas);
      this.el.textContent = '';
      this.el.appendChild(frag);
    },
    destellar: function (id) {
      if (!this.el) return;
      var t = this.el.querySelector('[data-pestana="' + id + '"]');
      if (!t) return;
      t.classList.add('ring-2', 'ring-brand-300');
      setTimeout(function () { t.classList.remove('ring-2', 'ring-brand-300'); }, 900);
    },
    escuchar: function (alPicar, alCerrar, alNueva) {
      if (!this.el) return;
      this.el.addEventListener('click', function (ev) {
        var cerrar = ev.target.closest('[data-cerrar-pestana]');
        if (cerrar) { ev.stopPropagation(); alCerrar(cerrar.dataset.cerrarPestana); return; }
        if (ev.target.closest('[data-nueva-pestana]')) { alNueva(); return; }
        var tab = ev.target.closest('[data-pestana]');
        if (tab) alPicar(tab.dataset.pestana);
      });
      // Clic de en medio sobre una pestaña: cerrarla, como en el navegador.
      this.el.addEventListener('auxclick', function (ev) {
        var tab = ev.button === 1 && ev.target.closest('[data-pestana]');
        if (tab) { ev.preventDefault(); alCerrar(tab.dataset.pestana); }
      });
    }
  };

  // ═════════════════════════════════════════════════════════════════════════
  // Modo normal: una página cualquiera, que es la pestaña activa.
  // ═════════════════════════════════════════════════════════════════════════

  var Normal = {
    asegurarActiva: function (e) {
      var act = buscar(e, e.activa);
      if (!act) {
        act = buscarPorRuta(e, aqui());
        if (!act) {
          act = { id: nuevaId(), url: aqui(), titulo: tituloLimpio(document.title), uso: Date.now() };
          e.tabs.unshift(act);
        }
        e.activa = act.id;
      }
      // Navegar en la página ES navegar en la pestaña activa.
      act.url = aqui();
      act.titulo = tituloLimpio(document.title);
      act.uso = Date.now();
      return act;
    },
    arrancar: function () {
      if (!Barra.montar()) return;
      var e = leer();
      this.asegurarActiva(e);
      guardar(e);
      Barra.pintar(e);
      Barra.escuchar(
        function picar(id) {
          var e2 = leer();
          if (id === e2.activa) return;
          e2.activa = id;
          guardar(e2);
          location.href = '/pestanas/';
        },
        function cerrar(id) {
          var e2 = leer();
          var i = e2.tabs.findIndex(function (t) { return t.id === id; });
          if (i < 0) return;
          if (id !== e2.activa) {
            e2.tabs.splice(i, 1);
            guardar(e2);
            Barra.pintar(e2);
            return;
          }
          // Cerrar la activa = irse de esta página: el guardián de ui.js avisa si hay cambios.
          e2.tabs.splice(i, 1);
          var sig = e2.tabs[Math.min(i, e2.tabs.length - 1)];
          e2.activa = sig.id;
          guardar(e2);
          location.href = e2.tabs.length > 1 ? '/pestanas/' : sig.url;
        },
        function nueva() { abrir('/', true, true); }
      );
      // Otra ventana del navegador cambió las pestañas: la barra se repinta sola.
      window.addEventListener('storage', function (ev) {
        if (ev.key === CLAVE) Barra.pintar(leer());
      });
    }
  };

  // ═════════════════════════════════════════════════════════════════════════
  // Modo shell: el contenedor.
  // ═════════════════════════════════════════════════════════════════════════

  var Shell = {
    listo: false,
    area: null,
    marcos: {},

    arrancar: function () {
      this.area = document.querySelector('[data-pestanas-area]');
      if (!this.area || !Barra.montar()) return;
      var e = leer();
      // `/pestanas/#/proyectos/12/` abre esa pantalla: el enlace se puede compartir.
      var pedida = location.hash.length > 1 ? normalizar(location.hash.slice(1)) : null;
      if (!e.tabs.length) {
        var t0 = { id: nuevaId(), url: pedida || '/', titulo: 'Dashboard', uso: Date.now() };
        e.tabs.push(t0);
        e.activa = t0.id;
        pedida = null;
      }
      if (pedida) {
        var ya = buscarPorRuta(e, pedida);
        if (ya) e.activa = ya.id;
        else if (e.tabs.length < TOPE) {
          var tn = { id: nuevaId(), url: pedida, titulo: 'Cargando…', uso: Date.now() };
          e.tabs.push(tn);
          e.activa = tn.id;
        }
      }
      if (!buscar(e, e.activa)) e.activa = e.tabs[0].id;
      guardar(e);
      this.listo = true;
      var self = this;
      Barra.escuchar(
        function (id) { self.activar(id); },
        function (id) { self.cerrar(id); },
        function () { self.abrir('/', true, true); }
      );
      window.addEventListener('message', function (ev) { self.recibir(ev); });
      window.addEventListener('beforeunload', function (ev) {
        var sucia = Object.keys(self.marcos).some(function (id) { return marcoSucio(self.marcos[id]); });
        if (!sucia) return;
        ev.preventDefault();
        ev.returnValue = '';
      });
      // El menú y el encabezado del contenedor navegan DENTRO de la pestaña activa.
      document.addEventListener('click', function (ev) { self.interceptarMenu(ev); });
      this.activar(e.activa);
    },

    estado: function () { return leer(); },

    abrir: function (ruta, enFrente, siempreNueva) {
      var e = leer();
      var ya = siempreNueva ? null : buscarPorRuta(e, ruta);
      if (ya) { this.activar(ya.id); return; }
      if (e.tabs.length >= TOPE) {
        avisar('Llegaste al tope de ' + TOPE + ' pestañas. Cierra una para abrir otra.');
        return;
      }
      var t = { id: nuevaId(), url: ruta, titulo: 'Cargando…', uso: Date.now() };
      e.tabs.push(t);
      guardar(e);
      if (enFrente) { this.activar(t.id); return; }
      Barra.pintar(e);
      Barra.destellar(t.id);
    },

    crearMarco: function (t) {
      var f = document.createElement('iframe');
      f.src = t.url;
      f.title = t.titulo || 'Pestaña';
      f.dataset.marco = t.id;
      f.className = 'absolute inset-0 h-full w-full border-0 bg-gray-50 dark:bg-gray-950';
      // Descargar un PDF, copiar al portapapeles o pedir la ubicación deben seguir
      // funcionando dentro de la pestaña.
      f.setAttribute('allow', 'clipboard-read; clipboard-write; geolocation; web-share');
      var self = this;
      f.addEventListener('load', function () { self.alCargar(t.id, f); });
      this.area.appendChild(f);
      this.marcos[t.id] = f;
      return f;
    },

    alCargar: function (id, f) {
      var ruta, titulo;
      try {
        ruta = f.contentWindow.location.pathname + f.contentWindow.location.search + f.contentWindow.location.hash;
        titulo = tituloLimpio(f.contentDocument.title);
      } catch (err) { return; }
      if (ruta.indexOf('/pestanas') === 0) { f.src = '/'; return; }
      this.actualizar(id, ruta, titulo);
    },

    actualizar: function (id, ruta, titulo) {
      var e = leer();
      var t = buscar(e, id);
      if (!t) return;
      t.url = ruta;
      if (titulo) t.titulo = titulo;
      guardar(e);
      Barra.pintar(e);
      if (id === e.activa) this.reflejar(t);
    },

    /** La barra de direcciones y el título dicen dónde estás (se puede compartir). */
    reflejar: function (t) {
      document.title = (t.titulo || 'Pestañas') + ' — El Taller';
      try { history.replaceState(null, '', '/pestanas/#' + t.url); } catch (err) { /* nada */ }
    },

    activar: function (id) {
      var e = leer();
      var t = buscar(e, id);
      if (!t) return;
      e.activa = id;
      t.uso = Date.now();
      guardar(e);
      var f = this.marcos[id] || this.crearMarco(t);
      Object.keys(this.marcos).forEach(function (k) {
        var m = this.marcos[k];
        m.hidden = k !== id;
      }, this);
      f.hidden = false;
      Barra.pintar(e);
      this.reflejar(t);
      this.descargarDormidas(e);
    },

    /** Deja vivos los marcos más recientes; los otros se quitan para no gastar
        memoria (la pared del NUC llegó a 5.4 GB con un solo navegador abierto).
        Nunca se descarga uno con cambios sin guardar. */
    descargarDormidas: function (e) {
      var self = this;
      var porUso = e.tabs.slice().sort(function (a, b) { return (b.uso || 0) - (a.uso || 0); });
      porUso.slice(CARGADAS_MAX).forEach(function (t) {
        var f = self.marcos[t.id];
        if (!f || t.id === e.activa || marcoSucio(f)) return;
        f.remove();
        delete self.marcos[t.id];
      });
    },

    cerrar: function (id) {
      var e = leer();
      var i = e.tabs.findIndex(function (t) { return t.id === id; });
      if (i < 0) return;
      var f = this.marcos[id];
      if (f && marcoSucio(f) &&
          !window.confirm('Esta pestaña tiene cambios sin guardar. ¿Cerrarla de todos modos?')) return;
      e.tabs.splice(i, 1);
      if (f) { f.remove(); delete this.marcos[id]; }
      if (e.tabs.length === 1) {
        // Con una sola pestaña ya no hace falta el contenedor: se vuelve a la página normal.
        e.activa = e.tabs[0].id;
        guardar(e);
        location.replace(e.tabs[0].url);
        return;
      }
      if (e.activa === id) e.activa = e.tabs[Math.min(i, e.tabs.length - 1)].id;
      guardar(e);
      this.activar(e.activa);
    },

    recibir: function (ev) {
      if (ev.origin !== ORIGEN || !ev.data || ev.data.tipo !== MSG) return;
      var id = null;
      Object.keys(this.marcos).forEach(function (k) {
        if (this.marcos[k].contentWindow === ev.source) id = k;
      }, this);
      if (ev.data.accion === 'abrir' && typeof ev.data.url === 'string') {
        var ruta = normalizar(ev.data.url);
        if (ruta) this.abrir(ruta, !!ev.data.enFrente);
      } else if (ev.data.accion === 'estado' && id) {
        var r = normalizar(ev.data.url);
        if (r) this.actualizar(id, r, tituloLimpio(ev.data.titulo));
      }
    },

    interceptarMenu: function (ev) {
      if (ev.defaultPrevented || ev.button !== 0) return;
      var a = ev.target.closest && ev.target.closest('a[href]');
      if (!a || Barra.el.contains(a) || this.area.contains(a)) return;
      if (a.target && a.target !== '_self') return;
      if (a.hasAttribute('download') || a.hasAttribute('hx-get') || a.hasAttribute('hx-post')) return;
      var href = a.getAttribute('href') || '';
      if (!href || href.charAt(0) === '#' || /^javascript:/i.test(href)) return;
      var ruta = normalizar(a.href);
      if (!ruta) return;                       // otro sitio (La Gerencia): navega normal
      ev.preventDefault();
      if (ev.metaKey || ev.ctrlKey) { this.abrir(ruta, false); return; }
      var e = leer();
      var f = this.marcos[e.activa] || this.crearMarco(buscar(e, e.activa));
      f.src = ruta;
    }
  };

  // ═════════════════════════════════════════════════════════════════════════
  // Modo marco: la página vive dentro de una pestaña.
  // ═════════════════════════════════════════════════════════════════════════

  var Marco = {
    arrancar: function () {
      var avisarEstado = function () {
        window.top.postMessage({ tipo: MSG, accion: 'estado', url: aqui(), titulo: document.title }, ORIGEN);
      };
      avisarEstado();
      window.addEventListener('popstate', avisarEstado);
      document.body.addEventListener('htmx:pushedIntoHistory', avisarEstado);
      document.body.addEventListener('htmx:replacedInHistory', avisarEstado);
      // Un enlace a OTRO sitio (La Gerencia) no puede abrir dentro del marco: La
      // Gerencia se niega a que la incrusten. Se abre en una ventana del navegador.
      document.addEventListener('click', function (ev) {
        if (ev.defaultPrevented || ev.button !== 0) return;
        var a = ev.target.closest && ev.target.closest('a[href]');
        if (!a || (a.target && a.target !== '_self')) return;
        var u;
        try { u = new URL(a.href, location.href); } catch (err) { return; }
        if (!/^https?:$/.test(u.protocol) || u.origin === ORIGEN) return;
        ev.preventDefault();
        window.open(u.href, '_blank', 'noopener');
      });
    }
  };

  // ═════════════════════════════════════════════════════════════════════════
  // Ctrl/⌘ + clic y el menú del clic derecho (en los tres modos)
  // ═════════════════════════════════════════════════════════════════════════

  /** ¿Qué pantalla abriría este clic? `null` si no es algo que se abra en pestaña. */
  function destinoDe(nodo) {
    if (!nodo || !nodo.closest) return null;
    if (nodo.closest('[data-sin-pestana], input, textarea, select, [contenteditable="true"]')) return null;
    if (Barra.el && Barra.el.contains(nodo)) return null;
    var a = nodo.closest('a[href]');
    if (a) {
      if (a.hasAttribute('download') || a.hasAttribute('hx-get') || a.hasAttribute('hx-post')) return null;
      var href = a.getAttribute('href') || '';
      if (!href || href.charAt(0) === '#' || /^(javascript|mailto|tel):/i.test(href)) return null;
      return normalizar(a.href) ? a.href : null;
    }
    // Filas y tarjetas clickeables de ui.js; un botón adentro hace lo suyo.
    if (nodo.closest('button, [role="button"]')) return null;
    var fila = nodo.closest('[data-href]');
    if (fila && fila.getAttribute('data-href')) return normalizar(fila.getAttribute('data-href')) ? fila.getAttribute('data-href') : null;
    return null;
  }

  function engancharCtrlClic() {
    // En captura y en `window`: gana a los manejadores de ui.js (que con Ctrl
    // abrían una ventana del navegador) y al de HTMX.
    window.addEventListener('click', function (ev) {
      if (!escritorio.matches || ev.button !== 0 || !(ev.metaKey || ev.ctrlKey) || ev.shiftKey || ev.altKey) return;
      var url = destinoDe(ev.target);
      if (!url) return;
      ev.preventDefault();
      ev.stopImmediatePropagation();
      abrir(url, false);
    }, true);
  }

  var Menu = {
    el: null,
    cerrar: function () { if (this.el) { this.el.remove(); this.el = null; } },
    abrir: function (x, y, url) {
      this.cerrar();
      var m = document.createElement('div');
      m.setAttribute('role', 'menu');
      m.className = 'fixed z-[80] min-w-[15rem] overflow-hidden rounded-lg border border-gray-200 bg-white py-1 text-sm shadow-theme-lg dark:border-gray-700 dark:bg-gray-900';
      var opciones = [
        ['Abrir en pestaña de El Despacho', function () { abrir(url, false); }],
        ['Abrir en ventana nueva del navegador', function () { window.open(url, '_blank', 'noopener'); }],
        ['Copiar enlace', function () {
          var abs = new URL(url, location.href).href;
          if (navigator.clipboard) navigator.clipboard.writeText(abs).then(function () { avisar('Enlace copiado.'); });
        }]
      ];
      opciones.forEach(function (op) {
        var b = document.createElement('button');
        b.type = 'button';
        b.setAttribute('role', 'menuitem');
        b.className = 'block w-full px-4 py-2 text-left text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800';
        b.textContent = op[0];
        b.addEventListener('click', function () { Menu.cerrar(); op[1](); });
        m.appendChild(b);
      });
      var pista = document.createElement('p');
      pista.className = 'border-t border-gray-100 px-4 py-1.5 text-[11px] text-gray-400 dark:border-gray-800';
      pista.textContent = 'Mayús + clic derecho: el menú del navegador';
      m.appendChild(pista);
      document.body.appendChild(m);
      var r = m.getBoundingClientRect();
      m.style.left = Math.max(4, Math.min(x, window.innerWidth - r.width - 4)) + 'px';
      m.style.top = Math.max(4, Math.min(y, window.innerHeight - r.height - 4)) + 'px';
      this.el = m;
    }
  };

  function engancharMenu() {
    document.addEventListener('contextmenu', function (ev) {
      if (!escritorio.matches || ev.shiftKey) { Menu.cerrar(); return; }
      var url = destinoDe(ev.target);
      if (!url) { Menu.cerrar(); return; }
      ev.preventDefault();
      Menu.abrir(ev.clientX, ev.clientY, url);
    });
    document.addEventListener('click', function (ev) {
      if (Menu.el && !Menu.el.contains(ev.target)) Menu.cerrar();
    });
    document.addEventListener('keydown', function (ev) {
      // El Esc que cancela un acento a medio escribir no cierra el menú.
      if (window.despachoComponiendo ? window.despachoComponiendo(ev) : (ev.isComposing || ev.keyCode === 229)) return;
      if (ev.key === 'Escape') Menu.cerrar();
    });
    window.addEventListener('scroll', function () { Menu.cerrar(); }, true);
    window.addEventListener('blur', function () { Menu.cerrar(); });
  }

  // ── Arranque ──────────────────────────────────────────────────────────────

  function arrancar() {
    if (enMarco) {
      Marco.arrancar();
      engancharCtrlClic();
      engancharMenu();
      return;
    }
    if (!escritorio.matches) {
      // En el celular no hay pestañas. Si alguien abre el contenedor, se le manda
      // a la pantalla que tenía activa.
      if (esShell) {
        var e = leer();
        var t = buscar(e, e.activa);
        location.replace(t ? t.url : '/');
      }
      return;
    }
    if (esShell) Shell.arrancar();
    else Normal.arrancar();
    engancharCtrlClic();
    engancharMenu();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', arrancar);
  else arrancar();

  // Para pruebas y para depurar a mano desde la consola.
  window.__pestanas = { leer: leer, normalizar: normalizar, TOPE: TOPE, CARGADAS_MAX: CARGADAS_MAX };
})();
