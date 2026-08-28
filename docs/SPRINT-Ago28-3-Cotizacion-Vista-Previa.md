# Sprint 3 — Vista previa de la cotización antes de generar la versión

> Tercero de los tres sprints de las notas de Oscar del 2026-08-28. El más
> delicado de los tres, y por eso va solo: toca cómo nacen las versiones de una
> cotización, que es de lo poco que el sistema **congela** para siempre.
>
> **Sin migraciones.**

---

## Lo que pidió Oscar

> «En el recuadro de cotizaciones agregar uno de vista previa antes de generar la
> v siguiente. En la pantalla de la vista previa poner un botón de generar y otro
> de enviar.»

**Decisión ya tomada** (AskUserQuestion del 28-ago): el botón **«Enviar» de esa
pantalla genera la versión Y abre el envío por correo**, en un solo paso. Se
descartó la variante de obligar a generar primero. «Generar» sólo congela.

---

## El problema de fondo, que es lo que hace interesante este sprint

Hoy, «Generar vN» hace dos cosas a la vez: **congela** la versión y la **crea**.
No hay forma de ver cómo va a quedar sin crearla — y una versión de más no es
gratis: cambia el número que ve el cliente, reinicia el semáforo de estatus al
primer paso, y se lleva una **foto de los productos** del proyecto
(`ProyectoProductoVersion`) que después alimenta las pestañas v1/v2/… del
recuadro «Productos involucrados».

Así que la vista previa tiene que enseñar **exactamente** el documento que se va
a generar. Una imitación —armar un HTML parecido con los datos del proyecto—
sería peor que no tenerla: se vería bien y mentiría en los detalles que importan
(el redondeo de los impuestos, qué líneas se agrupan, qué foto sale, cómo cae la
paginación).

### Por qué no se puede «sólo renderizar sin guardar»

[`services.construir_html_pdf(cot)`](../el-taller/apps/cotizaciones/services.py)
parte de `cot.items.select_related(...)`: necesita una cotización **con pk** y sus
líneas en la base. Y `calcular_totales()` también recorre `self.items`. Fabricar
objetos en memoria obligaría a duplicar el armador de líneas, que es justo lo que
haría que el preview y la realidad se separen con el tiempo.

### La forma que sí funciona: generar de verdad, y deshacer

```python
with transaction.atomic():
    cot = services.generar_desde_proyecto(proyecto, request.user, notificar=False)
    html = services.construir_html_pdf(cot, preview=True, acciones=...)
    transaction.set_rollback(True)
return HttpResponse(html)
```

Lo que ves es lo que se va a generar, **porque es lo que se generó** — sólo que
se deshace al terminar. Detalles que hacen que esto sea seguro aquí, y que hay
que comprobar en vez de suponer:

- **El número de versión no se consume**: se calcula dentro de la transacción
  (`ultima_cot.version + 1`) y el rollback lo revierte. Hay que probarlo:
  después de tres previews seguidos, la siguiente versión real sigue siendo la
  misma.
- **La foto de los productos tampoco queda**: `services_version.fotografiar` corre
  **dentro** del `atomic` de `generar_desde_proyecto`, así que se revierte con
  todo lo demás.
- **El evento SÍ hay que apagarlo.** `_emitir("cotizacion.generada", …)` corre
  **fuera** del `atomic` y encola en Redis, que no es transaccional: con rollback
  se anunciaría una cotización que no existe. De ahí el parámetro
  `notificar: bool = True` — el único refactor de este sprint sobre código
  existente, y es de una línea.
- **No hay red dentro de la transacción.** `construir_html_pdf` lee las fotos del
  almacén en disco (desde S-Medios-V1 ya no baja nada de Drive), así que la
  transacción es corta. Si algún día vuelve a tocar Drive, esto hay que
  revisarlo: una transacción abierta esperando a un servicio ajeno es una mala
  idea.

---

## La pantalla

Ya existe la mitad: [`pdf_ver`](../el-taller/apps/cotizaciones/views.py) (ruta
`cotizaciones:ver`) muestra el documento **como hoja, sobre fondo gris, con una
barra arriba** — es exactamente el envoltorio que se necesita
(`construir_html_pdf(cot, preview=True)`, y el `{% if preview %}` de
[`pdf.html`](../el-taller/templates/cotizaciones/pdf.html)).

Lo que falta es que esa barra pueda llevar **otras acciones**. Hoy trae «Bajar
PDF» e «Imprimir»; en la vista previa tiene que traer:

- **Generar vN** → POST a `proyectos-generar-cotizacion` (ya existe, ya devuelve
  el recuadro repintado y el modal de «¿pasar a Esperando respuesta?»).
- **Generar y enviar** → genera y abre el modal de envío (`cotizaciones:enviar`,
  que ya manda el correo con el PDF adjunto).

Parametrizar la barra, no bifurcar la plantilla: si se hace una copia de
`pdf.html` para el preview, en tres meses el documento y su vista previa no se
van a parecer. Basta con pasar las acciones por contexto y dejar las de siempre
como default para que `pdf_ver` no cambie en nada.

### El botón que lo abre

En [`_cotizaciones_panel.html`](../el-taller/templates/proyectos/_cotizaciones_panel.html),
junto a «Generar v{{ cot_next_version }}» y «Enviar por correo».

---

## Permisos

La vista previa es la antesala de generar, así que pide **`puede_crear_cotizaciones`**
—no el de ver—: quien no puede generar no tiene por qué ensayarlo. Y como toda
vista del módulo, primero `puede_ver_proyecto` sobre el proyecto.

---

## Qué probar

- El preview **no deja nada**: ni cotización, ni líneas, ni impuestos, ni fotos de
  versión. `Cotizacion.objects.count()` igual antes y después.
- **No consume el número**: tras varios previews, la versión que se genera de
  verdad es la que tocaba.
- **No emite el evento** `cotizacion.generada`.
- El HTML del preview y el de la cotización ya generada **coinciden** en lo que
  importa (conceptos, cantidades, totales) — es la prueba de que no es una
  imitación.
- «Generar» crea la versión y devuelve al recuadro; «Generar y enviar» crea y
  abre el envío.
- Un usuario con permiso de ver pero no de crear recibe 403.

---

## Antes de dar por cerrado

- `ruff check .` limpio.
- Suite **como el CI**: `pytest -q tests/ -n auto --dist loadfile` (con `-n auto`
  a secas salen dos fallos falsos de Redis en `test_portavoz_worker`).
- Candados: `test_no_renderiza_comentarios` (las dos apps) y `test_ayuda_novedades`.
- Documentos en el MISMO commit que sube `VERSION` (§10, items 6 y 8): Novedades
  + cuerpo del manual + `CLAUDE.md` §8 + `BITACORA.md` + memoria.
- **MCP**: la vista previa es una pantalla, no una capacidad nueva — declararlo
  explícito en el cierre en vez de dejarlo implícito.

## Deuda previsible

- El preview arma la versión completa cada vez que se abre. Con un proyecto de
  muchas líneas eso es trabajo real; si llegara a sentirse lento, el siguiente
  paso es medirlo (no suponerlo) y, si hace falta, cachearlo por unos segundos
  contra la última modificación del proyecto.
- La paginación del documento sigue siendo una **estimación** nuestra: la hoja la
  corta Google. El preview enseña el HTML, así que un corte de página puede
  quedar distinto en el PDF final. Es la misma limitación que ya tiene «Ver».
