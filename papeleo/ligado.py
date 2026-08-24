"""Decidir de quién es un documento, y guardarlo.

Dos caminos, y el automático es deliberadamente cobarde:

- **A mano** (`ligar`): alguien abre el papeleo, ve el documento y dice de quién
  es. Es la verdad, sin discusión.
- **Solo** (`ligar_automatico`): al entrar un documento se busca en su texto a
  quién menciona. **Sólo liga cuando no hay duda.** Si el texto menciona dos
  clientes, no elige: lo deja sin ligar y dice por qué. Un documento sin ligar
  se arregla en diez segundos; uno ligado al cliente equivocado manda el
  contrato de alguien a la ficha de otro, y eso nadie lo nota hasta que es
  caro.

El criterio de comparación es el de `lib.nombres`: sin acentos, sin puntuación
y sin terminación mercantil, para que «OPTIMIST S.A. DE C.V.» y «Optimist»
sean el mismo.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Tope de filas que se recorren al comparar en memoria. Un despacho no tiene
#: diez mil clientes, y sin tope un catálogo grande vuelve lenta cada entrada.
MAX_CANDIDATOS = 2000


def _cfg():
    from ajustes.models import ConfiguracionPapeleo

    return ConfiguracionPapeleo.obtener()


def candidatos(texto: str, minimo: int | None = None) -> dict:
    """A quién menciona el texto. Devuelve listas, no decide nada.

    Quien decide es `ligar_automatico`, y sólo si hay exactamente uno.
    """
    from lib.nombres import menciona

    if minimo is None:
        try:
            minimo = _cfg().minimo_caracteres_nombre
        except Exception:  # noqa: BLE001 — sin base, el default del modelo
            minimo = 6

    texto = (texto or "").strip()
    salida: dict[str, list] = {"clientes": [], "proyectos": [], "proveedores": []}
    if not texto:
        return salida

    try:
        from apps.la_cartera.models import Cliente
    except Exception:  # noqa: BLE001 — Gerencia sí las instala; una app suelta, no
        Cliente = None
    try:
        from apps.el_catalogo.models import Proveedor
    except Exception:  # noqa: BLE001
        Proveedor = None
    try:
        from apps.los_proyectos.models import Proyecto
    except Exception:  # noqa: BLE001
        Proyecto = None

    if Cliente is not None:
        for c in Cliente.objects.filter(activo=True)[:MAX_CANDIDATOS]:
            nombres = [c.razon_social, getattr(c, "razon_social_fiscal", "")]
            # También sus razones sociales alternas: el papeleo suele venir a
            # nombre de la que factura, no de la que todos usan de boca.
            try:
                nombres += [r.razon_social for r in c.razones_sociales.all()]
            except Exception:  # noqa: BLE001 — sin esa relación, con las dos basta
                pass
            if any(menciona(texto, n, minimo) for n in nombres if n):
                salida["clientes"].append(c)

    if Proveedor is not None:
        for p in Proveedor.objects.filter(activo=True)[:MAX_CANDIDATOS]:
            if menciona(texto, p.razon_social, minimo):
                salida["proveedores"].append(p)

    if Proyecto is not None:
        # El código (LC-0044) es exacto y corto: se busca literal, sin el
        # mínimo de letras, porque no aparece por casualidad.
        crudo = texto.upper()
        for pr in Proyecto.objects.filter(archivado=False)[:MAX_CANDIDATOS]:
            if (pr.codigo and pr.codigo.upper() in crudo) or menciona(
                    texto, pr.nombre or "", minimo):
                salida["proyectos"].append(pr)

    return salida


def ligar(documento_id: int, *, titulo: str = "", cliente=None, proyecto=None,
          proveedor=None, usuario=None, automatico: bool = False):
    """Guarda la liga. Idempotente: dos veces la misma no duplica.

    Exige exactamente una entidad — es lo mismo que exige la base, y fallar
    aquí con un mensaje claro es mejor que fallar allá con un IntegrityError.
    """
    from papeleo.models import PapeleoLigado

    dadas = [x for x in (cliente, proyecto, proveedor) if x is not None]
    if len(dadas) != 1:
        raise ValueError("Un documento se liga a exactamente una cosa: "
                         "cliente, proyecto o proveedor.")

    fila, creada = PapeleoLigado.objects.get_or_create(
        documento_id=int(documento_id),
        cliente=cliente, proyecto=proyecto, proveedor=proveedor,
        defaults={"titulo": (titulo or "")[:200], "ligado_por": usuario,
                  "automatico": automatico},
    )
    # Si ya existía y el título cambió en Paperless, se refresca la copia.
    if not creada and titulo and fila.titulo != titulo[:200]:
        fila.titulo = titulo[:200]
        fila.save(update_fields=["titulo"])
    return fila


def ligar_automatico(documento_id: int, *, titulo: str = "", texto: str = "",
                     usuario=None) -> dict:
    """Intenta ligar solo. Devuelve qué pasó, en español, y nunca lanza.

    La respuesta lleva `ligado` (la fila o None) y `motivo` — el motivo importa
    tanto como el resultado: «menciona a dos clientes» le dice a una persona
    qué hacer, «no se pudo» no le dice nada.
    """
    try:
        if not _cfg().ligar_automatico:
            return {"ligado": None, "motivo": "El ligado automático está apagado."}
    except Exception:  # noqa: BLE001 — sin configuración no se liga solo
        return {"ligado": None, "motivo": "No se pudo leer la configuración."}

    try:
        encontrados = candidatos(f"{titulo}\n{texto}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("papeleo: no se pudo buscar a quién ligar: %s", exc)
        return {"ligado": None, "motivo": "No se pudo revisar el texto."}

    # El proyecto gana sobre el cliente: es más específico, y un documento que
    # nombra el proyecto casi siempre nombra también a su cliente.
    for llave, campo in (("proyectos", "proyecto"), ("clientes", "cliente"),
                         ("proveedores", "proveedor")):
        halla = encontrados[llave]
        if len(halla) == 1:
            try:
                fila = ligar(documento_id, titulo=titulo, usuario=usuario,
                             automatico=True, **{campo: halla[0]})
            except Exception as exc:  # noqa: BLE001
                logger.warning("papeleo: no se pudo ligar #%s: %s", documento_id, exc)
                return {"ligado": None, "motivo": "No se pudo guardar la liga."}
            return {"ligado": fila, "motivo": f"Menciona a {fila.a_quien}."}
        if len(halla) > 1:
            nombres = ", ".join(str(x) for x in halla[:3])
            return {"ligado": None,
                    "motivo": f"Menciona a varios ({nombres}); mejor decídelo tú."}

    return {"ligado": None, "motivo": "No se reconoció a nadie en el texto."}


def papeleo_de(entidad, limite: int = 25) -> list:
    """El papeleo ligado a un cliente, proyecto o proveedor. Consulta la BASE.

    No le pregunta a Paperless: así la ficha se pinta igual de rápido y sigue
    pintándose si el archivo está caído.
    """
    from papeleo.models import PapeleoLigado

    campo = {"Cliente": "cliente", "Proyecto": "proyecto",
             "Proveedor": "proveedor"}.get(type(entidad).__name__)
    if not campo:
        return []
    return list(PapeleoLigado.objects.filter(**{campo: entidad})[:limite])


__all__ = ["MAX_CANDIDATOS", "candidatos", "ligar", "ligar_automatico", "papeleo_de"]
