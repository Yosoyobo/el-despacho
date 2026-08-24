# Sprint — Catálogo · alta de producto y ficha

> ## ✅ ENTREGADO — 22 de agosto, en `main` (VERSION 2026.08.24)
>
> Verificado contra `origin/main`: el atajo ya acepta proveedores y fija el
> principal · la calculadora ya aparece en el alta · el JS de la tarjeta ya
> **pisa** el proveedor al cambiar de producto (`if (prov && datos.proveedor_id)`,
> sin el `!prov.value`) · la ficha ya tiene archivar y eliminar.
>
> **Queda sólo el punto 5** (navegación entre categorías en la ficha) y la
> decisión de producto de 3c. El resto del documento se conserva como registro
> de lo que se pidió y por qué.

**Notas que cerró:** 2, 3, 4, 10. **Pendiente:** 11.
**Zona:** `el-taller/apps/el_catalogo/` · **Riesgo:** medio.

---

## Objetivo

Que dar de alta un producto desde el atajo rápido deje el producto **completo**:
con proveedor, con su calculadora si aplica y con proveedor principal. Y que la
ficha del producto tenga los dos botones que le faltan.

---

## Contexto verificado en el código

Hay **dos formas** de dar de alta un producto y no hacen lo mismo:

| Camino | Pide proveedores | Dónde |
|---|---|---|
| Modal de la lista de Productos | **Sí** | `catalogo/_modal_nuevo_producto.html` |
| Atajo «+ Crear producto nuevo en el catálogo» | **No** | `views.py::servicio_quick_create` |

El endpoint del atajo sólo acepta `nombre`, `categoria_id`, `precio_base` y
`costo` — [`el-taller/apps/el_catalogo/views.py:595`](../el-taller/apps/el_catalogo/views.py).
De ahí se cae todo lo demás:

- el producto nace **sin proveedor**;
- `servicio_usa_calculadora(srv)` pregunta `srv.proveedores.filter(razon_social__icontains="Simil Cuero Plymouth").exists()`
  ([`calculadora.py:38`](../el-taller/apps/el_catalogo/calculadora.py)), así que
  sin proveedor **no hay calculadora**;
- y `mostrar_calculadora` sólo se arma en la vista `editar`
  ([`views.py:461-464`](../el-taller/apps/el_catalogo/views.py)) — nunca en el alta;
- y tampoco puede quedar un proveedor principal.

**Los cuatro lugares que consumen el atajo** (todos hacen `fetch` a
`catalogo-quick-create`):

- `el-taller/templates/proyectos/form.html:58`
- `el-taller/templates/proyectos/detalle.html:165`
- `el-taller/templates/proyectos/_modal_agregar_producto.html:25`
- `el-taller/templates/cotizaciones/form.html:123`
- (el `fetch` compartido vive en `proyectos/_form_productos_js.html:1120`)

---

## Entregables

### 1 · Proveedor en el alta rápida (nota 2)

Agregar selector de proveedor al endpoint y a los cuatro paneles. Sugerencia:
reusar el patrón que ya existe en la ficha (`#prov-picker` con
`data-select-buscable` que sólo AGREGA + pastillas con ✕), en versión mínima —
basta con poder elegir **uno o varios** y que viajen en el POST.

El endpoint debe:
- aceptar la lista de proveedores y hacer `s.proveedores.set(...)` validando
  contra `Proveedor.objects.filter(activo=True)` (nunca confiar en los ids del
  cliente);
- devolverlos en el JSON de respuesta, para que el JS pueda pintar la etiqueta.

### 2 · La calculadora aparece en cuanto haya proveedor (nota 3)

Hoy sólo se muestra al **editar**. Que se muestre también:
- en el alta, en cuanto el proveedor «Simil Cuero Plymouth» quede marcado
  (puede ser client-side: el JS ya sabe qué proveedores se eligieron);
- en el modal de la lista de Productos, que sí pide proveedores y tampoco la
  muestra.

**El subtotal alimenta el `costo`**, no el precio — ya está así desde julio y
coincide con lo que dice la nota. No cambiarlo.

La constante del nombre vive en `calculadora.py::PROVEEDOR_CALCULADORA`. El
gating es por **nombre de proveedor**, frágil ante renombre; es lo que pidió
Oscar en su momento, no cambiarlo en este sprint.

### 3 · Proveedor principal (nota 4) — dos bugs localizados

Se rastreó en el código. **Guardar el campo funciona bien** (`ServicioForm` lo
tiene en `Meta.fields`, el `<select>` está dentro del `<form>` y `obj.save()` lo
persiste). Lo que falla son otras dos cosas, y las dos son arreglables sin
esperar reproducción:

#### 3a · La tarjeta del proyecto no pisa el proveedor al cambiar de producto

En [`_form_productos_js.html:398`](../el-taller/templates/proyectos/_form_productos_js.html):

```js
if (prov && !prov.value && datos.proveedor_id) prov.value = datos.proveedor_id;
```

Sólo autocompleta **si el campo está vacío**. Si la línea ya traía un proveedor
—el viejo, copiado antes de que cambiaras el principal en el catálogo— al elegir
otro producto **se queda el anterior**. Eso es literalmente «no se está
actualizando».

**El costo ya se arregló así el 7 de agosto** y el proveedor se quedó con la
regla vieja: `prellenarServicio` pasó de `if (costo && !costo.value)` a
`if (costo)` porque «el catálogo pisa». Aplicar lo mismo:

```js
if (prov && datos.proveedor_id) prov.value = datos.proveedor_id;
```

Sólo corre en el `change` del selector de producto, así que un proveedor puesto
a mano sigue respetándose hasta que cambies de producto — misma semántica que el
costo. **El precio NO se pisa** (se negocia por proyecto): no tocarlo.

#### 3b · El dropdown «★ Proveedor principal» no se entera de los cambios

El JS del picker de proveedores maneja `#prov-picker` y los checkboxes ocultos de
`#proveedores-lista`, pero **nunca toca el `<select>` de proveedor principal**
([`catalogo/form.html:372-440`](../el-taller/templates/catalogo/form.html)). Ese
select se pinta una vez con el queryset del servidor. Consecuencias reales:

- un proveedor **creado inline** con el quick-create no aparece en la lista de
  principal hasta recargar la página (`provAgregarOpcion` agrega la opción al
  picker, no al principal);
- si quitas un proveedor de las pastillas, el principal puede quedar apuntando a
  alguien que **ya no surte** el producto, sin aviso.

**Arreglo:** que `pintar()` mantenga el select de principal en sincronía con los
checkboxes marcados, y que `provAgregarOpcion` le agregue también la opción
nueva. Conservar la selección actual si sigue siendo válida.

#### 3c · Lo único que SÍ necesita decisión de producto

Cambiar el principal en el catálogo **no toca las líneas de proyecto que ya
existían**: el proveedor se copió al crear la línea y no se vuelve a leer
(`signals_catalogo.py:43` sólo lo ocupa si está vacío).

Eso es comportamiento actual por diseño, igual que un precio negociado. La
pregunta abierta es si debe propagarse a los proyectos abiertos, como sí hace la
calculadora con el costo (`apps/el_catalogo/propagacion.py`, que sólo toca líneas
sin egreso, sin cotización pagada y cuyo valor coincidía con el del catálogo).

**Este sprint entrega 3a y 3b.** Si Oscar decide que también debe propagarse,
3c es un añadido chico reusando `propagacion.py`.

### 4 · Botón de eliminar en la ficha (nota 10)

`catalogo/form.html` no tiene ni archivar ni eliminar. **Todo lo demás ya
existe** y se usa desde la lista:

- rutas `catalogo-archivar` y `catalogo-eliminar` (`urls.py:15-16`)
- modal `catalogo/_modal_eliminar_servicio.html`
- ejemplo de uso en `catalogo/_filas.html:37,42`

Es ponerlos en la ficha, al pie, gateados igual que en la lista (eliminar exige
el permiso `catalogo.eliminar`, que sólo tiene super_admin).

### 5 · Navegación entre categorías en la ficha (nota 11)

Poder saltar de una categoría a otra sin volver a la lista. Pastillas de
categoría en la ficha que lleven al filtro correspondiente de la lista es
suficiente — no hace falta inventar una pantalla.

---

## Trampas

- **El formulario BORRA los proveedores si el POST no los manda.** Cualquier
  cambio aquí se prueba con «guardar sin tocar proveedores» antes de darlo por
  bueno.
- **Al cambiar el widget de un `ModelChoiceField` hay que re-asignar el
  queryset**, o el `<select>` sale vacío. Ya mordió dos veces en este mismo
  formulario.
- `form.save_m2m()` es obligatorio en `nuevo` y `editar` — sin él los proveedores
  marcados no se guardan (bug real de julio, ya corregido; no reintroducirlo al
  refactorizar).
- El alta rápida crea el producto y **abre su ficha** (`catalogo-editar`), no la
  lista. Conservarlo.

---

## Pruebas

Archivo nuevo `tests/taller/test_catalogo_alta_proveedor.py`. Mínimo:

- el atajo crea el producto **con** los proveedores mandados;
- el atajo ignora un id de proveedor inactivo o inventado;
- guardar la ficha sin mandar `proveedores` **no** borra los que ya tenía;
- con «Simil Cuero Plymouth» ligado, la calculadora se muestra en el alta;
- la ficha muestra los botones de archivar y eliminar, y eliminar está oculto
  para quien no tiene `catalogo.eliminar`;
- **3a**: el JS de la tarjeta ya no condiciona el proveedor a que el campo esté
  vacío (buscar que la línea 398 no lleve `!prov.value`) — es el mismo tipo de
  candado que fija el contrato del costo desde agosto;
- **3b**: `provAgregarOpcion` agrega la opción también al select de principal.

Regresión obligatoria antes de commitear:

```
pytest tests/taller/test_ajustes_clientes_factura_jul23.py \
       tests/taller/test_ajustes_jul25.py \
       tests/taller/test_sprint_fiscal_estructura.py \
       tests/taller/test_unidades_quickcreate.py
pytest tests/taller/test_no_renderiza_comentarios.py tests/gerencia/test_no_renderiza_comentarios.py
ruff check .
```

---

## Cierre (obligatorio, mismo commit que sube VERSION)

1. `lib/version.py` — subir `VERSION` y `VERSION_FECHA` (**sólo la fecha**, nunca
   «tercera entrega de agosto»).
2. `docs/DOC_05_MANUAL_USUARIO.md` — bloque `## Novedades — … (<VERSION_FECHA>)`
   hasta arriba **y** el cuerpo del manual. El candado
   `tests/test_ayuda_novedades.py` falla en CI si falta el bloque.
3. `CLAUDE.md §8` — entrada del sprint con lo entregado, decisiones y deuda.
4. `BITACORA.md` — cierre de sesión.
5. `memory/` — archivo del sprint + una línea en `MEMORY.md`.

**Despliegue:** el CI **sí** despliega al NUC al hacer merge a `main` (la nota
que decía lo contrario se corrigió el 22 de agosto, commit `6354ec0`).

**Árbol:** `git worktree` propio sólo si hay otra sesión trabajando en paralelo.
El árbol principal quedó limpio.
