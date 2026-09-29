"""Los PDF unidos del papeleo se limpian de El Almacén (deuda Sep28).

«Unir en un PDF» dejaba el resultado en el almacén para siempre. Ahora nace con
la marca `temporal` y `papeleo_limpiar_unidos` lo borra pasados sus días, salvo
que el mismo archivo lo comparta otro registro (el almacén es por contenido).
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def almacen_propio(settings, tmp_path):
    from lib import almacen

    settings.MEDIOS_DIR = str(tmp_path / "medios")
    almacen.olvidar_meta()
    yield almacen
    almacen.olvidar_meta()


@pytest.fixture
def jefe(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    return u


@pytest.fixture
def union(monkeypatch):
    from lib import gotenberg, paperless

    monkeypatch.setattr(paperless, "esta_configurado", lambda: True)
    monkeypatch.setattr(paperless, "llave", lambda: "k")
    docs = {1: b"%PDF-1.4 uno", 2: b"%PDF-1.4 dos"}
    monkeypatch.setattr(paperless, "archivo",
                        lambda i, cara="preview": (docs[int(i)], "application/pdf"))
    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    monkeypatch.setattr(gotenberg, "unir", lambda pdfs: b"%PDF-1.4 UNIDO " + b"|".join(pdfs))


def _unir(client) -> str:
    r = client.post("/papeleo/unir", {"doc": ["1", "2"]})
    assert r.status_code == 302
    return r["Location"].rstrip("/").split("/")[-1]


def _envejecer(almacen, clave, dias=8):
    """Le cambia la fecha de nacimiento al meta (lo que lee la limpieza)."""
    datos = dict(almacen.meta(clave))
    datos["creado"] = (datetime.now(UTC) - timedelta(days=dias)).isoformat()
    almacen._escribir_meta(clave, datos)


def _limpiar(*args) -> str:
    salida = StringIO()
    call_command("papeleo_limpiar_unidos", *args, stdout=salida)
    return salida.getvalue()


def test_el_unido_nace_marcado_como_temporal(client, jefe, union, almacen_propio):  # noqa: ARG001
    clave = _unir(client)
    datos = almacen_propio.meta(clave)
    assert datos["temporal"] == "papeleo-unir"
    assert datos["creado"]


def test_borra_el_viejo_y_deja_el_reciente(client, jefe, union, almacen_propio,  # noqa: ARG001
                                           monkeypatch):
    from lib import gotenberg

    viejo = _unir(client)
    _envejecer(almacen_propio, viejo)
    monkeypatch.setattr(gotenberg, "unir", lambda pdfs: b"%PDF-1.4 OTRO UNIDO")
    reciente = _unir(client)

    salida = _limpiar()
    assert not almacen_propio.existe(viejo)
    assert almacen_propio.existe(reciente)
    assert "Se borraron 1" in salida


def test_en_seco_no_borra_nada(client, jefe, union, almacen_propio):  # noqa: ARG001
    clave = _unir(client)
    _envejecer(almacen_propio, clave)
    salida = _limpiar("--dry-run")
    assert almacen_propio.existe(clave)
    assert "borraría" in salida


def test_los_dias_se_pueden_ajustar(client, jefe, union, almacen_propio):  # noqa: ARG001
    clave = _unir(client)
    _envejecer(almacen_propio, clave, dias=8)
    _limpiar("--dias", "30")
    assert almacen_propio.existe(clave)
    _limpiar("--dias", "7")
    assert not almacen_propio.existe(clave)


def test_lo_que_otro_camino_guarda_igual_deja_de_ser_temporal(client, jefe, union,  # noqa: ARG001
                                                               almacen_propio):
    """Alguien bajó el unido y lo anexó a una cotización: MISMO archivo. La marca
    se cae al guardarse por el otro camino y la limpieza ya no lo toca."""
    clave = _unir(client)
    _envejecer(almacen_propio, clave)
    contenido, _m, _n = almacen_propio.leer(clave)
    otra = almacen_propio.guardar_bytes(contenido, mime="application/pdf", nombre="anexo.pdf")
    assert otra["id"] == clave and otra["duplicado"]
    assert "temporal" not in almacen_propio.meta(clave)

    _limpiar()
    assert almacen_propio.existe(clave)


def test_unir_lo_mismo_otra_vez_renueva_el_plazo(client, jefe, union, almacen_propio):  # noqa: ARG001
    clave = _unir(client)
    _envejecer(almacen_propio, clave)
    assert _unir(client) == clave
    assert almacen_propio.meta(clave)["temporal"] == "papeleo-unir"
    _limpiar()
    assert almacen_propio.existe(clave)


def test_un_registro_que_apunta_a_la_llave_la_salva(client, jefe, union, almacen_propio):
    """El segundo candado: la llave aparece en la base (aquí, el avatar)."""
    clave = _unir(client)
    _envejecer(almacen_propio, clave)
    jefe.avatar_drive_id = clave
    jefe.save(update_fields=["avatar_drive_id"])

    salida = _limpiar()
    assert almacen_propio.existe(clave)
    assert "se queda" in salida


def test_haber_visto_la_pantalla_no_lo_salva(client, jefe, union, almacen_propio):
    """La presencia anota `{"clave": …}` de la pantalla del unido: no es uso."""
    clave = _unir(client)
    _envejecer(almacen_propio, clave)
    jefe.actividad_kwargs = {"clave": clave}
    jefe.actividad_ruta = f"/papeleo/unido/{clave}/"
    jefe.save(update_fields=["actividad_kwargs", "actividad_ruta"])

    _limpiar()
    assert not almacen_propio.existe(clave)


def test_los_unidos_de_antes_de_la_marca_se_reconocen_por_nombre(almacen_propio):
    viejo = almacen_propio.guardar_bytes(b"%PDF-1.4 de antes", mime="application/pdf",
                                         nombre="Papeleo unido 2026-09-01 1015.pdf")["id"]
    otro_pdf = almacen_propio.guardar_bytes(b"%PDF-1.4 contrato", mime="application/pdf",
                                            nombre="Contrato.pdf")["id"]
    hace_un_mes = time.time() - 30 * 86400
    for clave in (viejo, otro_pdf):
        ruta = almacen_propio._dir_orig(clave) / "archivo"
        os.utime(ruta, (hace_un_mes, hace_un_mes))

    _limpiar()
    assert not almacen_propio.existe(viejo)
    assert almacen_propio.existe(otro_pdf), "sólo los unidos, nunca otro PDF"


def test_ya_limpio_la_pantalla_lo_dice_y_lo_olvida(client, jefe, union, almacen_propio):  # noqa: ARG001
    clave = _unir(client)
    _envejecer(almacen_propio, clave)
    _limpiar()
    r = client.get(f"/papeleo/unido/{clave}/", follow=True)
    assert "ya no está disponible" in r.content.decode()
    assert clave not in (client.session.get("papeleo_unidos") or {})
    assert client.get(f"/papeleo/unido/{clave}/bajar").status_code == 404


def test_el_cron_corre_diario_de_madrugada_dentro_del_bloque():
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent.parent
    cron = (raiz / "infra/cron/el-despacho.cron").read_text()
    linea = next(ln for ln in cron.splitlines()
                 if "papeleo_limpiar_unidos" in ln and not ln.startswith("#"))
    minuto, hora, dia, mes, semana = linea.split()[:5]
    assert (dia, mes, semana) == ("*", "*", "*")
    assert minuto.isdigit() and hora.isdigit() and int(hora) < 6
    assert cron.index("papeleo_limpiar_unidos") < cron.index("# <<< El Despacho <<<")
    # Ningún otro trabajo arranca en ese mismo minuto.
    ocupados = [ln.split()[:2] for ln in cron.splitlines()
                if ln and ln[0].isdigit() and "papeleo_limpiar_unidos" not in ln]
    assert [minuto, hora] not in ocupados
