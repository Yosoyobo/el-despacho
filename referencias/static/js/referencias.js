/*
 * Autocomplete de Referencias `@/#/$` — vanilla JS.
 *
 * Uso: agregar `data-referencias` a un <textarea>. El script auto-monta el
 * dropdown y se enlaza al evento input. Sin dependencias.
 *
 * Patrón:
 *  - Detecta sigil (@/#/$) precedido por inicio o espacio
 *  - Debounce 150ms
 *  - Llama /api/autocomplete/{usuarios|proyectos|clientes}?q=<prefijo>
 *  - Dropdown debajo del cursor con navegación por flechas + Enter/Tab/Esc
 *  - Reemplaza el token al seleccionar
 */
(function () {
  "use strict";

  const ENDPOINT_POR_SIGIL = {
    "@": "/api/autocomplete/usuarios",
    "#": "/api/autocomplete/proyectos",
    "$": "/api/autocomplete/clientes",
  };

  const COLOR_POR_SIGIL = {
    "@": "text-brand-600 dark:text-brand-400",
    "#": "text-violet-600 dark:text-violet-400",
    "$": "text-emerald-600 dark:text-emerald-400",
  };

  class AutocompleteReferencias {
    constructor(textarea) {
      this.textarea = textarea;
      this.dropdown = null;
      this.resultados = [];
      this.seleccionado = 0;
      this.activo = false;
      this.sigil = null;
      this.tokenInicio = -1;
      this.debounceTimer = null;

      textarea.addEventListener("input", () => this.onInput());
      textarea.addEventListener("keydown", (e) => this.onKeyDown(e));
      textarea.addEventListener("blur", () => setTimeout(() => this.cerrar(), 200));
    }

    onInput() {
      const cursor = this.textarea.selectionStart;
      const texto = this.textarea.value.slice(0, cursor);
      const m = texto.match(/(?:^|[^A-Za-z0-9_])([@#$])([A-Za-z0-9_-]{0,80})$/);
      if (!m) { this.cerrar(); return; }
      this.sigil = m[1];
      this.tokenInicio = cursor - m[2].length - 1;  // posición del sigil
      const prefijo = m[2].toLowerCase();
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this.fetchResultados(prefijo), 150);
    }

    fetchResultados(prefijo) {
      const url = ENDPOINT_POR_SIGIL[this.sigil] + "?q=" + encodeURIComponent(prefijo);
      fetch(url, { headers: { "Accept": "application/json" }, credentials: "same-origin" })
        .then((r) => r.ok ? r.json() : { resultados: [] })
        .then((data) => this.mostrarDropdown(data.resultados || []))
        .catch(() => this.cerrar());
    }

    mostrarDropdown(resultados) {
      this.resultados = resultados;
      this.seleccionado = 0;
      if (!resultados.length) { this.cerrar(); return; }
      if (!this.dropdown) this.crearDropdown();
      this.dropdown.innerHTML = "";
      resultados.forEach((r, i) => {
        const item = document.createElement("div");
        item.className = "px-3 py-2 cursor-pointer flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-800";
        item.dataset.index = i;
        item.innerHTML =
          '<span class="' + COLOR_POR_SIGIL[r.sigil] + ' font-mono font-medium">' + r.sigil + r.slug + '</span>' +
          '<span class="text-sm text-gray-700 dark:text-gray-300">' + escapeHtml(r.etiqueta) + '</span>' +
          (r.secundario ? '<span class="ml-auto text-xs text-gray-500">' + escapeHtml(r.secundario) + '</span>' : '');
        item.addEventListener("mousedown", (e) => { e.preventDefault(); this.elegir(i); });
        if (i === 0) item.classList.add("bg-gray-100", "dark:bg-gray-800");
        this.dropdown.appendChild(item);
      });
      this.posicionar();
      this.dropdown.style.display = "block";
      this.activo = true;
    }

    crearDropdown() {
      this.dropdown = document.createElement("div");
      this.dropdown.className =
        "absolute z-50 mt-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 " +
        "rounded-xl shadow-theme-lg max-h-64 overflow-y-auto min-w-[260px]";
      this.dropdown.style.display = "none";
      document.body.appendChild(this.dropdown);
    }

    posicionar() {
      const rect = this.textarea.getBoundingClientRect();
      this.dropdown.style.top = (window.scrollY + rect.bottom + 4) + "px";
      this.dropdown.style.left = (window.scrollX + rect.left + 16) + "px";
    }

    onKeyDown(e) {
      if (!this.activo) return;
      if (e.key === "ArrowDown") { e.preventDefault(); this.mover(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); this.mover(-1); }
      else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); this.elegir(this.seleccionado); }
      else if (e.key === "Escape") { this.cerrar(); }
    }

    mover(delta) {
      this.seleccionado = (this.seleccionado + delta + this.resultados.length) % this.resultados.length;
      Array.from(this.dropdown.children).forEach((el, i) => {
        el.classList.toggle("bg-gray-100", i === this.seleccionado);
        el.classList.toggle("dark:bg-gray-800", i === this.seleccionado);
      });
    }

    elegir(i) {
      const r = this.resultados[i];
      if (!r) return;
      const texto = this.textarea.value;
      const cursor = this.textarea.selectionStart;
      const antes = texto.slice(0, this.tokenInicio);
      const despues = texto.slice(cursor);
      const reemplazo = r.sigil + r.slug + " ";
      this.textarea.value = antes + reemplazo + despues;
      const nuevoCursor = antes.length + reemplazo.length;
      this.textarea.selectionStart = this.textarea.selectionEnd = nuevoCursor;
      this.textarea.focus();
      this.cerrar();
    }

    cerrar() {
      this.activo = false;
      if (this.dropdown) this.dropdown.style.display = "none";
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  }

  function montar() {
    // S-LC-Feedback-V4: aceptamos textarea e <input type="text"> con data-referencias.
    document.querySelectorAll("textarea[data-referencias], input[data-referencias]").forEach((ta) => {
      if (ta.__autocompleteRefs) return;
      ta.__autocompleteRefs = new AutocompleteReferencias(ta);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", montar);
  } else {
    montar();
  }
  // Reaplicar tras swaps de HTMX.
  document.body.addEventListener("htmx:afterSwap", montar);
})();
