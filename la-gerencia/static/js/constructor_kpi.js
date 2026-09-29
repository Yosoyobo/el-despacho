/* El constructor de KPIs de La Gerencia (S-KPIs-V2 · 2, 2026-09-29).
 *
 * Arma el formulario desde el esquema del DSL v2 (`kpi_dsl.esquema_para_ui`,
 * inyectado con json_script): agregar un campo al motor lo agrega aquí sin
 * tocar este archivo. El estado vive en un objeto `def` con la forma exacta
 * de la definición; en cada cambio se escribe en el <textarea> oculto y se
 * pide la vista previa (con un respiro para no disparar una por tecla).
 * Vanilla JS: sin librerías (§4 #17). Todo texto que viene de la base se pone
 * con textContent / new Option, nunca como HTML.
 */
(function () {
  "use strict";

  const raiz = document.getElementById("constructor-kpi");
  if (!raiz) return;
  const esquema = JSON.parse(document.getElementById("esquema-kpi").textContent);
  const inicial = JSON.parse(document.getElementById("definicion-kpi").textContent || "null");
  const salida = document.getElementById("definicion_json");
  const preview = document.getElementById("constructor-preview");
  const urlPreview = raiz.dataset.preview;
  const urlChalan = raiz.dataset.chalan;
  const csrf = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";

  const porClave = (lista) => Object.fromEntries(lista.map((x) => [x.clave, x]));
  const entidades = porClave(esquema.entidades);
  const etiquetaOp = Object.fromEntries(esquema.ops.map((o) => [o.clave, o.etiqueta]));
  const etiquetaOpFecha = Object.fromEntries(esquema.ops_fecha.map((o) => [o.clave, o.etiqueta]));

  let def = normalizar(inicial);

  // ── Utilidades de DOM ─────────────────────────────────────────────────
  function el(tag, attrs, ...hijos) {
    const n = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v !== undefined && v !== null && v !== false) n.setAttribute(k, v === true ? "" : v);
    });
    hijos.flat().forEach((h) => h && n.appendChild(typeof h === "string" ? document.createTextNode(h) : h));
    return n;
  }
  const CLASE_CAMPO = "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100";
  function select(opciones, valor, onchange, extra) {
    const s = el("select", Object.assign({ class: CLASE_CAMPO }, extra || {}));
    opciones.forEach(([v, t]) => { const o = new Option(t, v); if (String(v) === String(valor)) o.selected = true; s.add(o); });
    s.addEventListener("change", () => onchange(s.value));
    return s;
  }
  function etiqueta(texto, control, ayuda) {
    return el("label", { class: "block text-sm" },
      el("span", { class: "mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300", text: texto }),
      control,
      ayuda ? el("span", { class: "mt-1 block text-[11px] text-gray-400 dark:text-gray-500", text: ayuda }) : null);
  }
  function seccion(titulo, ...hijos) {
    return el("section", { class: "rounded-xl border border-gray-200 p-4 dark:border-gray-800" },
      el("h3", { class: "mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400", text: titulo }),
      ...hijos);
  }

  // ── El estado ─────────────────────────────────────────────────────────
  function normalizar(d) {
    const base = {
      entidad: esquema.entidades.length ? esquema.entidades[0].clave : "",
      tipo: "valor", agregacion: "count", campo: "", duracion: "",
      filtros: [], filtros_numerador: [], ventana_tiempo: "este_mes", campo_fecha: "",
      alcance_usuario: "todos", agrupar_por: "", top: esquema.top_default,
      comparar: false, formato: "", direccion: "",
    };
    if (!d || !entidades[d.entidad]) return base;
    return Object.assign(base, d, {
      filtros: (d.filtros || []).map((f) => Object.assign({}, f)),
      filtros_numerador: (d.filtros_numerador || []).map((f) => Object.assign({}, f)),
      campo: d.campo || "", duracion: d.duracion || "", campo_fecha: d.campo_fecha || "",
      agrupar_por: d.agrupar_por || "", formato: d.formato || "", direccion: d.direccion || "",
    });
  }
  function ent() { return entidades[def.entidad]; }
  function campo(clave) { return (ent().campos || []).find((c) => c.clave === clave); }

  function definicionFinal() {
    const d = { entidad: def.entidad, ventana_tiempo: def.ventana_tiempo,
      alcance_usuario: ent().solo_mio ? "mio" : def.alcance_usuario, filtros: limpiar(def.filtros) };
    if (def.tipo === "porcentaje") {
      d.tipo = "porcentaje";
      d.filtros_numerador = limpiar(def.filtros_numerador);
    }
    d.agregacion = def.agregacion;
    if (def.agregacion !== "count") {
      if (def.duracion) d.duracion = def.duracion; else if (def.campo) d.campo = def.campo;
    }
    if (def.campo_fecha && def.campo_fecha !== ent().campo_fecha) d.campo_fecha = def.campo_fecha;
    if (def.agrupar_por) { d.agrupar_por = def.agrupar_por; d.top = Number(def.top) || esquema.top_default; }
    if (def.comparar && def.ventana_tiempo !== "siempre") d.comparar = true;
    if (def.formato) d.formato = def.formato;
    if (def.direccion) d.direccion = def.direccion;
    return d;
  }
  function limpiar(filtros) {
    return filtros.filter((f) => f.campo && f.op && (f.campo_ref || f.valor !== "" && f.valor !== undefined && f.valor !== null
      && !(Array.isArray(f.valor) && !f.valor.length)))
      .map((f) => {
        const c = campo(f.campo) || {};
        const x = { campo: f.campo, op: f.op };
        if (f.campo_ref) { x.campo_ref = f.campo_ref; return x; }
        let v = f.valor;
        if (f.op === "vacio" || c.tipo === "booleano") v = (v === true || v === "true");
        else if ((c.tipo === "numero" || c.tipo === "dinero") && !Array.isArray(v)) v = Number(v);
        x.valor = v;
        return x;
      });
  }

  // ── Los renglones de filtro ───────────────────────────────────────────
  function valorFecha(f, onChange) {
    // hoy · hace N días · en N días · una fecha · otra fecha del registro
    let modo = "fecha", n = 7;
    const v = f.valor || "";
    if (f.campo_ref) modo = "ref";
    else if (v === "hoy") modo = "hoy";
    else if (/^hace_\d+_dias$/.test(v)) { modo = "hace"; n = Number(v.split("_")[1]); }
    else if (/^en_\d+_dias$/.test(v)) { modo = "en"; n = Number(v.split("_")[1]); }
    const caja = el("div", { class: "grid grid-cols-2 gap-2" });
    const otros = (ent().campos_fecha || []).filter((c) => c !== f.campo);
    const aplicar = (m, extra) => {
      delete f.campo_ref;
      if (m === "hoy") f.valor = "hoy";
      else if (m === "hace") f.valor = `hace_${extra || n}_dias`;
      else if (m === "en") f.valor = `en_${extra || n}_dias`;
      else if (m === "ref") { f.valor = ""; f.campo_ref = extra || otros[0] || ""; }
      else f.valor = extra || "";
      onChange();
    };
    const modos = [["hoy", "hoy"], ["hace", "hace N días"], ["en", "dentro de N días"], ["fecha", "una fecha"]];
    if (otros.length) modos.push(["ref", "otra fecha del mismo registro"]);
    caja.appendChild(select(modos, modo, (m) => aplicar(m)));
    if (modo === "hace" || modo === "en") {
      const num = el("input", { type: "number", min: "1", max: "3660", value: n, class: CLASE_CAMPO });
      num.addEventListener("change", () => aplicar(modo, num.value));
      caja.appendChild(num);
    } else if (modo === "fecha") {
      const d = el("input", { type: "date", value: /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : "", class: CLASE_CAMPO });
      d.addEventListener("change", () => aplicar("fecha", d.value));
      caja.appendChild(d);
    } else if (modo === "ref") {
      caja.appendChild(select(otros.map((c) => [c, campo(c).etiqueta]), f.campo_ref, (c) => aplicar("ref", c)));
    }
    return caja;
  }

  function valorControl(f, onChange) {
    const c = campo(f.campo);
    if (!c) return el("span");
    if (f.op === "vacio") {
      return select([["true", "sí (está vacío)"], ["false", "no (tiene valor)"]], String(f.valor !== false && f.valor !== "false"),
        (v) => { f.valor = v === "true"; onChange(); });
    }
    if (c.tipo === "booleano") {
      return select([["true", "sí"], ["false", "no"]], String(f.valor === true || f.valor === "true"),
        (v) => { f.valor = v === "true"; onChange(); });
    }
    if (c.tipo === "fecha") return valorFecha(f, onChange);
    if (c.opciones && c.opciones.length) {
      if (f.op === "in") {
        const elegidos = new Set(Array.isArray(f.valor) ? f.valor.map(String) : []);
        const s = el("select", { class: CLASE_CAMPO, multiple: true, size: Math.min(5, c.opciones.length) });
        c.opciones.forEach((o) => { const op = new Option(o.etiqueta, o.valor); op.selected = elegidos.has(String(o.valor)); s.add(op); });
        s.addEventListener("change", () => { f.valor = Array.from(s.selectedOptions).map((o) => o.value); onChange(); });
        return s;
      }
      return select([["", "Elige…"], ...c.opciones.map((o) => [o.valor, o.etiqueta])], f.valor ?? "",
        (v) => { f.valor = v; onChange(); });
    }
    const tipoInput = (c.tipo === "numero" || c.tipo === "dinero") ? "number" : "text";
    const i = el("input", { type: tipoInput, step: "any", value: Array.isArray(f.valor) ? f.valor.join(", ") : (f.valor ?? ""),
      class: CLASE_CAMPO, placeholder: f.op === "in" ? "separa con comas" : "" });
    i.addEventListener("change", () => {
      f.valor = f.op === "in" ? i.value.split(",").map((x) => x.trim()).filter(Boolean) : i.value;
      onChange();
    });
    return i;
  }

  function renglonFiltro(lista, idx) {
    const f = lista[idx];
    const campos = ent().campos || [];
    const c = campo(f.campo);
    const fila = el("div", { class: "grid grid-cols-1 gap-2 rounded-lg bg-gray-50 p-2 dark:bg-gray-800/40 md:grid-cols-[1fr_1fr_1.4fr_auto] md:items-start" });
    fila.appendChild(select([["", "Campo…"], ...campos.map((x) => [x.clave, x.etiqueta])], f.campo,
      (v) => { f.campo = v; const nc = campo(v); f.op = nc ? nc.ops[0] : ""; f.valor = ""; delete f.campo_ref; pintar(); }));
    const ops = c ? c.ops : [];
    const etiquetas = c && c.tipo === "fecha" ? etiquetaOpFecha : etiquetaOp;
    fila.appendChild(select(ops.map((o) => [o, etiquetas[o] || etiquetaOp[o] || o]), f.op,
      (v) => { f.op = v; if (v === "vacio") f.valor = true; else if (v === "in") f.valor = []; else f.valor = ""; delete f.campo_ref; pintar(); }));
    fila.appendChild(valorControl(f, () => { pintar(); }));
    fila.appendChild(el("button", { type: "button", class: "btn-secundario px-2 py-1 text-xs text-error-600", "aria-label": "Quitar filtro",
      onclick: () => { lista.splice(idx, 1); pintar(); } }, "✕"));
    return fila;
  }
  function listaFiltros(lista, vacio) {
    const caja = el("div", { class: "space-y-2" });
    if (!lista.length) caja.appendChild(el("p", { class: "text-xs text-gray-400", text: vacio }));
    lista.forEach((_, i) => caja.appendChild(renglonFiltro(lista, i)));
    caja.appendChild(el("button", { type: "button", class: "btn-secundario text-xs",
      onclick: () => { lista.push({ campo: "", op: "", valor: "" }); pintar(); } }, "+ Agregar condición"));
    return caja;
  }

  // ── El formulario completo ────────────────────────────────────────────
  function pintar() {
    const e = ent();
    raiz.replaceChildren();
    if (!e) { raiz.appendChild(el("p", { class: "text-sm text-gray-500", text: "No tienes permiso sobre ningún dato para armar un KPI." })); return; }

    // 1. Qué
    raiz.appendChild(seccion("1 · ¿De qué?",
      etiqueta("Se cuenta o se suma sobre", select(esquema.entidades.map((x) => [x.clave, x.etiqueta + (x.solo_mio ? " (sólo lo tuyo)" : "")]), def.entidad,
        (v) => { def = normalizar({ entidad: v, ventana_tiempo: def.ventana_tiempo }); pintar(); }))));

    // 2. Cómo
    const agregables = (e.campos || []).filter((c) => c.agregaciones.length);
    const opcionesDe = [...agregables.map((c) => ["campo:" + c.clave, c.etiqueta]),
      ...(e.duraciones || []).map((d) => ["duracion:" + d.clave, d.etiqueta + " (" + d.unidad + ")"])];
    const aggs = esquema.agregaciones.filter((a) => a.clave === "count" || opcionesDe.length);
    const como = [etiqueta("Resultado", select(esquema.tipos.map((t) => [t.clave, t.etiqueta]), def.tipo, (v) => { def.tipo = v; pintar(); })),
      etiqueta("Cálculo", select(aggs.map((a) => [a.clave, a.etiqueta]), def.agregacion, (v) => {
        def.agregacion = v;
        if (v !== "count" && !def.campo && !def.duracion && opcionesDe.length) {
          const [k, c] = opcionesDe[0][0].split(":"); if (k === "campo") def.campo = c; else def.duracion = c;
        }
        pintar();
      }))];
    if (def.agregacion !== "count") {
      const actual = def.duracion ? "duracion:" + def.duracion : "campo:" + def.campo;
      como.push(etiqueta("De", select(opcionesDe, actual, (v) => {
        const [k, c] = v.split(":"); def.campo = k === "campo" ? c : ""; def.duracion = k === "duracion" ? c : ""; pintar();
      })));
    }
    raiz.appendChild(seccion("2 · ¿Cómo se calcula?", el("div", { class: "grid grid-cols-1 gap-3 md:grid-cols-3" }, ...como),
      def.tipo === "porcentaje" ? el("p", { class: "mt-2 text-[11px] text-gray-500",
        text: "Un porcentaje compara una parte contra el total: el total son los que cumplen las condiciones de abajo; la parte, los que además cumplen las del paso 4." }) : null));

    // 3. Condiciones
    raiz.appendChild(seccion("3 · ¿Cuáles cuentan?", listaFiltros(def.filtros, "Sin condiciones: cuentan todos.")));

    // 4. La parte (porcentaje)
    if (def.tipo === "porcentaje") {
      raiz.appendChild(seccion("4 · ¿Qué parte del total es la que mides?",
        listaFiltros(def.filtros_numerador, "Agrega al menos una condición: p. ej. «Completada es hasta Fecha compromiso» para «a tiempo».")));
    }

    // 5. Periodo
    const periodo = [etiqueta("Periodo", select(esquema.ventanas.map((v) => [v.clave, v.etiqueta]), def.ventana_tiempo,
      (v) => { def.ventana_tiempo = v; if (v === "siempre") def.comparar = false; pintar(); }))];
    if ((e.campos_fecha || []).length > 1 && def.ventana_tiempo !== "siempre") {
      periodo.push(etiqueta("Según la fecha de", select([["", campo(e.campo_fecha) ? campo(e.campo_fecha).etiqueta + " (normal)" : "la normal"],
        ...e.campos_fecha.filter((c) => c !== e.campo_fecha).map((c) => [c, campo(c).etiqueta])], def.campo_fecha, (v) => { def.campo_fecha = v; pintar(); })));
    }
    const comp = el("input", { type: "checkbox", class: "rounded", checked: def.comparar, disabled: def.ventana_tiempo === "siempre" });
    comp.addEventListener("change", () => { def.comparar = comp.checked; pintar(); });
    periodo.push(el("label", { class: "flex items-center gap-2 self-end pb-2 text-sm text-gray-700 dark:text-gray-200" }, comp, "Comparar con el periodo anterior"));
    raiz.appendChild(seccion("5 · ¿De cuándo?", el("div", { class: "grid grid-cols-1 gap-3 md:grid-cols-3" }, ...periodo)));

    // 6. Agrupar y alcance
    const grupo = [etiqueta("Repartir por", select([["", "No repartir"], ...(e.agrupaciones || []).map((g) => [g.clave, g.etiqueta])], def.agrupar_por,
      (v) => { def.agrupar_por = v; pintar(); }), "Repartir por persona o por cliente permite ponerle meta a cada quien.")];
    if (def.agrupar_por) {
      const top = el("input", { type: "number", min: "1", max: esquema.top_max, value: def.top, class: CLASE_CAMPO });
      top.addEventListener("change", () => { def.top = top.value; pintar(); });
      grupo.push(etiqueta("Cuántos mostrar", top));
    }
    if (e.soporta_mio && !e.solo_mio) {
      grupo.push(etiqueta("De quién", select(esquema.alcances.map((a) => [a.clave, a.etiqueta]), def.alcance_usuario,
        (v) => { def.alcance_usuario = v; pintar(); }), "«Sólo lo mío»: cada quien ve el número de lo suyo."));
    }
    raiz.appendChild(seccion("6 · Reparto", el("div", { class: "grid grid-cols-1 gap-3 md:grid-cols-3" }, ...grupo)));

    // 7. Cómo se lee
    raiz.appendChild(seccion("7 · ¿Cómo se lee?", el("div", { class: "grid grid-cols-1 gap-3 md:grid-cols-2" },
      etiqueta("Formato", select([["", "Automático"], ...esquema.formatos.map((f) => [f.clave, f.etiqueta])], def.formato, (v) => { def.formato = v; pintar(); })),
      etiqueta("Hacia dónde es mejor", select([["", "Sólo informa (automático)"], ...esquema.direcciones.map((d) => [d.clave, d.etiqueta])], def.direccion,
        (v) => { def.direccion = v; pintar(); }), "Con «menos es mejor» sus metas son un tope y sus umbrales, techos."))));

    salida.value = JSON.stringify(definicionFinal());
    pedirPreview();
  }

  // ── Vista previa ──────────────────────────────────────────────────────
  let espera = null, ultima = "";
  function pedirPreview() {
    clearTimeout(espera);
    espera = setTimeout(function () {
      if (salida.value === ultima) return;
      ultima = salida.value;
      const cuerpo = new URLSearchParams({ definicion_json: salida.value, csrfmiddlewaretoken: csrf });
      fetch(urlPreview, { method: "POST", body: cuerpo, headers: { "X-CSRFToken": csrf, "HX-Request": "true" } })
        .then((r) => r.text()).then((html) => { preview.innerHTML = html; })
        .catch(() => { preview.textContent = "No se pudo calcular la vista previa."; });
    }, 350);
  }

  // ── Pedírselo a El Chalán ─────────────────────────────────────────────
  const btnChalan = document.getElementById("chalan-llenar");
  if (btnChalan) {
    btnChalan.addEventListener("click", function () {
      const texto = document.getElementById("chalan-texto").value.trim();
      const aviso = document.getElementById("chalan-aviso");
      if (!texto) { aviso.textContent = "Escribe qué quieres medir."; return; }
      btnChalan.disabled = true; aviso.textContent = "El Chalán lo está armando…";
      fetch(urlChalan, { method: "POST", body: new URLSearchParams({ texto: texto, csrfmiddlewaretoken: csrf }),
        headers: { "X-CSRFToken": csrf } })
        .then((r) => r.json()).then(function (r) {
          if (!r.ok) { aviso.textContent = r.error || "El Chalán no pudo."; return; }
          def = normalizar(r.definicion);
          const titulo = document.getElementById("kpi-titulo");
          if (titulo && !titulo.value && r.titulo) titulo.value = r.titulo;
          aviso.textContent = "Listo: revisa el formulario y la vista previa antes de guardar.";
          pintar();
        })
        .catch(() => { aviso.textContent = "El Chalán no respondió."; })
        .finally(() => { btnChalan.disabled = false; });
    });
  }

  pintar();
})();
