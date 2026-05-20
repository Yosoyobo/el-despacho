// Widgets de formulario TailAdmin — Wave 2 del arco S-TailAdmin-Sweep.
// Vanilla JS, sin librería. Sólo enchufa los partials `_tags_input.html` y
// `_file_upload.html`. Los demás (_checkbox, _radio, _switch, _datepicker,
// _select_buscable) funcionan sin JS adicional.
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
