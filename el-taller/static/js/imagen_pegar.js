/**
 * Recuadros de imagen: pegar (Ctrl/Cmd+V) o elegir archivo → Drive.
 *
 * LC 2026-07-26 (Oscar): «el input de las imágenes de productos lo vamos a
 * habilitar subir (o pegar, después de picar en un recuadro para definir el
 * destino)». De ahí el flujo: se pica el recuadro para ELEGIR EL DESTINO y
 * luego se pega. Con un solo recuadro en la página no hace falta picar.
 *
 * Se usa en tres lugares: la ficha del producto (catálogo), las tarjetas de
 * «Productos involucrados» del proyecto y el historial de usos. Cada recuadro
 * dice a qué endpoint sube con `data-url`; el servidor decide si la foto queda
 * en el uso o en el producto del catálogo (ver ProyectoProducto.imagen_destino).
 *
 * LC 2026-07-26 (Oscar): con el recuadro seleccionado, la tecla **Delete** (o
 * Backspace) DESLIGA la foto — antes, una imagen equivocada se quedaba ligada
 * para siempre. El archivo NO se borra de Drive: el mismo file_id puede estar
 * congelado en una cotización ya enviada. Si la foto que se ve es la heredada
 * del catálogo (`data-img-compartida`), se pide confirmación porque afecta a
 * todos los proyectos que usan ese producto.
 *
 * En la página del PRODUCTO el borrado es DIFERIDO (`data-img-diferido`): no se
 * postea nada, se apunta en un campo oculto y se aplica al «Guardar producto».
 * Si el usuario se sale sin guardar, la foto sigue ahí (Oscar 2026-07-26).
 *
 * Contrato del recuadro:
 *
 *   <div data-img-slot data-url="/…/imagen" [data-img-compartida]
 *        [data-img-diferido data-img-quitar-campo="#id-del-hidden"]>
 *     <img data-img-preview>            (opcional)
 *     <p  data-img-hint>…</p>           (opcional)
 *     <input type="file" data-img-file>  (opcional)
 *     <button data-img-elegir>…</button> (opcional)
 *     <p  data-img-estado></p>          (opcional)
 *   </div>
 *
 * Se re-escanea en `htmx:afterSwap` para que funcione dentro de modales y de
 * fragmentos inyectados (gotcha del repo: los <script> inline inyectados por
 * HTMX corren con `document.currentScript === null`).
 */
(function () {
  "use strict";

  var MAX_BYTES = 25 * 1024 * 1024;
  var CLASES_ACTIVO = ["ring-2", "ring-brand-400"];

  function csrf() {
    var inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (inp) return inp.value;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function slots() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-img-slot]"));
  }

  function activo() {
    return document.querySelector("[data-img-slot][data-img-activo]");
  }

  function activar(slot) {
    slots().forEach(function (s) {
      if (s === slot) return;
      delete s.dataset.imgActivo;
      s.classList.remove.apply(s.classList, CLASES_ACTIVO);
    });
    slot.dataset.imgActivo = "1";
    slot.classList.add.apply(slot.classList, CLASES_ACTIVO);
  }

  // El aviso puede vivir DENTRO del recuadro o fuera (recuadros chicos, como la
  // tarjeta de producto del proyecto: 64px no dan para un párrafo). Fuera se
  // referencia con `data-img-estado-sel`, y puede fijar sus propias clases de
  // base con `data-clase-base`.
  function estado(slot, texto, esError) {
    var sel = slot.getAttribute("data-img-estado-sel");
    var el = (sel && document.querySelector(sel)) || slot.querySelector("[data-img-estado]");
    if (!el) return;
    el.textContent = texto || "";
    el.className = (el.getAttribute("data-clase-base") || "mt-1 text-xs") + " " + (esError
      ? "text-error-600 dark:text-error-400"
      : "text-success-600 dark:text-success-400");
  }

  function pintar(slot, src) {
    var img = slot.querySelector("[data-img-preview]");
    if (!img) return;
    img.src = src;
    img.classList.remove("hidden");
    var hint = slot.querySelector("[data-img-hint]");
    if (hint) hint.classList.add("hidden");
  }

  function despintar(slot) {
    var img = slot.querySelector("[data-img-preview]");
    if (img) { img.removeAttribute("src"); img.classList.add("hidden"); }
    var hint = slot.querySelector("[data-img-hint]");
    if (hint) hint.classList.remove("hidden");
  }

  function tieneImagen(slot) {
    var img = slot.querySelector("[data-img-preview]");
    return !!(img && !img.classList.contains("hidden"));
  }

  // Avisa al guard de "cambios sin guardar" de ui.js (si la página lo usa).
  function marcarSucio(el) {
    var form = el.closest && el.closest("form");
    if (form) form.dataset.cambiosSinGuardar = "1";
  }

  function campoQuitar(slot) {
    var sel = slot.getAttribute("data-img-quitar-campo");
    return sel ? document.querySelector(sel) : null;
  }

  // Quitar (tecla Delete): desliga la foto. El archivo se queda en Drive a
  // propósito — puede estar congelado en una cotización ya enviada.
  function quitar(slot) {
    var url = slot.getAttribute("data-url");
    if (!url || !tieneImagen(slot)) return;
    // Si la que se ve es la del CATÁLOGO (heredada), quitarla afecta a todos los
    // proyectos que usan ese producto: eso sí se pregunta.
    if (slot.hasAttribute("data-img-compartida")
        && !window.confirm("Esta foto es la del producto del catálogo y la usan todos sus proyectos.\n\n¿Quitarla de todos modos?")) {
      return;
    }
    // Modo DIFERIDO (página del producto, Oscar 2026-07-26): no se postea nada.
    // Se apunta el cambio en un campo oculto del formulario y se aplica cuando
    // el usuario aprieta «Guardar producto». Si se sale sin guardar, la foto
    // sigue ahí.
    if (slot.hasAttribute("data-img-diferido")) {
      var campo = campoQuitar(slot);
      if (campo) campo.value = "1";
      despintar(slot);
      slot.dataset.imgPendiente = "1";
      estado(slot, "Se quitará al guardar el producto.");
      marcarSucio(slot);
      return;
    }
    estado(slot, "Quitando…");
    var body = new FormData();
    body.append("quitar", "1");
    fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf() }, body: body })
      .then(function (r) {
        if (r.status === 403) return { ok: false, error: "Sin permiso para cambiar esta imagen." };
        return r.json().catch(function () {
          return { ok: false, error: "El servidor no aceptó la operación." };
        });
      })
      .then(function (data) {
        if (data && data.ok) {
          despintar(slot);
          slot.removeAttribute("data-img-compartida");
          estado(slot, data.mensaje || "✓ Foto quitada.");
        } else {
          estado(slot, (data && data.error) || "No se pudo quitar la imagen.", true);
        }
      })
      .catch(function () { estado(slot, "Error de red al quitar la imagen.", true); });
  }

  function subir(slot, blob) {
    if (!blob) return;
    var url = slot.getAttribute("data-url");
    if (!url) return;
    if (blob.size > MAX_BYTES) {
      estado(slot, "La imagen supera 25 MB.", true);
      return;
    }
    // Una foto nueva cancela el borrado pendiente del modo diferido.
    var campo = campoQuitar(slot);
    if (campo) campo.value = "";
    delete slot.dataset.imgPendiente;
    // Preview optimista con el blob local: se ve al instante, aunque Drive tarde.
    try { pintar(slot, URL.createObjectURL(blob)); } catch (e) { /* sin preview */ }
    estado(slot, "Subiendo…");
    var body = new FormData();
    body.append("imagen", blob, blob.name || ("captura-" + Date.now() + ".png"));
    fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf() }, body: body })
      .then(function (r) {
        if (r.status === 403) return { ok: false, error: "Sin permiso para cambiar esta imagen." };
        return r.json().catch(function () {
          return { ok: false, error: "El servidor no aceptó la imagen." };
        });
      })
      .then(function (data) {
        if (data && data.ok) {
          estado(slot, data.mensaje || "✓ Imagen guardada.");
          if (data.url) pintar(slot, data.url);
          if (data.destino) slot.dataset.imgDestino = data.destino;
        } else {
          estado(slot, (data && data.error) || "No se pudo subir la imagen.", true);
        }
      })
      .catch(function () { estado(slot, "Error de red al subir la imagen.", true); });
  }

  function montar(slot) {
    if (slot.dataset.imgMontado) return;
    slot.dataset.imgMontado = "1";
    if (!slot.hasAttribute("tabindex")) slot.setAttribute("tabindex", "0");

    slot.addEventListener("click", function () { activar(slot); });
    slot.addEventListener("focus", function () { activar(slot); });

    var file = slot.querySelector("[data-img-file]");
    var elegir = slot.querySelector("[data-img-elegir]");
    if (elegir && file) {
      elegir.addEventListener("click", function (ev) {
        ev.preventDefault();
        activar(slot);
        file.click();
      });
    }
    if (file) {
      file.addEventListener("change", function () {
        if (file.files && file.files[0]) subir(slot, file.files[0]);
      });
      // Los recuadros chicos (tarjeta del proyecto, historial de usos) no traen
      // botón: un clic los elige como destino para pegar, y doble clic abre el
      // selector de archivos.
      slot.addEventListener("dblclick", function () {
        activar(slot);
        file.click();
      });
    }
  }

  function escanear() { slots().forEach(montar); }

  // Pegar: va al recuadro activo. Con uno solo en la página, a ése.
  document.addEventListener("paste", function (ev) {
    var lista = slots();
    if (!lista.length) return;
    var destino = activo() || (lista.length === 1 ? lista[0] : null);
    if (!destino) return;
    var items = (ev.clipboardData && ev.clipboardData.items) || [];
    for (var i = 0; i < items.length; i++) {
      if (items[i].type && items[i].type.indexOf("image") === 0) {
        var blob = items[i].getAsFile();
        if (blob) {
          ev.preventDefault();
          activar(destino);
          subir(destino, blob);
          try { destino.scrollIntoView({ block: "center" }); } catch (e) { /* ignora */ }
        }
        return;
      }
    }
  });

  // Delete/Backspace sobre el recuadro = quitar la foto (LC 2026-07-26, Oscar).
  // El listener es global pero solo actúa si el evento viene DEL recuadro (que
  // es focusable por su `tabindex`): así escribir Backspace en cualquier campo
  // del formulario jamás borra una imagen.
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Delete" && ev.key !== "Backspace") return;
    var slot = ev.target && ev.target.closest && ev.target.closest("[data-img-slot]");
    if (!slot) return;
    var tag = (ev.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    ev.preventDefault();  // Backspace: evita el "atrás" del navegador.
    quitar(slot);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", escanear);
  } else {
    escanear();
  }
  document.body.addEventListener("htmx:afterSwap", escanear);
})();
