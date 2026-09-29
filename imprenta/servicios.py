"""Guardar, versionar y restaurar los ajustes de los documentos.

Todo cambio pasa por `guardar()`, que hace tres cosas en una transacción:

1. **Toma la «foto inicial» la primera vez.** Antes del primer cambio se guarda
   cómo estaba todo, para que «volver a esta versión» pueda regresar al
   documento de siempre aunque nadie lo haya fotografiado antes.
2. **Aplica los cambios** a `AjusteImprenta` (un ámbito por fila) y a la hoja
   general (`ajustes.ConfiguracionDocumento`).
3. **Toma la foto nueva** con el resumen en palabras de lo que cambió.

El testigo de edición pisada sale del mismo historial: la pantalla recuerda con
qué versión se abrió (`base`), y si al guardar alguien más guardó encima, se
comparan campo por campo lo que había al abrir, lo que hay hoy y lo que se manda.
Hay choque sólo si guardar reescribiría el cambio de otra persona — la misma
regla que `lib.edicion` aplica a los formularios de modelos.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from . import config, esquema, tipos
from .models import AjusteImprenta, VersionImprenta


def _hoja():
    from ajustes.models import ConfiguracionDocumento

    return ConfiguracionDocumento.obtener()


def hoja_como_dict(hoja=None) -> dict:
    hoja = hoja or _hoja()
    datos = {c.clave: getattr(hoja, c.clave) for c in esquema.HOJA.campos}
    datos["interlineado"] = str(datos["interlineado"])
    return datos


def foto_actual() -> dict:
    """Todos los ajustes de los documentos, tal como están guardados hoy."""
    return {
        "hoja": hoja_como_dict(),
        "ambitos": {a.ambito: dict(a.valores or {}) for a in AjusteImprenta.objects.all()},
    }


def _secciones(ambito: str):
    if ambito == "hoja":
        return (esquema.HOJA,)
    return config.secciones_de(ambito)


def _nombre(ambito: str) -> str:
    if ambito == "hoja":
        return esquema.HOJA.titulo
    for s in esquema.SECCIONES_GLOBALES:
        if s.clave == ambito:
            return s.titulo
    d = tipos.definicion(ambito)
    return d.nombre if d else ambito


def _valores(foto: dict, ambito: str) -> dict:
    if ambito == "hoja":
        return dict(foto.get("hoja") or {})
    return dict((foto.get("ambitos") or {}).get(ambito) or {})


def resumen(antes: dict, despues: dict) -> list[str]:
    """Lo que cambió entre dos fotos, en palabras y con el nombre de su parte."""
    ambitos = ["hoja", *sorted(set(antes.get("ambitos") or {})
                               | set(despues.get("ambitos") or {}))]
    lineas = []
    for ambito in ambitos:
        secciones = _secciones(ambito)
        if not secciones:
            continue
        a = esquema.mezclar(secciones, _valores(antes, ambito))
        d = esquema.mezclar(secciones, _valores(despues, ambito))
        for cambio in esquema.diferencias(secciones, a, d):
            lineas.append(f"{_nombre(ambito)} · {cambio}")
    return lineas


@dataclass
class Choque:
    """Guardar reescribiría lo que otra persona guardó mientras editabas."""

    version: VersionImprenta
    campos: list[str]


def ultima_version() -> VersionImprenta | None:
    return VersionImprenta.objects.select_related("usuario").first()


def revisar_choque(base: int | None, cambios: dict[str, dict]) -> Choque | None:
    """¿Se pisaría algo? `base` es la versión con la que se abrió la pantalla."""
    ultima = ultima_version()
    if ultima is None or base is None or ultima.pk == base:
        return None
    if base == 0:
        # Se abrió cuando aún no había historial: lo que vio es el «Estado
        # inicial», que se fotografía justo antes del primer guardado.
        primera = VersionImprenta.objects.order_by("creado_en", "pk").first()
        vista = primera.foto if primera else {}
    else:
        try:
            vista = VersionImprenta.objects.get(pk=base).foto
        except VersionImprenta.DoesNotExist:
            return None
    hoy = foto_actual()
    pisados = []
    for ambito, nuevos in cambios.items():
        secciones = _secciones(ambito)
        a = esquema.mezclar(secciones, _valores(vista, ambito))
        h = esquema.mezclar(secciones, _valores(hoy, ambito))
        for s in secciones:
            for c in s.campos:
                if c.clave not in nuevos:
                    continue
                cambio_en_base = esquema._norm(a.get(c.clave)) != esquema._norm(h.get(c.clave))
                reescribe = esquema._norm(nuevos[c.clave]) != esquema._norm(h.get(c.clave))
                if cambio_en_base and reescribe:
                    pisados.append(f"{_nombre(ambito)} · {c.etiqueta}")
    return Choque(ultima, pisados) if pisados else None


def _aplicar_hoja(valores: dict) -> None:
    from decimal import Decimal

    hoja = _hoja()
    for c in esquema.HOJA.campos:
        if c.clave in valores:
            valor = valores[c.clave]
            if c.clave == "interlineado":
                valor = Decimal(str(valor))
            setattr(hoja, c.clave, valor)
    hoja.save()


def _aplicar(ambito: str, valores: dict, usuario) -> None:
    if ambito == "hoja":
        _aplicar_hoja(valores)
        return
    fila, _ = AjusteImprenta.objects.get_or_create(ambito=ambito)
    fila.valores = {**(fila.valores or {}), **valores}
    fila.actualizado_por = usuario
    fila.save()


def guardar(cambios: dict[str, dict], usuario, motivo: str = "") -> VersionImprenta:
    """Aplica `{ambito: valores_limpios}` y deja su versión en el historial."""
    with transaction.atomic():
        antes = foto_actual()
        if not VersionImprenta.objects.exists():
            VersionImprenta.objects.create(
                usuario=None, foto=antes, resumen=[], motivo="Estado inicial")
        for ambito, valores in cambios.items():
            _aplicar(ambito, valores, usuario)
        despues = foto_actual()
        version = VersionImprenta.objects.create(
            usuario=usuario, foto=despues, resumen=resumen(antes, despues),
            motivo=motivo or ", ".join(_nombre(a) for a in cambios))
    config.olvidar()
    _avisar(usuario, version)
    return version


def restaurar(version: VersionImprenta, usuario) -> VersionImprenta:
    """Deja todo como en `version` y toma una versión nueva que lo diga."""
    foto = version.foto or {}
    with transaction.atomic():
        antes = foto_actual()
        _aplicar_hoja(foto.get("hoja") or {})
        guardados = foto.get("ambitos") or {}
        for fila in AjusteImprenta.objects.all():
            if fila.ambito not in guardados:
                fila.valores = {}
                fila.actualizado_por = usuario
                fila.save()
        for ambito, valores in guardados.items():
            fila, _ = AjusteImprenta.objects.get_or_create(ambito=ambito)
            fila.valores = dict(valores)
            fila.actualizado_por = usuario
            fila.save()
        despues = foto_actual()
        nueva = VersionImprenta.objects.create(
            usuario=usuario, foto=despues, resumen=resumen(antes, despues),
            motivo=f"Volvió a la versión del {_fecha(version)}", restaurada_de=version)
    config.olvidar()
    _avisar(usuario, nueva)
    return nueva


def _fecha(version: VersionImprenta) -> str:
    from django.utils import timezone

    return timezone.localtime(version.creado_en).strftime("%d/%m/%Y %H:%M")


def _avisar(usuario, version: VersionImprenta) -> None:
    """Evento del Portavoz (el mismo tipo de siempre para esta pantalla)."""
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        emitir(EventoPortavoz(
            tipo="ajuste.documentos_configurado",
            actor_id=getattr(usuario, "pk", None),
            actor_email=getattr(usuario, "email", None),
            payload={"version_id": version.pk, "motivo": version.motivo,
                     "cambios": len(version.resumen or [])},
        ))
    except Exception:  # noqa: BLE001 — el aviso no detiene el guardado
        pass


__all__ = ["Choque", "foto_actual", "guardar", "hoja_como_dict", "restaurar",
           "resumen", "revisar_choque", "ultima_version"]
