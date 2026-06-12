/*
 * Widget AI 🤖 (S-Chalanes-UX #2) — "Redactar con El Chalán" en cualquier
 * textarea. Vanilla JS, sin dependencias.
 *
 * Markup esperado (ver _componentes_tailadmin/_textarea_ia.html):
 *   <div data-textarea-ia data-endpoint="/chalan/redactar" data-target="#ia-x"
 *        data-contexto-modelo="proyecto" data-contexto-id="12">
 *     <textarea id="ia-x" name="x" data-referencias>…</textarea>
 *     <input data-ia-instruccion>
 *     <button data-ia-redactar>🤖 Redactar</button>
 *     <span data-ia-estado></span>
 *   </div>
 *
 * Patrón Copilot (MVP): rellena el textarea con la propuesta; el usuario
 * revisa/edita y guarda con el submit normal del form. No auto-publica.
 */
(function () {
  "use strict";

  function csrfDe(el) {
    const form = el.closest("form");
    const inp = form && form.querySelector('input[name="csrfmiddlewaretoken"]');
    if (inp) return inp.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function montar(root) {
    if (root.dataset.iaMontado) return;
    root.dataset.iaMontado = "1";
    const target = root.querySelector(root.dataset.target) ||
                   document.querySelector(root.dataset.target);
    const btn = root.querySelector("[data-ia-redactar]");
    const instr = root.querySelector("[data-ia-instruccion]");
    const estado = root.querySelector("[data-ia-estado]");
    if (!target || !btn || !instr) return;

    const setEstado = (txt, err) => {
      if (!estado) return;
      estado.textContent = txt || "";
      estado.className = "text-xs " + (err
        ? "text-error-600 dark:text-error-400"
        : "text-gray-500 dark:text-gray-400");
    };

    const pedir = () => {
      const instruccion = (instr.value || "").trim();
      if (!instruccion) { setEstado("Escribe qué quieres que redacte.", true); instr.focus(); return; }
      btn.disabled = true;
      setEstado("El Chalán está redactando…");
      const body = new URLSearchParams({
        instruccion: instruccion,
        texto_actual: target.value || "",
        contexto_modelo: root.dataset.contextoModelo || "",
        contexto_id: root.dataset.contextoId || "",
        estacion: root.dataset.estacion || "",
      });
      fetch(root.dataset.endpoint, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfDe(root),
          "Content-Type": "application/x-www-form-urlencoded",
          "Accept": "application/json",
        },
        credentials: "same-origin",
        body: body.toString(),
      })
        .then((r) => r.ok ? r.json() : { ok: false, error: "Error " + r.status })
        .then((data) => {
          if (data && data.ok) {
            target.value = data.texto;
            target.dispatchEvent(new Event("input", { bubbles: true }));
            target.focus();
            setEstado("Listo — revísalo y guarda.");
          } else {
            setEstado((data && data.error) || "El Chalán no respondió.", true);
          }
        })
        .catch(() => setEstado("No se pudo contactar a El Chalán.", true))
        .finally(() => { btn.disabled = false; });
    };

    btn.addEventListener("click", pedir);
    instr.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); pedir(); }
    });
  }

  function montarTodos(raiz) {
    (raiz || document).querySelectorAll("[data-textarea-ia]").forEach(montar);
  }

  document.addEventListener("DOMContentLoaded", () => montarTodos());
  // HTMX: remontar lo que llegue por swap (modales, paneles inyectados).
  document.body && document.body.addEventListener("htmx:afterSwap", (e) => montarTodos(e.target));
  window.montarTextareaIA = montarTodos;
})();
