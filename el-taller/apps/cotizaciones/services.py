"""Services de Las Cotizaciones.

Cubre transiciones de estado y emisión de eventos Portavoz.
Los cálculos viven en `Cotizacion.calcular_totales` para que el detalle
sea consultable sin importar este módulo.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Cotizacion


def _emitir(tipo: str, cot: Cotizacion, actor, payload_extra: dict | None = None):
    payload = {
        "cotizacion_id": cot.id,
        "codigo": cot.codigo,
        "cliente_id": cot.cliente_id,
        "estado": cot.estado,
    }
    if payload_extra:
        payload.update(payload_extra)
    emitir(EventoPortavoz(
        tipo=tipo,
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload=payload,
    ))


def emitir_creada(cot: Cotizacion, actor):
    _emitir("cotizacion.creada", cot, actor, {"titulo": cot.titulo})


def emitir_eliminada(cot: Cotizacion, actor):
    """Borrado permanente (LC 2026-07-25). Se emite ANTES del delete para que el
    payload conserve código/cliente/estado."""
    _emitir("cotizacion.eliminada", cot, actor, {"titulo": cot.titulo})


def construir_html_pdf(cot: Cotizacion, *, preview: bool = False) -> str:
    """Renderiza el HTML imprimible de la cotización (template `pdf.html`).

    Las imágenes van con **URL absoluta, pública y firmada**: el PDF lo genera
    Google convirtiendo este HTML, y Google baja las imágenes desde sus
    servidores de forma anónima (ver `lib/almacen.py`). Una ruta relativa o
    el proxy autenticado dejarían huecos en el documento.

    `preview=True` añade SOLO el envoltorio de pantalla (hoja carta con sus
    márgenes, fondo gris y barra con «Bajar PDF»). El documento que se le manda
    a Google va siempre sin envoltorio — así el preview se puede maquillar sin
    tocar el PDF.
    """
    from django.template.loader import render_to_string

    from lib import almacen

    from .notas import notas_para

    items = list(cot.items.select_related("servicio", "unidad_fk").all())
    fotos_vivas = _fotos_vivas_del_proyecto(cot)
    # S-Medios-V1: ya no hay nada que precalentar. El derivado existe en disco
    # desde que se subió la foto y su ancho y alto están en el `meta.json`, así
    # que medirla es exacto y gratis — antes se abría la imagen con Pillow y, si
    # no estaba en caché, el estimador la suponía cuadrada.
    # LC 2026-07-26 (Oscar): las líneas marcadas `agrupado` son PROCESOS DE VENTA
    # del concepto anterior (el «Ponchado» del Bordado): se cobran aparte pero se
    # imprimen como renglones extra DENTRO de la tabla de montos de su producto,
    # no como un bloque numerado propio. Así la numeración cuenta productos.
    filas = []
    for it in items:
        if it.agrupado and filas:
            filas[-1]["extras"].append(it)
            continue
        file_id = _foto_del_item(it, fotos_vivas)
        ancho, alto = _medida_foto(almacen.proporcion(file_id))
        filas.append({
            "it": it,
            # La foto: la del uso en el proyecto si le pusieron una propia, si no
            # la congelada con la versión (ver `_foto_del_item`).
            "imagen": almacen.url(file_id, "w1000", absoluta=True),
            # Medida FIJA con la que va en el documento (ver `_medida_foto`): el
            # template las pinta como atributos, así que ninguna foto puede
            # descuadrar la hoja por más alta que sea.
            "img_ancho": ancho,
            "img_alto": alto,
            "extras": [],
        })
    totales = cot.calcular_totales()
    notas = notas_para(cot)
    # El «Desglose de Elementos» es lo que se está comprando, así que las
    # ALTERNATIVAS de volumen no van (si fueran, la lista no cuadraría con el
    # subtotal de abajo). Se leen en la tabla de montos de su producto.
    items_desglose = [it for it in items if not it.informativo]
    # El plan de las notas decide TRES cosas de golpe: el hueco que las empuja al
    # pie, si el documento va apretado y si arrancan a dos renglones de una hoja
    # nueva (LC 2026-08-18, ver `_plan_notas`).
    plan_notas = _plan_notas(cot, filas, items_desglose, notas)
    return render_to_string("cotizaciones/pdf.html", {
        "cot": cot,
        "items": items,
        "items_desglose": items_desglose,
        "filas": filas,
        "totales": totales,
        # LC 2026-08-04 (Oscar): con UN solo producto la tabla de desglose repite
        # exactamente la tablita de montos del bloque — así que no se imprime.
        # Los impuestos y el total SÍ (es lo que el interruptor debe agregar).
        "mostrar_desglose": _mostrar_desglose(cot, filas),
        # Oscar 2026-07-25: el desglose de impuestos va SIN porcentajes. El
        # nombre que arma `lib.fiscal` los trae entre paréntesis («Retención de
        # IVA (10.6667%)»), así que aquí se limpian solo para el documento —
        # Contaduría y la UI los siguen viendo completos.
        "impuestos_pdf": [
            {**imp, "nombre": _sin_porcentaje(imp.get("nombre", ""))}
            for imp in totales.get("impuestos_detalle", [])
        ],
        "notas": notas,
        "logo_url": f"{almacen.base_publica()}/static/branding/Logo_LC-256.png",
        "espacio_notas_pt": plan_notas["espacio_pt"],
        "apretado": plan_notas["apretado"],
        "brs_notas": plan_notas["brs"],
        "preview": preview,
        "url_descargar": _url_descargar(cot) if preview else "",
        "nombre_archivo": cot.nombre_pdf,
        # Sólo lo pinta la vista previa: en el PDF el pie lo pone la API de Docs.
        "pie_documento": PIE_DOCUMENTO,
    })


def _url_descargar(cot: Cotizacion) -> str:
    """Ruta para bajar el PDF real (Drive). "" si el urlconf no la expone."""
    from django.urls import NoReverseMatch, reverse
    try:
        return reverse("cotizaciones:pdf", args=[cot.pk])
    except NoReverseMatch:
        return ""


# ── Márgenes de la hoja (LC 2026-08-17, Oscar + render de referencia) ────────
#
# Hasta ahora el documento salía con el margen por default de Google (una
# pulgada por lado), y por eso el encabezado quedaba mucho más abajo que en el
# formato que Oscar armaba a mano: ahí la fecha, el logotipo y el cliente
# arrancan casi al borde. El margen superior baja a media pulgada (el
# encabezado sube ~1.3 cm) y el inferior a 0.6", con lo que el área imprimible
# crece **10%** — el «empujar el límite inferior hacia abajo» del pedido: cabe
# más contenido por hoja y se evita la hoja de más con dos renglones.
#
# Los laterales NO se tocan: el ancho del texto es el del render de referencia.
#
# Son la FUENTE ÚNICA: de aquí salen los márgenes que se le piden a la API de
# Documentos (`PAGINA_DOCUMENTO`) y el alto útil con el que el estimador simula
# la paginación. Si se cambian y el estimador no, el hueco de las notas queda
# mal — la lección de la ronda del 2026-08-04.
#
# ⚠️ LC 2026-08-18 R2 — **el de arriba no está funcionando** («desistamos por
# ahora, pero anótalo por ahí», Oscar). Se le pide a la API de Documentos y el
# PDF sale con la pulgada por default de Google. Se deja pedido: no cuesta nada
# y si algún día lo respeta, el encabezado sube como pide el formato de
# referencia. Lo que SÍ se corrigió es el estimador, que ahora planea con el
# margen real (`_MARGEN_SUPERIOR_REAL_PT`) — si planeara con éste, creería que
# hay media pulgada más de hoja y empujaría las notas de página.
_MARGEN_SUPERIOR_PT = 36     # 0.5" — se pide, Google no lo aplica (ver arriba)
_MARGEN_INFERIOR_PT = 43     # ~0.6"
# Distancia del pie al borde inferior. Vive DENTRO del margen inferior, así que
# el pie no le quita nada al contenido (43 − 20 = 23pt de aire bajo el texto).
_MARGEN_PIE_PT = 20
# Distancia del ENCABEZADO al borde superior. LC 2026-08-18 (Oscar): «no se pudo
# lo de los márgenes en elementos de arriba — en Google Docs existe un header
# dentro de cada documento, quizás va por ahí». Iba por ahí: al pedir
# `useCustomHeaderFooterMargins` (que hacía falta para el pie) el encabezado
# quedó con el margen del editor, media pulgada; un encabezado vacío a 36pt más
# su renglón terminan por DEBAJO del margen superior, y Google baja el cuerpo
# para no encimarlo. Con el encabezado pegado arriba, el cuerpo por fin arranca
# donde dice `marginTop`.
_MARGEN_ENCABEZADO_PT = 12

# Pie fijo del documento (Oscar 2026-08-17: «agrégale un 1/1, bien abajo, fijo,
# y que no afecte nunca cuánto contenido cabe»). Es texto LITERAL: la API de
# Documentos no tiene petición para insertar el campo automático de número de
# página, así que un contador que avance no es posible por esta vía. En un
# documento de dos hojas ambas dirían «1/1»; hoy prácticamente todas las
# cotizaciones son de una.
PIE_DOCUMENTO = "1/1"

# Lo que se le pide a la API de Documentos tras la conversión. Ver
# `lib.google_drive.GoogleDriveWrapper._ajustar_pagina`.
PAGINA_DOCUMENTO = {
    "margen_superior_pt": _MARGEN_SUPERIOR_PT,
    "margen_inferior_pt": _MARGEN_INFERIOR_PT,
    "margen_pie_pt": _MARGEN_PIE_PT,
    "margen_encabezado_pt": _MARGEN_ENCABEZADO_PT,
    "pie_texto": PIE_DOCUMENTO,
}


def pagina_documento(cot=None) -> dict:
    """Lo que se le pide al generador: lo del GUI, o esto de arriba.

    `PAGINA_DOCUMENTO` deja de ser la última palabra y pasa a ser el **valor
    por defecto**: desde 2026-08-24 los márgenes y el pie se editan en
    Gerencia → Ajustes → Documentos (Oscar: «debemos poder editar todo lo
    posible de los PDFs en el GUI»). Si nadie ha tocado nada, o si la tabla
    todavía no existe, sale exactamente lo de siempre.
    """
    from lib.documentos import pagina_configurada

    pagina = pagina_configurada(default=PAGINA_DOCUMENTO)
    if cot is None:
        return pagina

    # Una cotización que aún no se manda sale MARCADA, para que no se confunda
    # con la que ya salió. Las dos se ven idénticas hoy, y confundirlas frente a
    # un cliente es de los errores caros.
    from lib.documentos import marca_borrador

    if not getattr(cot, "enviada_en", None):
        marca = marca_borrador()
        if marca:
            pagina = {**pagina, "marca_agua": marca}

    # Y los metadatos, para que las propiedades del archivo digan de qué es. Un
    # PDF sin título es imposible de encontrar en una carpeta con cien.
    proyecto = getattr(cot, "proyecto", None)
    cliente = getattr(cot, "cliente", None)
    pagina = {**pagina, "metadatos": {
        "Title": getattr(cot, "titulo_documento", "") or "Cotización",
        "Author": "Learning Center",
        "Subject": getattr(proyecto, "nombre", "") or getattr(cliente, "razon_social", "") or "",
        "Keywords": getattr(cot, "codigo", "") or "",
    }}
    return pagina

# Alto de la hoja carta (11" = 792pt) menos los márgenes de arriba y abajo.
#
# LC 2026-08-18 R2 (Oscar: «lo del margen superior del PDF no funcionó,
# desistamos por ahora»): el margen de arriba que se le pide a la API de
# Documentos NO se está aplicando en el PDF, así que el estimador tiene que
# contar el que Google usa de verdad — su pulgada por default. Si contara los
# 36pt que se piden, creería que hay 36pt más de hoja de los que hay, subestimaría
# y las notas se pasarían de página. Se sigue PIDIENDO el margen chico (no cuesta
# nada y si algún día lo respeta, sólo sobra aire), pero se planea con el real.
_ALTO_HOJA_PT = 792
_MARGEN_SUPERIOR_REAL_PT = 72   # 1" — lo que aplica Google, no lo que se pide
_ALTO_UTIL_PT = _ALTO_HOJA_PT - _MARGEN_SUPERIOR_REAL_PT - _MARGEN_INFERIOR_PT

# Caja en la que DEBE caber la foto del producto (ver `_medida_foto`). El alto
# es el tope duro que pidió Oscar (2026-07-26, ronda 3): «alrededor del alto de
# 4 celdas de la tabla». Sin este tope una foto vertical (la bata: 1×2) se comía
# media página y descuadraba el documento.
#
# LC 2026-08-18 (Oscar): «cuando la descripción es corta, alinear al borde
# inferior el texto y la imagen, y achicar un poco la foto». El tope baja de 76
# a 64pt: con el texto y la foto asentados abajo, lo que sobra queda ARRIBA —
# entre el nombre del concepto y la descripción— y la tablita de precios vuelve
# a quedar pegada a la descripción, que era el hueco que se notaba.
_ANCHO_FOTO_PT = 150
_ALTO_FOTO_PT = 64


def _medida_foto(proporcion: float) -> tuple[int, int]:
    """`(ancho, alto)` en puntos con los que la foto entra en el documento.

    La imagen se escala para caber COMPLETA en la caja `_ANCHO_FOTO_PT ×
    _ALTO_FOTO_PT`, conservando su proporción. Se devuelven las DOS medidas
    porque el documento las pinta como atributos del `<img>`: dejarle una sola a
    la conversión de Docs es lo que hacía que una foto vertical creciera sin
    control.

    Si no se pudo medir (Drive caído, imagen que Pillow no abre), se asume
    cuadrada del alto máximo: una foto chica nunca rompe el formato.
    """
    prop = float(proporcion or 0)
    if prop <= 0:
        return _ALTO_FOTO_PT, _ALTO_FOTO_PT
    alto = _ANCHO_FOTO_PT * prop
    if alto <= _ALTO_FOTO_PT:
        return _ANCHO_FOTO_PT, max(1, int(round(alto)))
    return max(1, int(round(_ALTO_FOTO_PT / prop))), _ALTO_FOTO_PT

# Colchón al pie: la paginación real la hace Google, no nosotros, así que el
# bloque de notas se deja un poco arriba del borde. Sin este colchón, un error
# de estimación de unos milímetros manda el último renglón a una hoja nueva
# (Oscar 2026-07-25: «no debe de suceder así»). LC 2026-07-29: subió de 28 a 56
# porque las notas de la cotización de Tessa se partieron en dos hojas.
_MARGEN_SEGURIDAD_PT = 56

# Tope del hueco que empuja las notas al pie (LC 2026-07-29, Oscar: «se siguen
# creando espacios extraños e innecesarios, así como páginas vacías»). El hueco
# sale de una ESTIMACIÓN, así que un error grande abría medio hoja de agujero —
# o empujaba las notas tan abajo que el párrafo que Google agrega al final del
# documento se iba solo a una hoja nueva (la página 4 vacía de la cotización de
# Dekalogo). Con tope, un error de estimación cuesta unos milímetros.
_TOPE_HUECO_NOTAS_PT = 96

# Lo que hay que dejar libre al FINAL del documento. Al convertir, Google cierra
# el cuerpo con un párrafo propio que no se puede quitar; si el contenido termina
# pegado al borde inferior, ese párrafo se va solo a una hoja nueva y sale la
# **página en blanco** que reportó Oscar (2026-08-18 R2: «nos generó una pág 3 en
# blanco… regla: no páginas en blanco»). Reservarlo es lo único que lo evita.
_COLA_DOCUMENTO_PT = 28

# Lo mínimo que debe sobrar para dejar las notas en la última hoja SIN aire.
# Oscar (2026-08-18 R2): «cuando haya conflicto, puedes quitar los <br>s entre el
# último elemento y el bloque de notas para que quepa todo». Es el tercer escalón
# de `_plan_notas`, y existe porque el segundo exige además el colchón de
# seguridad: entre «cabe justo» y «cabe con holgura» se prefiere apretar antes
# que mandar las notas —y con ellas una hoja entera— a la página siguiente.
_COLCHON_MINIMO_NOTAS_PT = 8

# Encabezado (fecha/logo/cliente) + título centrado. El título dejó de llevar
# 28pt de aire abajo (Oscar 2026-07-28, punto 2: «un <br> de más»), y en la
# ronda del 2026-08-04 («apretar aún más el interlineado de todo») bajó a 8pt.
_ALTO_ENCABEZADO_PT = 60 + 24

# Lo que el convertidor de Google le SUMA a cada bloque por su cuenta: mete un
# párrafo vacío alrededor de cada tabla (quirk #5 de `pdf.html`) y respeta a su
# manera los márgenes. Calibrado midiendo dos documentos reales (LC 2026-07-29,
# cotizaciones de Tessa Studio y Dekalogo): la estimación se quedaba ~60pt corta
# por bloque, y con 6 bloques eso son casi 6 cm de error acumulado — de ahí que
# el hueco de las notas saliera disparatado. Se prefiere pasarse de largo:
# sobreestimar sólo pone las notas un poco más arriba.
_OVERHEAD_BLOQUE_PT = 60

# Lo que se ahorra por bloque en modo APRETADO. LC 2026-08-18 (Oscar): «cuando
# las notas se pasen a una hoja vacía, apretar esta distancia a ver si lo
# arregla». El renglón que Google mete entre dos tablas seguidas no se puede
# quitar (quirk #5), pero los márgenes sí: la tabla de la descripción pierde sus
# 3pt de abajo y la de montos baja de 10 a 3. Son ~10pt por bloque; con seis
# bloques, casi una pulgada — de sobra para recuperar unas notas que se pasaban
# de hoja por poco.
_AHORRO_APRETADO_PT = 10


def _alto_bloque(fila) -> int:
    """Alto estimado (pt) del bloque de un producto: nombre + especificaciones
    o foto + su tabla de montos, más lo que el convertidor agrega por su cuenta
    (`_OVERHEAD_BLOQUE_PT`). Es una **estimación** — la paginación real la hace
    Google."""
    cuerpo = 0
    renglones = len(getattr(fila["it"], "detalle_lineas", []) or [])
    if renglones:
        cuerpo = renglones * 13
    if fila.get("imagen"):
        # La foto va acotada a una caja fija (`_medida_foto`), así que su alto
        # real es el que ya se calculó al armar la fila.
        cuerpo = max(cuerpo, int(fila.get("img_alto") or _ALTO_FOTO_PT))
    # nombre + cuerpo + tabla de montos (+ un renglón por proceso de venta).
    # LC 2026-08-04: las medidas bajaron con el interlineado del documento
    # (`pdf.html`: body 1.15 → 1.02, celdas 2pt → 1pt de padding, márgenes de
    # 18/24pt → 10/14pt). Si el estimador no baja con él, cree que el documento
    # ocupa más de lo que ocupa y las notas se quedan flotando a media hoja.
    alto = 18 + cuerpo + 4 + 32 + 10 + len(fila.get("extras") or []) * 15
    return alto + _OVERHEAD_BLOQUE_PT


def _mostrar_desglose(cot, filas) -> bool:
    """Si el documento lleva la tabla «Desglose de Elementos».

    LC 2026-08-04 (Oscar): «si sólo tiene 1 producto, al prender el interruptor
    no se mete la tabla de desglose, pero sí se meten los montos de impuestos» —
    con un solo bloque la tabla es una copia literal de la tablita de montos que
    ya se imprimió arriba. `filas` son los BLOQUES de producto (los procesos de
    venta viven dentro de su bloque, no cuentan como producto aparte).
    """
    return bool(getattr(cot, "incluir_desglose", False)) and len(filas or []) > 1


def _alto_desglose(cot, items, con_tabla: bool = True) -> int:
    """Alto estimado (pt) del bloque «Desglose de Elementos» + los totales.

    `con_tabla=False` cuando el desglose se omite (un solo producto) y sólo se
    imprimen los impuestos y el total.
    """
    impuestos = len(cot.calcular_totales().get("impuestos_detalle", []))
    alto = 0
    if con_tabla:
        # `items` incluye los procesos de venta: en el desglose cada uno es su
        # propio renglón (ahí sí van en lista plana).
        alto += 30 + 16 + len(items) * 15 + 10   # título + encabezados + filas
    alto += (2 + impuestos) * 14 + 18            # subtotal + impuestos + total
    return alto + _OVERHEAD_BLOQUE_PT


def _paginar(cot, filas, items, *, apretado: bool = False) -> dict:
    """Simula la paginación del documento por BLOQUES ATÓMICOS.

    Cada bloque de producto (y el desglose, y las notas) viaja dentro de una
    tabla envoltorio de una sola celda cuya fila lleva `preventOverflow` (ver
    `lib.google_drive._endurecer_paginacion`), así que **no se parte**: o cabe
    en lo que resta de la hoja o pasa entero a la siguiente. Esa regla es la
    que se simula aquí.

    Devuelve `{"libre": int}` — los puntos que quedan sin usar en la última
    hoja, para decidir cuánto hueco meterle al bloque de notas.

    Es una estimación (la hoja real la corta Google), así que sólo se usa para
    algo cuyo peor caso son unos milímetros: ver `_TOPE_HUECO_NOTAS_PT`.
    """
    ahorro = _AHORRO_APRETADO_PT if apretado else 0
    usado = _ALTO_ENCABEZADO_PT
    for fila in filas:
        alto = _alto_bloque(fila) - ahorro
        if usado > _ALTO_ENCABEZADO_PT and usado + alto > _ALTO_UTIL_PT:
            usado = alto          # el bloque arranca hoja nueva
        else:
            usado += alto
    if cot.incluir_desglose:
        alto = _alto_desglose(cot, items, con_tabla=_mostrar_desglose(cot, filas)) - ahorro
        usado = alto if usado + alto > _ALTO_UTIL_PT else usado + alto
    # La cola del documento (el párrafo que Google agrega al cerrar el cuerpo) se
    # descuenta siempre: lo que sobra de verdad es menos que lo que sobra en el
    # HTML.
    libre = _ALTO_UTIL_PT - min(usado, _ALTO_UTIL_PT) - _COLA_DOCUMENTO_PT
    return {"libre": max(0, libre)}


def _plan_notas(cot, filas, items, notas) -> dict:
    """Dónde quedan las notas y cuánto aire lleva el documento.

    Devuelve `{"apretado": bool, "espacio_pt": int, "brs": int}`.

    La escalera que pidió Oscar (2026-08-18), en ese orden:

    1. **Aire normal.** Si las notas caben en lo que queda de la última hoja, se
       van hasta el pie con el hueco de siempre (Oscar 2026-07-25: dinámico, con
       tope, ver `_TOPE_HUECO_NOTAS_PT`).
    2. **Apretado.** Si no caben, se aprietan los márgenes de todos los bloques
       (`_AHORRO_APRETADO_PT`) y se vuelve a medir: muchas veces con eso alcanza
       y el documento se queda en una sola hoja.
    3. **Sin aire.** Si caben pero justas, se les quita todo el hueco (Oscar
       2026-08-18 R2: «cuando haya conflicto, puedes quitar los <br>s entre el
       último elemento y el bloque de notas para que quepa todo»). Este escalón
       es el que evita la hoja de más cuando falta poquito.
    4. **Hoja nueva.** Si ni así caben, pasan enteras a la siguiente —el
       envoltorio de tabla con `preventOverflow` impide que se partan— y ahí
       arrancan a **dos renglones** del margen superior, para que no queden
       pegadas al borde.

    Todo se apoya en `_paginar`, que es una ESTIMACIÓN: la hoja de verdad la
    corta Google. Por eso lo único que se decide con esto es el aire, cuyo peor
    caso son unos milímetros.
    """
    # LC 2026-08-04: bajan con el interlineado del documento (las notas van a
    # 9pt con `line-height:1.0` y padding 0).
    alto_notas = 18 + len(notas) * 13
    if getattr(cot, "terminos", ""):
        alto_notas += 20 + len(cot.terminos.splitlines()) * 11

    for apretado in (False, True):
        libre = _paginar(cot, filas, items, apretado=apretado)["libre"]
        hueco = libre - alto_notas - _MARGEN_SEGURIDAD_PT
        if hueco > 0:
            return {"apretado": apretado,
                    "espacio_pt": int(min(hueco, _TOPE_HUECO_NOTAS_PT)),
                    "brs": 0}
    # Escalón 3: caben, pero justas. Se les quita TODO el aire antes que mandar
    # una hoja entera a la basura (Oscar 2026-08-18 R2). Si aun así el estimador
    # se equivocó, el peor caso es el mismo que el escalón 4 —Google las manda
    # enteras a la hoja siguiente, porque el bloque viaja en una fila con
    # `preventOverflow`—, sólo que sin los dos renglones de arriba.
    libre = _paginar(cot, filas, items, apretado=True)["libre"]
    if libre - alto_notas >= _COLCHON_MINIMO_NOTAS_PT:
        return {"apretado": True, "espacio_pt": 0, "brs": 0}
    return {"apretado": True, "espacio_pt": 0, "brs": 2}


def _espacio_antes_de_notas(cot, filas, items, notas) -> int:
    """Sólo el hueco del plan de arriba (se conserva por los que ya lo usaban)."""
    return _plan_notas(cot, filas, items, notas)["espacio_pt"]


def _fotos_vivas_del_proyecto(cot) -> dict:
    """Fotos PROPIAS de los usos vigentes del proyecto, indexadas para casarlas
    con las líneas del documento.

    LC 2026-07-28 (Oscar, punto 4): «la imagen distinta que subí al alias de un
    producto no está sirviendo, se está incrustando la imagen principal». La
    foto se congela con la versión (`CotizacionItem.imagen_file_id`), así que si
    la versión se generó ANTES de subir la foto del alias, el documento seguía
    saliendo con la del catálogo. La foto propia de un uso es una decisión
    explícita de ESE proyecto, así que gana siempre; la congelada sigue
    cubriendo el caso que motivó el congelado (que después le cambien la foto al
    producto del catálogo).

    **Por qué el NOMBRE manda (LC 2026-07-29, Oscar: «se sigue poniendo la
    imagen del producto padre»).** Dos líneas del mismo proyecto pueden apuntar
    al MISMO producto del catálogo con alias distintos («Playera dry fit —
    negro» y «— blanco»): la llave `("srv", servicio, variación)` es la misma
    para las dos, así que casar por producto le daba a ambas la foto de la
    primera. Lo que de verdad distingue un alias es su nombre, y el nombre del
    concepto se congela desde `nombre_visible`, así que casa exacto. La llave
    por producto se conserva sólo como respaldo y **sólo cuando no hay
    ambigüedad** (un único uso de ese producto en el proyecto).
    """
    proyecto = getattr(cot, "proyecto", None)
    if proyecto is None:
        return {}
    try:
        lineas = list(proyecto.productos.select_related("servicio").all())
    except Exception:  # noqa: BLE001 — proyecto borrado o sin acceso al related
        return {}
    # Cuántas líneas comparten cada producto — se cuentan TODAS, no sólo las que
    # tienen foto propia: si el producto se usa dos veces, la llave por producto
    # no puede decidir cuál de las dos es (y le pasaría la foto del alias a la
    # línea que debe salir con la del catálogo).
    usos_por_producto: dict = {}
    for pp in lineas:
        clave = ("srv", pp.servicio_id, pp.variacion_id)
        usos_por_producto[clave] = usos_por_producto.get(clave, 0) + 1

    vivas: dict = {}
    for pp in lineas:
        if not pp.imagen_es_propia:
            continue
        file_id = pp.imagen_file_id.strip()
        nombre = pp.nombre_visible.strip().lower()
        if nombre:
            vivas.setdefault(("nom", nombre), file_id)
        clave = ("srv", pp.servicio_id, pp.variacion_id)
        if usos_por_producto.get(clave) == 1:
            vivas.setdefault(clave, file_id)
    return vivas


def _foto_del_item(it, fotos_vivas: dict) -> str:
    """`file_id` de la foto que va en el documento para esta línea: la propia
    del uso en el proyecto si la hay, si no la congelada con la versión.

    Se casa primero por NOMBRE del concepto (el alias es lo que distingue dos
    usos del mismo producto) y sólo después por producto — ver
    `_fotos_vivas_del_proyecto`.
    """
    if fotos_vivas:
        viva = fotos_vivas.get(("nom", it.concepto_visible.strip().lower()))
        if not viva:
            viva = fotos_vivas.get(("srv", it.servicio_id, it.variacion_id))
        if viva:
            return viva
    return it.imagen_visible_file_id


def _sin_porcentaje(nombre: str) -> str:
    """«Retención de IVA (10.6667%)» → «Retención de IVA»."""
    import re
    return re.sub(r"\s*\([^)]*%\s*\)\s*$", "", nombre or "").strip()


def enviar_por_correo(cot: Cotizacion, actor, email_destino: str = ""):
    """Manda la cotización por El Cartero con el PDF adjunto (best-effort).

    Devuelve `lib.cartero.ResultadoCorreo`. Genera el PDF si Drive está
    disponible; si no, manda el correo sin adjunto. Nunca lanza."""
    from lib import cartero

    destino = (email_destino or cot.enviada_a_email
               or getattr(cot.cliente, "email_contacto", "") or "").strip()
    if not destino:
        return cartero.ResultadoCorreo(ok=False, error="El cliente no tiene correo.")

    adjuntos = []
    res_pdf = generar_pdf(cot, actor)
    if res_pdf.ok and res_pdf.pdf_bytes:
        adjuntos.append(cartero.Adjunto(
            nombre=f"{cot.codigo}.pdf", contenido=res_pdf.pdf_bytes, mime="application/pdf"))

    asunto, html = _render_correo(cot)
    return cartero.enviar(destinatario=destino, asunto=asunto, html=html, adjuntos=adjuntos)


def _render_correo(cot: Cotizacion) -> tuple[str, str]:
    """(asunto, cuerpo_html) desde la PlantillaCorreo editable; fallback al
    template de archivo si la plantilla no existe."""
    from cuentas.templatetags.forms_helpers import dinero
    totales = cot.calcular_totales()
    contexto = {
        "codigo": cot.codigo,
        "titulo": cot.titulo,
        "cliente": cot.cliente.razon_social,
        "total": dinero(totales["total"]),
        "moneda": cot.moneda,
        "fecha_validez": cot.fecha_validez.strftime("%d/%m/%Y") if cot.fecha_validez else "",
        "notas": cot.notas or "",
    }
    try:
        from ajustes.models import PlantillaCorreo
        return PlantillaCorreo.obtener("cotizacion").render(contexto)
    except Exception:  # noqa: BLE001 — fallback al template de archivo
        from django.template.loader import render_to_string
        html = render_to_string("cotizaciones/email.html", {"cot": cot})
        return f"Cotización {cot.codigo} · Learning Center", html


def generar_pdf(cot: Cotizacion, actor):
    """Genera (o regenera) el PDF de la cotización vía Google Docs y lo guarda
    en Drive. Devuelve `lib.documentos.ResultadoPdf`. Borra el PDF anterior si
    lo había. Fallback gracioso (nunca lanza)."""
    from lib.documentos import generar_pdf as _gen
    from lib.google_drive import drive

    # El precalentado vive dentro de `construir_html_pdf` (ahí se MIDEN las fotos
    # para acotarlas), así que aquí ya no se repite.
    html = construir_html_pdf(cot)
    res = _gen(html=html, nombre=cot.nombre_pdf, subcarpeta="Cotizaciones",
               pagina=pagina_documento(cot))
    if not res.ok:
        return res

    # Borra el PDF previo (best-effort) antes de apuntar al nuevo.
    if cot.pdf_file_id and cot.pdf_file_id != res.data.get("id"):
        import contextlib
        with contextlib.suppress(Exception):
            drive.borrar(cot.pdf_file_id)

    cot.pdf_file_id = res.data.get("id", "")
    cot.pdf_url = res.data.get("webViewLink", "")
    cot.pdf_generado_en = timezone.now()
    cot.save(update_fields=["pdf_file_id", "pdf_url", "pdf_generado_en"])
    _emitir("cotizacion.pdf_generado", cot, actor, {"pdf_file_id": cot.pdf_file_id})
    return res


def emitir_actualizada(cot: Cotizacion, actor):
    _emitir("cotizacion.actualizada", cot, actor)


def marcar_enviada(cot: Cotizacion, actor, email_destino: str = "") -> Cotizacion:
    """Deja constancia de que la cotización ya se le mandó al cliente.

    Trabaja por FASE, no por el nombre del estado: antes exigía el literal
    'borrador' y Learning Center no usa ese estado, así que el botón Enviar
    era imposible de usar y todo se quedaba en "Generada" para siempre.

    Volver a mandarla es válido (se re-sella la fecha); lo que no tiene
    sentido es "enviar" algo ya ganado o ya perdido.
    """
    from apps.cotizaciones.embudo import fase_efectiva, slug_destino
    from apps.cotizaciones.models import FASE_ENVIADA, FASE_GANADA, FASE_PERDIDA

    fase = fase_efectiva(cot)
    if fase == FASE_GANADA:
        raise ValueError("Esta cotización ya está ganada; no hace falta mandarla otra vez.")
    if fase == FASE_PERDIDA:
        raise ValueError("Esta cotización ya se dio por perdida.")
    with transaction.atomic():
        cot.estado = slug_destino(FASE_ENVIADA, "enviada")
        cot.enviada_en = timezone.now()
        cot.enviada_a_email = email_destino or cot.enviada_a_email or (
            getattr(cot.cliente, "email_contacto", "") or ""
        )
        cot.save(update_fields=["estado", "enviada_en", "enviada_a_email", "actualizado_en"])
    _emitir("cotizacion.enviada", cot, actor, {"email_destino": cot.enviada_a_email})
    return cot


def marcar_aprobada(cot: Cotizacion, actor, nombre: str, email: str = "",
                    referencia: str = "") -> Cotizacion:
    from apps.cotizaciones.embudo import fase_efectiva, slug_destino
    from apps.cotizaciones.models import FASE_GANADA, FASE_PERDIDA

    fase = fase_efectiva(cot)
    if fase == FASE_GANADA:
        raise ValueError("Esta cotización ya estaba ganada.")
    if fase == FASE_PERDIDA:
        raise ValueError("Esta cotización ya se dio por perdida.")
    if not nombre.strip():
        raise ValueError("Debe registrarse el nombre de quien aprobó.")
    with transaction.atomic():
        cot.estado = slug_destino(FASE_GANADA, "aprobada")
        cot.aprobada_en = timezone.now()
        cot.aprobada_por_nombre = nombre.strip()
        cot.aprobada_por_email = email.strip()
        cot.referencia_aprobacion = referencia.strip()
        cot.save(update_fields=[
            "estado", "aprobada_en", "aprobada_por_nombre",
            "aprobada_por_email", "referencia_aprobacion", "actualizado_en",
        ])
    _emitir("cotizacion.aprobada", cot, actor, {
        "aprobada_por": cot.aprobada_por_nombre,
    })
    # Acuse al cliente, si hay una regla encendida para esto. Best-effort y
    # después del commit: aprobar la cotización no puede fallar por el correo.
    def _avisar():
        from lib import reglas_correo
        reglas_correo.cotizacion_aprobada(cot)

    transaction.on_commit(_avisar)
    return cot


def marcar_rechazada(cot: Cotizacion, actor, motivo: str) -> Cotizacion:
    from apps.cotizaciones.embudo import fase_efectiva, slug_destino
    from apps.cotizaciones.models import FASE_GANADA, FASE_PERDIDA

    fase = fase_efectiva(cot)
    if fase == FASE_PERDIDA:
        raise ValueError("Esta cotización ya se dio por perdida.")
    if fase == FASE_GANADA:
        raise ValueError("Esta cotización ya está ganada; anúlala si se cayó el trato.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe registrarse el motivo de rechazo.")
    with transaction.atomic():
        cot.estado = slug_destino(FASE_PERDIDA, "rechazada")
        cot.rechazada_en = timezone.now()
        cot.motivo_rechazo = motivo
        cot.save(update_fields=["estado", "rechazada_en", "motivo_rechazo", "actualizado_en"])
    _emitir("cotizacion.rechazada", cot, actor, {"motivo": motivo[:200]})
    return cot


def marcar_anulada(cot: Cotizacion, actor, motivo: str) -> Cotizacion:
    if cot.estado == "anulada":
        raise ValueError("La cotización ya estaba anulada.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe registrarse el motivo de anulación.")
    with transaction.atomic():
        cot.estado = "anulada"
        cot.anulada_en = timezone.now()
        cot.anulada_por = actor if getattr(actor, "is_authenticated", False) else None
        cot.motivo_anulacion = motivo[:300]
        cot.save(update_fields=[
            "estado", "anulada_en", "anulada_por", "motivo_anulacion", "actualizado_en",
        ])
    _emitir("cotizacion.anulada", cot, actor, {"motivo": motivo[:200]})
    return cot


def duplicar(cot: Cotizacion, actor) -> Cotizacion:
    """Crea una copia en estado borrador con los mismos items e impuestos."""
    from .models import CotizacionImpuesto, CotizacionItem
    with transaction.atomic():
        nueva = Cotizacion.objects.create(
            cliente=cot.cliente,
            proyecto=cot.proyecto,
            titulo=f"Copia de {cot.titulo}"[:200],
            estado="borrador",
            moneda=cot.moneda,
            descuento_global_porcentaje=cot.descuento_global_porcentaje,
            notas=cot.notas,
            terminos=cot.terminos,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        for it in cot.items.all():
            CotizacionItem.objects.create(
                cotizacion=nueva,
                orden=it.orden,
                servicio=it.servicio,
                concepto=it.concepto,
                imagen_file_id=it.imagen_file_id,
                descripcion=it.descripcion,
                cantidad=it.cantidad,
                unidad=it.unidad,
                precio_unitario=it.precio_unitario,
                descuento_porcentaje=it.descuento_porcentaje,
                # LC 2026-07-26: la copia conserva qué líneas son procesos de
                # venta, o el documento las volvería bloques numerados aparte.
                agrupado=it.agrupado,
            )
        for ci in cot.impuestos.all():
            CotizacionImpuesto.objects.create(cotizacion=nueva, tasa=ci.tasa)
    emitir_creada(nueva, actor)
    return nueva


def crear_factura_anticipo(cot: Cotizacion, actor) -> Factura:  # noqa: F821
    """Genera una Factura por el monto del anticipo de la cotización.

    Requiere `cot.anticipo_pendiente == True`. Crea la factura en
    estado 'borrador' con:
    - monto = `cot.anticipo_monto` (línea única)
    - cliente, proyecto: heredados de la cotización
    - cotizacion_origen = esta cotización
    - titulo = "Anticipo de {COT-XXXX}"
    - notas mencionan el anticipo

    Marca `cot.anticipo_facturado_en = now`. Idempotente: si ya fue
    facturado, levanta `ValueError`.
    """
    from datetime import date as _date
    from decimal import Decimal as _Decimal

    if cot.estado != "aprobada":
        raise ValueError("Solo se puede generar factura de anticipo desde una cotización aprobada.")
    if cot.anticipo_monto <= 0:
        raise ValueError("Esta cotización no tiene anticipo configurado.")
    if cot.anticipo_facturado_en is not None:
        raise ValueError("Ya se generó la factura del anticipo para esta cotización.")

    from apps.facturacion.models import Factura, FacturaItem

    monto = cot.anticipo_monto
    with transaction.atomic():
        factura = Factura.objects.create(
            cliente=cot.cliente,
            proyecto=cot.proyecto,
            cotizacion_origen=cot,
            titulo=f"Anticipo de {cot.codigo}",
            estado="borrador",
            fecha_emision=_date.today(),
            moneda=cot.moneda,
            # El anticipo es un monto plano (ya se calculó del total); sin
            # recomputar impuestos encima para no doble-contabilizar.
            regimen_fiscal="exento",
            descuento_global_porcentaje=_Decimal("0"),
            notas=f"Anticipo del {cot.anticipo_porcentaje}% sobre {cot.codigo}.\n\n{cot.notas}".strip(),
            terminos=cot.terminos,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        FacturaItem.objects.create(
            factura=factura,
            orden=0,
            descripcion=f"Anticipo · {cot.titulo}",
            cantidad=_Decimal("1.00"),
            unidad="servicio",
            precio_unitario=monto,
            descuento_porcentaje=_Decimal("0.00"),
        )
        cot.anticipo_facturado_en = timezone.now()
        cot.save(update_fields=["anticipo_facturado_en", "actualizado_en"])

    _emitir("cotizacion.anticipo_facturado", cot, actor, {
        "factura_id": factura.pk,
        "factura_codigo": factura.codigo,
        "anticipo_monto": float(monto),
    })
    return factura


# --- Cotizaciones versionadas POR PROYECTO -------------------------------
# Recuadro "Cotizaciones" del detalle de proyecto (render Oscar 2026-06-27).
# El usuario arma los Productos involucrados en la página del proyecto y pica
# "Generar": se crea una Cotizacion real (aparece también en /cotizaciones/)
# tomando un SNAPSHOT de los productos incluidos actuales, como v1, v2, v3…

# Fallback si el catálogo EstadoCotizacion aún no está sembrado.
ESTADOS_PROYECTO_FALLBACK = {"generada", "enviada", "aprobada", "pagada"}


def generar_desde_proyecto(proyecto, actor) -> Cotizacion:
    """Genera la siguiente versión de cotización del proyecto.

    Toma los Productos involucrados INCLUIDOS actuales (cantidad + precio
    efectivo) y los congela como líneas de una Cotizacion nueva. Suma las
    tasas `aplicable_default` salvo que el proyecto sea IVA exento, para que el
    total calce con `proyecto.monto_a_facturar`.

    **Render LC 2026-06-30: al generar, el estatus se reinicia al primer paso
    del flujo (Generada).** El estatus es único de la cotización (vive en la
    versión más reciente, la única editable); generar una versión nueva la pone
    en 'generada' y el pizza-tracker vuelve al inicio. Las versiones anteriores
    conservan, en solo lectura, el último estado que tuvieron.
    """
    from decimal import Decimal

    from ajustes.models.tasa import TasaImpositiva

    from . import descripcion
    from .models import CotizacionImpuesto, CotizacionItem, estados_cot_activos

    with transaction.atomic():
        ultima_cot = (
            Cotizacion.objects.filter(proyecto=proyecto, version__gt=0)
            .order_by("-version")
            .first()
        )
        _activos = estados_cot_activos()
        estado_inicial = _activos[0]["slug"] if _activos else "generada"
        version = (ultima_cot.version + 1) if ultima_cot else 1
        cot = Cotizacion.objects.create(
            cliente=proyecto.cliente,
            proyecto=proyecto,
            titulo=(proyecto.nombre or proyecto.codigo)[:200],
            estado=estado_inicial,
            version=version,
            regimen_fiscal=proyecto.regimen_fiscal,
            descuento_global_porcentaje=Decimal("0.00"),
            # LC 2026-07: los interruptores del documento se HEREDAN de la
            # versión anterior — si ya decidiste incluir desglose y cobrar de
            # un solo pago, la v+1 no te lo vuelve a preguntar.
            incluir_desglose=(ultima_cot.incluir_desglose if ultima_cot else False),
            forma_pago=(ultima_cot.forma_pago if ultima_cot else Cotizacion.FORMA_ANTICIPO),
            # Igual con el encabezado escrito a mano: si ya se corrigió en la
            # v1, la v2 no vuelve a salir con el título automático.
            titulo_documento_manual=(
                ultima_cot.titulo_documento_manual if ultima_cot else ""
            ),
            anticipo_porcentaje=(
                ultima_cot.anticipo_porcentaje if ultima_cot else Decimal("0.00")
            ),
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        # LC 2026-07: las descripciones escritas a mano en la versión anterior
        # se HEREDAN (nadie quiere reescribir el branding en cada versión).
        indice = descripcion.indice_previo(ultima_cot)
        orden = 0
        # S-Ajustes-Ago12-B: las parejas (línea del proyecto, línea del cliente)
        # para congelar además el lado del COSTO, que la cotización no guarda.
        pares_foto = []
        for pp in proyecto.productos_incluidos:
            i = orden
            orden += 1
            # El cliente ve el nombre del producto EN ESTE PROYECTO (el alias, si
            # se le puso); el FK al catálogo se conserva aparte. La higiene de
            # «Servicio · Variación» vive en `nombre_catalogo`.
            # La NOTA interna del producto NO se copia (no sale en el documento).
            item = CotizacionItem.objects.create(
                cotizacion=cot,
                orden=i,
                servicio=pp.servicio if pp.servicio_id else None,
                variacion=pp.variacion if pp.variacion_id else None,
                concepto=pp.nombre_visible[:150],
                # La foto se congela con la versión: la del uso si le pusieron
                # una propia, si no la del catálogo (LC 2026-07-26).
                imagen_file_id=pp.imagen_efectiva_file_id,
                descripcion=descripcion.descripcion_para(
                    pp, descripcion.heredado(indice, pp)),
                cantidad=Decimal(str(pp.cantidad_efectiva)),
                precio_unitario=pp.precio_efectivo,
            )
            pares_foto.append((pp, item))
            # LC 2026-08-17 (Oscar): las ESCALAS DE VOLUMEN visibles que no son la
            # activa se congelan como renglones extra del mismo bloque —
            # `agrupado` para que se impriman dentro de la tabla de montos de su
            # producto, e `informativo` para que NO sumen al total (el total es el
            # de la opción activa, que es la que cargó el `item` de arriba).
            for opcion in pp.opciones_documento():
                if opcion is None and pp.escala_activa is None:
                    continue      # la Opción A ya es el `item` principal
                if opcion is not None and opcion.activa:
                    continue      # la escala activa también es el `item`
                cantidad = pp.cantidad if opcion is None else opcion.cantidad
                precio = pp.precio_propio if opcion is None else opcion.precio_efectivo
                CotizacionItem.objects.create(
                    cotizacion=cot,
                    orden=orden,
                    servicio=pp.servicio if pp.servicio_id else None,
                    concepto=pp.nombre_visible[:150],
                    descripcion="",
                    cantidad=Decimal(str(cantidad)),
                    precio_unitario=precio,
                    agrupado=True,
                    informativo=True,
                )
                orden += 1
            # LC 2026-07-26 (Oscar): los PROCESOS DE VENTA de la línea (Ponchado,
            # arte…) se cobran aparte, así que son líneas propias — con
            # `agrupado=True` para que el documento las imprima dentro de la
            # tabla de montos de su producto en vez de como bloques numerados.
            for v in pp.ventas.all():
                CotizacionItem.objects.create(
                    cotizacion=cot,
                    orden=orden,
                    concepto=v.descripcion[:150],
                    descripcion="",
                    cantidad=Decimal(str(v.cantidad)),
                    precio_unitario=v.precio_decimal,
                    agrupado=True,
                )
                orden += 1
        # S-Ajustes-Ago12-B: la foto completa de los productos de esta versión
        # (con merma, costo, proveedor y procesos) vive del lado del proyecto —
        # la cotización sólo guarda lo que ve el cliente. Alimenta las pestañas
        # v1/v2/… del recuadro «Productos involucrados».
        from apps.los_proyectos import services_version
        services_version.fotografiar(cot, pares_foto)
        # Solo el régimen 'iva' usa las tasas de la M2M; 'honorarios' y 'exento'
        # se calculan con lógica dedicada (lib.fiscal) y no dependen de tasas.
        # `iva_exento` legacy sigue vetando las tasas (back-compat).
        if proyecto.regimen_fiscal == "iva" and not proyecto.iva_exento:
            for tasa in TasaImpositiva.objects.filter(aplicable_default=True, activa=True):
                CotizacionImpuesto.objects.create(cotizacion=cot, tasa=tasa)
    _emitir("cotizacion.generada", cot, actor, {
        "proyecto_id": proyecto.pk, "version": cot.version,
        "total": float(cot.calcular_totales()["total"]),
    })
    return cot


def marcar_estado_proyecto(cot: Cotizacion, estado: str, actor) -> Cotizacion:
    """Setter LIBRE de estado para el recuadro del proyecto (los pasos
    configurados en Gerencia, en cualquier orden — como la barra de status del
    proyecto). No exige nombre/motivo; sella el timestamp de los pasos conocidos
    (enviada/aprobada/pagada) y emite el evento Portavoz adecuado."""
    from django.utils import timezone

    from .models import estados_cot_activos

    validos = {e["slug"] for e in estados_cot_activos()} or ESTADOS_PROYECTO_FALLBACK
    if estado not in validos:
        raise ValueError(f"Estado de cotización inválido: {estado}")
    cot.estado = estado
    updates = ["estado", "actualizado_en"]
    ahora = timezone.now()
    if estado == "enviada" and not cot.enviada_en:
        cot.enviada_en = ahora
        updates.append("enviada_en")
    elif estado == "aprobada" and not cot.aprobada_en:
        cot.aprobada_en = ahora
        updates.append("aprobada_en")
    elif estado == "pagada" and not cot.pagada_en:
        cot.pagada_en = ahora
        updates.append("pagada_en")
    cot.save(update_fields=updates)
    evento = {
        "enviada": "cotizacion.enviada",
        "aprobada": "cotizacion.aprobada",
        "pagada": "cotizacion.pagada",
        "anticipo": "cotizacion.anticipo_requerido",
    }.get(estado, "cotizacion.actualizada")
    _emitir(evento, cot, actor, {"version": cot.version})
    # S-LC-Feedback-V13: al pasar a «Anticipo» se avisa a finanzas para que
    # registren el ingreso del anticipo ligado al proyecto. Best-effort.
    if estado == "anticipo" and cot.proyecto_id:
        try:
            from apps.taller_home.push_handlers import (
                notificar_anticipo_por_registrar,
            )
            notificar_anticipo_por_registrar(cot)
        except Exception:  # noqa: BLE001 — un push roto no rompe el cambio de estatus
            pass
    return cot


# --- KPIs ----------------------------------------------------------------

def kpis_landing() -> dict:
    """Conteos para el header de la lista de Cotizaciones.

    Cuenta DOCUMENTOS (todas las versiones), que es justo lo que la lista de
    abajo muestra. El embudo del negocio se cuenta por OPORTUNIDAD (la última
    versión de cada proyecto) y vive en `apps.cotizaciones.embudo` — son dos
    preguntas distintas y por eso son dos números distintos.

    Clasifica por FASE, no por el nombre del estado: el despacho renombra y
    apaga estados a su gusto. Antes se buscaban los literales 'borrador' y
    'enviada'; Learning Center los había apagado y todos los conteos daban
    cero, así que la conversión salía 100%.
    """
    from datetime import date

    from apps.cotizaciones.embudo import dias_desde_envio
    from apps.cotizaciones.models import (
        FASE_ARMADA,
        FASE_ENVIADA,
        FASE_GANADA,
        FASE_PERDIDA,
        slugs_de_fase,
    )

    hoy = date.today()
    perdidas_slugs = slugs_de_fase(FASE_PERDIDA)
    qs = Cotizacion.objects.exclude(estado__in=perdidas_slugs) if perdidas_slugs \
        else Cotizacion.objects.all()

    armadas = slugs_de_fase(FASE_ARMADA)
    enviadas = slugs_de_fase(FASE_ENVIADA)
    ganadas = slugs_de_fase(FASE_GANADA)

    try:
        from ajustes.models import ConfiguracionAnalisis
        dias_silencio = ConfiguracionAnalisis.obtener().dias_silencio_cotizacion or 0
    except Exception:  # noqa: BLE001
        dias_silencio = 45

    # Enviadas que ya pasaron el plazo de silencio configurado en Gerencia
    # (antes era 'fecha_validez vencida', que casi nadie llena).
    enfriadas = 0
    if enviadas and dias_silencio:
        for cot in qs.filter(estado__in=enviadas).only(
            "enviada_en", "fecha_emision", "creado_en"
        ):
            if dias_desde_envio(cot, hoy) >= dias_silencio:
                enfriadas += 1

    # Ganadas con anticipo por facturar: se itera porque `anticipo_monto` es
    # una property derivada. El conjunto es de decenas.
    anticipos_pendientes = 0
    if ganadas:
        anticipos_pendientes = sum(
            1
            for c in qs.filter(estado__in=ganadas, anticipo_facturado_en__isnull=True)
            if c.anticipo_monto > 0
        )

    return {
        # Claves históricas (las consumen la lista y Sala de Juntas), ya con la
        # semántica correcta.
        "borradores": qs.filter(estado__in=armadas).count() if armadas else 0,
        "enviadas": qs.filter(estado__in=enviadas).count() if enviadas else 0,
        "aprobadas": qs.filter(estado__in=ganadas).count() if ganadas else 0,
        "vencidas": enfriadas,
        "anticipos_pendientes": anticipos_pendientes,
        # Nombres claros para lo nuevo.
        "sin_enviar": qs.filter(estado__in=armadas).count() if armadas else 0,
        "ganadas": qs.filter(estado__in=ganadas).count() if ganadas else 0,
        "enfriadas": enfriadas,
        "perdidas": (
            Cotizacion.objects.filter(estado__in=perdidas_slugs).count()
            if perdidas_slugs else 0
        ),
        "dias_silencio": dias_silencio,
    }


def cotizaciones_con_anticipo_pendiente():
    """Lista de cotizaciones aprobadas con `anticipo_pendiente=True`.

    Útil para CxC unificado (S-Finanzas-V2 #D) y KPIs. Itera porque
    `anticipo_monto` es una property derivada; sobre 5 usuarios el
    conjunto es pequeño (< 50 por mes esperado).
    """
    qs = (
        Cotizacion.objects.filter(estado="aprobada", anticipo_facturado_en__isnull=True)
        .select_related("cliente", "proyecto")
        .order_by("-aprobada_en")
    )
    return [c for c in qs if c.anticipo_monto > 0]
