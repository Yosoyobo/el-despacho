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

from . import _gate, registrar


def _fecha_compromiso_proyecto(fecha_str):
    """Convierte una fecha ISO ('YYYY-MM-DD') a datetime aware a las 12:00 PM.

    C6 S-LC-Feedback-V6: Proyecto.fecha_compromiso pasó a DateTimeField con
    hora; el Dictado recibe sólo una fecha del LLM, así que fijamos mediodía.
    """
    from datetime import date as _d
    from datetime import datetime as _dt
    from datetime import time as _t

    from django.utils import timezone as _tz

    dia = _d.fromisoformat(str(fecha_str)[:10])
    naive = _dt.combine(dia, _t(12, 0))
    return _tz.make_aware(naive) if _tz.is_naive(naive) else naive


CAMPOS_PROYECTO_PERMITIDOS = {"estado", "monto_cotizado", "fecha_compromiso", "descripcion"}
CAMPOS_TAREA_PERMITIDOS = {"estado", "prioridad", "asignado_slug", "fecha_compromiso", "hora", "tipo"}
CAMPOS_CLIENTE_PERMITIDOS = {
    "razon_social", "rfc", "nombre_contacto", "email_contacto",
    "telefono", "direccion", "notas", "estado",
}
ESTADOS_PROYECTO_VALIDOS = {
    "por_cotizar", "esperando_respuesta", "en_proceso_diseno",
    "en_proceso_produccion", "entregado", "cerrado", "en_pausa", "cancelado",
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


def _campos_a_actualizar(payload: dict, permitidos: set[str]) -> dict:
    """Devuelve los campos a actualizar.

    El LLM a veces anida los cambios en `campos` y otras veces los pone al
    nivel superior del payload (junto al slug). Aceptamos ambos: si `campos`
    no trae nada útil, recogemos las claves permitidas del nivel superior.
    Esto cierra el bug 'pedí actualizar una fecha y no funcionó' (la fecha
    llegaba arriba y `campos` quedaba vacío → "Sin campos válidos").
    """
    campos = payload.get("campos")
    if isinstance(campos, dict) and any(k in permitidos for k in campos):
        return {k: v for k, v in campos.items() if k in permitidos}
    return {k: v for k, v in (payload or {}).items() if k in permitidos}


def _fecha_hora_de(payload: dict) -> tuple[str | None, str | None]:
    """Devuelve (fecha 'YYYY-MM-DD'|None, hora 'HH:MM[:SS]'|None).

    `Tarea.fecha_compromiso` es DateField y `Tarea.hora` es TimeField aparte,
    pero el LLM a veces mete la hora dentro de `fecha_compromiso`
    ('2026-06-18T15:00:00' o '2026-06-18 15:00'). Aquí la separamos: la parte de
    fecha va a `fecha_compromiso` y la de hora a `hora` (si no vino ya un `hora`
    explícito). Cierra el bug 'el valor tiene un formato de fecha inválido'.
    """
    fecha = (str(payload.get("fecha_compromiso")).strip() if payload.get("fecha_compromiso") else None)
    hora = (str(payload.get("hora")).strip() if payload.get("hora") else None)
    if fecha and ("T" in fecha or " " in fecha):
        sep = "T" if "T" in fecha else " "
        parte_fecha, _, parte_hora = fecha.partition(sep)
        fecha = parte_fecha.strip() or None
        if not hora and parte_hora.strip():
            hora = parte_hora.strip()
    if hora:
        hora = hora.replace("hrs", "").replace("h", "").strip()[:8]  # HH:MM o HH:MM:SS
    return fecha or None, hora or None


def _resolver_tarea(tarea_id, contexto: dict | None = None):
    """Resuelve una Tarea por id numérico o por `@accion_N` (Capa 1 — referencia
    a una tarea creada en una acción anterior del mismo dictado)."""
    from apps.el_pizarron.models import Tarea
    if tarea_id in (None, ""):
        raise ValueError("Falta `tarea_id`.")
    s = _limpiar_slug(str(tarea_id))
    ref = _ref_anterior(s, contexto, "tarea")
    if ref:
        t = Tarea.objects.filter(pk=ref).select_related("proyecto", "proyecto__cliente").first()
        if t:
            return t
    if s.isdigit():
        t = Tarea.objects.filter(pk=int(s)).select_related("proyecto", "proyecto__cliente").first()
        if t:
            return t
    raise ValueError(f"Tarea `{tarea_id}` no encontrada.")


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


def _resolver_proyecto_para(payload: dict, contexto: dict | None = None):
    """Resuelve el proyecto de una tarea/mandado.

    Toda tarea/entrega cuelga de un proyecto (FK obligatoria). Si el usuario solo
    dio un cliente ('entregar players para $noko-devs'), no hay proyecto_slug:
    caemos al cliente y usamos su ÚNICO proyecto activo. Si tiene varios o ninguno,
    levantamos un error claro y accionable (que el chat le muestra al usuario)."""
    slug = (payload.get("proyecto_slug") or "").strip()
    if slug:
        return _resolver_proyecto(slug, contexto)
    cli_slug = (payload.get("cliente_slug") or "").strip()
    if not cli_slug:
        raise ValueError("Falta el proyecto: dime de qué proyecto es (ej. #LC-0001).")
    cliente = _resolver_cliente(cli_slug, contexto)
    from apps.los_proyectos.models import Proyecto
    activos = list(
        Proyecto.objects.filter(cliente=cliente)
        .exclude(estado__in=("entregado", "cancelado"))
        .order_by("-creado_en")
    )
    if len(activos) == 1:
        return activos[0]
    if not activos:
        raise ValueError(
            f"{cliente.razon_social} no tiene proyectos activos. Crea uno primero "
            "o dime el proyecto.")
    codigos = ", ".join(f"#{p.codigo}" for p in activos[:6])
    raise ValueError(
        f"{cliente.razon_social} tiene varios proyectos ({codigos}). ¿En cuál lo registro?")


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
    _gate(usuario, "es_admin", "crear proyectos")

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
            fecha_compromiso = _fecha_compromiso_proyecto(fecha_str)
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
    _gate(usuario, "puede_editar_cartera", "crear clientes")
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
    _gate(usuario, "puede_editar_cartera", "actualizar clientes")
    cliente = _resolver_cliente((accion.payload.get("cliente_slug") or "").lower(), contexto)
    campos = _campos_a_actualizar(accion.payload or {}, CAMPOS_CLIENTE_PERMITIDOS)
    aplicado = []
    for k, v in campos.items():
        setattr(cliente, k, v)
        aplicado.append(k)
    if not aplicado:
        raise ValueError("Sin campos válidos para actualizar.")
    cliente.save(update_fields=[*aplicado, "actualizado_en"])
    accion.entidad_tipo = "cliente"
    accion.entidad_id = cliente.pk


@registrar("actualizar_proyecto")
def actualizar_proyecto(accion, usuario, contexto=None):
    _gate(usuario, "es_admin", "actualizar proyectos")
    proyecto = _resolver_proyecto(accion.payload.get("proyecto_slug", ""), contexto)
    campos = _campos_a_actualizar(accion.payload or {}, CAMPOS_PROYECTO_PERMITIDOS)
    aplicado = []
    for k, v in campos.items():
        # C6 S-LC-Feedback-V6: fecha_compromiso del proyecto es datetime con
        # hora (default 12:00). El LLM manda una fecha ISO; la convertimos.
        if k == "fecha_compromiso" and v:
            try:
                v = _fecha_compromiso_proyecto(v)
            except ValueError as exc:
                raise ValueError(f"`fecha_compromiso` inválida: {v}") from exc
        setattr(proyecto, k, v)
        aplicado.append(k)
    if not aplicado:
        raise ValueError("Sin campos válidos para actualizar.")
    proyecto.save(update_fields=[*aplicado, "actualizado_en"])
    accion.entidad_tipo = "proyecto"
    accion.entidad_id = proyecto.pk


@registrar("asignar_usuario_proyecto")
def asignar_usuario_proyecto(accion, usuario, contexto=None):
    _gate(usuario, "es_admin", "asignar usuarios a proyectos")
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
    proyecto = _resolver_proyecto_para(accion.payload, contexto)
    titulo = (accion.payload.get("titulo") or "").strip()
    if not titulo:
        raise ValueError("Falta `titulo` en payload.")
    asignado_slug = (accion.payload.get("asignado_slug") or "").strip()
    asignada_a = _resolver_usuario(asignado_slug, contexto) if asignado_slug else None
    fecha, hora = _fecha_hora_de(accion.payload)
    prioridad = (accion.payload.get("prioridad") or "media").lower()
    if prioridad not in {"baja", "media", "alta"}:
        prioridad = "media"
    tipo = (accion.payload.get("tipo") or "tarea").lower()
    if tipo not in {"tarea", "entrega", "junta", "recoger"}:
        tipo = "tarea"
    from apps.el_pizarron.models import Tarea
    t = Tarea.objects.create(
        proyecto=proyecto, titulo=titulo[:200], asignada_a=asignada_a,
        fecha_compromiso=fecha, hora=hora, prioridad=prioridad, tipo=tipo, creado_por=usuario,
    )
    accion.entidad_tipo = "tarea"
    accion.entidad_id = t.pk

    # S-LC-Proyecto-V2: si es entrega/recoger, resuelve el runner (manual por
    # `runner_slug`, o auto "el menos cargado" si `runner_auto`/sin slug).
    from apps.el_pizarron import runners
    if runners.requiere_runner(t):
        runner_slug = (accion.payload.get("runner_slug") or "").strip()
        if runner_slug:
            runners.asignar_runner(t, _resolver_usuario(runner_slug, contexto), actor=usuario)
        else:
            runners.asignar_runner_auto(t, actor=usuario)

    # Dispara push automático (S2b.4) si hay asignado.
    if asignada_a:
        from apps.taller_home.push_handlers import notificar_tarea_asignada
        notificar_tarea_asignada(t, usuario)


@registrar("actualizar_tarea")
def actualizar_tarea(accion, usuario, contexto=None):
    tarea = _resolver_tarea(accion.payload.get("tarea_id"), contexto)
    campos = _campos_a_actualizar(accion.payload or {}, CAMPOS_TAREA_PERMITIDOS)
    # Normaliza fecha/hora si vienen (el LLM puede meter la hora en la fecha).
    if "fecha_compromiso" in campos or "hora" in campos:
        fecha, hora = _fecha_hora_de(accion.payload)
        if "fecha_compromiso" in campos:
            campos["fecha_compromiso"] = fecha
        if hora is not None:
            campos["hora"] = hora
    aplicado: list[str] = []
    for k, v in campos.items():
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


@registrar("asignar_runner")
def asignar_runner_ejec(accion, usuario, contexto=None):
    """S-LC-Proyecto-V2: asigna un runner (repartidor) a una tarea de entrega/
    recolección. `runner_slug` lo fija manualmente; sin él (o con `auto`) lo
    designa el sistema (el menos cargado)."""
    from apps.el_pizarron import runners
    tarea = _resolver_tarea(accion.payload.get("tarea_id"), contexto)
    if not runners.requiere_runner(tarea):
        raise ValueError("Solo las tareas de tipo entrega/recoger llevan runner.")
    runner_slug = (accion.payload.get("runner_slug") or "").strip()
    if runner_slug:
        runners.asignar_runner(tarea, _resolver_usuario(runner_slug, contexto), actor=usuario)
    else:
        if runners.asignar_runner_auto(tarea, actor=usuario) is None:
            raise ValueError("No hay runners disponibles para asignar.")
    accion.entidad_tipo = "tarea"
    accion.entidad_id = tarea.pk


def _resolver_destino(payload, contexto=None):
    """Resuelve el destino de un mandado a (lat, lng, etiqueta). Acepta, en orden:
    `destino_lat`+`destino_lng`, `poi` (lugar conocido por nombre) o `destino_texto`
    (dirección libre → Nominatim). Devuelve None si no se pudo resolver."""
    lat = payload.get("destino_lat")
    lng = payload.get("destino_lng")
    if lat is not None and lng is not None:
        try:
            return (float(lat), float(lng), (payload.get("destino_texto") or "").strip()[:200])
        except (TypeError, ValueError):
            pass
    poi_txt = (payload.get("poi") or "").strip()
    if poi_txt:
        from apps.el_pizarron.poi import resolver_poi
        p = resolver_poi(poi_txt)
        if p:
            return (p["lat"], p["lng"], p["label"][:200])
    texto = (payload.get("destino_texto") or "").strip()
    if texto:
        from lib.geocoding import primer_resultado
        r = primer_resultado(texto)
        if r:
            return (r["lat"], r["lng"], (r["nombre"] or texto)[:200])
    return None


def _destino_de_cliente(cliente):
    """Destino de respaldo cuando el mandado no trae uno explícito: la dirección
    del cliente (geocodificada) o, si no, su última ubicación geolocalizada (de
    una visita de El Checador). Devuelve (lat, lng, etiqueta) o None. Best-effort,
    nunca lanza — un mandado sin destino sigue siendo válido (se fija a mano)."""
    if not cliente:
        return None
    direccion = (getattr(cliente, "direccion", "") or "").strip()
    if direccion:
        try:
            from lib.geocoding import primer_resultado
            r = primer_resultado(direccion)
            if r:
                return (r["lat"], r["lng"], direccion[:200])
        except Exception:  # noqa: BLE001 — geocoder caído no debe romper la creación
            pass
    try:
        from apps.checador.services import ultima_ubicacion_de
        v = ultima_ubicacion_de(cliente=cliente)
        if v and v.lat is not None and v.lng is not None:
            etiqueta = (getattr(cliente, "razon_social", "") or "Cliente")[:200]
            return (float(v.lat), float(v.lng), etiqueta)
    except Exception:  # noqa: BLE001
        pass
    return None


@registrar("crear_mandado")
def crear_mandado(accion, usuario, contexto=None):
    """S-Mandados-V2: crea una entrega/recolección con destino resuelto desde una
    dirección o el nombre de un lugar conocido (POI). Internamente es una Tarea de
    tipo entrega/recoger con destino fijado → el signal crea el Mandado y se
    auto-asigna el runner más cercano. Mismo nivel de acceso que crear_tarea."""
    payload = accion.payload or {}
    proyecto = _resolver_proyecto_para(payload, contexto)
    titulo = (payload.get("titulo") or "").strip()
    if not titulo:
        raise ValueError("Falta `titulo` del mandado.")
    tipo = (payload.get("tipo") or "recoger").lower()
    if tipo not in {"entrega", "recoger"}:
        tipo = "recoger"
    asignado_slug = (payload.get("asignado_slug") or "").strip()
    asignada_a = _resolver_usuario(asignado_slug, contexto) if asignado_slug else None
    fecha, hora = _fecha_hora_de(payload)

    from apps.el_pizarron.models import Tarea
    t = Tarea.objects.create(
        proyecto=proyecto, titulo=titulo[:200], asignada_a=asignada_a,
        fecha_compromiso=fecha, hora=hora, tipo=tipo, creado_por=usuario,
    )
    # Fija el destino ANTES de auto-asignar para que la cercanía aplique.
    # Si no vino destino explícito, cae a la dirección/ubicación del cliente.
    destino = _resolver_destino(payload, contexto) or _destino_de_cliente(getattr(proyecto, "cliente", None))
    if destino:
        t.destino_lat, t.destino_lng, t.destino_etiqueta = destino
        t.save(update_fields=["destino_lat", "destino_lng", "destino_etiqueta"])

    accion.entidad_tipo = "tarea"
    accion.entidad_id = t.pk

    from apps.el_pizarron import runners
    runner_slug = (payload.get("runner_slug") or "").strip()
    if runner_slug:
        runners.asignar_runner(t, _resolver_usuario(runner_slug, contexto), actor=usuario)
    else:
        runners.asignar_runner_auto(t, actor=usuario)


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
    _gate(usuario, "puede_ver_finanzas", "registrar egresos")
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
