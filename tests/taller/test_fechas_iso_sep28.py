"""Candado: todo `<input type="date">` se pinta en ISO (`AAAA-MM-DD`).

Con `es-mx` activo, un `DateInput` sin `format=` localiza el valor
(«28/09/2026») y el navegador, que sólo entiende ISO, muestra el campo EN
BLANCO: al editar una cotización la fecha de emisión parecía borrada. Pasó en
ocho formularios a la vez (2026-09-28).
"""
import datetime
import pathlib
import re

from django.utils import translation

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CARPETAS = ("el-taller", "la-gerencia", "la-recepcion", "cuentas", "ajustes", "papeleo", "lib")


def test_ningun_dateinput_de_tipo_fecha_sin_formato_iso():
    patron = re.compile(r"DateInput\((?P<args>[^)]*)\)")
    culpables = []
    for carpeta in CARPETAS:
        for py in (RAIZ / carpeta).rglob("*.py"):
            if "migrations" in py.parts:
                continue
            texto = py.read_text(encoding="utf-8")
            for m in patron.finditer(texto):
                args = m.group("args")
                if '"date"' in args and "format=" not in args:
                    linea = texto[: m.start()].count("\n") + 1
                    culpables.append(f"{py.relative_to(RAIZ)}:{linea}")
    assert not culpables, (
        "DateInput de tipo fecha sin format=\"%Y-%m-%d\" (se ve en blanco con es-mx): "
        + ", ".join(culpables)
    )


def test_la_fecha_de_emision_de_la_cotizacion_llega_al_navegador_en_iso():
    from apps.cotizaciones.forms import CotizacionForm

    campo = CotizacionForm.base_fields["fecha_emision"]
    with translation.override("es-mx"):
        html = campo.widget.render("fecha_emision", datetime.date(2026, 9, 28))
    assert 'value="2026-09-28"' in html, html
