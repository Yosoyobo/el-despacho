"""El Testigo — el aviso de edición pisada (S-Pendientes-Sep28 · Deploy 3).

El problema que resuelve: si dos personas —o dos ventanas de la misma— tienen
abierto el mismo registro, el último guardado pisaba al otro **sin avisar**. El
autoguardado del proyecto lo hacía constantemente.

Cómo, sin migraciones:

1. **Al pintar el formulario** se le cuelga un campo oculto, el *testigo*: la
   huella de CADA campo tal como estaba en la base cuando se abrió la pantalla
   (y de cada línea de sus formsets, y de lo que se guarda por fuera del form,
   como los procesos de una tarjeta o las tasas de una cotización).

2. **Al recibir el POST** se comparan tres cosas por campo:
   - lo que había cuando abriste (el testigo),
   - lo que hay HOY en la base (el `initial` del form armado sobre la instancia
     que se acaba de leer),
   - lo que mandas.

   Hay **choque** sólo si un campo cambió en la base desde que abriste **y** lo
   que mandas es distinto de lo que hay ahora; o sea, si guardar reescribiría el
   trabajo de alguien más. Entonces NO se guarda y se pregunta.

¿Por qué campo por campo y no un solo sello (`actualizado_en`)? Porque el sello
se mueve con cambios que no chocan con nada: la barra de estado del proyecto,
recalcular su monto, reordenar tarjetas, una celda de la edición rápida en otro
campo… Con un solo sello el autoguardado se habría peleado consigo mismo justo
después de picar un estado (la barra lo guarda aparte y el JS sincroniza el
campo oculto). Campo por campo, sólo avisa cuando de verdad se iba a pisar algo.
El sello sí se usa: para decir **cuándo** fue.

3. **Quién.** Ningún modelo guarda `actualizado_por`, así que cada guardado que
   pasa por aquí deja su *firma* en el caché: quién, cuándo, desde qué ventana y
   con qué `actualizado_en` quedó la base. Si la firma corresponde al estado
   actual, se nombra a la persona; si no —lo cambió otra pantalla o El Chalán—
   se dice «otra persona u otra ventana» con la hora que marca la base.

Una petición **sin testigo** (una pestaña abierta antes de este cambio, una
integración, un test viejo) pasa como siempre: no hay con qué comparar y
bloquearla dejaría a alguien sin poder guardar. Tampoco se revisa cuando llega
`_edicion_forzar=1` — es el «Guardar la mía de todos modos».

**Varias piezas en un mismo POST.** El autoguardado del proyecto manda, además
de lo suyo, la pestaña de una versión de cotización si está abierta. Cada pieza
lleva su propio testigo (con su propio `campo`, porque la pestaña se carga
después de la página) y `revisar_juntas` las revisa todas: si una choca, no se
guarda ninguna —el guardado es uno solo— y el aviso nombra lo de todas.

Nada de esto lanza hacia afuera: si el caché no responde, el aviso sale sin
nombre; si algo no se puede comparar, se deja pasar. El testigo protege, no
estorba.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

CAMPO_TESTIGO = "_edicion_testigo"
CAMPO_FORZAR = "_edicion_forzar"
#: Cabecera con la que el 409 del autoguardado le avisa a `ui.js` que su
#: respuesta sí se pinta (trae el aviso por OOB) aunque sea un 4xx.
CABECERA_CHOQUE = "X-Edicion-Choque"
#: id del contenedor del testigo: el OOB del autoguardado lo reemplaza entero.
ID_CONTENEDOR = "edicion-testigo"
VERSION = 1
#: La firma dura lo que una pestaña olvidada abierta: un mes.
TTL_FIRMA = 60 * 60 * 24 * 30
#: Cuántos campos se nombran en el aviso antes de «y N más».
MAX_CAMPOS_AVISO = 6

# Campos de los formsets que no son datos: su pk, la casilla de borrar, el orden.
_NO_DATOS = frozenset({"id", "DELETE", "ORDER"})


class _SinDato:
    """Centinela: el valor no llegó en el POST (no hay nada que comparar)."""

    def __repr__(self) -> str:  # pragma: no cover - sólo para depurar
        return "SIN_DATO"


SIN_DATO = _SinDato()


# ── Huellas ───────────────────────────────────────────────────────────────


def _dec(d: Decimal) -> str:
    """«10», «10.0» y «10.00» son el mismo número: se comparan igual."""
    try:
        return format(d.normalize(), "f")
    except Exception:  # noqa: BLE001 - NaN/Infinity
        return str(d)


def _a_json(valor):
    """Versión serializable y estable de un valor (listas en su orden)."""
    if isinstance(valor, Decimal):
        return _dec(valor)
    if isinstance(valor, dict):
        return {str(k): _a_json(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_a_json(v) for v in valor]
    if valor is None or isinstance(valor, bool | int | float | str):
        return valor
    return str(valor)


def lista_canonica(valor) -> str:
    """Cadena estable de una estructura ORDENADA (procesos, líneas, tasas…).

    A diferencia de `canonico`, aquí el orden importa: dos procesos en otro orden
    sí son un cambio."""
    return json.dumps(_a_json(valor), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def canonico(valor) -> str:
    """Cadena estable de un valor de formulario.

    Una lista (un M2M, unos checkboxes) se ordena: el orden en que la base
    devuelve las filas no es un cambio de nadie."""
    if valor is None or valor is SIN_DATO:
        return ""
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, Decimal):
        return _dec(valor)
    if isinstance(valor, str):
        return valor
    if hasattr(valor, "_meta") and hasattr(valor, "pk"):
        return str(valor.pk)
    if isinstance(valor, list | tuple | set | frozenset):
        return json.dumps(sorted(canonico(v) for v in valor), ensure_ascii=False)
    if isinstance(valor, dict):
        return lista_canonica(valor)
    return str(valor)


def huella(valor) -> str:
    return hashlib.sha1(canonico(valor).encode("utf-8")).hexdigest()[:10]


def _es_fk_inline(campo) -> bool:
    from django.forms.models import InlineForeignKeyField
    return isinstance(campo, InlineForeignKeyField)


def huellas_de_form(form, ignorar=()) -> dict[str, str]:
    """La huella de cada campo con lo que hay en la BASE.

    Sale del `initial`, que Django arma al construir el form a partir de la
    instancia — así que vale igual para un form sin datos (al pintar) que para
    uno con el POST (al recibir), y no le afecta que `is_valid()` ya haya
    escrito los valores nuevos sobre la instancia (§14 Bug D)."""
    salida: dict[str, str] = {}
    for nombre, campo in form.fields.items():
        if nombre in _NO_DATOS or nombre in ignorar or _es_fk_inline(campo):
            continue
        try:
            salida[nombre] = huella(campo.prepare_value(form[nombre].initial))
        except Exception:  # noqa: BLE001 - un campo raro no tumba el testigo
            continue
    return salida


def _cambiados_por_mi(form, ignorar=()) -> set[str]:
    """Campos donde lo que mandas es distinto de lo que hay HOY en la base.

    Se saltan los que no llegaron en el POST: una vista que conserva el valor
    cuando falta (el régimen fiscal del proyecto) no está pisando nada.

    NO se usa `form.changed_data`: en un campo con `show_hidden_initial` (Django
    lo prende solo cuando el default del modelo es una función, como la fecha de
    emisión) compara contra el `initial-…` oculto que viajó en el POST —lo que
    había al ABRIR—, no contra la base. Con eso, una fecha que otra persona
    cambió y que tú reenvías vieja no contaría como «la mandas distinta» y la
    pisarías en silencio."""
    if not getattr(form, "is_bound", False):
        return set()
    salida: set[str] = set()
    for nombre, campo in form.fields.items():
        if nombre in ignorar or nombre in ("id", "ORDER") or _es_fk_inline(campo):
            continue
        try:
            bf = form[nombre]
            if not campo.has_changed(bf.initial, bf.data):
                continue
        except Exception:  # noqa: BLE001 - un campo raro no tumba el testigo
            continue
        omitido = False
        with contextlib.suppress(Exception):
            omitido = campo.widget.value_omitted_from_data(
                form.data, form.files, form.add_prefix(nombre))
        if not omitido:
            salida.add(nombre)
    return salida


def _huella_posteada(form, nombre) -> str | None:
    """La huella de lo que mandas, normalizado igual que la de la base.

    Sólo sirve para saber si TÚ tocaste el campo (para el texto que se copia):
    si la normalización no empata, se asume que sí — sobra un renglón, no falta."""
    campo = form.fields.get(nombre)
    if campo is None:
        return None
    try:
        return huella(campo.prepare_value(campo.to_python(form[nombre].data)))
    except Exception:  # noqa: BLE001
        return None


def _etiqueta(form, nombre) -> str:
    campo = form.fields.get(nombre)
    etiqueta = str(getattr(campo, "label", "") or "").strip()
    # El par día + hora del proyecto: «Hora» a secas no dice de qué.
    if nombre.endswith("_hora"):
        dia = form.fields.get(nombre[: -len("_hora")] + "_dia")
        if dia is not None and dia.label:
            return f"{dia.label} (hora)"
    return etiqueta or nombre.replace("_", " ").capitalize()


def _legible(form, nombre) -> str:
    """Lo que mandas, como lo leería una persona (no un pk ni un «on»)."""
    from django import forms

    campo = form.fields.get(nombre)
    dato = form[nombre].data if campo is not None else None
    try:
        if isinstance(campo, forms.BooleanField):
            return "Sí" if campo.to_python(dato) else "No"
        if isinstance(campo, forms.ModelMultipleChoiceField):
            objs = campo.to_python(dato)
            return ", ".join(str(o) for o in objs) or "(ninguno)"
        if isinstance(campo, forms.ModelChoiceField):
            obj = campo.to_python(dato)
            return str(obj) if obj else "(vacío)"
        if isinstance(campo, forms.ChoiceField):
            mapa = {}
            for clave, etiqueta in campo.choices:
                if isinstance(etiqueta, list | tuple):
                    continue  # grupos: no se aplanan
                mapa[str(getattr(clave, "value", clave))] = str(etiqueta)
            if isinstance(dato, list | tuple):
                return ", ".join(mapa.get(str(d), str(d)) for d in dato) or "(ninguno)"
            return mapa.get(str(dato), str(dato or "")) or "(vacío)"
    except Exception:  # noqa: BLE001
        pass
    if isinstance(dato, list | tuple):
        return ", ".join(str(d) for d in dato) or "(vacío)"
    texto = "" if dato is None else str(dato)
    return texto.strip() or "(vacío)"


# ── Piezas que describe cada vista ────────────────────────────────────────


@dataclass
class Extra:
    """Algo que se guarda por fuera de los campos del form.

    `actual` es la cadena canónica de lo que hay en la base; `posteado` lo que
    llegó (ya canónico), o una función sin argumentos que lo calcula —se llama
    sólo si hace falta, porque normalizar un JSON puede costar una consulta—,
    o `SIN_DATO` si no llegó. `legible` describe lo mandado para copiarlo."""

    etiqueta: str
    actual: str
    posteado: Any = SIN_DATO
    legible: Callable[[], str] | None = None

    def valor_posteado(self):
        valor = self.posteado() if callable(self.posteado) else self.posteado
        return SIN_DATO if valor is SIN_DATO else canonico(valor)

    def texto(self) -> str:
        if self.legible is None:
            return "(lo cambiaste)"
        try:
            return self.legible() or "(vacío)"
        except Exception:  # noqa: BLE001
            return "(lo cambiaste)"


@dataclass
class Grupo:
    """Un formset de líneas (productos, contactos, partidas…)."""

    formset: Any
    #: Cómo se nombra una línea en el aviso (««Playera dry fit»»). Recibe la
    #: instancia que está HOY en la base.
    etiqueta_linea: Callable[[Any], str] | None = None
    #: Lo que la línea guarda por fuera de sus campos. Recibe el form de la línea.
    extras_linea: Callable[[Any], dict[str, Extra]] | None = None
    ignorar: tuple = ()


@dataclass
class Choque:
    campos: list[str]
    quien: str
    cuando: datetime | None
    #: Lo que la persona escribió, legible, para el portapapeles.
    texto: str
    #: El testigo que llegó en el POST: se vuelve a pintar TAL CUAL, para que un
    #: «Guardar» normal siga chocando hasta que se decida qué hacer.
    testigo: str

    @property
    def campos_visibles(self) -> list[str]:
        return self.campos[:MAX_CAMPOS_AVISO]

    @property
    def campos_de_mas(self) -> int:
        return max(0, len(self.campos) - MAX_CAMPOS_AVISO)


def nueva_ventana() -> str:
    return uuid.uuid4().hex[:12]


def leer_testigo(crudo) -> dict | None:
    if not crudo:
        return None
    try:
        datos = json.loads(crudo)
    except (TypeError, ValueError):
        return None
    if not isinstance(datos, dict) or datos.get("v") != VERSION:
        return None
    return datos


def _formas_existentes(formset):
    """Las líneas que YA estaban guardadas (no las nuevas del formset)."""
    try:
        return list(formset.initial_forms)
    except Exception:  # noqa: BLE001
        return []


class Edicion:
    """Lo que se edita en una pantalla: un objeto, su form y sus formsets.

    Uso en la vista::

        ed = Edicion(obj, form, grupos={"items": Grupo(formset)})
        # GET → contexto(request, testigo=ed.testigo())
        # POST, ANTES de guardar → choque = ed.revisar(request)
        # tras guardar → firmar(obj, request.user, ventana_posteada(request))

    `form` puede ser None cuando la pieza es sólo un formset (la pestaña de una
    versión de cotización). `campo` es el nombre del oculto donde viaja SU
    testigo: el de siempre, salvo en una pieza que comparte el POST con otra.
    """

    def __init__(self, obj, form, *, grupos: dict[str, Grupo] | None = None,
                 extras: dict[str, Extra] | None = None, ignorar=(),
                 campo: str = CAMPO_TESTIGO):
        self.obj = obj
        self.form = form
        self.grupos = grupos or {}
        self.extras = extras or {}
        self.ignorar = tuple(ignorar)
        self.campo = campo

    # ── El testigo (al pintar) ────────────────────────────────────────────

    def _huellas_linea(self, grupo: Grupo, form) -> dict[str, str]:
        datos = huellas_de_form(form, grupo.ignorar)
        if grupo.extras_linea is not None:
            for clave, extra in (grupo.extras_linea(form) or {}).items():
                datos["~" + clave] = huella(extra.actual)
        return datos

    def huellas(self) -> dict:
        datos = {
            "f": huellas_de_form(self.form, self.ignorar) if self.form is not None else {},
            "x": {k: huella(e.actual) for k, e in self.extras.items()},
            "g": {},
        }
        for clave, grupo in self.grupos.items():
            lineas = {}
            for f in _formas_existentes(grupo.formset):
                pk = getattr(getattr(f, "instance", None), "pk", None)
                if pk is not None:
                    lineas[str(pk)] = self._huellas_linea(grupo, f)
            datos["g"][clave] = lineas
        return datos

    def testigo(self, ventana: str | None = None) -> str:
        datos = self.huellas()
        datos.update({"v": VERSION, "w": ventana or nueva_ventana(),
                      "t": round(time.time(), 3)})
        return json.dumps(datos, ensure_ascii=False, separators=(",", ":"))

    def testigo_para(self, request) -> str:
        """El testigo que se pinta en esta respuesta.

        Tras un POST que NO se guardó (errores de validación) se conserva el que
        llegó: la persona sigue editando sobre lo que abrió, no sobre lo de hoy."""
        if request.method == "POST":
            crudo = request.POST.get(self.campo)
            if leer_testigo(crudo) is not None:
                return crudo
        return self.testigo()

    # ── La revisión (al recibir) ──────────────────────────────────────────

    def revisar(self, request) -> Choque | None:
        """¿Guardar esto pisaría el trabajo de alguien? None = adelante.

        Llamarla ANTES de guardar (y de preferencia antes de `is_valid()`)."""
        post = request.POST
        if (post.get(CAMPO_FORZAR) or "").strip() == "1":
            return None
        crudo = post.get(self.campo)
        original = leer_testigo(crudo)
        if original is None:
            return None
        try:
            choques, mios = self._comparar(original)
        except Exception:  # noqa: BLE001 - el testigo protege, no estorba
            return None
        if not choques:
            return None
        quien, cuando = self._quien(request, original)
        vistos: list[str] = []
        for c in choques:
            if c not in vistos:
                vistos.append(c)
        return Choque(campos=vistos, quien=quien, cuando=cuando,
                      texto=_texto_mio(self.obj, mios), testigo=crudo)

    def texto_mio(self, request) -> str:
        """Lo que la persona cambió en ESTA pieza, legible, aunque no choque.

        Para el portapapeles cuando choca OTRA pieza del mismo POST: tampoco esto
        se guardó. Vacío si no hay testigo o no cambió nada."""
        original = leer_testigo(request.POST.get(self.campo))
        if original is None:
            return ""
        try:
            _choques, mios = self._comparar(original)
        except Exception:  # noqa: BLE001
            return ""
        return _texto_mio(self.obj, mios) if mios else ""

    def _comparar(self, original: dict) -> tuple[list[str], list[tuple[str, str]]]:
        choques: list[str] = []
        mios: list[tuple[str, str]] = []

        # 1) El formulario principal (una pieza de sólo líneas no tiene).
        of = original.get("f") or {}
        form = self.form
        actual = huellas_de_form(form, self.ignorar) if form is not None else {}
        cambiados = _cambiados_por_mi(form, self.ignorar) if form is not None else set()
        for nombre in (form.fields if form is not None else ()):
            if nombre not in cambiados:
                continue
            etiqueta = _etiqueta(form, nombre)
            antes = of.get(nombre)
            if antes is not None and actual.get(nombre) not in (None, antes):
                choques.append(etiqueta)
            if antes is None or _huella_posteada(form, nombre) != antes:
                mios.append((etiqueta, _legible(form, nombre)))

        # 2) Lo que se guarda por fuera del form.
        ox = original.get("x") or {}
        for clave, extra in self.extras.items():
            _revisar_extra(extra, ox.get(clave), choques, mios)

        # 3) Las líneas.
        og = original.get("g") or {}
        for clave, grupo in self.grupos.items():
            self._revisar_grupo(grupo, og.get(clave) or {}, choques, mios)
        return choques, mios

    def _revisar_grupo(self, grupo: Grupo, originales: dict, choques, mios) -> None:
        fs = grupo.formset
        pk_nombre = fs.model._meta.pk.name
        for f in _formas_existentes(fs):
            crudo = str(f.data.get(f.add_prefix(pk_nombre)) or "").strip()
            if not crudo:
                continue
            antes = originales.get(crudo)
            if antes is None:
                continue  # la línea no estaba cuando abriste: nada que comparar
            borrar = str(f.data.get(f.add_prefix("DELETE")) or "").lower() in (
                "on", "true", "1")
            inst = f.instance if getattr(f.instance, "pk", None) is not None else None
            if inst is None:
                # Alguien la quitó mientras la tenías abierta.
                if not borrar:
                    choques.append("Una línea que alguien más quitó")
                continue
            etiqueta_linea = (grupo.etiqueta_linea(inst) if grupo.etiqueta_linea
                              else "una línea")
            actual = self._huellas_linea(grupo, f)
            otros = {k for k, v in antes.items() if actual.get(k) not in (None, v)}
            if borrar:
                if otros:
                    choques.append(f"{etiqueta_linea} (la quitas, pero alguien más la cambió)")
                mios.append((etiqueta_linea, "La quitaste"))
                continue
            cambiados = _cambiados_por_mi(f, grupo.ignorar)
            for nombre in f.fields:
                if nombre not in cambiados or nombre == "DELETE":
                    continue
                etiqueta = f"{_etiqueta(f, nombre)} de {etiqueta_linea}"
                if nombre in otros:
                    choques.append(etiqueta)
                previo = antes.get(nombre)
                if previo is None or _huella_posteada(f, nombre) != previo:
                    mios.append((etiqueta, _legible(f, nombre)))
            if grupo.extras_linea is not None and any(k.startswith("~") for k in otros):
                for clave, extra in (grupo.extras_linea(f) or {}).items():
                    _revisar_extra(extra, antes.get("~" + clave), choques, mios)
            elif grupo.extras_linea is not None:
                # Nadie más los tocó: no pueden chocar, pero lo que TÚ cambiaste
                # también va al portapapeles.
                for clave, extra in (grupo.extras_linea(f) or {}).items():
                    _extra_mio(extra, antes.get("~" + clave), mios)

    def _quien(self, request, original: dict) -> tuple[str, datetime | None]:
        firma = leer_firma(self.obj)
        marca = _iso(getattr(self.obj, "actualizado_en", None))
        desde = float(original.get("t") or 0)
        if firma and firma.get("m") == marca and float(firma.get("en") or 0) > desde:
            cuando = datetime.fromtimestamp(float(firma["en"]), tz=UTC)
            if firma.get("uid") != getattr(request.user, "pk", None):
                return (firma.get("nombre") or "Otra persona"), cuando
            ventana = firma.get("w") or ""
            if ventana and ventana != original.get("w"):
                return "Tú mismo, desde otra ventana o pestaña", cuando
            if not ventana:
                return "Tú mismo, desde otra pantalla", cuando
        return "Otra persona u otra ventana", getattr(self.obj, "actualizado_en", None)


def revisar_juntas(request, ediciones: list[Edicion]) -> Choque | None:
    """Revisa varias piezas que viajan en el MISMO POST. None = adelante.

    El guardado es uno solo, así que si UNA choca no se guarda ninguna, y el
    aviso lo dice completo: los campos que chocaron de todas y, para copiar, lo
    que la persona cambió en todas (lo de la pieza que no chocó tampoco se
    guardó). El testigo del choque es el de la PRIMERA pieza —la dueña del
    contenedor del aviso—, tal como llegó: así un «Guardar» normal sigue
    chocando hasta que se decida. Las demás conservan el suyo en la página.

    `_edicion_forzar=1` vale para todas: «Guardar la mía» es una sola decisión.
    """
    if not ediciones:
        return None
    choques = [e.revisar(request) for e in ediciones]
    if not any(c is not None for c in choques):
        return None
    primero = next(c for c in choques if c is not None)
    campos: list[str] = []
    textos: list[str] = []
    for ed_, c in zip(ediciones, choques, strict=True):
        if c is not None:
            campos.extend(x for x in c.campos if x not in campos)
            textos.append(c.texto)
        else:
            texto = ed_.texto_mio(request)
            if texto:
                textos.append(texto)
    return Choque(campos=campos, quien=primero.quien, cuando=primero.cuando,
                  texto="\n\n".join(textos),
                  testigo=request.POST.get(ediciones[0].campo) or "")


def _revisar_extra(extra: Extra, antes: str | None, choques, mios) -> None:
    if antes is None:
        return
    posteado = extra.valor_posteado()
    if posteado is SIN_DATO or posteado == extra.actual:
        return  # no llegó, o lo que mandas es lo que ya hay: no pisa nada
    if huella(extra.actual) != antes:
        choques.append(extra.etiqueta)
    if huella(posteado) != antes:
        mios.append((extra.etiqueta, extra.texto()))


def _extra_mio(extra: Extra, antes: str | None, mios) -> None:
    posteado = extra.valor_posteado()
    if posteado is SIN_DATO or posteado == extra.actual:
        return
    if antes is None or huella(posteado) != antes:
        mios.append((extra.etiqueta, extra.texto()))


def _texto_mio(obj, mios: list[tuple[str, str]]) -> str:
    titulo = str(obj) if obj is not None else ""
    renglones = [f"Lo que tenía escrito en «{titulo}»:" if titulo else "Lo que tenía escrito:"]
    if not mios:
        renglones.append("(No cambiaste nada: lo que tenías es lo que habías abierto.)")
    vistos = set()
    for etiqueta, valor in mios:
        if (etiqueta, valor) in vistos:
            continue
        vistos.add((etiqueta, valor))
        renglones.append(f"• {etiqueta}: {valor}")
    return "\n".join(renglones)


# ── La firma (quién guardó por última vez) ─────────────────────────────────


def _iso(valor) -> str:
    if valor is None:
        return ""
    try:
        return valor.isoformat()
    except AttributeError:
        return str(valor)


def _clave_firma(obj) -> str:
    return f"edicion:firma:{obj._meta.label_lower}:{obj.pk}"


def leer_firma(obj) -> dict | None:
    if obj is None or getattr(obj, "pk", None) is None:
        return None
    try:
        from django.core.cache import cache
        datos = cache.get(_clave_firma(obj))
    except Exception:  # noqa: BLE001 - sin caché, el aviso sale sin nombre
        return None
    return datos if isinstance(datos, dict) else None


def firmar(obj, usuario, ventana: str | None = None) -> None:
    """Deja la firma del guardado que ACABA de pasar. Nunca lanza.

    Se lee `actualizado_en` de la base (no de la instancia): la vista pudo haber
    guardado otra vez después (recalcular el monto, espejar un contacto) y la
    firma tiene que empatar con el estado final."""
    if obj is None or getattr(obj, "pk", None) is None or usuario is None:
        return
    try:
        from django.core.cache import cache
        marca = (type(obj)._base_manager.filter(pk=obj.pk)
                 .values_list("actualizado_en", flat=True).first())
        nombre = (getattr(usuario, "nombre_completo", "") or "").strip() or getattr(
            usuario, "email", "") or "Otra persona"
        cache.set(_clave_firma(obj), {
            "uid": usuario.pk, "nombre": nombre, "en": time.time(),
            "w": ventana or "", "m": _iso(marca),
        }, TTL_FIRMA)
    except Exception:  # noqa: BLE001
        return


def ventana_posteada(request, campo: str = CAMPO_TESTIGO) -> str:
    datos = leer_testigo(request.POST.get(campo)) if request.method == "POST" else None
    return str((datos or {}).get("w") or "")


# ── Para las plantillas ────────────────────────────────────────────────────


def contexto(request, *, testigo: str, choque: Choque | None = None,
             archivos: bool = False) -> dict:
    """Lo que necesita `edicion/_testigo.html`.

    `url` es a dónde lleva «Ver su versión»: la MISMA pantalla, pero con GET
    (tras un POST no se puede recargar sin que el navegador ofrezca reenviarlo).
    """
    return {
        "id": ID_CONTENEDOR,
        "testigo": testigo,
        "choque": choque,
        "url": request.get_full_path(),
        "archivos": archivos,
    }


def respuesta_choque_htmx(request, edicion: dict, *, indicador_id: str = ""):
    """El 409 del autoguardado: trae el aviso y el testigo viejo por OOB.

    `ui.js` lo reconoce por la cabecera y deja que se pinte (un 4xx normalmente
    no se pinta). Con el aviso en pantalla, el autoguardado se detiene."""
    from django.shortcuts import render

    resp = render(request, "edicion/_choque_oob.html",
                  {"edicion": edicion, "indicador_id": indicador_id}, status=409)
    resp[CABECERA_CHOQUE] = "1"
    return resp
