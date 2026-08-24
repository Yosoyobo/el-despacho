"""S-Papeleo-V1 — el archivo de papeleo (Paperless) conectado a El Despacho.

Lo que estas pruebas cuidan, en orden de importancia:

1. **Sin llave se apaga, no falla.** Es el modo en el que va a estar el sistema
   hasta que alguien pegue el token, así que es el camino más transitado.
2. **El ligado automático es cobarde.** Con dos candidatos NO elige. Un
   documento sin ligar se arregla en diez segundos; uno ligado al cliente
   equivocado manda el contrato de alguien a la ficha de otro.
3. **La base impide la liga imposible** (dos entidades, o la misma dos veces),
   porque un constraint no se olvida y una promesa del código sí.
4. **Las dos direcciones no se confunden**: el enlace nunca puede salir con
   `http://paperless:8000`, que sólo existe dentro de Docker.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from lib import nombres, paperless

# ── lib.nombres — el criterio para comparar nombres de empresa ──────────────


def test_normaliza_quitando_acentos_puntuacion_y_terminacion_mercantil():
    assert (nombres.normalizar("MARKETING VEINTITRÉS GRADOS, S.A. DE C.V.")
            == nombres.normalizar("marketing veintitres grados"))


def test_compacto_junta_lo_que_un_humano_dice_de_corrido():
    assert nombres.compacto("KARI KARI") == "karikari"


def test_menciona_encuentra_el_nombre_dentro_de_un_texto_largo():
    texto = "Remisión de mercancía entregada a OPTIMIST S.A. de C.V. el 3 de marzo"
    assert nombres.menciona(texto, "Optimist") is True


def test_menciona_ignora_nombres_cortos_para_no_ligar_por_casualidad():
    """«Sol» aparece dentro de «solamente»; ligar por eso sería peor que nada."""
    assert nombres.menciona("El pago se hará solamente en efectivo", "Sol") is False


# ── Sin llave: se apaga solo ────────────────────────────────────────────────


def test_sin_llave_no_esta_configurado(monkeypatch, settings):  # noqa: ARG001
    monkeypatch.delenv(paperless.ENV_LLAVE, raising=False)
    monkeypatch.setattr(paperless, "llave", lambda: "")
    assert paperless.esta_configurado() is False


def test_sin_llave_buscar_devuelve_none_y_no_lanza(monkeypatch):
    """None es «no se pudo preguntar», distinto de [] que es «no hay nada»."""
    monkeypatch.setattr(paperless, "llave", lambda: "")
    assert paperless.buscar("contrato") is None


def test_buscar_sin_texto_no_pega_a_la_red(monkeypatch):
    def _explota(*a, **k):  # pragma: no cover — debe no llamarse
        raise AssertionError("no debió preguntarle a Paperless")

    monkeypatch.setattr(paperless, "_pedir", _explota)
    assert paperless.buscar("   ") == []


def test_la_capacidad_avisa_apagada_en_vez_de_tronar(monkeypatch):
    from capacidades import lecturas

    monkeypatch.setattr(paperless, "llave", lambda: "")
    salida = lecturas._h_buscar_papeleo({"texto": "contrato"}, None)
    assert salida["disponible"] is False
    assert "Gerencia" in salida["nota"]


# ── Las dos direcciones ─────────────────────────────────────────────────────


def test_el_enlace_nunca_usa_la_direccion_interna_de_docker(monkeypatch):
    """`http://paperless:8000` sólo existe dentro de la red de Docker: un enlace
    a esa dirección no abre en ninguna máquina. Sin dirección pública, vacío."""
    monkeypatch.setattr(paperless, "url_publica", lambda: "")
    assert paperless.url_web(7) == ""


def test_el_enlace_apunta_al_detalle_con_la_direccion_publica(monkeypatch):
    monkeypatch.setattr(paperless, "url_publica", lambda: "http://100.121.244.5:8204")
    assert paperless.url_web(7) == "http://100.121.244.5:8204/documents/7/details"


@pytest.mark.django_db
def test_la_direccion_publica_sale_de_la_configuracion():
    from ajustes.models import ConfiguracionPapeleo

    cfg = ConfiguracionPapeleo.obtener()
    cfg.url_publica = "http://10.0.0.9:8204/"
    cfg.save()
    # Sin la diagonal del final, para no armar enlaces con doble diagonal.
    assert paperless.url_publica() == "http://10.0.0.9:8204"


# ── El recorte del texto del OCR ────────────────────────────────────────────


def test_el_detalle_recorta_el_texto_y_lo_dice(monkeypatch):
    largo = "x" * (paperless.TOPE_TEXTO + 500)
    monkeypatch.setattr(paperless, "_pedir",
                        lambda *a, **k: {"id": 3, "title": "Contrato", "content": largo})
    d = paperless.detalle(3)
    assert len(d["texto"]) == paperless.TOPE_TEXTO
    assert d["texto_recortado"] is True


# ── La liga: lo que impide la base ──────────────────────────────────────────


@pytest.fixture
def cliente(db):
    from apps.la_cartera.models import Cliente

    return Cliente.objects.create(razon_social="Optimist Studio")


@pytest.fixture
def proveedor(db):
    from apps.el_catalogo.models import Proveedor

    return Proveedor.objects.create(razon_social="Simil Cuero Plymouth")


@pytest.mark.django_db
def test_no_se_puede_ligar_a_dos_cosas_a_la_vez(cliente, proveedor):
    from papeleo.models import PapeleoLigado

    with pytest.raises(IntegrityError), transaction.atomic():
        PapeleoLigado.objects.create(documento_id=1, cliente=cliente,
                                     proveedor=proveedor)


@pytest.mark.django_db
def test_no_se_puede_ligar_a_nada(cliente):  # noqa: ARG001
    from papeleo.models import PapeleoLigado

    with pytest.raises(IntegrityError), transaction.atomic():
        PapeleoLigado.objects.create(documento_id=1)


@pytest.mark.django_db
def test_la_misma_liga_dos_veces_no_duplica(cliente):
    from papeleo import ligado
    from papeleo.models import PapeleoLigado

    ligado.ligar(42, titulo="Contrato", cliente=cliente)
    ligado.ligar(42, titulo="Contrato", cliente=cliente)
    assert PapeleoLigado.objects.filter(documento_id=42).count() == 1


@pytest.mark.django_db
def test_el_mismo_documento_puede_ser_de_un_cliente_y_de_un_proyecto(cliente):
    """No es duplicado: una remisión pertenece al cliente Y a su proyecto."""
    from apps.los_proyectos.models import Proyecto

    from papeleo import ligado
    from papeleo.models import PapeleoLigado

    pr = Proyecto.objects.create(nombre="Gorras", cliente=cliente)
    ligado.ligar(9, cliente=cliente)
    ligado.ligar(9, proyecto=pr)
    assert PapeleoLigado.objects.filter(documento_id=9).count() == 2


@pytest.mark.django_db
def test_ligar_a_dos_entidades_falla_con_mensaje_claro(cliente, proveedor):
    """Fallar aquí con una frase entendible es mejor que fallar en la base."""
    from papeleo import ligado

    with pytest.raises(ValueError, match="exactamente una"):
        ligado.ligar(1, cliente=cliente, proveedor=proveedor)


@pytest.mark.django_db
def test_el_titulo_queda_copiado_para_que_la_fila_siga_legible(cliente):
    from papeleo import ligado

    fila = ligado.ligar(5, titulo="Contrato marco 2026", cliente=cliente)
    assert fila.titulo == "Contrato marco 2026"
    assert fila.a_quien == "Optimist Studio"


# ── El ligado automático: sólo cuando no hay duda ───────────────────────────


@pytest.mark.django_db
def test_apagado_no_liga_nada(cliente):  # noqa: ARG001
    from papeleo import ligado

    r = ligado.ligar_automatico(1, texto="Factura de Optimist Studio")
    assert r["ligado"] is None
    assert "apagado" in r["motivo"]


@pytest.fixture
def auto_encendido(db):
    from ajustes.models import ConfiguracionPapeleo

    cfg = ConfiguracionPapeleo.obtener()
    cfg.ligar_automatico = True
    cfg.save()
    return cfg


@pytest.mark.django_db
def test_liga_solo_cuando_hay_un_unico_candidato(cliente, auto_encendido):  # noqa: ARG001
    from papeleo import ligado

    r = ligado.ligar_automatico(11, titulo="Remisión",
                                texto="Entregado a Optimist Studio el lunes")
    assert r["ligado"] is not None
    assert r["ligado"].cliente_id == cliente.pk
    assert r["ligado"].automatico is True


@pytest.mark.django_db
def test_con_dos_candidatos_no_adivina(cliente, auto_encendido):  # noqa: ARG001
    """El caso que justifica la cobardía: dos clientes mencionados, ninguno gana."""
    from apps.la_cartera.models import Cliente

    from papeleo import ligado

    Cliente.objects.create(razon_social="Optimist Marketing")
    r = ligado.ligar_automatico(12, texto="Contrato entre Optimist Studio y "
                                          "Optimist Marketing")
    assert r["ligado"] is None
    assert "varios" in r["motivo"]


@pytest.mark.django_db
def test_el_proyecto_gana_sobre_el_cliente_porque_es_mas_especifico(
        cliente, auto_encendido):  # noqa: ARG001
    from apps.los_proyectos.models import Proyecto

    from papeleo import ligado

    pr = Proyecto.objects.create(nombre="Gorras bordadas", cliente=cliente)
    r = ligado.ligar_automatico(
        13, texto=f"Remisión del proyecto {pr.codigo} para Optimist Studio")
    assert r["ligado"].proyecto_id == pr.pk


@pytest.mark.django_db
def test_sin_reconocer_a_nadie_lo_dice(auto_encendido):  # noqa: ARG001
    from papeleo import ligado

    r = ligado.ligar_automatico(14, texto="Recibo de estacionamiento")
    assert r["ligado"] is None
    assert "no se reconoció" in r["motivo"].lower()


@pytest.mark.django_db
def test_el_papeleo_de_una_entidad_sale_de_la_base_sin_preguntarle_a_paperless(
        cliente, monkeypatch):
    """La ficha se pinta igual si el archivo está caído."""
    from papeleo import ligado

    def _explota(*a, **k):  # pragma: no cover
        raise AssertionError("la ficha no debe depender de Paperless")

    monkeypatch.setattr(paperless, "_pedir", _explota)
    ligado.ligar(21, titulo="Contrato", cliente=cliente)
    assert [f.documento_id for f in ligado.papeleo_de(cliente)] == [21]


# ── Permisos ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_el_modulo_papeleo_es_delegable_desde_el_directorio():
    """Si no está en el catálogo ni en los módulos visibles, no hay forma de
    dárselo a nadie desde la pantalla de permisos."""
    from cuentas.context_processors import MODULOS_VISIBLES
    from lib.permisos_defaults import CATALOGO_PERMISOS

    assert "papeleo" in CATALOGO_PERMISOS
    assert set(CATALOGO_PERMISOS["papeleo"]) == {"ver", "ligar", "subir"}
    assert "papeleo" in MODULOS_VISIBLES


@pytest.mark.django_db
def test_sin_permiso_la_capacidad_no_aparece_en_el_catalogo_del_chalan():
    from capacidades.gating import gate_ok
    from cuentas.models.usuario import Usuario

    u = Usuario.objects.create_user(email="nadie@lc.mx", password="x",
                                    nombre_completo="Nadie", rol="miembro")
    assert gate_ok("papeleo", u) is False


@pytest.mark.django_db
def test_el_super_admin_si_puede_buscar_papeleo():
    from capacidades.gating import gate_ok
    from cuentas.models.usuario import Usuario

    u = Usuario.objects.create_user(email="jefe@lc.mx", password="x",
                                    nombre_completo="Jefe", rol="super_admin")
    assert gate_ok("papeleo", u) is True
