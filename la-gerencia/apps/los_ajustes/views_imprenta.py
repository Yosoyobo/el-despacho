"""Gerencia → Ajustes → Documentos: La Imprenta.

Oscar (2026-09-29): «quiero poder editar, modificar y personalizar aún más la
generación de PDFs». La pantalla que había movía la hoja y el motor; ésta es
esa misma más la marca, los datos del despacho y lo propio de cada tipo de
documento, con **vista previa en vivo sin guardar**, un **PDF de prueba** que
sale del motor de verdad e **historial con «volver a esta versión»**.

Cada pestaña es un formulario propio y se guarda sola. Qué hace falta para
cambiar cada una (permiso granular, §4 #20; super_admin es failsafe):

  general · marca · tipos  → `documentos.editar_estilo`
  despacho (datos y firma) → `documentos.editar_datos`
  restaurar una versión    → las tres de edición

Los nombres de los campos de la hoja general van SIN prefijo (`motor`,
`margen_superior_pt`…), como en la pantalla anterior; los demás llevan el de
su ámbito (`marca__color_acento`, `cotizacion__bloque_fotos`).
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from lib import permisos
from lib.permisos import requiere_permiso

#: Pestaña → (título, ámbitos que guarda, acción de `documentos` que exige).
PESTANAS_FIJAS = {
    "general": ("Hoja y motor", ("hoja",), "editar_estilo"),
    "marca": ("Marca y tablas", ("marca", "tablas"), "editar_estilo"),
    "despacho": ("Datos y firma", ("despacho", "firma"), "editar_datos"),
}

#: Tipos de imagen que se aceptan para el logotipo y la firma.
_MIMES_IMAGEN = {"image/png", "image/jpeg", "image/webp"}
_MAX_IMAGEN = 5 * 1024 * 1024


def _pestanas() -> dict:
    from imprenta.tipos import TIPOS

    pestanas = dict(PESTANAS_FIJAS)
    for slug, (definicion, _) in TIPOS.items():
        pestanas[slug] = (definicion.nombre, (slug,), "editar_estilo")
    return pestanas


def _claves_permitidas(user, ambito: str) -> set[str]:
    """Los campos de un ámbito que `user` puede guardar, sección por sección."""
    from imprenta import config

    claves = set()
    for s in config.secciones_de(ambito):
        if _puede(user, s.permiso):
            claves.update(c.clave for c in s.campos)
    return claves


def _puede(user, accion: str) -> bool:
    return {
        "ver": permisos.puede_ver_documentos,
        "editar_estilo": permisos.puede_editar_estilo_documentos,
        "editar_notas": permisos.puede_editar_notas_documentos,
        "editar_datos": permisos.puede_editar_datos_documentos,
    }[accion](user)


# ── Leer el formulario ──────────────────────────────────────────────────────


def _leer_hoja(post) -> dict:
    """La hoja general con los nombres de siempre (sin prefijo)."""
    from imprenta import esquema

    datos = {c.clave: post.get(c.clave) for c in esquema.HOJA.campos}
    return {c.clave: c.limpiar(datos[c.clave]) for c in esquema.HOJA.campos}


def _leer_ambito(post, archivos, ambito: str, guardado: dict, *, subir: bool) -> tuple[dict, list[str]]:
    """Los valores limpios de un ámbito + los avisos (una imagen rechazada).

    Las imágenes no viajan en el campo: el formulario manda la llave actual en
    un oculto, un archivo nuevo en `<campo>_archivo` y `<campo>_quitar` para
    volver a la de siempre. `subir=False` (la vista previa) no guarda archivos:
    se previsualiza con la imagen ya guardada.
    """
    from imprenta import config, esquema

    prefijo = f"{ambito}__"
    secciones = config.secciones_de(ambito)
    valores = esquema.limpiar(secciones, post, prefijo)
    avisos = []
    for s in secciones:
        for c in s.campos:
            if c.tipo != esquema.IMAGEN:
                continue
            actual = guardado.get(c.clave, "")
            valores[c.clave] = actual
            if post.get(f"{prefijo}{c.clave}_quitar"):
                valores[c.clave] = ""
                continue
            archivo = archivos.get(f"{prefijo}{c.clave}_archivo") if subir else None
            if archivo is None:
                continue
            tipo = (getattr(archivo, "content_type", "") or "").lower()
            if tipo not in _MIMES_IMAGEN or archivo.size > _MAX_IMAGEN:
                avisos.append(f"{c.etiqueta}: sube un PNG, JPG o WebP de hasta 5 MB.")
                continue
            from lib import almacen

            meta = almacen.guardar_fileobj(archivo, mime=tipo, nombre=archivo.name)
            valores[c.clave] = meta.get("id", "") or actual
    return valores, avisos


def _borrador(request, pestana: str) -> dict:
    """{ambito: valores} del formulario de una pestaña, sin guardar nada."""
    from imprenta import config

    _, ambitos, _ = _pestanas()[pestana]
    guardado = config.guardado()
    borrador = {}
    for ambito in ambitos:
        if ambito == "hoja":
            borrador["hoja"] = _leer_hoja(request.POST)
        else:
            borrador[ambito], _ = _leer_ambito(
                request.POST, request.FILES, ambito, guardado.get(ambito, {}), subir=False)
    return borrador


# ── La pantalla ─────────────────────────────────────────────────────────────


@requiere_permiso("documentos", "ver")
@require_http_methods(["GET", "POST"])
def documentos_panel(request):
    from imprenta import config, servicios

    pestanas = _pestanas()
    # Un POST sin `seccion` viene de la pantalla anterior (o de su prueba): es la
    # hoja general.
    pestana = (request.POST.get("seccion") if request.method == "POST"
               else request.GET.get("tab")) or "general"
    if pestana not in pestanas and pestana != "historial":
        pestana = "general"

    if request.method == "POST":
        if pestana == "historial":
            raise Http404
        titulo, ambitos, accion = pestanas[pestana]
        guardado = config.guardado()
        cambios, avisos = {}, []
        for ambito in ambitos:
            if ambito == "hoja":
                if _puede(request.user, accion):
                    cambios["hoja"] = _leer_hoja(request.POST)
                continue
            # Cada sección pide SU permiso (las notas, `editar_notas`): lo de las
            # que no puede cambiar se ignora, no se guarda.
            permitidas = _claves_permitidas(request.user, ambito)
            if not permitidas:
                continue
            valores, av = _leer_ambito(
                request.POST, request.FILES, ambito, guardado.get(ambito, {}), subir=True)
            cambios[ambito] = {k: v for k, v in valores.items() if k in permitidas}
            avisos.extend(av)
        if not cambios:
            return HttpResponseForbidden("No tienes permiso para cambiar esta parte de los documentos.")

        base = request.POST.get("base")
        base = int(base) if (base or "").isdigit() else None
        if not request.POST.get("forzar"):
            choque = servicios.revisar_choque(base, cambios)
            if choque is not None:
                # Se repinta con lo que MANDÓ, no con lo guardado: así «Guardar lo
                # mío de todos modos» reenvía exactamente eso.
                return _pintar(request, pestana, choque=choque, status=409, enviados=cambios)

        version = servicios.guardar(cambios, request.user, motivo=titulo)
        for aviso in avisos:
            messages.warning(request, aviso)
        if version.resumen:
            messages.success(request, f"Guardado. {len(version.resumen)} cambio(s) en «{titulo}».")
        else:
            messages.info(request, "Guardado. No había nada distinto.")
        return redirect(f"{reverse('ajustes-documentos')}?tab={pestana}")

    return _pintar(request, pestana)


def _pintar(request, pestana: str, *, choque=None, status: int = 200, enviados=None):
    from imprenta import config, esquema, servicios, tipos

    pestanas = _pestanas()
    guardado = config.guardado()
    enviados = enviados or {}
    ultima = servicios.ultima_version()

    contexto = {
        "pestana": pestana,
        # Sin `url`: `_tabs.html` arma `?tab=<clave>` solo. Con url, su
        # `|default:…|add:clave` le volvía a pegar la clave (`?tab=marcamarca`) y
        # todas las pestañas caían de vuelta en la primera.
        "tabs": [{"clave": c, "etiqueta": t} for c, (t, _, _) in pestanas.items()]
        + [{"clave": "historial", "etiqueta": "Historial"}],
        "base": ultima.pk if ultima else 0,
        "choque": choque,
        "puede": {a: _puede(request.user, a)
                  for a in ("editar_estilo", "editar_notas", "editar_datos")},
    }

    if pestana == "historial":
        from imprenta.models import VersionImprenta

        contexto["versiones"] = list(VersionImprenta.objects.select_related("usuario")[:60])
        contexto["puede_restaurar"] = all(contexto["puede"].values())
        return render(request, "ajustes/imprenta/panel.html", contexto, status=status)

    titulo, ambitos, accion = pestanas[pestana]
    contexto["titulo_pestana"] = titulo
    # Se puede guardar si alguna sección de la pestaña es suya (las notas
    # tienen su propio permiso; la hoja general, el de estilo).
    contexto["puede_guardar"] = (
        _puede(request.user, accion) if pestana == "general"
        else any(_claves_permitidas(request.user, a) for a in ambitos))

    # Qué documento se previsualiza: el de la pestaña, o la cotización.
    tipo_vista = pestana if tipos.definicion(pestana) else next(iter(tipos.TIPOS))
    contexto["tipo_vista"] = tipo_vista
    contexto["ejemplos"] = tipos.ejemplos(tipo_vista, usuario=request.user)
    contexto["nombre_tipo_vista"] = tipos.definicion(tipo_vista).nombre

    if pestana == "general":
        from lib import gotenberg

        cfg = config._hoja_guardada()
        if cfg is not None and "hoja" in enviados:
            import copy

            cfg = copy.copy(cfg)
            for clave, valor in enviados["hoja"].items():
                setattr(cfg, clave, valor)
        try:
            gotenberg_vivo = gotenberg.disponible(forzar=True)
        except Exception:  # noqa: BLE001
            gotenberg_vivo = False
        from ajustes.models.documento import MOTORES, TAMANOS_CHOICES

        contexto.update({"cfg": cfg, "motores": MOTORES, "tamanos": TAMANOS_CHOICES,
                         "gotenberg_vivo": gotenberg_vivo,
                         "alto_util_pt": cfg.alto_util_pt if cfg else 0})
    else:
        grupos = []
        for ambito in ambitos:
            valores = esquema.mezclar(config.secciones_de(ambito),
                                      {**guardado.get(ambito, {}), **enviados.get(ambito, {})})
            for s in config.secciones_de(ambito):
                grupos.append({"ambito": ambito, "seccion": s,
                               "editable": _puede(request.user, s.permiso),
                               "campos": [_campo_vista(ambito, c, valores) for c in s.campos]})
        contexto["grupos"] = grupos
    return render(request, "ajustes/imprenta/panel.html", contexto, status=status)


def _campo_vista(ambito: str, c, valores: dict) -> dict:
    """Lo que necesita la plantilla para pintar un campo del esquema."""
    from imprenta import config

    valor = valores.get(c.clave)
    vista = {"c": c, "nombre": f"{ambito}__{c.clave}", "valor": valor,
             "id": f"f-{ambito}-{c.clave}"}
    if c.tipo == "imagen":
        vista["url"] = config.url_imagen(valor) if valor else ""
    if c.tipo == "multi":
        vista["marcados"] = set(valor or [])
    return vista


# ── Vista previa y PDF de prueba ────────────────────────────────────────────


def _config_de_vista(request, destino: str):
    from imprenta import config, tipos

    pestana = request.POST.get("seccion") or "general"
    if pestana not in _pestanas():
        pestana = "general"
    tipo = request.POST.get("tipo") or ""
    if not tipos.definicion(tipo):
        tipo = next(iter(tipos.TIPOS))
    return tipo, config.resolver(tipo, borrador=_borrador(request, pestana), destino=destino)


def _ejemplo(request, tipo: str) -> int | None:
    from imprenta import tipos

    crudo = request.POST.get("ejemplo") or ""
    validos = {pk for pk, _ in tipos.ejemplos(tipo, limite=50, usuario=request.user)}
    if crudo.isdigit() and int(crudo) in validos:
        return int(crudo)
    return next(iter(validos), None) if validos else None


@requiere_permiso("documentos", "ver")
@require_POST
def documentos_vista(request):
    """El documento dibujado con lo que hay en el formulario, SIN guardar."""
    from imprenta import tipos

    tipo, cfg = _config_de_vista(request, "pantalla")
    pk = _ejemplo(request, tipo)
    if pk is None:
        return HttpResponse(_sin_ejemplos(tipos.definicion(tipo).nombre))
    html = tipos.adaptador(tipo).html(pk, cfg, preview=True, sin_barra=True)
    resp = HttpResponse(html)
    resp["Cache-Control"] = "no-store"
    return resp


@requiere_permiso("documentos", "ver")
@require_POST
def documentos_vista_pdf(request):
    """El PDF de prueba: lo arma el motor de verdad, con los cambios sin guardar.

    No se guarda en Drive ni toca el documento: sólo se descarga para ver cómo
    saldría. Si el motor propio no contesta se dice, en vez de caer a Google —
    que no respetaría la mitad de lo que se está probando.
    """
    from imprenta import tipos
    from lib import gotenberg

    tipo, cfg = _config_de_vista(request, "motor")
    pk = _ejemplo(request, tipo)
    if pk is None:
        return HttpResponse(_sin_ejemplos(tipos.definicion(tipo).nombre))
    if not gotenberg.disponible(forzar=True):
        return HttpResponse(
            "<p style='font-family:sans-serif;padding:2rem'>El motor propio (Chromium) "
            "no está contestando, así que no se puede armar el PDF de prueba. La vista "
            "previa sigue funcionando.</p>", status=503)
    ad = tipos.adaptador(tipo)
    try:
        pdf = gotenberg.html_a_pdf(ad.html(pk, cfg, preview=False), pagina=ad.pagina(pk, cfg))
    except Exception as exc:  # noqa: BLE001
        return HttpResponse(
            f"<p style='font-family:sans-serif;padding:2rem'>No se pudo armar el PDF: {exc}</p>",
            status=502)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = 'inline; filename="prueba.pdf"'
    resp["Cache-Control"] = "no-store"
    return resp


def _sin_ejemplos(nombre: str) -> str:
    return ("<p style='font-family:sans-serif;padding:2rem;color:#667085'>No hay "
            f"ningún documento de tipo «{nombre}» que puedas previsualizar: o todavía no "
            "existe uno, o tu permiso no alcanza para ver ese módulo.</p>")


@requiere_permiso("documentos", "ver")
@require_POST
def documentos_restaurar(request, pk: int):
    """Vuelve todos los ajustes a como estaban en una versión."""
    from imprenta import servicios
    from imprenta.models import VersionImprenta

    if not all(_puede(request.user, a) for a in ("editar_estilo", "editar_notas", "editar_datos")):
        return HttpResponseForbidden("Volver a una versión cambia todo: hace falta poder editar todo.")
    version = get_object_or_404(VersionImprenta, pk=pk)
    nueva = servicios.restaurar(version, request.user)
    messages.success(request, f"Listo: los documentos quedaron como en esa versión "
                              f"({len(nueva.resumen or [])} cambio(s)).")
    return redirect(f"{reverse('ajustes-documentos')}?tab=historial")
