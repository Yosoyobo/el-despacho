"""Lo que El Chalán puede hacer con las herramientas del servidor.

Oscar, 2026-08-24: «si puedo clickear, teclear, lo puede hacer el chalán». Las
piezas estaban instaladas y él no las alcanzaba — podía armar un PDF, mandarlo
al archivo y convertir un Word, y no lo sabía.

Mismo contrato que el resto: `(accion, usuario, contexto)`, lanza `ValueError`
si algo no cuadra, y **nada se aplica sin la confirmación humana** que garantiza
`services.aplicar` (§20). El permiso se vuelve a comprobar aquí aunque el prompt
ya filtre por rol: el prompt es una sugerencia, esto es la puerta.
"""

from __future__ import annotations

from . import _gate, registrar


def _payload(accion) -> dict:
    return accion.payload if hasattr(accion, "payload") else (accion or {})


def _apunta_a_cotizacion(accion, cot) -> None:
    """Deja anotado en la acción a qué cotización llevó, para el botón «Ir a la
    cotización» del resultado. `services.aplicar` descarta lo que devuelve el
    ejecutor; lo que lee es `accion.entidad_tipo/entidad_id` (como hacen los
    ejecutores de `avanzados.py`). Una acción de prueba (dict) no lleva campos."""
    if hasattr(accion, "entidad_tipo"):
        accion.entidad_tipo = "cotizacion"
        accion.entidad_id = cot.pk


def _cotizacion(codigo: str):
    from apps.cotizaciones.models import Cotizacion

    cod = (codigo or "").strip()
    if not cod:
        raise ValueError("Falta decir de cuál cotización.")
    cot = Cotizacion.objects.filter(codigo__iexact=cod).first()
    if cot is None:
        raise ValueError(f"No existe la cotización «{cod}».")
    return cot


@registrar("generar_pdf_cotizacion")
def generar_pdf_cotizacion(accion, usuario, contexto=None):
    """Arma (o rehace) el PDF de una cotización.

    Es lo mismo que el botón de la pantalla; sirve para cuando alguien pide
    «mándame el PDF de la COT-2026-0044» sin ir a buscarla.
    """
    _gate(usuario, "puede_ver_cotizaciones", "generar el PDF de una cotización")
    from apps.cotizaciones import services

    cot = _cotizacion(_payload(accion).get("codigo", ""))
    res = services.generar_pdf(cot, usuario)
    if not getattr(res, "ok", False):
        raise ValueError(
            f"No se pudo armar el PDF: {getattr(res, 'error', 'sin detalle')}")
    _apunta_a_cotizacion(accion, cot)
    return {"entidad_tipo": "cotizacion", "entidad_id": cot.pk,
            "resumen": f"PDF de {cot.codigo} listo."}


@registrar("archivar_documento")
def archivar_documento(accion, usuario, contexto=None):
    """Manda al archivo del papeleo el PDF de una cotización.

    El archivo lo pasa por el lector de texto y lo indexa solo, así que después
    se encuentra por cualquier palabra que diga adentro.
    """
    _gate(usuario, "puede_subir_papeleo", "mandar documentos al archivo")
    from lib import paperless

    if not paperless.esta_configurado():
        raise ValueError(
            "El archivo no está conectado: falta la llave de Paperless en "
            "Gerencia → Papeleo.")

    cot = _cotizacion(_payload(accion).get("codigo", ""))
    if not cot.pdf_file_id:
        raise ValueError(
            f"{cot.codigo} todavía no tiene PDF. Propón primero generarlo.")

    from lib import almacen

    try:
        # Misma firma que la descarga de Drive: (contenido, mime, nombre).
        contenido, _mime, _nombre = almacen.leer(cot.pdf_file_id)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo leer el PDF de {cot.codigo}: {exc}") from exc

    if not contenido:
        raise ValueError(f"El PDF de {cot.codigo} está vacío o no se encontró.")

    nombre = f"{getattr(cot, 'nombre_pdf', cot.codigo)}.pdf"
    if not paperless.subir(contenido, nombre, titulo=nombre[:-4]):
        raise ValueError("El archivo no aceptó el documento.")
    # `subir` devuelve el id de la TAREA: el lector de texto corre después.
    # Prometer «ya quedó archivado» sería mentir por unos minutos.
    _apunta_a_cotizacion(accion, cot)
    return {"entidad_tipo": "cotizacion", "entidad_id": cot.pk,
            "resumen": (f"{cot.codigo} va camino al archivo. Tarda unos minutos "
                        "en poderse buscar por su texto.")}


@registrar("convertir_a_pdf")
def convertir_a_pdf(accion, usuario, contexto=None):
    """Convierte un Word o Excel guardado a PDF.

    Pensado para lo que llega de proveedores: se vuelve PDF sin que nadie tenga
    que abrir Office.
    """
    _gate(usuario, "puede_ver_cotizaciones", "convertir documentos")
    from lib import almacen, gotenberg

    p = _payload(accion)
    clave = str(p.get("archivo") or p.get("clave") or "").strip()
    nombre = str(p.get("nombre") or "documento.docx").strip()
    if not clave:
        raise ValueError("Falta decir qué archivo convertir.")
    if not gotenberg.es_office(nombre):
        raise ValueError(f"«{nombre}» no es un documento de Office.")

    try:
        contenido, _mime, _nombre = almacen.leer(clave)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo leer el archivo: {exc}") from exc
    if not contenido:
        raise ValueError("El archivo está vacío o no se encontró.")

    pdf = gotenberg.office_a_pdf(contenido, nombre)
    destino = nombre.rsplit(".", 1)[0] + ".pdf"
    guardado = almacen.guardar_bytes(pdf, nombre=destino, mime="application/pdf")
    # El Almacén devuelve la llave en `id` (antes se leía `clave`, que no existe,
    # y el resultado caía siempre al nombre del archivo).
    return {"entidad_tipo": "archivo",
            "entidad_id": (guardado or {}).get("id") or destino,
            "resumen": f"«{nombre}» convertido a PDF."}


@registrar("anexar_a_cotizacion")
def anexar_a_cotizacion(accion, usuario, contexto=None):
    """Pega un documento del archivo del papeleo al final de una cotización.

    Sep28: en el chat no se sube un archivo a una cotización, pero sí se puede
    decir «anéxale a la COT-2026-0044 la ficha técnica del papeleo #45» — el
    documento ya está en el archivo, y de ahí se trae.

    Pide DOS permisos: editar cotizaciones (cambia el documento que ve el
    cliente) y ver el papeleo (se está leyendo un documento del archivo). Tener
    uno solo no alcanza: con el primero sin el segundo se podría sacar al PDF de
    un cliente un contrato que no se tiene permiso de ver.
    """
    _gate(usuario, "puede_editar_cotizaciones", "anexar documentos a una cotización")
    _gate(usuario, "puede_ver_papeleo", "leer el archivo del papeleo")
    from apps.cotizaciones import anexos

    from lib import paperless

    if not paperless.esta_configurado():
        raise ValueError(
            "El archivo no está conectado: falta la llave de Paperless en "
            "Gerencia → Papeleo.")

    p = _payload(accion)
    cot = _cotizacion(p.get("codigo", ""))
    if not cot.permite_editar_texto:
        raise ValueError(f"{cot.codigo} ya está cerrada: su documento no se modifica.")
    try:
        documento_id = int(str(p.get("documento_id") or p.get("documento") or "")
                           .lstrip("#").strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Falta decir qué documento del papeleo anexar (su número, el que "
            "devuelve `buscar_papeleo`).") from exc

    res = anexos.anexar_desde_papeleo(cot, documento_id, usuario)
    if not res.ok:
        raise ValueError(res.mensaje)
    _apunta_a_cotizacion(accion, cot)
    return {"entidad_tipo": "cotizacion", "entidad_id": cot.pk,
            "resumen": f"{res.mensaje} Va al final del PDF de {cot.codigo}."}
