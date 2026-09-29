"""Las pantallas del papeleo, en El Taller (operación).

La configuración vive en La Gerencia; buscar y ligar es trabajo del día, así
que va aquí — el criterio con el que las Campañas se mudaron de una a otra.

Todo lo que pinta viene de una de dos fuentes, y la diferencia importa: la
BÚSQUEDA le pregunta a Paperless (es lo único que sabe leer el texto de un
escaneo), y **de quién es cada documento sale de nuestra base**. Por eso una
ficha con papeleo ligado se sigue pintando aunque el archivo esté caído.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from lib.permisos import puede_ligar_papeleo, puede_subir_papeleo, puede_ver_papeleo


def _prohibido(mensaje: str = "No tienes permiso para ver el papeleo."):
    return HttpResponse(mensaje, status=403)


def _con_duenos(documentos: list[dict]) -> list[dict]:
    """Le pega a cada documento de quién es y por dónde se ve.

    De quién es sale de NUESTRA base en **una sola consulta** — una por
    documento sería un N+1 en la pantalla más usada del módulo. Y el enlace
    apunta adentro de El Despacho, no a Paperless: su dirección sólo existe en
    el tailnet y desde el celular en la calle no abre.
    """
    from papeleo.models import PapeleoLigado

    duenos: dict[int, list[str]] = {}
    filas = (PapeleoLigado.objects
             .filter(documento_id__in=[d["id"] for d in documentos])
             .select_related("cliente", "proyecto", "proveedor"))
    for f in filas:
        duenos.setdefault(f.documento_id, []).append(f.a_quien)
    for d in documentos:
        d["de_quien"] = duenos.get(d["id"], [])
        d["ver"] = f"/papeleo/{d['id']}/"
        d["miniatura"] = f"/papeleo/{d['id']}/miniatura"
    return documentos


@login_required
def buscar(request):
    """La pantalla de búsqueda. Sin llave, lo dice en vez de salir vacía."""
    from lib import paperless

    if not puede_ver_papeleo(request.user):
        return _prohibido()

    texto = (request.GET.get("q") or "").strip()
    conectado = paperless.esta_configurado()
    documentos: list[dict] = []
    fallo = False
    total = None

    if conectado:
        # Sin palabra se enseña lo último que entró. Una pantalla de archivo que
        # sólo contesta si le escribes algo obliga a adivinar una palabra para
        # descubrir que el documento existe: eso no es «ver el archivo».
        hallados = paperless.buscar(texto, 20) if texto else paperless.listar(20)
        if hallados is None:
            fallo = True
        else:
            documentos = _con_duenos(hallados)
            total = paperless.cuantos()

    # Para el selector de «¿de quién es?». Sólo si esta persona puede ligar:
    # a quien sólo lee, la lista de clientes no le sirve de nada.
    clientes = []
    if puede_ligar_papeleo(request.user):
        from apps.la_cartera.models import Cliente

        clientes = list(Cliente.objects.filter(activo=True)
                        .order_by("razon_social")[:500])

    return render(request, "papeleo/buscar.html", {
        "texto": texto,
        "clientes": clientes,
        "documentos": documentos,
        "conectado": conectado,
        "fallo": fallo,
        "total": total,
        "puede_ligar": puede_ligar_papeleo(request.user),
        "puede_subir": puede_subir_papeleo(request.user),
        "breadcrumb_items": [{"label": "Papeleo"}],
    })


@login_required
def ver(request, documento_id: int):
    """La ficha de UN documento, con el documento a la vista.

    Antes el único camino era «Abrir →» a Paperless: otra app, otra sesión, y
    una dirección que **sólo existe dentro del tailnet** — desde el celular en
    la calle no abre. Aquí se ve dentro de El Despacho, con el permiso que ya
    se comprobó, y al lado se dice de quién es y se puede ligar.
    """
    from lib import paperless

    if not puede_ver_papeleo(request.user):
        return _prohibido()

    if not paperless.esta_configurado():
        return render(request, "papeleo/ver.html", {
            "conectado": False, "documento": None,
            "breadcrumb_items": [{"label": "Papeleo", "url": "/papeleo/"},
                                 {"label": "Documento"}],
        })

    doc = paperless.detalle(documento_id)
    if doc is None:
        # No se distingue «no existe» de «no contestó», y está bien: las dos se
        # arreglan igual desde aquí (volver y reintentar), y afirmar la que no
        # es manda a buscar el problema donde no está.
        messages.error(request, "No se pudo traer ese documento del archivo.")
        return redirect("papeleo-buscar")

    doc = _con_duenos([doc])[0]

    clientes = []
    if puede_ligar_papeleo(request.user):
        from apps.la_cartera.models import Cliente

        clientes = list(Cliente.objects.filter(activo=True)
                        .order_by("razon_social")[:500])

    return render(request, "papeleo/ver.html", {
        "conectado": True,
        "documento": doc,
        "clientes": clientes,
        "puede_ligar": puede_ligar_papeleo(request.user),
        "abrir_en_paperless": paperless.url_web(documento_id),
        "breadcrumb_items": [{"label": "Papeleo", "url": "/papeleo/"},
                             {"label": doc["titulo"]}],
    })


def _servir(request, documento_id: int, cara: str, *, descargar: bool = False):
    """El proxy. Comprueba el permiso y entrega los bytes del documento.

    Es un proxy y no un enlace público a propósito: el papeleo son contratos y
    comprobantes del negocio. Quien no puede ver papeleo no lo ve, aunque
    adivine el número del documento.
    """
    from lib import paperless

    if not puede_ver_papeleo(request.user):
        return _prohibido()

    traido = paperless.archivo(documento_id, cara)
    if traido is None:
        return HttpResponse("No se pudo traer el documento.", status=404)

    contenido, tipo = traido
    r = HttpResponse(contenido, content_type=tipo)
    # `inline` para que se vea sin bajarlo; `attachment` sólo cuando lo piden.
    disp = "attachment" if descargar else "inline"
    r["Content-Disposition"] = f'{disp}; filename="documento-{documento_id}"'
    # La miniatura sí se puede guardar un rato: no cambia. El documento no, por
    # si alguien pierde el permiso entre una visita y la siguiente.
    r["Cache-Control"] = "private, max-age=3600" if cara == "thumb" else "private, no-store"
    r["X-Content-Type-Options"] = "nosniff"
    return r


@login_required
def archivo(request, documento_id: int):
    """El documento, para verlo en la página."""
    return _servir(request, documento_id, "preview")


@login_required
def descargar(request, documento_id: int):
    """El documento, para guardarlo."""
    return _servir(request, documento_id, "download", descargar=True)


@login_required
def miniatura(request, documento_id: int):
    """La imagen chica de la tarjeta."""
    return _servir(request, documento_id, "thumb")


@login_required
@require_POST
def ligar(request, documento_id: int):
    """Dice de quién es un documento. Una sola entidad, la que venga."""
    from papeleo import ligado

    if not puede_ligar_papeleo(request.user):
        return _prohibido("No tienes permiso para ligar papeleo.")

    destino = {}
    if pk := (request.POST.get("cliente") or "").strip():
        from apps.la_cartera.models import Cliente

        destino["cliente"] = Cliente.objects.filter(pk=pk).first()
    elif pk := (request.POST.get("proyecto") or "").strip():
        from apps.los_proyectos.models import Proyecto

        destino["proyecto"] = Proyecto.objects.filter(pk=pk).first()
    elif pk := (request.POST.get("proveedor") or "").strip():
        from apps.el_catalogo.models import Proveedor

        destino["proveedor"] = Proveedor.objects.filter(pk=pk).first()

    if not destino or not next(iter(destino.values())):
        messages.error(request, "Dime de quién es: un cliente, un proyecto o un "
                                "proveedor.")
    else:
        try:
            fila = ligado.ligar(documento_id, titulo=request.POST.get("titulo") or "",
                                usuario=request.user, **destino)
            messages.success(request, f"Quedó ligado a {fila.a_quien}.")
            _emitir("papeleo.ligado", request.user,
                    {"documento_id": documento_id, "a_quien": fila.a_quien})
        except ValueError as exc:
            messages.error(request, str(exc))

    return redirect(request.POST.get("volver") or "papeleo-buscar")


@login_required
@require_POST
def desligar(request, pk: int):
    """Quita una liga. No toca el documento en Paperless."""
    from papeleo.models import PapeleoLigado

    if not puede_ligar_papeleo(request.user):
        return _prohibido("No tienes permiso para ligar papeleo.")

    fila = PapeleoLigado.objects.filter(pk=pk).first()
    if fila is not None:
        quien = fila.a_quien
        fila.delete()
        messages.success(request, f"Se quitó la liga con {quien}.")
        _emitir("papeleo.desligado", request.user, {"a_quien": quien})

    # Desde el recuadro de una ficha llega por HTMX (el botón no puede ir en un
    # <form>: el sidebar de esas fichas ya vive dentro del de autoguardado).
    # Se contesta con HX-Redirect para que la página se repinte y el mensaje se
    # vea — patrón Wave 5.
    if request.headers.get("HX-Request") == "true":
        destino = request.headers.get("HX-Current-URL") or "/papeleo/"
        return HttpResponse(status=204, headers={"HX-Redirect": destino})
    return redirect(request.POST.get("volver") or "papeleo-buscar")


@login_required
@require_POST
def subir(request):
    """Manda un archivo al archivo del papeleo, desde El Despacho."""
    from lib import paperless

    if not puede_subir_papeleo(request.user):
        return _prohibido("No tienes permiso para subir papeleo.")

    archivo = request.FILES.get("archivo")
    if archivo is None:
        messages.error(request, "No elegiste ningún archivo.")
        return redirect("papeleo-buscar")

    etiquetas = []
    try:
        from ajustes.models import ConfiguracionPapeleo

        marca = (ConfiguracionPapeleo.obtener().etiqueta_entrada or "").strip()
        if marca and (eid := paperless.id_de_etiqueta(marca)):
            etiquetas.append(eid)
    except Exception:  # noqa: BLE001 — sin etiqueta se archiva igual
        pass

    # Word y Excel se vuelven PDF antes de entrar (Paperless sin Office no los
    # lee). Si el convertidor no contesta, se archiva el original y se avisa.
    from lib.a_pdf import preparar

    preparado = preparar(archivo.read(), archivo.name)

    tarea = paperless.subir(preparado.contenido, preparado.nombre,
                            titulo=(request.POST.get("titulo") or "").strip(),
                            etiquetas_ids=etiquetas)
    if tarea:
        # No se promete que ya quedó: el OCR corre después y tarda.
        messages.success(request, "Recibido. El archivo lo va a leer en unos "
                                  "minutos; hasta entonces no se puede buscar "
                                  "por su texto.")
        if preparado.convertido:
            messages.info(request, f"«{archivo.name}» se convirtió a PDF antes de "
                                   f"archivarlo («{preparado.nombre}»).")
        if preparado.aviso:
            messages.warning(request, f"{preparado.aviso} Puede que no se "
                                      "encuentre por lo que dice adentro.")
        _emitir("papeleo.subido", request.user,
                {"nombre": preparado.nombre, "convertido": preparado.convertido})
    else:
        messages.error(request, "El archivo de papeleo no aceptó el documento.")
    return redirect("papeleo-buscar")


@login_required
def sugerencias(request):
    """A quién se le podría ligar un documento — para el buscador de la pantalla."""
    if not puede_ligar_papeleo(request.user):
        return JsonResponse({"resultados": []}, status=403)

    from lib.busqueda import q_texto

    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"resultados": []})

    salida = []
    from apps.el_catalogo.models import Proveedor
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto

    for c in Cliente.objects.filter(q_texto(q, "razon_social"), activo=True)[:5]:
        salida.append({"tipo": "cliente", "id": c.pk, "nombre": str(c)})
    for p in Proyecto.objects.filter(
            q_texto(q, "nombre", "codigo"), archivado=False)[:5]:
        salida.append({"tipo": "proyecto", "id": p.pk,
                       "nombre": f"{p.nombre} ({p.codigo})"})
    for v in Proveedor.objects.filter(q_texto(q, "razon_social"), activo=True)[:5]:
        salida.append({"tipo": "proveedor", "id": v.pk, "nombre": str(v)})
    return JsonResponse({"resultados": salida})


# ── Unir varios documentos en un solo PDF ──────────────────────────────────
#
# Se elige en la pantalla del papeleo, Gotenberg los junta en el orden en que se
# marcaron, y el resultado se ofrece para bajarlo y —si se puede subir— para
# archivarlo como un documento más. Sirve para mandar UN archivo en vez de cinco:
# quien recibe cinco adjuntos abre el primero que ve.
#
# **El resultado vive en El Almacén, no en la sesión**: un PDF de varios megas no
# cabe en una cookie ni conviene en Redis. Lo que sí va en la sesión es la LISTA
# de lo que ESTA persona unió, y es el candado: la descarga sólo sirve claves que
# están ahí. Sin eso, quien tuviera permiso de ver el papeleo podría pedir
# cualquier archivo del almacén adivinando su llave.

#: Cuántos documentos se juntan de una vez. Veinte contratos en un archivo ya es
#: un expediente; más, y la conversión se vuelve lenta para nada.
MAX_UNIR = 20
_SESION_UNIDOS = "papeleo_unidos"
#: Cuántos resultados se recuerdan por persona. Los viejos se olvidan (el archivo
#: se queda en el almacén; sólo deja de estar a su alcance desde aquí).
_MAX_RECORDADOS = 10


def _ids_a_unir(request) -> list[int]:
    """Los documentos marcados, en el orden en que se marcaron.

    Las casillas llegan en el orden de la página (lo más reciente primero), que
    casi nunca es el orden que se quiere en el expediente. La pantalla anota el
    orden de los clics en `orden`; si no llegó o no cuadra, se usa el de la
    página. Nunca se une algo que no se marcó.
    """
    marcados: list[int] = []
    for v in request.POST.getlist("doc"):
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n > 0 and n not in marcados:
            marcados.append(n)

    orden: list[int] = []
    for v in (request.POST.get("orden") or "").split(","):
        try:
            n = int(v.strip())
        except (TypeError, ValueError):
            continue
        if n in marcados and n not in orden:
            orden.append(n)
    orden += [n for n in marcados if n not in orden]
    return orden[:MAX_UNIR]


def _es_pdf(contenido: bytes) -> bool:
    return b"%PDF" in (contenido or b"")[:1024]


def _unidos(request) -> dict:
    return dict(request.session.get(_SESION_UNIDOS) or {})


def _recordar_unido(request, clave: str, datos: dict) -> None:
    unidos = _unidos(request)
    unidos[clave] = datos
    # Se conservan los más recientes: el dict guarda el orden de inserción.
    while len(unidos) > _MAX_RECORDADOS:
        unidos.pop(next(iter(unidos)))
    request.session[_SESION_UNIDOS] = unidos


def _clave_valida(clave: str) -> bool:
    import re

    return bool(re.fullmatch(r"[0-9a-f]{64}", clave or ""))


@login_required
@require_POST
def unir(request):
    """Junta los documentos marcados en un solo PDF."""
    from django.utils import timezone

    from lib import almacen, gotenberg, paperless

    if not puede_ver_papeleo(request.user):
        return _prohibido()

    ids = _ids_a_unir(request)
    if len(ids) < 2:
        messages.error(request, "Marca al menos dos documentos para unirlos.")
        return redirect("papeleo-buscar")
    if not paperless.esta_configurado():
        messages.error(request, "El archivo de papeleo no está conectado.")
        return redirect("papeleo-buscar")
    if not gotenberg.disponible():
        # Se dice qué falta en vez de un «no se pudo»: es el convertidor, no el
        # archivo, y cada uno se arregla en un lugar distinto.
        messages.error(request, "El servicio que une los PDF no está contestando. "
                                "Vuelve a intentar en un momento.")
        return redirect("papeleo-buscar")

    pdfs: list[bytes] = []
    incluidos: list[dict] = []
    saltados: list[dict] = []
    for doc_id in ids:
        titulo = (request.POST.get(f"titulo_{doc_id}") or f"Documento #{doc_id}")[:160]
        traido = paperless.archivo(doc_id, "download")
        if traido is None:
            saltados.append({"id": doc_id, "titulo": titulo,
                             "motivo": "no se pudo traer del archivo"})
            continue
        contenido, _tipo = traido
        if not _es_pdf(contenido):
            # Una foto suelta o un Excel que entró sin convertir: Gotenberg sólo
            # une PDF. Se dice cuál se quedó fuera en lugar de fallar todo.
            saltados.append({"id": doc_id, "titulo": titulo,
                             "motivo": "no es PDF, no se puede unir"})
            continue
        pdfs.append(contenido)
        incluidos.append({"id": doc_id, "titulo": titulo})

    if len(pdfs) < 2:
        detalle = "; ".join(f"«{s['titulo']}»: {s['motivo']}" for s in saltados)
        messages.error(request, "No quedaron al menos dos documentos que se puedan "
                                f"unir. {detalle}".strip())
        return redirect("papeleo-buscar")

    try:
        unido = gotenberg.unir(pdfs)
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"No se pudieron unir los documentos: {exc}")
        return redirect("papeleo-buscar")

    nombre = f"Papeleo unido {timezone.localtime():%Y-%m-%d %H%M}.pdf"
    try:
        guardado = almacen.guardar_bytes(unido, mime="application/pdf", nombre=nombre)
    except Exception as exc:  # noqa: BLE001 — disco lleno, permisos
        messages.error(request, f"Se unieron pero no se pudieron guardar: {exc}")
        return redirect("papeleo-buscar")

    clave = guardado["id"]
    _recordar_unido(request, clave, {
        "nombre": nombre, "incluidos": incluidos, "saltados": saltados,
        "archivado": False,
    })
    _emitir("papeleo.subido", request.user,
            {"nombre": nombre, "unidos": len(incluidos), "origen": "unir"})
    return redirect("papeleo-unido", clave=clave)


def _datos_unido(request, clave: str):
    """Los datos de un resultado DE ESTA PERSONA, o None. Es el candado."""
    if not _clave_valida(clave):
        return None
    return _unidos(request).get(clave)


@login_required
def unido(request, clave: str):
    """El resultado: bajarlo y, si se puede, archivarlo."""
    if not puede_ver_papeleo(request.user):
        return _prohibido()
    datos = _datos_unido(request, clave)
    if datos is None:
        messages.error(request, "Ese PDF unido ya no está disponible; vuelve a "
                                "unir los documentos.")
        return redirect("papeleo-buscar")
    return render(request, "papeleo/unido.html", {
        "clave": clave,
        "datos": datos,
        "titulo_sugerido": datos["nombre"][:-4],
        "puede_subir": puede_subir_papeleo(request.user),
        "breadcrumb_items": [{"label": "Papeleo", "url": "/papeleo/"},
                             {"label": "PDF unido"}],
    })


@login_required
def unido_bajar(request, clave: str):
    """El PDF unido, como descarga."""
    from urllib.parse import quote

    from lib import almacen

    if not puede_ver_papeleo(request.user):
        return _prohibido()
    datos = _datos_unido(request, clave)
    if datos is None:
        return HttpResponse("Ese PDF unido ya no está disponible.", status=404)
    try:
        contenido, _mime, _nombre = almacen.leer(clave)
    except Exception:  # noqa: BLE001
        return HttpResponse("No se encontró el PDF unido.", status=404)

    nombre = datos["nombre"]
    ascii_ = nombre.encode("ascii", "ignore").decode() or "papeleo-unido.pdf"
    r = HttpResponse(contenido, content_type="application/pdf")
    r["Content-Disposition"] = (f'attachment; filename="{ascii_}"; '
                                f"filename*=UTF-8''{quote(nombre)}")
    r["Cache-Control"] = "private, no-store"
    r["X-Content-Type-Options"] = "nosniff"
    return r


@login_required
@require_POST
def unido_archivar(request, clave: str):
    """Manda el PDF unido al archivo, como un documento más."""
    from lib import almacen, paperless

    if not puede_subir_papeleo(request.user):
        return _prohibido("No tienes permiso para subir papeleo.")
    datos = _datos_unido(request, clave)
    if datos is None:
        messages.error(request, "Ese PDF unido ya no está disponible.")
        return redirect("papeleo-buscar")
    if datos.get("archivado"):
        # Dos clics no dejan dos copias en el archivo.
        messages.info(request, "Ese PDF unido ya se mandó al archivo.")
        return redirect("papeleo-unido", clave=clave)

    try:
        contenido, _mime, _nombre = almacen.leer(clave)
    except Exception:  # noqa: BLE001
        messages.error(request, "No se encontró el PDF unido.")
        return redirect("papeleo-buscar")

    etiquetas = []
    try:
        from ajustes.models import ConfiguracionPapeleo

        marca = (ConfiguracionPapeleo.obtener().etiqueta_entrada or "").strip()
        if marca and (eid := paperless.id_de_etiqueta(marca)):
            etiquetas.append(eid)
    except Exception:  # noqa: BLE001 — sin etiqueta se archiva igual
        pass

    titulo = (request.POST.get("titulo") or datos["nombre"][:-4]).strip()[:160]
    tarea = paperless.subir(contenido, datos["nombre"], titulo=titulo,
                            etiquetas_ids=etiquetas)
    if not tarea:
        messages.error(request, "El archivo de papeleo no aceptó el documento.")
        return redirect("papeleo-unido", clave=clave)

    datos["archivado"] = True
    _recordar_unido(request, clave, datos)
    messages.success(request, "Va camino al archivo. En unos minutos se puede "
                              "buscar por lo que dice adentro.")
    _emitir("papeleo.subido", request.user,
            {"nombre": datos["nombre"], "origen": "unir"})
    return redirect("papeleo-buscar")


def _emitir(tipo: str, usuario, payload: dict) -> None:
    """Avisa por El Portavoz. Best-effort: no se cae una pantalla por esto."""
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        emitir(EventoPortavoz(tipo=tipo, actor_id=usuario.pk,
                              actor_email=usuario.email, payload=payload))
    except Exception:  # noqa: BLE001
        pass
