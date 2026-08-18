# Duplicar proyecto: la copia vuelve a ser una copia

> **Estado: cerrado y mandado el 2026-08-18 (VERSION 2026.08.13).**
> Este documento nació como handoff para otro chat («no lo empujes ahorita, deja
> un md»); Oscar destrabó las dos decisiones que faltaban el mismo día y se subió.
> Se queda en `docs/` como la explicación de por qué la copia copiaba mal —que es
> lo que costó trabajo entender— y para el pendiente de la §5.

---

## 1. De dónde salió

Al cerrar `S-Ajustes-Ago18` (2026.08.12) se agregó `precio_unitario_expr` a
`services_duplicar.py`. Al tocar ese bucle se ve completo — y ahí se nota lo que
NO está. Tres cosas que la copia perdía, **ninguna reportada por Learning Center**:
salieron leyendo el diff, no probando.

1. **El alias del producto.** `duplicar_proyecto` no copiaba `nombre_proyecto`,
   así que la copia volvía al nombre del catálogo: «TShirt Modelo Janet» se
   convertía otra vez en «TShirt Oversize Color». Como el documento arma el
   concepto **y su especificación** a partir de ese nombre
   (`apps.cotizaciones.descripcion.esqueleto`), la cotización de la copia decía
   otra cosa que la del original. De paso faltaba `orden`, así que la copia
   tampoco respetaba el arrastre.

2. **Los procesos de VENTA.** El bucle recorría `procesos` y `escalas` pero no
   `ventas`. La copia **salía más barata que el original y nada lo avisaba**;
   peor, `monto_estimado` SÍ se heredaba (e incluía esos cobros), así que el
   número guardado ni siquiera concordaba con sus propios productos.

   Vale la pena decir por qué no era una exclusión deliberada: el docstring del
   módulo excluye «flujos de dinero histórico» —cotizaciones, facturas, egresos,
   montos cobrados— y un proceso de venta no es eso. Es **precio**: parte de lo
   que se cotiza, como el precio unitario.

3. **La foto propia de la línea.** Quedó como pregunta abierta y Oscar la
   contestó: *«las fotos de productos van ligadas a su alias o nombre y sí viajan
   al duplicar»*. Que es exactamente la regla que ya vivía en
   `ProyectoProducto.imagen_destino` — si la línea tiene alias, la foto es de ese
   uso; si no, es del producto del catálogo. Si el alias viaja, la foto tiene que
   viajar con él.

---

## 2. Qué cambió

**`el-taller/apps/los_proyectos/services_duplicar.py`** (duplicar un proyecto):

- La línea nueva copia **`nombre_proyecto`**, **`orden`** e **`imagen_file_id` /
  `imagen_url`**.
- Bucle nuevo que clona los **`ProyectoProductoVenta`** (descripción, cantidad,
  precio y su cuenta escrita `precio_expr`).
- `prefetch_related` incluye `"ventas"` (sin eso, una consulta por línea).
- El docstring del módulo dice ahora lo que de verdad viaja.

**`el-taller/apps/los_proyectos/views.py::duplicar_producto`** (el ⧉ de la
tarjeta): copia también la foto. Ese ya se llevaba el alias, los procesos y las
ventas.

> ⚠️ **Esto revierte una decisión documentada.** En `S-Ajustes-Ago12-B` el ⧉ se
> dejó a propósito «sin heredar el FK egreso ni la foto propia». La regla que dio
> Oscar el 2026-08-18 es general —la foto va con el alias— y el ⧉ sí copia el
> alias, así que quedaba incoherente. **El FK `egreso` se sigue sin heredar**: eso
> es marca de idempotencia de producción y su exclusión no cambia.

**Sin migraciones. Sin cambios de UI. Sin tocar La Gerencia.**

Sobre copiar la foto: se copia la **referencia** al archivo de Drive, no el
archivo. Dos líneas apuntan al mismo `file_id`, y eso es seguro porque quitar la
foto de una sólo **desliga** — el archivo nunca se borra de Drive
(`forms._desligar_imagen`, decisión de Jul-26-R2: el mismo id puede estar
congelado en una cotización ya enviada). El proxy `catalogo-imagen-producto`
tampoco se rompe: valida que el id pertenezca a algún producto, uso o línea de
cotización, y una línea duplicada es un uso válido.

---

## 3. Cómo se verificó

7 tests nuevos en `tests/taller/test_proyecto_duplicar_margen.py` —el archivo que
ya cubría duplicar—, y **todos se corrieron contra el código SIN arreglar**:

| Ronda | Resultado sin el arreglo |
|---|---|
| alias + ventas | `2 failed, 7 passed` |
| fotos | `2 failed, 9 passed` |

Con el arreglo: **11 passed**. Los otros tres (cuentas escritas, opciones de
volumen, y que el dinero histórico sigue sin heredarse) son red para la próxima
relación de la línea que alguien olvide.

**Un test que no viste fallar no prueba nada** — por eso las dos rondas de arriba.

---

## 4. Qué quedó en los docs

- `CLAUDE.md` §8 — entrada «S-Ajustes-Ago18 · duplicar proyecto».
- `BITACORA.md` — cierre con el razonamiento completo.
- `docs/DOC_05_MANUAL_USUARIO.md` — párrafo dentro del bloque de Novedades del
  18 de agosto (mismo día que 2026.08.12, así que comparten bloque; el candado
  `tests/test_ayuda_novedades.py` exige que `VERSION_FECHA` coincida con el
  encabezado de ese bloque).

---

## 5. Lo que NO se hizo

**La foto no viaja al generar una versión de cotización desde un proyecto
duplicado… porque no tiene por qué.** Ahí sí se congela (`services_version.fotografiar`
copia `imagen_efectiva_file_id`), y como la línea duplicada ya trae su foto, la
versión de la copia sale igual que la del original. No hay nada pendiente aquí;
se anota porque es la pregunta natural.

**`monto_estimado` se hereda tal cual del original.** Antes eso era un problema
—el número incluía cobros que la copia no tenía—; ahora concuerda. No se llama a
`recalcular_monto_estimado()` para no cambiar lo que no hace falta, pero si algún
día el original tiene un monto rancio, la copia lo hereda rancio.

---

## 6. Advertencia de proceso

**Dos sesiones en el mismo working tree se pisan** (lección de `S-Ajustes-Ago12-B`:
un `git commit -a` y un `git reset --hard` ajenos barrieron un sprint en vuelo,
dos veces). Si otro chat va a trabajar mientras alguien anda en este repo, que use
su propio `git worktree`. Y al retomar, si `git log` / `git status` no coinciden
con lo que dice la documentación, revisar el reflog **antes** de tocar nada.
