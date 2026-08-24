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

    if conectado and texto:
        hallados = paperless.buscar(texto, 20)
        if hallados is None:
            fallo = True
        else:
            documentos = hallados
            # De quién es cada uno, de una sola consulta a NUESTRA base (no una
            # por documento, que sería un N+1 en la pantalla más usada).
            from papeleo.models import PapeleoLigado

            duenos: dict[int, list[str]] = {}
            filas = (PapeleoLigado.objects
                     .filter(documento_id__in=[d["id"] for d in documentos])
                     .select_related("cliente", "proyecto", "proveedor"))
            for f in filas:
                duenos.setdefault(f.documento_id, []).append(f.a_quien)
            for d in documentos:
                d["abrir"] = paperless.url_web(d["id"])
                d["de_quien"] = duenos.get(d["id"], [])

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
        "puede_ligar": puede_ligar_papeleo(request.user),
        "puede_subir": puede_subir_papeleo(request.user),
        "breadcrumb_items": [{"label": "Papeleo"}],
    })


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

    tarea = paperless.subir(archivo.read(), archivo.name,
                            titulo=(request.POST.get("titulo") or "").strip(),
                            etiquetas_ids=etiquetas)
    if tarea:
        # No se promete que ya quedó: el OCR corre después y tarda.
        messages.success(request, "Recibido. El archivo lo va a leer en unos "
                                  "minutos; hasta entonces no se puede buscar "
                                  "por su texto.")
        _emitir("papeleo.subido", request.user, {"nombre": archivo.name})
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


def _emitir(tipo: str, usuario, payload: dict) -> None:
    """Avisa por El Portavoz. Best-effort: no se cae una pantalla por esto."""
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        emitir(EventoPortavoz(tipo=tipo, actor_id=usuario.pk,
                              actor_email=usuario.email, payload=payload))
    except Exception:  # noqa: BLE001
        pass
