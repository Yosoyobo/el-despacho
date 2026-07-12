// Widgets de formulario TailAdmin — Wave 2 del arco S-TailAdmin-Sweep.
// Vanilla JS, sin librería. Enchufa los partials `_tags_input.html`,
// `_file_upload.html` y el combobox `[data-select-buscable]` (LC Buzón §4).
(function () {
  'use strict';

  // --- Tags input ---
  function pintarChips(root, hidden, chips, typer) {
    chips.innerHTML = '';
    var valores = (hidden.value || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    valores.forEach(function (txt, i) {
      var chip = document.createElement('span');
      chip.className = 'inline-flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-300';
      chip.textContent = txt;
      var x = document.createElement('button');
      x.type = 'button';
      x.setAttribute('aria-label', 'Eliminar ' + txt);
      x.className = 'text-brand-500 hover:text-brand-700 dark:text-brand-300';
      x.textContent = '×';
      x.addEventListener('click', function () {
        valores.splice(i, 1);
        hidden.value = valores.join(',');
        pintarChips(root, hidden, chips, typer);
      });
      chip.appendChild(x);
      chips.appendChild(chip);
    });
  }

  document.querySelectorAll('[data-tags-input]').forEach(function (root) {
    var hidden = root.querySelector('[data-tags-hidden]');
    var chips = root.querySelector('[data-tags-chips]');
    var typer = root.querySelector('[data-tags-typer]');
    if (!hidden || !chips || !typer) return;
    pintarChips(root, hidden, chips, typer);

    function add() {
      var t = typer.value.trim();
      if (!t) return;
      var valores = (hidden.value || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      if (valores.indexOf(t) === -1) valores.push(t);
      hidden.value = valores.join(',');
      typer.value = '';
      pintarChips(root, hidden, chips, typer);
    }

    typer.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        add();
      } else if (e.key === 'Backspace' && !typer.value) {
        var valores = (hidden.value || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
        valores.pop();
        hidden.value = valores.join(',');
        pintarChips(root, hidden, chips, typer);
      }
    });
    typer.addEventListener('blur', add);
    root.addEventListener('click', function (e) {
      if (e.target === root) typer.focus();
    });
  });

  // --- File upload con dropzone y lista de seleccionados ---
  document.querySelectorAll('[data-file-upload]').forEach(function (root) {
    var input = root.querySelector('[data-file-upload-input]');
    var lista = root.querySelector('[data-file-upload-list]');
    var label = root.querySelector('label.cursor-pointer');
    if (!input || !lista || !label) return;

    function pintarSeleccion() {
      lista.innerHTML = '';
      var files = input.files;
      if (!files || !files.length) return;
      for (var i = 0; i < files.length; i++) {
        var li = document.createElement('li');
        li.className = 'flex items-center gap-2';
        li.textContent = '• ' + files[i].name + ' (' + Math.round(files[i].size / 1024) + ' KB)';
        lista.appendChild(li);
      }
    }
    input.addEventListener('change', pintarSeleccion);

    ['dragenter', 'dragover'].forEach(function (ev) {
      label.addEventListener(ev, function (e) {
        e.preventDefault();
        label.classList.add('border-brand-400', 'bg-brand-50/60');
      });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      label.addEventListener(ev, function (e) {
        e.preventDefault();
        label.classList.remove('border-brand-400', 'bg-brand-50/60');
      });
    });
    label.addEventListener('drop', function (e) {
      if (!e.dataTransfer || !e.dataTransfer.files || !e.dataTransfer.files.length) return;
      input.files = e.dataTransfer.files;
      pintarSeleccion();
    });
  });
})();

// --- Combobox type-to-search (LC Buzón §4) ---------------------------------
// Mejora CUALQUIER <select data-select-buscable> con un panel de búsqueda al
// abrir, SIN reestructurar el DOM: el <select> nativo sigue siendo la fuente de
// verdad (valor, display, submit). Sólo interceptamos la apertura con ratón
// (pointer fino) para mostrar un panel filtrable; en táctil dejamos el picker
// nativo. Como NO envuelve el <select>, es inmune a clones de formset y swaps
// HTMX sin re-init, y lee las <option> vivas (soporta repoblado dinámico).
// Búsqueda cruzada: además del texto de la opción, matchea `data-buscar`.
(function () {
  'use strict';

  var abierto = null;
  var UMBRAL = 6; // menos opciones → picker nativo (no vale la pena buscar)

  function norm(s) {
    return (s || '').toString().toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function aplica(sel) {
    return sel && sel.tagName === 'SELECT' && sel.hasAttribute('data-select-buscable') &&
      !sel.disabled && !sel.multiple && sel.options.length >= UMBRAL;
  }

  function cerrar() {
    if (!abierto) return;
    var a = abierto; abierto = null;
    document.removeEventListener('pointerdown', a.onDoc, true);
    window.removeEventListener('resize', a.onRepos, true);
    window.removeEventListener('scroll', a.onRepos, true);
    if (a.panel.parentNode) a.panel.parentNode.removeChild(a.panel);
    a.select.classList.remove('ring-2', 'ring-brand-500/40');
  }

  function abrir(select) {
    cerrar();
    var panel = document.createElement('div');
    panel.className = 'sb-panel z-[80] rounded-xl border border-gray-200 bg-white shadow-theme-lg dark:border-gray-700 dark:bg-gray-900';
    panel.style.position = 'fixed';

    var input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Buscar…';
    input.className = 'w-full rounded-t-xl border-0 border-b border-gray-100 bg-transparent px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-0 dark:border-gray-800 dark:text-gray-100';
    panel.appendChild(input);

    var lista = document.createElement('ul');
    lista.className = 'max-h-60 overflow-y-auto py-1 text-sm';
    panel.appendChild(lista);

    var vacio = document.createElement('div');
    vacio.className = 'hidden px-3 py-3 text-sm text-gray-400';
    vacio.textContent = 'Sin resultados';
    panel.appendChild(vacio);

    var resaltado = -1;

    function elegir(idx) {
      if (select.selectedIndex !== idx) {
        select.selectedIndex = idx;
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
      cerrar();
    }

    function pintar(filtro) {
      lista.innerHTML = '';
      resaltado = -1;
      var f = norm(filtro), vis = 0;
      Array.prototype.forEach.call(select.options, function (op, i) {
        var extra = op.getAttribute('data-buscar') || '';
        if (f && norm(op.textContent + ' ' + extra).indexOf(f) === -1) return;
        var li = document.createElement('li');
        var activa = i === select.selectedIndex;
        li.className = 'px-3 py-2 ' + (op.disabled
          ? 'cursor-default text-gray-300 dark:text-gray-600'
          : 'cursor-pointer hover:bg-brand-50 dark:hover:bg-brand-500/10 ' +
            (activa ? 'bg-brand-50/60 font-medium text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                    : 'text-gray-700 dark:text-gray-200'));
        li.textContent = op.textContent.trim() || '—';
        li.dataset.idx = i;
        if (!op.disabled) {
          li.addEventListener('pointerdown', function (e) { e.preventDefault(); elegir(i); });
          vis++;
        }
        lista.appendChild(li);
      });
      vacio.classList.toggle('hidden', vis > 0);
    }

    function mover(delta) {
      var items = Array.prototype.filter.call(lista.querySelectorAll('li'), function (li) {
        return li.dataset.idx !== undefined && !select.options[+li.dataset.idx].disabled;
      });
      if (!items.length) return;
      resaltado = (resaltado + delta + items.length) % items.length;
      items.forEach(function (li, k) {
        li.classList.toggle('bg-brand-100', k === resaltado);
        li.classList.toggle('dark:bg-brand-500/20', k === resaltado);
      });
      items[resaltado].scrollIntoView({ block: 'nearest' });
    }

    input.addEventListener('input', function () { pintar(input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); mover(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); mover(-1); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        var items = lista.querySelectorAll('li[data-idx]');
        var li = null, k = 0;
        for (var n = 0; n < items.length; n++) {
          if (select.options[+items[n].dataset.idx].disabled) continue;
          if (resaltado === -1 || k === resaltado) { li = items[n]; break; }
          k++;
        }
        if (li) elegir(+li.dataset.idx);
      } else if (e.key === 'Escape') { e.preventDefault(); cerrar(); select.focus(); }
    });

    function repos() {
      var r = select.getBoundingClientRect();
      panel.style.left = r.left + 'px';
      panel.style.top = (r.bottom + 4) + 'px';
      panel.style.width = Math.max(r.width, 220) + 'px';
    }

    document.body.appendChild(panel);
    repos();
    pintar('');
    select.classList.add('ring-2', 'ring-brand-500/40');
    setTimeout(function () { input.focus(); }, 0);

    function onDoc(e) { if (!panel.contains(e.target) && e.target !== select) cerrar(); }
    document.addEventListener('pointerdown', onDoc, true);
    window.addEventListener('resize', repos, true);
    window.addEventListener('scroll', repos, true);
    abierto = { select: select, panel: panel, onDoc: onDoc, onRepos: repos };
  }

  // LC revisión buzón: el buscador también aplica en MÓVIL. Usamos `pointerdown`
  // (mouse + touch + pen) y prevenimos el picker nativo para abrir el panel
  // filtrable en todos los dispositivos.
  document.addEventListener('pointerdown', function (e) {
    var sel = e.target.closest && e.target.closest('select[data-select-buscable]');
    if (!aplica(sel)) return;
    e.preventDefault();
    if (abierto && abierto.select === sel) { cerrar(); return; }
    abrir(sel);
  }, true);

  document.addEventListener('keydown', function (e) {
    var sel = document.activeElement;
    if (!aplica(sel)) return;
    if ((e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') &&
        !(abierto && abierto.select === sel)) {
      e.preventDefault();
      abrir(sel);
    }
  }, true);
})();
