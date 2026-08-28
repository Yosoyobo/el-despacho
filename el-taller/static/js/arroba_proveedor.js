// ===========================================================================
// «@» para ligar un proveedor a un gasto — componente compartido.
//
// LC 2026-08-28 (Oscar): «el uso del @ para etiquetar proveedores en procesos
// adicionales, dentro de la página de editar un producto, no está funcionando.
// Asegurar que funcione en todos lados.»
//
// No estaba roto: existía sólo en la tarjeta de producto del proyecto, metido
// dentro de su plantilla. Portarlo copiando el código habría dejado dos copias
// que tarde o temprano divergen, así que vive aquí y lo usan las dos pantallas
// (la tarjeta del proyecto y la ficha del producto).
//
// Contrato por atributos — ninguna pantalla necesita JavaScript propio:
//
//   <div data-arroba-fila data-proc-prov="3">
//     <input data-arroba-proveedor data-arroba-url="/catalogo/proveedores/buscar">
//     <span data-proc-prov-chip class="hidden">
//       @<span data-proc-prov-nombre></span>
//       <button type="button" data-proc-prov-clear>×</button>
//     </span>
//   </div>
//
// Al ligar o desligar escribe el id en `data-proc-prov` de la fila, pinta el
// chip y dispara `arroba:proveedor` (burbujea, con `detail = {id, nombre}`)
// para que cada pantalla guarde a su manera.
// ===========================================================================
(function () {
  'use strict';

  var pop = null, activo = null, items = [], hi = 0, tmr = null;

  function cerrar() {
    if (pop && pop.parentNode) pop.parentNode.removeChild(pop);
    pop = null; activo = null; items = [];
  }

  function escapar(t) {
    return String(t).replace(/[<>&]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c];
    });
  }

  function posicionar(input) {
    var r = input.getBoundingClientRect();
    pop.style.left = r.left + 'px';
    pop.style.top = (r.bottom + 4) + 'px';
    pop.style.width = Math.max(200, r.width) + 'px';
  }

  function pintar() {
    if (!pop) return;
    if (!items.length) {
      pop.innerHTML = '<div class="px-3 py-2 text-xs text-gray-400">Sin proveedores…</div>';
      return;
    }
    pop.innerHTML = items.map(function (it, i) {
      return '<button type="button" data-i="' + i + '" class="block w-full truncate px-3 py-1.5 text-left text-sm ' +
        (i === hi ? 'bg-brand-50 dark:bg-brand-500/10 ' : '') +
        'text-gray-700 hover:bg-brand-50 dark:text-gray-200 dark:hover:bg-brand-500/10">@ ' +
        escapar(it.nombre) + '</button>';
    }).join('');
  }

  // Escribe el vínculo en la fila y avisa a quien lo tenga que guardar.
  function ligar(fila, id, nombre) {
    if (!fila) return;
    fila.setAttribute('data-proc-prov', id == null ? '' : String(id));
    var chip = fila.querySelector('[data-proc-prov-chip]');
    var nom = fila.querySelector('[data-proc-prov-nombre]');
    if (nom) nom.textContent = nombre || '';
    if (chip) chip.classList.toggle('hidden', id == null);
    fila.dispatchEvent(new CustomEvent('arroba:proveedor', {
      bubbles: true, detail: { id: id, nombre: nombre || '' },
    }));
  }

  function elegir(i) {
    var it = items[i];
    if (!it || !activo) return;
    var fila = activo.closest('[data-arroba-fila]');
    activo.value = activo.value.replace(/@[^@]*$/, '').trim();  // quita el "@loquesea"
    var input = activo;
    cerrar();
    ligar(fila, it.id, it.nombre);
    input.dispatchEvent(new Event('input', { bubbles: true }));  // re-serializa
  }

  function consulta(input) {
    var m = /@([^@]*)$/.exec(input.value);
    return m ? m[1] : null;
  }

  function buscar(q, input) {
    var url = input.getAttribute('data-arroba-url');
    if (!url) return;
    fetch(url + '?q=' + encodeURIComponent(q), {
      headers: { Accept: 'application/json' }, credentials: 'same-origin',
    }).then(function (r) {
      if (!r.ok || activo !== input) return null;
      return r.json();
    }).then(function (d) {
      if (!d || activo !== input) return;
      items = d.resultados || []; hi = 0;
      if (!pop) {
        pop = document.createElement('div');
        pop.className = 'fixed z-[60] max-h-56 overflow-auto rounded-lg border border-gray-200 bg-white py-1 shadow-theme-lg dark:border-gray-700 dark:bg-gray-800';
        document.body.appendChild(pop);
      }
      posicionar(input); pintar();
    }).catch(function () { /* sin red: el gasto se guarda igual, sin proveedor */ });
  }

  document.addEventListener('input', function (e) {
    var input = e.target;
    if (!input || !input.matches || !input.matches('[data-arroba-proveedor]')) return;
    var q = consulta(input);
    if (q === null) { cerrar(); return; }
    activo = input;
    clearTimeout(tmr);
    tmr = setTimeout(function () { buscar(q, input); }, 180);
  });

  document.addEventListener('keydown', function (e) {
    if (!pop || !activo) return;
    if (e.key === 'ArrowDown') { hi = Math.min(items.length - 1, hi + 1); pintar(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { hi = Math.max(0, hi - 1); pintar(); e.preventDefault(); }
    else if (e.key === 'Enter') { if (items.length) { elegir(hi); e.preventDefault(); } }
    else if (e.key === 'Escape') { cerrar(); }
  });

  document.addEventListener('click', function (e) {
    if (pop && pop.contains(e.target)) {
      var b = e.target.closest('[data-i]');
      if (b) elegir(parseInt(b.getAttribute('data-i'), 10));
      return;
    }
    var clr = e.target.closest && e.target.closest('[data-proc-prov-clear]');
    if (clr) {
      var fila = clr.closest('[data-arroba-fila]');
      ligar(fila, null, '');
      var input = fila && fila.querySelector('[data-arroba-proveedor]');
      if (input) input.dispatchEvent(new Event('input', { bubbles: true }));
      e.preventDefault();
      return;
    }
    if (pop && e.target !== activo) cerrar();
  });

  window.addEventListener('scroll', cerrar, true);
})();
