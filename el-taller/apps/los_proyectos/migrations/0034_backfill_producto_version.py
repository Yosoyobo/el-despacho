"""Reconstruye la foto de productos de las versiones de cotización que YA existen.

S-Ajustes-Ago12-B. Sin esto, las pestañas v1/v2/… saldrían vacías para todo lo
cotizado antes de este deploy — que es justo lo que Oscar quiere ver.

Qué se puede reconstruir y con qué honestidad:

* **Exacto, de la cotización** (es lo que el cliente vio y está congelado):
  concepto, especificaciones, cantidad, precio unitario, foto, `servicio`,
  `variacion` y el orden. Los `CotizacionItem` con `agrupado=True` que siguen a
  cada producto **son** sus procesos de venta, así que se rearman como
  `ventas_json`.
* **Aproximado, de la línea que el proyecto tiene HOY** (merma, costo unitario,
  proveedor, procesos de producción): la cotización nunca los guardó, así que no
  hay de dónde sacar los de entonces. Esas filas quedan marcadas
  `reconstruido=True` para que la pestaña lo advierta y nadie lea un margen
  histórico que jamás se midió.
* Si no hay línea que empareje —el producto ya se quitó del proyecto— el lado
  del costo se deja **vacío** en vez de inventarse.

**El emparejado va por NOMBRE primero**, y sólo cae a `(servicio, variacion)`
cuando ese par se usa UNA vez en el proyecto. Es la lección de S-Ajustes-Jul29
(la foto del alias): dos líneas del mismo producto del catálogo con alias
distintos —«Playera dry fit — negro» / «— blanco»— comparten la llave por
producto, así que emparejar por ahí le colgaría a una el costo de la otra. Y una
línea ya emparejada no se vuelve a usar.

Ojo: los modelos históricos de una migración **no traen properties**, así que
`concepto_visible` / `nombre_visible` van reimplementados aquí (mismo criterio
que `apps.cotizaciones.descripcion.indice_previo`, igual que hizo `0029`).

Reversible: al revertir se borran sólo las filas que creó esta migración
(`reconstruido=True`); las que haya escrito el generador se quedan.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import migrations

LOTE = 400


# ── Nombres (reimplementación de las properties del modelo) ──────────────────

def _nombre_catalogo(servicio, variacion) -> str:
    """Espejo de `ProyectoProducto.nombre_catalogo`, con la higiene anti «X · X»."""
    nombre = (getattr(servicio, "nombre", "") or "").strip() if servicio else ""
    if not nombre:
        nombre = "Producto"
    vnom = (getattr(variacion, "nombre", "") or "").strip() if variacion else ""
    if not vnom or vnom.lower() in nombre.lower():
        return nombre
    if nombre.lower() in vnom.lower():
        return vnom
    return f"{nombre} · {vnom}"


def _nombre_item(it) -> str:
    """Espejo de `CotizacionItem.concepto_visible`.

    Las líneas anteriores a LC 2026-07 no tienen `concepto`: guardaban el nombre
    en el primer renglón de `descripcion`.
    """
    propio = (it.concepto or "").strip()
    if propio:
        return propio
    if it.servicio_id or it.variacion_id:
        return _nombre_catalogo(
            it.servicio if it.servicio_id else None,
            it.variacion if it.variacion_id else None,
        )
    return ((it.descripcion or "").strip().splitlines() or [""])[0].strip()


def _nombre_linea(pp) -> str:
    """Espejo de `ProyectoProducto.nombre_visible`."""
    alias = (pp.nombre_proyecto or "").strip()
    if alias:
        return alias
    return _nombre_catalogo(
        pp.servicio if pp.servicio_id else None,
        pp.variacion if pp.variacion_id else None,
    )


def _entero(valor) -> int:
    """`CotizacionItem.cantidad` es decimal; la línea del proyecto es entera.

    Se redondea (no se trunca): 2.5 → 3. Truncar convertiría «2.5 pz» en 2 y el
    costo por pieza saldría mal.
    """
    try:
        d = Decimal(str(valor or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return 0
    return max(0, int(d))


def _texto_monto(valor) -> str:
    """Los montos van al JSON como texto: `Decimal` no es serializable y `float`
    perdería centavos. `sincronizar_procesos` los lee con `Decimal(str(...))`."""
    try:
        return str(Decimal(str(valor or 0)).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError, TypeError):
        return "0.00"


# ── Emparejado contra las líneas vivas del proyecto ──────────────────────────

class _Emparejador:
    """Encuentra la línea actual del proyecto que corresponde a un concepto.

    Se construye uno POR VERSIÓN: la v1 y la v2 pueden traer el mismo producto y
    cada una tiene derecho a emparejarlo.
    """

    def __init__(self, lineas):
        self.usadas: set[int] = set()
        self.por_nombre: dict[str, list] = {}
        self.por_srv: dict[tuple, list] = {}
        for pp in lineas:
            self.por_nombre.setdefault(_nombre_linea(pp).lower(), []).append(pp)
            self.por_srv.setdefault((pp.servicio_id, pp.variacion_id), []).append(pp)

    def _tomar(self, cola) -> object | None:
        for pp in cola:
            if pp.pk not in self.usadas:
                self.usadas.add(pp.pk)
                return pp
        return None

    def buscar(self, nombre: str, servicio_id, variacion_id):
        pp = self._tomar(self.por_nombre.get((nombre or "").strip().lower(), []))
        if pp is not None:
            return pp
        # Sólo si el par producto+variación se usa UNA vez: con dos alias del
        # mismo producto, esta llave es ambigua y se prefiere no adivinar.
        cola = self.por_srv.get((servicio_id, variacion_id), [])
        if len(cola) == 1:
            return self._tomar(cola)
        return None


def _procesos_de(pp) -> list[dict]:
    """Procesos de producción de la línea, en la forma que serializa la tarjeta."""
    filas = []
    for p in pp.procesos.all().order_by("orden", "creado_en"):
        filas.append({
            "tipo": p.tipo,
            "proveedor_id": p.proveedor_id,
            "descripcion": p.descripcion or "",
            "costo": _texto_monto(p.costo),
            "costo_expr": p.costo_expr or "",
            "por_pieza": bool(p.por_pieza),
        })
    return filas


# ── La reconstrucción ────────────────────────────────────────────────────────

def reconstruir(apps, schema_editor):
    Cotizacion = apps.get_model("cotizaciones", "Cotizacion")
    ProyectoProducto = apps.get_model("proyectos", "ProyectoProducto")
    Version = apps.get_model("proyectos", "ProyectoProductoVersion")

    cots = (
        Cotizacion.objects
        .filter(version__gt=0, proyecto__isnull=False)
        .order_by("proyecto_id", "version")
        .prefetch_related("items", "items__servicio", "items__variacion")
    )

    cache_proyecto: dict[int, list] = {}
    pendientes: list = []

    def _lineas_de(proyecto_id: int) -> list:
        # Ordenado por proyecto, así que basta con recordar el último (el cache
        # no crece con el número de proyectos).
        if proyecto_id not in cache_proyecto:
            cache_proyecto.clear()
            cache_proyecto[proyecto_id] = list(
                ProyectoProducto.objects
                .filter(proyecto_id=proyecto_id)
                .select_related("servicio", "variacion")
                .prefetch_related("procesos")
                .order_by("orden", "creado_en")
            )
        return cache_proyecto[proyecto_id]

    def _volcar():
        if pendientes:
            Version.objects.bulk_create(pendientes, ignore_conflicts=True)
            pendientes.clear()

    # `iterator()` tras `prefetch_related` exige `chunk_size` (Django lo valida).
    for cot in cots.iterator(chunk_size=100):
        try:
            # Idempotente: una versión ya fotografiada no se vuelve a tocar.
            if Version.objects.filter(cotizacion_id=cot.pk).exists():
                continue
            emparejador = _Emparejador(_lineas_de(cot.proyecto_id))
            orden = 0
            actual = None  # la última fila de PRODUCTO, dueña de las ventas
            for it in sorted(cot.items.all(), key=lambda x: (x.orden, x.pk)):
                nombre = _nombre_item(it)
                if it.agrupado:
                    # Proceso de VENTA del concepto anterior (LC 2026-07-26).
                    if actual is not None:
                        actual.ventas_json.append({
                            "descripcion": nombre[:200],
                            "cantidad": max(1, _entero(it.cantidad)),
                            "precio": _texto_monto(it.precio_unitario),
                        })
                    continue

                pp = emparejador.buscar(nombre, it.servicio_id, it.variacion_id)
                catalogo = _nombre_catalogo(
                    it.servicio if it.servicio_id else None,
                    it.variacion if it.variacion_id else None,
                ) if (it.servicio_id or it.variacion_id) else ""
                # El alias se guarda sólo si de verdad difiere del catálogo, para
                # que «Restaurar esta versión» no invente un alias donde no había.
                alias = "" if (catalogo and nombre.strip().lower() == catalogo.strip().lower()) else nombre

                actual = Version(
                    cotizacion_id=cot.pk,
                    item_id=it.pk,
                    orden=orden,
                    servicio_id=it.servicio_id,
                    variacion_id=it.variacion_id,
                    proveedor_id=(pp.proveedor_id if pp is not None else None),
                    nombre_proyecto=alias[:150],
                    cantidad=_entero(it.cantidad),
                    merma=(pp.merma if pp is not None else 0),
                    precio_unitario=it.precio_unitario,
                    costo_unitario=(pp.costo_unitario if pp is not None else None),
                    costo_unitario_expr=(
                        (pp.costo_unitario_expr or "") if pp is not None else ""),
                    nota=(it.descripcion or ""),
                    # Las versiones anteriores a LC 2026-07-26 no congelaban foto:
                    # se cae a la propia del uso (nunca a la del catálogo — eso lo
                    # resuelve `imagen_efectiva_file_id` al pintar).
                    imagen_file_id=(
                        (it.imagen_file_id or "")
                        or ((pp.imagen_file_id or "") if pp is not None else "")
                    ),
                    incluir_en_calculo=True,
                    procesos_json=(_procesos_de(pp) if pp is not None else []),
                    ventas_json=[],
                    reconstruido=True,
                )
                pendientes.append(actual)
                orden += 1
            if len(pendientes) >= LOTE:
                _volcar()
        except Exception:  # noqa: BLE001 — un proyecto raro no aborta el resto
            _volcar()
            continue

    _volcar()


def deshacer(apps, schema_editor):
    Version = apps.get_model("proyectos", "ProyectoProductoVersion")
    Version.objects.filter(reconstruido=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0033_producto_version"),
    ]

    operations = [
        migrations.RunPython(reconstruir, deshacer),
    ]
