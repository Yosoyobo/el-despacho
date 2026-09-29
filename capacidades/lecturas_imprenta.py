"""Lecturas de La Imprenta para El Chalán (2026-09-29).

- `formato_documentos` — cómo están configurados los PDF: quién los arma, la
  hoja, la marca, qué datos del despacho hay capturados y, por cada tipo de
  documento, qué partes van apagadas y qué rótulos cambiaron. Gating
  `documentos` (`documentos.ver`).

Cambiar el formato NO se hace por chat: es la pantalla Ajustes → Documentos de
La Gerencia, que tiene vista previa, PDF de prueba e historial para deshacer —
nada de eso existe en una conversación, y un cambio de formato a ciegas frente
a un cliente es justo lo que la pantalla evita. `lib.dictado_catalogo` lo declara.

Los datos bancarios salen enmascarados (últimos 4 dígitos): el chat termina en
pantallas, notificaciones y registros donde una CLABE completa no tiene por qué ir.
"""

from __future__ import annotations

from .registro import Capacidad, registrar


def _enmascarar(valor: str) -> str:
    valor = (valor or "").strip()
    return f"…{valor[-4:]}" if len(valor) > 4 else ("capturado" if valor else "")


def _h_formato_documentos(args: dict, usuario) -> dict:
    from imprenta import config, esquema, servicios, tipos

    cfg_base = config.resolver(next(iter(tipos.TIPOS)))
    hoja = cfg_base.hoja
    marca = cfg_base.marca
    fuente = dict(esquema.OPCIONES_FUENTE).get(marca.get("fuente_cuerpo"), "Arial")
    d = cfg_base.despacho
    datos = {
        "nombre": d.get("nombre") or "",
        "razon_social": d.get("razon_social") or "",
        "rfc": d.get("rfc") or "",
        "telefono": d.get("telefono") or "",
        "correo": d.get("correo") or "",
        "web": d.get("web") or "",
        "banco": d.get("banco") or "",
        "cuenta": _enmascarar(d.get("cuenta")),
        "clabe": _enmascarar(d.get("clabe")),
        "firma": "con imagen" if cfg_base.firma.get("imagen") else "sin imagen",
        "firmante": cfg_base.firma.get("nombre") or "",
    }
    documentos = []
    for slug, (definicion, _) in tipos.TIPOS.items():
        cfg = config.resolver(slug)
        apagados = [b.etiqueta for b in definicion.bloques if not cfg.bloque(b.clave)]
        rotulos = {c.default: cfg.rotulo(c.clave, c.default) for c in definicion.columnas
                   if cfg.rotulo(c.clave, c.default) != c.default}
        documentos.append({
            "tipo": definicion.nombre,
            "partes_apagadas": apagados,
            "rotulos_cambiados": rotulos,
            "titulo": cfg.doc.get("titulo") or "el de siempre",
            "datos_del_despacho_que_ensena": [dict(esquema.DATOS_DESPACHO).get(x, x)
                                              for x in cfg.doc.get("datos_despacho") or []],
        })
    ultima = servicios.ultima_version()
    return {
        "quien_arma_el_pdf": dict(esquema.MOTORES).get(getattr(hoja, "motor", "auto"), "auto"),
        "hoja": {
            "tamano": getattr(hoja, "get_tamano_papel_display", lambda: "Carta")(),
            "margenes_pt": {
                "arriba": getattr(hoja, "margen_superior_pt", None),
                "abajo": getattr(hoja, "margen_inferior_pt", None),
                "izquierda": getattr(hoja, "margen_izquierdo_pt", None),
                "derecha": getattr(hoja, "margen_derecho_pt", None),
            },
            "interlineado": str(getattr(hoja, "interlineado", "")),
            "pie": getattr(hoja, "pie_texto", ""),
            "numera_paginas": getattr(hoja, "numerar_paginas", True),
        },
        "marca": {
            "logotipo": "propio" if marca.get("logo") else "el de Learning Center",
            "letra": fuente,
            "color_acento": marca.get("color_acento"),
            "color_texto": marca.get("color_texto"),
        },
        "datos_del_despacho": datos,
        "documentos": documentos,
        "ultimo_cambio": {
            "cuando": ultima.creado_en.isoformat() if ultima else None,
            "quien": (getattr(ultima.usuario, "email", "") if ultima and ultima.usuario else ""),
            "que": (ultima.resumen or [])[:8] if ultima else [],
        },
        "donde_se_cambia": "La Gerencia → Ajustes → Documentos (vista previa, PDF de prueba e historial).",
        "nota": "El formato no se cambia por chat: se cambia en esa pantalla.",
    }


_LECTURAS = {
    "formato_documentos": Capacidad(
        nombre="formato_documentos",
        descripcion=(
            "Cómo están configurados los documentos PDF (cotizaciones y los demás): "
            "quién los arma (Chromium o Google), la hoja y sus márgenes, la marca "
            "(logotipo, letra, colores), qué datos del despacho hay capturados (los "
            "bancarios enmascarados) y, por tipo de documento, qué partes van "
            "apagadas, qué rótulos cambiaron y qué datos del despacho enseña; más el "
            "último cambio. Cambiar el formato NO se hace por chat: es la pantalla "
            "Ajustes → Documentos de La Gerencia."
        ),
        args_schema={},
        gating="documentos", fn=_h_formato_documentos,
    ),
}

for _cap in _LECTURAS.values():
    registrar(_cap)
