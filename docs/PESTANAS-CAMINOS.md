# Pestañas dentro de El Despacho — los caminos

> Escrito el 2026-08-28 a petición de Oscar: «quiero meter un sistema de tabs
> hasta arriba de El Despacho, para poder hacer cambios a varias cosas o páginas
> sin tener muchas ventanas abiertas. Dime las implicaciones sin que hagamos
> nada este sprint.»
>
> **No se ejecutó nada.** Esto es el reconocimiento y las tres formas de
> hacerlo, con su precio. Sirve para decidir después, con datos y no de oído.

---

## Lo que hay que saber antes de elegir

El front de El Despacho está construido sobre un supuesto que hoy se cumple
siempre: **sólo hay una página viva a la vez**. No es descuido, es lo que
permitió que un modal, un arrastre o un buscador se escriban una vez y sirvan en
todas las pantallas. Pero es exactamente el supuesto que rompen las pestañas.

Lo medido en el repo (2026-08-28):

| Qué | Cuánto | Por qué importa |
|---|---|---|
| Plantillas que apuntan al modal único `#modal-slot` | **107** | Un modal abierto en la pestaña B se inyecta en el mismo cajón que el de la A |
| Escuchas globales sobre el documento en los archivos de JavaScript | **69** (40 sólo en `ui.js`) | Reaccionan a lo que pasa en *cualquier* pestaña |
| Búsquedas por identificador único en plantillas | **238** | `#form-proyecto`, `#formset-productos`, `#guardado-indicador`… y un `id` por cada campo de cada formulario |
| Variables compartidas en `window` | **20** | Una sola copia para todas las pestañas |

**El modo de falla que importa no se ve.** Con dos proyectos abiertos, los
identificadores se repiten. El navegador, cuando le piden «el formulario del
proyecto», contesta **el de la primera pestaña**. Escribes en la segunda y el
autoguardado lo escribe en el proyecto de la primera — sin un mensaje de error,
sin nada raro en pantalla. Se descubre días después, cuando los datos ya están
mezclados.

---

## Camino A — pestañas de verdad (varias páginas en el mismo documento)

Es lo que uno imagina al decir «pestañas»: todo vive junto y se muestra una a la
vez.

**Qué obliga a hacer:** reescribir el front para que cada pieza cuelgue de su
contenedor en lugar del documento entero. Modales, arrastre, buscadores de los
desplegables, pegado de imágenes, autoguardado, el indicador de «● Sin guardar»
(hoy hay uno solo), el calendario, el geolocalizador. También hay que darle a
cada pestaña su propio juego de identificadores, porque Django los genera
iguales.

**Precio:** 4 a 6 sprints, y después una temporada de errores difíciles de
reproducir — de los que sólo aparecen con dos pestañas de lo mismo abiertas.
Es el arco TailAdmin otra vez, pero en JavaScript.

**Cuándo tendría sentido:** si algún día se decide reescribir el front por otra
razón, esto viaja gratis con esa reescritura. Solo, no se paga.

---

## Camino B — pestañas con marcos aislados *(la recomendación)*

Cada pestaña es un documento independiente dentro de la página. El sistema no se
entera: la aplicación se sigue escribiendo igual que hoy.

**Qué se gana:** cero colisiones de identificadores, cero reescritura, y es
**reversible** — si no gusta, se quita y no queda deuda.

**Qué cuesta:**

- **Memoria.** Cada pestaña carga la aplicación completa. Ya tenemos el
  antecedente del navegador de la pared del NUC, que llegó a 5.4 GB. Hay que
  topar el número de pestañas (seis, por ejemplo) y descargar las dormidas.
- **El menú y el encabezado se duplicarían** dentro de cada marco. Se resuelve
  sirviendo las páginas en modo «sin menú», algo que el sistema ya sabe hacer.
- **La barra de direcciones** deja de decir dónde estás, salvo que se sincronice
  a mano. Compartir un enlace se vuelve menos obvio.
- **Sólo escritorio.** En el celular no caben y estorban.

**Precio:** 1 sprint de prototipo para medir la memoria de verdad, + 1 de pulido.

---

## Camino C — no hacer pestañas

Atajos que abran en pestaña del navegador y una lista de «recientes» que te
devuelva a donde ibas.

**Precio:** medio sprint. No resuelve tener muchas ventanas: las ordena.

---

## Lo que hay que resolver ANTES, tome el camino que tome

Dos pestañas del **mismo** proyecto pueden pisarse los guardados. Hoy nada lo
impide y el autoguardado escribe solo, así que **este riesgo ya existe** con dos
ventanas del navegador abiertas — las pestañas sólo lo harían más frecuente.

Lo que falta es un aviso de «alguien más cambió esto mientras editabas» antes de
sobrescribir. Es trabajo útil con o sin pestañas, y debería ir primero.

---

## Recomendación

1. Primero, el aviso de edición pisada (vale por sí solo).
2. Después, un prototipo del **camino B** de un sprint, con la memoria medida en
   la máquina de verdad y no estimada.
3. El **camino A** sólo si algún día se reescribe el front por otro motivo.
