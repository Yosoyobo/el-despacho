// El Site — inicialización de ApexCharts. Vanilla JS, sin frameworks.
//
// Patrón:
// - Cada container con data-chart="<tipo>" carga su serie de
//   data-series='[...]' (JSON) y se transforma en un chart de Apex.
// - Re-init seguro tras swaps de HTMX (escuchamos htmx:afterSwap).
// - Instancias guardadas en un Map para destruir antes de re-crear.

(function () {
  if (typeof window === "undefined") return;

  const instancias = new Map(); // id -> ApexCharts

  function tema() {
    return document.documentElement.classList.contains("dark") ? "dark" : "light";
  }

  function colorPorEstado(estado) {
    if (estado === "ok") return "#12b76a";              // success-500
    if (estado === "error") return "#f04438";           // error-500
    if (estado === "no_configurada") return "#98a2b3";  // gray-400
    return "#d0d5dd";                                   // gray-300
  }

  function destruir(id) {
    const prev = instancias.get(id);
    if (prev) {
      try { prev.destroy(); } catch (e) {}
      instancias.delete(id);
    }
  }

  function leerSerie(el) {
    try { return JSON.parse(el.dataset.series || "[]"); } catch (e) { return []; }
  }

  function sparkArea(el) {
    const serie = leerSerie(el);
    const id = el.id;
    if (!id || !window.ApexCharts) return;
    destruir(id);
    const datos = serie.map((p) => p.latencia_ms || 0);
    const estado = serie.length ? serie[serie.length - 1].estado : "sin_datos";
    const color = colorPorEstado(estado);
    const opts = {
      chart: { type: "area", height: 40, sparkline: { enabled: true }, animations: { enabled: false } },
      stroke: { curve: "smooth", width: 2 },
      fill: { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0, stops: [0, 90] } },
      colors: [color],
      series: [{ name: "latencia", data: datos }],
      tooltip: {
        theme: tema(),
        x: { show: false },
        y: { formatter: (v) => v + " ms" },
        marker: { show: false },
      },
    };
    const c = new ApexCharts(el, opts);
    c.render();
    instancias.set(id, c);
  }

  function donaSalud(el) {
    const serie = leerSerie(el);
    const id = el.id;
    if (!id || !window.ApexCharts) return;
    destruir(id);
    const labels = serie.map((s) => s.label);
    const valores = serie.map((s) => s.valor);
    const colores = serie.map((s) => s.color);
    const dark = tema() === "dark";
    const opts = {
      chart: { type: "donut", height: 240, animations: { speed: 400 } },
      series: valores,
      labels,
      colors: colores,
      stroke: { width: 2, colors: [dark ? "#101828" : "#ffffff"] },
      plotOptions: {
        pie: {
          donut: {
            size: "72%",
            labels: {
              show: true,
              name: { fontSize: "12px", color: dark ? "#98a2b3" : "#667085" },
              value: {
                fontSize: "28px",
                fontWeight: 700,
                color: dark ? "#f9fafb" : "#101828",
                formatter: (v) => v,
              },
              total: {
                show: true,
                label: "Total",
                color: dark ? "#98a2b3" : "#667085",
                formatter: () => valores.reduce((a, b) => a + b, 0),
              },
            },
          },
        },
      },
      dataLabels: { enabled: false },
      legend: {
        position: "bottom",
        labels: { colors: dark ? "#d0d5dd" : "#344054" },
        markers: { width: 10, height: 10, radius: 5 },
      },
      tooltip: { theme: tema() },
    };
    const c = new ApexCharts(el, opts);
    c.render();
    instancias.set(id, c);
  }

  function areaLatencias(el) {
    const series = leerSerie(el);  // [{name, color, data: [{x, y}, ...]}]
    const id = el.id;
    if (!id || !window.ApexCharts) return;
    destruir(id);
    const dark = tema() === "dark";
    const opts = {
      chart: { type: "area", height: 280, toolbar: { show: false }, animations: { speed: 300 }, zoom: { enabled: false } },
      series,
      colors: series.map((s) => s.color || "#465fff"),
      stroke: { curve: "smooth", width: 2 },
      fill: { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: 0.25, opacityTo: 0, stops: [0, 90] } },
      dataLabels: { enabled: false },
      xaxis: {
        type: "datetime",
        labels: { style: { colors: dark ? "#98a2b3" : "#667085", fontSize: "11px" } },
        axisBorder: { show: false },
        axisTicks: { show: false },
      },
      yaxis: {
        labels: { style: { colors: dark ? "#98a2b3" : "#667085", fontSize: "11px" }, formatter: (v) => Math.round(v) + " ms" },
      },
      grid: { borderColor: dark ? "#1d2939" : "#f2f4f7", strokeDashArray: 4 },
      legend: {
        position: "top",
        horizontalAlign: "left",
        labels: { colors: dark ? "#d0d5dd" : "#344054" },
        markers: { width: 10, height: 10, radius: 5 },
      },
      tooltip: { theme: tema(), x: { format: "dd MMM HH:mm" } },
    };
    const c = new ApexCharts(el, opts);
    c.render();
    instancias.set(id, c);
  }

  function barrasChequeos(el) {
    const serie = leerSerie(el);  // [{ fecha, ok, error }]
    const id = el.id;
    if (!id || !window.ApexCharts) return;
    destruir(id);
    const dark = tema() === "dark";
    const cats = serie.map((d) => d.fecha);
    const opts = {
      chart: { type: "bar", height: 220, stacked: true, toolbar: { show: false }, animations: { speed: 300 } },
      series: [
        { name: "OK", data: serie.map((d) => d.ok) },
        { name: "Error", data: serie.map((d) => d.error) },
      ],
      colors: ["#12b76a", "#f04438"],
      plotOptions: { bar: { columnWidth: "48%", borderRadius: 4, borderRadiusApplication: "end" } },
      dataLabels: { enabled: false },
      xaxis: { categories: cats, labels: { style: { colors: dark ? "#98a2b3" : "#667085", fontSize: "11px" } }, axisBorder: { show: false }, axisTicks: { show: false } },
      yaxis: { labels: { style: { colors: dark ? "#98a2b3" : "#667085", fontSize: "11px" } } },
      grid: { borderColor: dark ? "#1d2939" : "#f2f4f7", strokeDashArray: 4 },
      legend: { position: "top", horizontalAlign: "left", labels: { colors: dark ? "#d0d5dd" : "#344054" } },
      tooltip: { theme: tema() },
    };
    const c = new ApexCharts(el, opts);
    c.render();
    instancias.set(id, c);
  }

  // ── Pintores genéricos (cualquier app del despacho) ──────────────────

  function donutGenerica(el) {
    const serie = leerSerie(el);  // [{label, valor, color}]
    const id = el.id;
    if (!id || !window.ApexCharts) return;
    destruir(id);
    const dark = tema() === "dark";
    const labels = serie.map((s) => s.label);
    const valores = serie.map((s) => s.valor);
    const colores = serie.map((s) => s.color);
    const altura = parseInt(el.dataset.altura || "260", 10);
    const total = valores.reduce((a, b) => a + b, 0);
    const opts = {
      chart: { type: "donut", height: altura, animations: { speed: 400 } },
      series: valores,
      labels,
      colors: colores,
      stroke: { width: 2, colors: [dark ? "#101828" : "#ffffff"] },
      plotOptions: {
        pie: {
          donut: {
            size: "70%",
            labels: {
              show: true,
              name: { fontSize: "12px", color: dark ? "#98a2b3" : "#667085" },
              value: {
                fontSize: "24px",
                fontWeight: 700,
                color: dark ? "#f9fafb" : "#101828",
              },
              total: {
                show: true,
                label: el.dataset.totalLabel || "Total",
                color: dark ? "#98a2b3" : "#667085",
                formatter: () => total,
              },
            },
          },
        },
      },
      dataLabels: { enabled: false },
      legend: {
        position: el.dataset.legend || "bottom",
        labels: { colors: dark ? "#d0d5dd" : "#344054" },
        markers: { width: 10, height: 10, radius: 5 },
      },
      tooltip: { theme: tema() },
    };
    const c = new ApexCharts(el, opts);
    c.render();
    instancias.set(id, c);
  }

  function areaCategoria(el) {
    // data-series='{"labels":[...],"series":[{name,data,color}]}'
    let raw;
    try { raw = JSON.parse(el.dataset.series || "{}"); } catch (e) { return; }
    const id = el.id;
    if (!id || !window.ApexCharts) return;
    destruir(id);
    const dark = tema() === "dark";
    const opts = {
      chart: { type: "area", height: parseInt(el.dataset.altura || "280", 10), toolbar: { show: false }, animations: { speed: 300 }, zoom: { enabled: false } },
      series: (raw.series || []).map((s) => ({ name: s.name, data: s.data || [] })),
      colors: (raw.series || []).map((s) => s.color || "#465fff"),
      stroke: { curve: "smooth", width: 2 },
      fill: { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: 0.3, opacityTo: 0, stops: [0, 90] } },
      dataLabels: { enabled: false },
      xaxis: {
        categories: raw.labels || [],
        labels: { style: { colors: dark ? "#98a2b3" : "#667085", fontSize: "11px" } },
        axisBorder: { show: false }, axisTicks: { show: false },
      },
      yaxis: {
        labels: {
          style: { colors: dark ? "#98a2b3" : "#667085", fontSize: "11px" },
          formatter: (v) => {
            const fmt = el.dataset.formato;
            if (fmt === "moneda") return "$" + Math.round(v).toLocaleString();
            return Math.round(v).toLocaleString();
          },
        },
      },
      grid: { borderColor: dark ? "#1d2939" : "#f2f4f7", strokeDashArray: 4 },
      legend: { position: "top", horizontalAlign: "left", labels: { colors: dark ? "#d0d5dd" : "#344054" }, markers: { width: 10, height: 10, radius: 5 } },
      tooltip: { theme: tema() },
    };
    const c = new ApexCharts(el, opts);
    c.render();
    instancias.set(id, c);
  }

  function barrasCategoria(el) {
    // data-series='{"labels":[...],"series":[{name,data,color}]}'
    let raw;
    try { raw = JSON.parse(el.dataset.series || "{}"); } catch (e) { return; }
    const id = el.id;
    if (!id || !window.ApexCharts) return;
    destruir(id);
    const dark = tema() === "dark";
    const horizontal = el.dataset.horizontal === "true";
    const opts = {
      chart: { type: "bar", height: parseInt(el.dataset.altura || "260", 10), stacked: el.dataset.stacked === "true", toolbar: { show: false }, animations: { speed: 300 } },
      series: (raw.series || []).map((s) => ({ name: s.name, data: s.data || [] })),
      colors: (raw.series || []).map((s, i) => s.color || ["#465fff", "#12b76a", "#f79009", "#f04438"][i % 4]),
      plotOptions: { bar: { horizontal, columnWidth: "48%", borderRadius: 4, borderRadiusApplication: "end" } },
      dataLabels: { enabled: false },
      xaxis: { categories: raw.labels || [], labels: { style: { colors: dark ? "#98a2b3" : "#667085", fontSize: "11px" } }, axisBorder: { show: false }, axisTicks: { show: false } },
      yaxis: { labels: { style: { colors: dark ? "#98a2b3" : "#667085", fontSize: "11px" } } },
      grid: { borderColor: dark ? "#1d2939" : "#f2f4f7", strokeDashArray: 4 },
      legend: { position: "top", horizontalAlign: "left", labels: { colors: dark ? "#d0d5dd" : "#344054" } },
      tooltip: { theme: tema() },
    };
    const c = new ApexCharts(el, opts);
    c.render();
    instancias.set(id, c);
  }

  function radialKpi(el) {
    // data-series='{"valor": 75, "label":"…", "color":"#12b76a"}'
    let raw;
    try { raw = JSON.parse(el.dataset.series || "{}"); } catch (e) { return; }
    const id = el.id;
    if (!id || !window.ApexCharts) return;
    destruir(id);
    const dark = tema() === "dark";
    const opts = {
      chart: { type: "radialBar", height: parseInt(el.dataset.altura || "180", 10), sparkline: { enabled: true } },
      series: [Math.max(0, Math.min(100, Number(raw.valor || 0)))],
      colors: [raw.color || "#465fff"],
      plotOptions: {
        radialBar: {
          hollow: { size: "62%" },
          track: { background: dark ? "#1d2939" : "#f2f4f7", strokeWidth: "100%" },
          dataLabels: {
            name: { offsetY: -8, color: dark ? "#98a2b3" : "#667085", fontSize: "11px" },
            value: { offsetY: 0, color: dark ? "#f9fafb" : "#101828", fontSize: "22px", fontWeight: 700, formatter: (v) => raw.formato === "moneda" ? "$" + Math.round(v) : Math.round(v) + "%" },
          },
        },
      },
      labels: [raw.label || ""],
    };
    const c = new ApexCharts(el, opts);
    c.render();
    instancias.set(id, c);
  }

  const PINTORES = {
    "spark-area": sparkArea,
    "dona-salud": donaSalud,
    "area-latencias": areaLatencias,
    "barras-chequeos": barrasChequeos,
    // Genéricos:
    "donut": donutGenerica,
    "area-cat": areaCategoria,
    "barras": barrasCategoria,
    "radial-kpi": radialKpi,
  };

  function pintar(raiz) {
    if (typeof ApexCharts === "undefined") return;
    const scope = raiz || document;
    const nodos = scope.querySelectorAll("[data-chart]");
    nodos.forEach((el) => {
      const fn = PINTORES[el.dataset.chart];
      if (fn) fn(el);
    });
  }

  function repintarTodo() {
    // En cambio de tema o swap masivo, destruir todo y volver a pintar.
    Array.from(instancias.keys()).forEach(destruir);
    pintar(document);
  }

  document.addEventListener("DOMContentLoaded", () => pintar(document));
  document.body && document.body.addEventListener("htmx:afterSwap", (e) => {
    if (e.target) pintar(e.target);
  });
  // Si el toggle de tema dispara un evento, repintamos.
  window.addEventListener("despacho:tema", repintarTodo);

  // Limpieza al salir.
  window.addEventListener("beforeunload", () => {
    Array.from(instancias.keys()).forEach(destruir);
  });
})();
