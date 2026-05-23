"""Ejecutores básicos V1 — proyectos, tareas, recados, buzón.

Cada función toma `(accion: DictadoAccion, usuario: Usuario, contexto: dict)`
y aplica el cambio. Lanza `ValueError` si el payload es inválido o la entidad
no existe.

`contexto["entidades_creadas"]` es un dict `{orden: {tipo, id}}` con las
entidades creadas por acciones previas del MISMO dictado. Habilita
referencias como `@accion_0` en payload (capa 1) y fuzzy fallback por
nombre cuando el LLM adivina un slug que no coincide con el real (capa 2).
"""

from __future__ import annotations

import re

from . import registrar

CAMPOS_PROYECTO_PERMITIDOS = {"estado", "monto_cotizado", "fecha_compromiso", "descripcion"}
CAMPOS_TAREA_PERMITIDOS = {"estado", "prioridad", "asignado_slug", "fecha_compromiso"}
CAMPOS_CLIENTE_PERMITIDOS = {
    "razon_social", "rfc", "nombre_contacto", "email_contacto",
    "telefono", "direccion", "notas", "estado",
}
ESTADOS_PROYECTO_VALIDOS = {
    "por_cotizar", "esperando_respuesta", "en_proceso_diseno",
    "en_proceso_produccion", "entregado", "en_pausa", "cancelado",
}


REF_ACCION_RE = re.compile(r"^@accion_(\d+)$")


def _limpiar_slug(slug: str) -> str:
    """Quita prefijos `@/#/$` que el LLM a veces emite literales en el slug.

    Ejemplo: el LLM mete `cliente_slug: "$optimist"` cuando debería ser
    `cliente_slug: "optimist"`. Preserva `@accion_N` (referencia entre
    acciones) que sí debe iniciar con `@`.
    """
    if not slug:
        return slug
    s = slug.strip()
    if REF_ACCION_RE.match(s):
        return s
    while s and s[0] in ("$", "#", "@"):
        s = s[1:]
    return s


def _ref_anterior(slug: str, contexto: dict | None, tipo_esperado: str):
    """Capa 1 — resuelve `@accion_N` mirando `contexto.entidades_creadas`.

    Retorna la instancia del modelo o None si el slug no es una referencia
    o si la referencia no existe / es de otro tipo.
    """
    if not slug or not contexto:
        return None
    m = REF_ACCION_RE.match(slug.strip())
    if not m:
        return None
    orden = int(m.group(1))
    entidades = (contexto or {}).get("entidades_creadas") or {}
    info = entidades.get(orden)
    if not info or info.get("tipo") != tipo_esperado:
        return None
    return info.get("id")


def _fuzzy_recientes(slug: str, contexto: dict | None, tipo: str, modelo):
    """Capa 2 — fuzzy match contra entidades del mismo dictado por nombre.

    Si el LLM adivinó un slug que no existe en DB pero suena al nombre de
    una entidad recién creada en este mismo dictado, la resuelve.
    """
    from django.utils.text import slugify
    if not slug or not contexto:
        return None
    pedido = slugify(slug)
    entidades = (contexto or {}).get("entidades_creadas") or {}
    candidatos_ids = [
        info["id"] for info in entidades.values()
        if info.get("tipo") == tipo and info.get("id")
    ]
    if not candidatos_ids:
        return None
    for obj in modelo.objects.filter(pk__in=candidatos_ids):
        nombre_attr = "razon_social" if tipo == "cliente" else "nombre"
        nombre = getattr(obj, nombre_attr, "") or ""
        slug_nombre = slugify(nombre)
        if not slug_nombre:
            continue
        if pedido == slug_nombre or pedido in slug_nombre or slug_nombre in pedido:
            return obj
    return None


def _sugerencia_recien_creado(contexto: dict | None, tipo: str, modelo) -> str:
    """Capa 3 — arma sugerencia útil para el error message."""
    if not contexto:
        return ""
    entidades = (contexto or {}).get("entidades_creadas") or {}
    ids = [info["id"] for info in entidades.values() if info.get("tipo") == tipo]
    if not ids:
        return ""
    obj = modelo.objects.filter(pk__in=ids).first()
    if not obj:
        return ""
    if tipo == "cliente":
        return f' ¿Quisiste decir "{obj.razon_social}" (slug: `{obj.slug}`, recién creado en esta misma acción)?'
    return f' ¿Quisiste decir "{obj.codigo} · {obj.nombre}" (slug: `{obj.slug}`, recién creado en esta misma acción)?'


def _resolver_proyecto(slug: str, contexto: dict | None = None):
    from apps.los_proyectos.models import Proyecto
    if not slug:
        raise ValueError("Falta `proyecto_slug` en payload.")
    slug = _limpiar_slug(slug)
    # Capa 1: @accion_N
    ref_id = _ref_anterior(slug, contexto, "proyecto")
    if ref_id:
        obj = Proyecto.objects.filter(pk=ref_id).first()
        if obj:
            return obj
    # Slug literal
    proyecto = Proyecto.objects.filter(slug=slug.lower()).first()
    if proyecto:
        return proyecto
    # Capa 2: fuzzy contra recién creados
    fuzzy = _fuzzy_recientes(slug, contexto, "proyecto", Proyecto)
    if fuzzy:
        return fuzzy
    # Capa 3: error útil
    sugerencia = _sugerencia_recien_creado(contexto, "proyecto", Proyecto)
    raise ValueError(f"Proyecto `{slug}` no encontrado.{sugerencia}")


def _resolver_cliente(slug: str, contexto: dict | None = None):
    from apps.la_cartera.models import Cliente
    if not slug:
        raise ValueError("Falta `cliente_slug` en payload.")
    slug = _limpiar_slug(slug)
    ref_id = _ref_anterior(slug, contexto, "cliente")
    if ref_id:
        obj = Cliente.objects.filter(pk=ref_id).first()
        if obj:
            return obj
    cliente = Cliente.objects.filter(slug=slug.lower()).first()
    if cliente:
        return cliente
    fuzzy = _fuzzy_recientes(slug, contexto, "cliente", Cliente)
    if fuzzy:
        return fuzzy
    sugerencia = _sugerencia_recien_creado(contexto, "cliente", Cliente)
    raise ValueError(f"Cliente `${slug}` no encontrado.{sugerencia}")


def _resolver_usuario(slug: str, contexto: dict | None = None):
    from cuentas.models.usuario import Usuario
    slug = _limpiar_slug(slug)
    u = Usuario.objects.filter(slug=slug.lower(), is_active=True).first()
    if not u:
        raise ValueError(f"Usuario `@{slug}` no encontrado.")
    return u


@registrar("crear_proyecto")
def crear_proyecto(accion, usuario, contexto=None):
    """Crea un Proyecto a partir del payload del dictado.

    Payload: nombre (requerido), cliente_slug (requerido, $cliente),
    descripcion?, estado?, fecha_compromiso?, monto_estimado?,
    monto_cotizado?.
    """
    from datetime import date as _date

    from apps.los_proyectos.models import Proyecto

    payload = accion.payload or {}
    nombre = (payload.get("nombre") or "").strip()
    if not nombre:
        raise ValueError("Falta `nombre` en payload.")
    cliente = _resolver_cliente((payload.get("cliente_slug") or "").lower(), contexto)

    estado = (payload.get("estado") or "por_cotizar").lower()
    if estado not in ESTADOS_PROYECTO_VALIDOS:
        estado = "por_cotizar"

    fecha_compromiso = None
    fecha_str = payload.get("fecha_compromiso")
    if fecha_str:
        try:
            fecha_compromiso = _date.fromisoformat(str(fecha_str)[:10])
        except ValueError as exc:
            raise ValueError(f"`fecha_compromiso` inválida: {fecha_str}") from exc

    kwargs = {
        "nombre": nombre[:200],
        "cliente": cliente,
        "estado": estado,
        "descripcion": (payload.get("descripcion") or "")[:2000],
        "creado_por": usuario,
    }
    if fecha_compromiso:
        kwargs["fecha_compromiso"] = fecha_compromiso
    for campo in ("monto_estimado", "monto_cotizado"):
        valor = payload.get(campo)
        if valor in (None, ""):
            continue
        try:
            kwargs[campo] = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"`{campo}` inválido: {valor}") from exc

    proyecto = Proyecto.objects.create(**kwargs)
    accion.entidad_tipo = "proyecto"
    accion.entidad_id = proyecto.pk


@registrar("crear_cliente")
def crear_cliente(accion, usuario, contexto=None):
    """Crea un Cliente. Payload: razon_social (requerido), rfc?, nombre_contacto?,
    email_contacto?, telefono?, direccion?, notas?, estado?.
    """
    from apps.la_cartera.models import Cliente

    payload = accion.payload or {}
    razon = (payload.get("razon_social") or "").strip()
    if not razon:
        raise ValueError("Falta `razon_social` en payload.")
    estado = (payload.get("estado") or "prospecto").lower()
    if estado not in {"prospecto", "activo", "inactivo"}:
        estado = "prospecto"
    cliente = Cliente.objects.create(
        razon_social=razon[:200],
        rfc=(payload.get("rfc") or "")[:13],
        nombre_contacto=(payload.get("nombre_contacto") or "")[:200],
        email_contacto=(payload.get("email_contacto") or "")[:254],
        telefono=(payload.get("telefono") or "")[:40],
        direccion=(payload.get("direccion") or ""),
        notas=(payload.get("notas") or ""),
        estado=estado,
        creado_por=usuario,
    )
    accion.entidad_tipo = "cliente"
    accion.entidad_id = cliente.pk


@registrar("actualizar_cliente")
def actualizar_cliente(accion, usuario, contexto=None):
    cliente = _resolver_cliente((accion.payload.get("cliente_slug") or "").lower(), contexto)
    campos = accion.payload.get("campos") or {}
    if not isinstance(campos, dict):
        raise ValueError("Campo `campos` debe ser dict.")
    aplicado = []
    for k, v in campos.items():
        if k not in CAMPOS_CLIENTE_PERMITIDOS:
            continue
        setattr(cliente, k, v)
        aplicado.append(k)
    if not aplicado:
        raise ValueError("Sin campos válidos para actualizar.")
    cliente.save(update_fields=[*aplicado, "actualizado_en"])
    accion.entidad_tipo = "cliente"
    accion.entidad_id = cliente.pk


@registrar("actualizar_proyecto")
def actualizar_proyecto(accion, usuario, contexto=None):
    proyecto = _resolver_proyecto(accion.payload.get("proyecto_slug", ""), contexto)
    campos = accion.payload.get("campos") or {}
    if not isinstance(campos, dict):
        raise ValueError("Campo `campos` debe ser dict.")
    aplicado = []
    for k, v in campos.items():
        if k not in CAMPOS_PROYECTO_PERMITIDOS:
            continue
        setattr(proyecto, k, v)
        aplicado.append(k)
    if not aplicado:
        raise ValueError("Sin campos válidos para actualizar.")
    proyecto.save(update_fields=[*aplicado, "actualizado_en"])
    accion.entidad_tipo = "proyecto"
    accion.entidad_id = proyecto.pk


@registrar("asignar_usuario_proyecto")
def asignar_usuario_proyecto(accion, usuario, contexto=None):
    proyecto = _resolver_proyecto(accion.payload.get("proyecto_slug", ""), contexto)
    u = _resolver_usuario(accion.payload.get("usuario_slug", ""), contexto)
    rol_en_proyecto = (accion.payload.get("rol_en_proyecto") or "disenador").lower()
    if rol_en_proyecto not in {"lider", "disenador", "produccion", "revisor"}:
        rol_en_proyecto = "disenador"
    from apps.los_proyectos.models import ProyectoAsignacion
    ProyectoAsignacion.objects.update_or_create(
        proyecto=proyecto, usuario=u,
        defaults={"rol_en_proyecto": rol_en_proyecto},
    )
    accion.entidad_tipo = "asignacion"
    accion.entidad_id = proyecto.pk


@registrar("crear_tarea")
def crear_tarea(accion, usuario, contexto=None):
    proyecto = _resolver_proyecto(accion.payload.get("proyecto_slug", ""), contexto)
    titulo = (accion.payload.get("titulo") or "").strip()
    if not titulo:
        raise ValueError("Falta `titulo` en payload.")
    asignado_slug = (accion.payload.get("asignado_slug") or "").strip()
    asignada_a = _resolver_usuario(asignado_slug, contexto) if asignado_slug else None
    fecha = accion.payload.get("fecha_compromiso") or None
    prioridad = (accion.payload.get("prioridad") or "media").lower()
    if prioridad not in {"baja", "media", "alta"}:
        prioridad = "media"
    from apps.el_pizarron.models import Tarea
    t = Tarea.objects.create(
        proyecto=proyecto, titulo=titulo[:200], asignada_a=asignada_a,
        fecha_compromiso=fecha, prioridad=prioridad, creado_por=usuario,
    )
    accion.entidad_tipo = "tarea"
    accion.entidad_id = t.pk

    # Dispara push automático (S2b.4) si hay asignado.
    if asignada_a:
        from apps.taller_home.push_handlers import notificar_tarea_asignada
        notificar_tarea_asignada(t, usuario)


@registrar("actualizar_tarea")
def actualizar_tarea(accion, usuario, contexto=None):
    from apps.el_pizarron.models import Tarea
    tarea_id = accion.payload.get("tarea_id")
    if not tarea_id:
        raise ValueError("Falta `tarea_id`.")
    tarea = Tarea.objects.filter(pk=tarea_id).first()
    if not tarea:
        raise ValueError(f"Tarea {tarea_id} no encontrada.")
    campos = accion.payload.get("campos") or {}
    aplicado: list[str] = []
    for k, v in campos.items():
        if k not in CAMPOS_TAREA_PERMITIDOS:
            continue
        if k == "asignado_slug":
            tarea.asignada_a = _resolver_usuario(v, contexto)
            aplicado.append("asignada_a")
        else:
            setattr(tarea, k, v)
            aplicado.append(k)
    if not aplicado:
        raise ValueError("Sin campos válidos para actualizar.")
    tarea.save(update_fields=aplicado)
    accion.entidad_tipo = "tarea"
    accion.entidad_id = tarea.pk


@registrar("crear_recado")
def crear_recado_ejec(accion, usuario, contexto=None):
    from apps.recados.services import crear_recado
    destinatarios = accion.payload.get("destinatarios_slugs") or []
    cuerpo = (accion.payload.get("cuerpo") or "").strip()
    if not (destinatarios and cuerpo):
        raise ValueError("Recado necesita `destinatarios_slugs` + `cuerpo`.")
    # Servicio existente: crear_recado(autor, cuerpo, destinatarios_usuarios=[...], destinatarios_grupos=[...])
    from cuentas.models.usuario import Usuario
    ids = set(Usuario.objects.filter(
        slug__in=[s.lower() for s in destinatarios], is_active=True,
    ).values_list("pk", flat=True))
    if not ids:
        raise ValueError("Ningún destinatario válido.")
    recado = crear_recado(autor=usuario, cuerpo=cuerpo, destinatarios_ids=ids)
    accion.entidad_tipo = "recado"
    accion.entidad_id = recado.pk


@registrar("crear_mensaje_buzon")
def crear_mensaje_buzon_ejec(accion, usuario, contexto=None):
    from buzon.models import MensajeBuzon
    tipo = (accion.payload.get("tipo") or "otro").lower()
    if tipo not in {"sugerencia", "problema", "otro"}:
        tipo = "otro"
    asunto = (accion.payload.get("asunto") or "").strip()
    cuerpo = (accion.payload.get("cuerpo") or "").strip()
    if not (asunto and cuerpo):
        raise ValueError("Mensaje del Buzón necesita `asunto` + `cuerpo`.")
    msg = MensajeBuzon.objects.create(autor=usuario, tipo=tipo, asunto=asunto[:200], cuerpo=cuerpo)
    accion.entidad_tipo = "buzon"
    accion.entidad_id = msg.pk
    # Push automático S2b.4
    from apps.taller_home.push_handlers import notificar_buzon_nuevo
    notificar_buzon_nuevo(msg, usuario)


@registrar("registrar_egreso")
def registrar_egreso(accion, usuario, contexto=None):
    """Crea un Egreso a partir del payload del dictado (DOC_06 §7).

    Payload esperado: monto, descripcion, centro_de_costo_slug, proyecto_slug?,
    proveedor_nombre?, pagado_por_slug?, solicitado_por_slug?, estado_pago?,
    metodo?, fecha?.
    """
    from datetime import date as _date

    from apps.tesoreria.models import CentroDeCosto, Egreso
    from apps.tesoreria.push_handlers import notificar_reembolso_pendiente

    payload = accion.payload or {}
    try:
        monto = float(payload.get("monto") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("`monto` inválido.") from exc
    if monto <= 0:
        raise ValueError("`monto` debe ser > 0.")
    descripcion = (payload.get("descripcion") or "").strip()
    if not descripcion:
        raise ValueError("`descripcion` requerida.")

    centro_slug = (payload.get("centro_de_costo_slug") or "otros").lower()
    centro = CentroDeCosto.objects.filter(slug=centro_slug, activo=True).first()
    if not centro:
        centro = CentroDeCosto.objects.filter(slug="otros", activo=True).first()
    if not centro:
        raise ValueError(f"Centro de costo `{centro_slug}` no encontrado y no hay fallback.")

    proyecto = None
    proyecto_slug = (payload.get("proyecto_slug") or "").lower()
    if proyecto_slug:
        proyecto = _resolver_proyecto(proyecto_slug, contexto)

    pagado_por_slug = (payload.get("pagado_por_slug") or "").lower()
    pagado_por = _resolver_usuario(pagado_por_slug, contexto) if pagado_por_slug else usuario

    solicitado_por = None
    solicitado_por_slug = (payload.get("solicitado_por_slug") or "").lower()
    if solicitado_por_slug:
        solicitado_por = _resolver_usuario(solicitado_por_slug, contexto)

    estado_pago = (payload.get("estado_pago") or "pagado").lower()
    if estado_pago not in {"pagado", "por_reembolsar", "pendiente"}:
        estado_pago = "pagado"
    metodo = (payload.get("metodo") or "transferencia").lower()
    if metodo not in {"transferencia", "tarjeta_empresa", "tarjeta_personal",
                      "efectivo", "cheque", "otro"}:
        metodo = "otro"
    if metodo == "tarjeta_personal" and estado_pago == "pagado":
        estado_pago = "por_reembolsar"

    import contextlib

    fecha_str = payload.get("fecha")
    fecha = _date.today()
    if fecha_str:
        with contextlib.suppress(ValueError):
            fecha = _date.fromisoformat(str(fecha_str)[:10])

    egreso = Egreso.objects.create(
        monto=monto, descripcion=descripcion[:300],
        proveedor_nombre=(payload.get("proveedor_nombre") or "")[:200],
        centro_de_costo=centro, proyecto=proyecto,
        pagado_por=pagado_por, solicitado_por=solicitado_por,
        estado_pago=estado_pago, metodo=metodo,
        origen="sala_juntas", fecha=fecha, creado_por=usuario,
    )
    accion.entidad_tipo = "egreso"
    accion.entidad_id = egreso.pk

    if estado_pago == "por_reembolsar":
        notificar_reembolso_pendiente(egreso, usuario)
