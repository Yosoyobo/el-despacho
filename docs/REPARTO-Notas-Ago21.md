# El Reparto — notas del buzón del 21 de agosto

**Estado al 22 de agosto de 2026.** Las notas de esa ronda, repartidas por zona
del sistema. Este archivo es el índice; cada sprint tiene su propio documento.

| | |
|---|---|
| Notas de la ronda | 14 |
| **Ya resueltas** | **2** (Bloque 0) |
| Listas para ejecutar | 9, en 3 sprints |
| Bloqueadas | 3 (falta información) |

---

## ✅ Cerrado — Bloque 0 · Las fotos de producto

**Las dos partes quedaron resueltas entre el 21 y el 22 de agosto.** No hay nada
que hacer aquí.

**Problema 1 — la credencial.** Era lo que se diagnosticó: el permiso guardado de
Drive es del 7 de junio y el cliente OAuth del login se reemplazó el 21 de
agosto. Se resolvió **sin tocar la consola de Google**: el respaldo del 13 de
agosto trae el cliente viejo cifrado con la misma llave maestra, así que descifra
hoy; se pegó en los campos **dedicados** de Drive. El acceso con Google se quedó
con el cliente nuevo y Drive recuperó su historia. Verificado bajando una foto
real por la API.

> La trampa que se señaló se esquivó: **nunca se picó «Reconectar»** con el
> cliente nuevo. Sigue vigente como regla — hacerlo dejaría ciego todo el
> histórico, en silencio.

**Problema 2 — Drive en el camino de lectura.** El Almacén está desplegado
(`lib/almacen.py` ya en `main`). Los medios viven en disco, los sirve El
Mostrador, y Drive quedó de espejo. La importación bajó **87 de 88** archivos
(21.1 MB); el que falta es un adjunto de junio que ya habían borrado de Drive.

**Nota 5 («cambié un producto y no se actualizó la imagen»)** era esto mismo: la
subida fallaba en silencio. Sólo falta **volver a probarla una vez** para
cerrarla formalmente.

---

## Lo que sigue pendiente

### Sprint 1 — Catálogo · alta de producto y ficha
📄 [`SPRINT-Catalogo-Alta.md`](SPRINT-Catalogo-Alta.md)
**Notas 2, 3, 4, 10, 11.** El atajo «+ Crear producto nuevo en el catálogo» no
pide proveedor, y de ahí se caen la calculadora de Simil y el proveedor
principal. Más los dos botones que faltan en la ficha.
**Riesgo:** medio · **Es el más valioso**: destraba el flujo de captura.

### Sprint 2 — Tarjeta de producto del proyecto
📄 [`SPRINT-Tarjeta-Producto.md`](SPRINT-Tarjeta-Producto.md)
**Notas 12, 13, 8 y verificar la 5.** Bote de basura, la tarjeta que tarda en
aparecer, y el diagnóstico de los colores repetidos.
**Riesgo:** medio · un archivo grande y sensible.

### Sprint 3 — Semáforo de cotización + estilo del Kanban
📄 [`SPRINT-Visual-Cotizacion-Kanban.md`](SPRINT-Visual-Cotizacion-Kanban.md)
**Notas 9 y 1.** Los dos son de bajo riesgo y caben en un despliegue corto.

---

## 🔒 Bloqueadas — falta información

### Nota 7 · Se cortó un título en el documento
**Lo que pide Oscar ya es el diseño que está en el código.** El título del
concepto vive dentro de la misma tabla que sus especificaciones y su foto, y
todo el bloque va en **una sola fila** de la tabla envoltorio — la única
primitiva que el convertidor de Google no parte entre páginas
([`pdf.html:265-267`](../el-taller/templates/cotizaciones/pdf.html)). Antes de
exportar se le pide además a la API de Documentos que marque esas filas como
«no partir».

Falló la **aplicación**, no el formato. Tres causas posibles:

1. **La protección no se aplicó.** Es lo primero y es gratis: cuando eso falla el
   sistema deja un aviso en la bitácora con el id del documento
   ([`lib/google_drive.py:610`](../lib/google_drive.py)). Ahora que todo corre en
   el NUC, se ve con `docker compose logs el-taller | grep "blindar la paginación"`
   o desde El Vigía.
2. **El convertidor aplana las tablas anidadas** y el envoltorio no protege el
   bloque de adentro. Hipótesis abierta desde julio.
3. **El bloque es más alto que una hoja.** Ahí ninguna protección sirve: una fila
   más alta que la página tiene que partirse. Pasa con descripción larga + foto.

**Para desbloquear:** (a) revisar la bitácora buscando ese aviso y (b) el **PDF
exacto** donde pasó, el archivo, no la captura.

### Nota 6 · «@ de tareas en cada tarjeta de productos involucrados»
**Pendiente de diseño (decisión de Oscar, 22 de agosto).** No se ejecuta hasta
definir qué hace la @: crear una tarea ligada al producto, mencionar a una
persona, o listar las tareas que ya existen. Toca el mismo archivo que el
Sprint 2, así que irá en un sprint propio y posterior.

### Nota 4 · Proveedor principal — ya NO está bloqueada
Se rastreó en el código y son **dos bugs concretos**, los dos dentro del
Sprint 1. Guardar el campo funciona bien; lo que falla es que la tarjeta del
proyecto no pisa el proveedor al cambiar de producto, y que el dropdown de
«★ Proveedor principal» no se entera de los proveedores que agregas o quitas en
la misma pantalla. Detalle en el sprint.

Lo único que queda como decisión de producto: **si cambiar el principal en el
catálogo debe propagarse a los proyectos ya abiertos** (hoy no lo hace, igual que
un precio negociado). El sprint entrega los dos bugs sin esperar esa respuesta.

---

## Cómo se ejecutan: 3 sesiones, un mensaje cada una

**Una sesión por sprint.** El mensaje es literalmente:

> Lee `docs/SPRINT-Catalogo-Alta.md` y ejecútalo completo.

**Por qué no los tres en una sola sesión:** cada sprint sube `VERSION` y escribe
su bloque de Novedades. Tres en uno serían un solo despliegue que no se puede
revertir por partes — justo lo que este reparto quiere evitar. Y una sesión con
las tres zonas encima acumula contexto de más y empieza a mezclar.

**El orden importa entre 1 y 2:** los dos tocan
`proyectos/_form_productos_js.html` — el Sprint 1 la llamada del alta rápida, el
Sprint 2 la tarjeta y el rerender. **Van secuenciales**, nunca en paralelo.

**El Sprint 3 es independiente:** no comparte archivos con los otros dos. Puede
correr en paralelo en su propio worktree, o dejarse al final. Es el más barato.

```
Sesión A → Sprint 1 (Catálogo)      ──┐ secuenciales:
Sesión B → Sprint 2 (Tarjeta)       ──┘ comparten _form_productos_js.html

Sesión C → Sprint 3 (Cotización + Kanban)   independiente, cuando quieras
```

---

## Antes de empezar cualquier sprint

Tres cosas del contexto nuevo que cambian cómo se ejecuta:

1. **El árbol de trabajo está ocupado.** La rama `agent/plantillas-correo` tiene
   cambios sin commitear (alias de remitente). Cualquier sprint nuevo va en su
   **propio `git worktree`** — dos sesiones en el mismo árbol se pisan, y ya pasó
   una vez con pérdida de trabajo.

2. **El despliegue al NUC es MANUAL.** El job del CI está gateado hasta que
   existan los secretos de Tailscale; hoy sale con un aviso «Deploy al NUC
   omitido». El `pull && up -d` se hace a mano — ver
   [`MUDANZA-AL-NUC-LC.md`](MUDANZA-AL-NUC-LC.md).

3. **Las fotos ya no salen de Drive.** Si un sprint toca imágenes de producto, se
   usa el filtro `|medio_url` sobre El Almacén. La tarjeta del proyecto ya está
   migrada.

---

Desarrollado por [NoKo Devs](https://devs.noko.mx) · © 2026 Learning Center
