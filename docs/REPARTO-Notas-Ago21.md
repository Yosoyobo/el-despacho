# El Reparto — notas del buzón del 21 de agosto

**Estado al 23 de agosto de 2026**, verificado contra `origin/main`
(VERSION 2026.08.24). Este archivo es el índice; cada sprint tiene su documento.

| | |
|---|---|
| Notas de la ronda | 14 |
| **Cerradas** | **8** |
| Listas para ejecutar | 4, en 2 sprints |
| Pendientes | 2 (una de diseño, una de información) |

---

## ✅ Cerrado

### Bloque 0 · Las fotos de producto (21-22 de agosto)

**La credencial.** Era lo diagnosticado: el permiso de Drive es del 7 de junio y
el cliente del login se reemplazó el 21 de agosto. Se resolvió **sin tocar la
consola de Google** — el respaldo del 13 de agosto trae el cliente viejo cifrado
con la misma llave maestra, así que descifra hoy; se pegó en los campos
**dedicados** de Drive.

> La trampa se esquivó: **nunca se picó «Reconectar»** con el cliente nuevo.
> Sigue vigente como regla — hacerlo dejaría ciego todo el histórico, en silencio.

**Drive fuera del camino de lectura.** El Almacén está desplegado. Los medios
viven en disco, los sirve El Mostrador y Drive quedó de espejo. La importación
bajó 87 de 88 archivos (el que falta es un adjunto de junio ya borrado de Drive).

**Nota 5** («cambié un producto y no se actualizó la imagen») era esto mismo.
Falta **probarla una vez** para cerrarla formalmente — va en el Sprint 2.

### Sprint 1 · Catálogo (22 de agosto, VERSION 2026.08.24)

📄 [`SPRINT-Catalogo-Alta.md`](SPRINT-Catalogo-Alta.md) — **entregado.**
Cerró las notas **2, 3, 4 y 10**. Verificado en `main`: el atajo ya acepta
proveedores y fija el principal, la calculadora aparece en el alta, el JS de la
tarjeta ya **pisa** el proveedor al cambiar de producto, y la ficha ya tiene
archivar y eliminar.

Quedó fuera el punto 5 del sprint (**nota 11**, navegación entre categorías) y la
decisión de producto 3c.

### Nota 12 · Bote de basura en la tarjeta

Entró junto con el Sprint 1. El botón `producto-eliminar` ya usa un `<svg>`.

---

## Lo que sigue

### Sprint 2 — Tarjeta de producto del proyecto
📄 [`SPRINT-Tarjeta-Producto.md`](SPRINT-Tarjeta-Producto.md)
**Notas 13 y 8, más verificar la 5.** La tarjeta que tarda en aparecer (causa ya
identificada: el autoguardado devuelve el formset entero), el diagnóstico de los
colores repetidos, y probar una vez la subida de imagen.
**Riesgo:** medio · un archivo grande y sensible.

### Sprint 3 — Semáforo de cotización + estilo del Kanban
📄 [`SPRINT-Visual-Cotizacion-Kanban.md`](SPRINT-Visual-Cotizacion-Kanban.md)
**Notas 9 y 1.** Intacto: verificado que el detalle de la cotización sigue sin
semáforo y que la ficha del Kanban sigue con su contorno de 2px.
**Riesgo:** bajo · despliegue corto.

### Nota 11 — navegación entre categorías en la ficha
Quedó suelta al cerrar el Sprint 1. Es chica; cabe en el Sprint 3 o en cualquier
despliegue de Catálogo que venga.

---

## Cómo se ejecutan: 2 sesiones, un mensaje cada una

Una sesión por sprint. El mensaje es literalmente:

> Lee `docs/SPRINT-Tarjeta-Producto.md` y ejecútalo completo.

**Ahora sí pueden ir en paralelo.** El conflicto que había era entre los Sprints
1 y 2 (los dos tocaban `proyectos/_form_productos_js.html`); con el 1 ya
entregado, el 2 y el 3 no comparten un solo archivo.

**Por qué no los dos en una sesión:** cada sprint sube `VERSION` y escribe su
bloque de Novedades. Dos en uno serían un despliegue que no se puede revertir por
partes.

---

## 🔒 Pendientes

### Nota 7 · Se cortó un título en el documento
**Lo que pide Oscar ya es el diseño que está en el código.** El título del
concepto vive dentro de la misma tabla que sus especificaciones y su foto, y todo
el bloque va en **una sola fila** de la tabla envoltorio — la única primitiva que
el convertidor de Google no parte entre páginas
([`pdf.html:265-267`](../el-taller/templates/cotizaciones/pdf.html)). Antes de
exportar se le pide además a la API de Documentos que marque esas filas como
«no partir».

Falló la **aplicación**, no el formato. Tres causas posibles:

1. **La protección no se aplicó.** Es lo primero y es gratis: cuando eso falla el
   sistema deja un aviso en la bitácora con el id del documento
   ([`lib/google_drive.py:610`](../lib/google_drive.py)). Se ve con
   `docker compose logs el-taller | grep "blindar la paginación"` o desde El Vigía.
2. **El convertidor aplana las tablas anidadas** y el envoltorio no protege el
   bloque de adentro. Hipótesis abierta desde julio.
3. **El bloque es más alto que una hoja.** Ahí ninguna protección sirve: una fila
   más alta que la página tiene que partirse. Pasa con descripción larga + foto.

**Para desbloquear:** (a) revisar la bitácora buscando ese aviso y (b) el **PDF
exacto** donde pasó, el archivo, no la captura.

### Nota 6 · «@ de tareas en cada tarjeta de productos involucrados»
**Pendiente de diseño (decisión de Oscar, 22 de agosto).** No se ejecuta hasta
definir qué hace la @: crear una tarea ligada al producto, mencionar a una
persona, o listar las que ya existen. Toca el mismo archivo que el Sprint 2, así
que irá en un sprint propio y posterior.

### Decisión de producto abierta (no bloquea nada)
Cambiar el proveedor principal en el catálogo **no toca las líneas de proyecto
que ya existían** — el proveedor se copió al crear la línea, igual que un precio
negociado. ¿Debe propagarse a los proyectos abiertos, como sí hace la calculadora
con el costo? Si la respuesta es sí, es un añadido chico reusando
`apps/el_catalogo/propagacion.py`.

---

## Contexto para ejecutar

1. **El CI sí despliega al NUC** al hacer merge a `main`. La nota que decía lo
   contrario se corrigió el 22 de agosto (commit `6354ec0`).
2. **El árbol principal está limpio** — el trabajo de plantillas de correo ya se
   fusionó. Un `git worktree` propio sólo hace falta si hay otra sesión en
   paralelo.
3. **Las fotos ya no salen de Drive.** Si un sprint toca imágenes, se usa el
   filtro `|medio_url` sobre El Almacén. La tarjeta del proyecto ya está migrada.

---

Desarrollado por [NoKo Devs](https://devs.noko.mx) · © 2026 Learning Center
