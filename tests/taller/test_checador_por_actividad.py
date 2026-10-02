"""El Checador por actividad (Oscar 2026-10-01).

«A partir de la primera actividad del usuario en el taller se cuenta como entrada
hasta la última actividad del día; el día corta a las 23:59. Para la ubicación
debe pedir ubicación para hacer el match.» Decisiones de la conversación:
cualquier clic o pantalla cuenta (no el sondeo); lo checado a mano gana en su
extremo; las pausas largas se descuentan sólo con un segundo interruptor.
"""

from __future__ import annotations

import datetime
import json

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _aware(y, m, d, h, mi=0):
    return timezone.make_aware(datetime.datetime(y, m, d, h, mi))


def _con_actividad(u, *, pausas=False, umbral=60):
    u.checador_por_actividad = True
    u.checador_descontar_pausas = pausas
    u.checador_pausa_min = umbral
    u.save()
    return u


def _jornada(u, fecha=None):
    from apps.checador.models import Jornada
    qs = Jornada.objects.filter(usuario=u)
    return qs.filter(fecha=fecha).first() if fecha else qs.first()


# ───────────────────── la actividad abre y alarga la jornada ─────────────────────

class TestActividad:
    def test_apagado_no_toca_nada(self, usuario_factory):
        from apps.checador import actividad
        u = usuario_factory()
        assert actividad.registrar_actividad(u, _aware(2026, 10, 1, 9)) is None
        assert _jornada(u) is None

    def test_la_primera_actividad_es_la_entrada(self, usuario_factory):
        from apps.checador import actividad
        u = _con_actividad(usuario_factory())
        j = actividad.registrar_actividad(u, _aware(2026, 10, 1, 9, 12))
        assert j.entrada_en == _aware(2026, 10, 1, 9, 12)
        assert j.entrada_por_actividad and j.estado == "abierta"
        assert j.entrada_sin_geo  # hasta que llegue la ubicación
        assert j.salida_en is None

    def test_la_ultima_actividad_se_mueve_y_la_entrada_no(self, usuario_factory):
        from apps.checador import actividad
        u = _con_actividad(usuario_factory())
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
        j = actividad.registrar_actividad(u, _aware(2026, 10, 1, 17, 40))
        assert j.entrada_en == _aware(2026, 10, 1, 9)
        assert j.actividad_ultima_en == _aware(2026, 10, 1, 17, 40)
        assert j.minutos_en_curso == 8 * 60 + 40
        assert j.en_curso_texto == "8 h 40 m"

    def test_el_dia_corta_a_las_2359(self, usuario_factory):
        from apps.checador import actividad
        u = _con_actividad(usuario_factory())
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 23, 58))
        actividad.registrar_actividad(u, _aware(2026, 10, 2, 0, 2))
        assert _jornada(u, datetime.date(2026, 10, 1)).entrada_en == _aware(2026, 10, 1, 23, 58)
        assert _jornada(u, datetime.date(2026, 10, 2)).entrada_en == _aware(2026, 10, 2, 0, 2)

    def test_la_entrada_por_actividad_lleva_retardo(self, usuario_factory):
        from apps.checador import actividad
        from apps.checador.models import HorarioLaboral
        u = _con_actividad(usuario_factory())
        HorarioLaboral.objects.update_or_create(
            usuario=u, dia_semana=3,  # jueves 2026-10-01
            defaults={"hora_entrada": datetime.time(9, 0), "hora_salida": datetime.time(18, 0),
                      "tolerancia_min": 15, "activo": True},
        )
        j = actividad.registrar_actividad(u, _aware(2026, 10, 1, 9, 45))
        assert j.retardo_min == 30


# ───────────────────── pausas: segundo interruptor ─────────────────────

class TestPausas:
    def test_sin_el_interruptor_cuenta_de_corrido(self, usuario_factory):
        from apps.checador import actividad
        u = _con_actividad(usuario_factory(), pausas=False)
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
        j = actividad.registrar_actividad(u, _aware(2026, 10, 1, 13))  # 4 h sin tocar nada
        assert j.pausa_min == 0
        assert j.minutos_en_curso == 240

    def test_con_el_interruptor_descuenta_los_huecos_largos(self, usuario_factory):
        from apps.checador import actividad
        u = _con_actividad(usuario_factory(), pausas=True, umbral=60)
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 10))      # 60 min: no es MAYOR
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 12))      # 120 min: pausa
        j = actividad.registrar_actividad(u, _aware(2026, 10, 1, 12, 30))  # 30 min: no
        assert j.pausa_min == 120
        assert j.minutos_en_curso == 210 - 120 + 0  # 9:00→12:30 = 210, menos 120

    def test_una_reentrada_a_mano_no_descuenta_dos_veces(self, usuario_factory):
        """La pausa entre una salida y una re-entrada a mano ya no cuenta por los
        segmentos; la actividad no puede volver a restarla."""
        from apps.checador import actividad, services
        u = _con_actividad(usuario_factory(), pausas=True, umbral=30)
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 12, 59))  # pausa 239
        services.checar_entrada(u, registrado_en=_aware(2026, 10, 1, 13))  # gana la mano
        services.checar_salida(u, registrado_en=_aware(2026, 10, 1, 14))
        services.checar_entrada(u, registrado_en=_aware(2026, 10, 1, 16))  # re-entrada
        j = actividad.registrar_actividad(u, _aware(2026, 10, 1, 16, 5))
        assert j.pausa_min == 0  # la de la mañana quedó fuera al checar a mano

    def test_ajustar_las_dos_horas_a_mano_olvida_las_pausas(self, usuario_factory):
        from apps.checador import actividad, services
        u = _con_actividad(usuario_factory(), pausas=True, umbral=30)
        admin = usuario_factory(rol="super_admin")
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 12))
        j = services.editar_jornada_directo(
            usuario=u, fecha=datetime.date(2026, 10, 1), admin=admin,
            valor_entrada=_aware(2026, 10, 1, 9), valor_salida=_aware(2026, 10, 1, 18),
        )
        assert j.pausa_min == 0 and not j.entrada_por_actividad
        assert j.minutos_trabajados == 540


# ───────────────────── lo checado a mano gana ─────────────────────

class TestConviven:
    def test_la_entrada_a_mano_reemplaza_la_de_actividad(self, usuario_factory):
        from apps.checador import actividad, services
        u = _con_actividad(usuario_factory())
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 8, 50))
        j = services.checar_entrada(u, registrado_en=_aware(2026, 10, 1, 9, 5))
        assert j.entrada_en == _aware(2026, 10, 1, 9, 5)
        assert not j.entrada_por_actividad

    def test_tras_la_salida_a_mano_la_actividad_no_la_mueve(self, usuario_factory):
        from apps.checador import actividad, services
        u = _con_actividad(usuario_factory())
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
        services.checar_salida(u, registrado_en=_aware(2026, 10, 1, 17))
        j = actividad.registrar_actividad(u, _aware(2026, 10, 1, 19))
        assert j.salida_en == _aware(2026, 10, 1, 17)
        assert not j.salida_por_actividad
        assert j.minutos_trabajados == 8 * 60

    def test_sin_checar_salida_se_cierra_con_la_ultima_actividad(self, usuario_factory):
        from apps.checador import actividad, services
        u = _con_actividad(usuario_factory())
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 17, 40))
        actividad.registrar_ubicacion(u, lat=19.43, lng=-99.13, precision=12,
                                      ahora=_aware(2026, 10, 1, 17, 40))
        # 23:30 todavía es el mismo día: no se cierra.
        assert services.cerrar_jornadas_vencidas(ahora=_aware(2026, 10, 1, 23, 30)) == 0
        assert services.cerrar_jornadas_vencidas(ahora=_aware(2026, 10, 2, 0, 5)) == 1
        j = _jornada(u)
        assert j.salida_en == _aware(2026, 10, 1, 17, 40)
        assert j.salida_por_actividad and not j.salida_automatica
        assert j.salida_lat == 19.43 and not j.salida_sin_geo
        assert j.estado == "cerrada" and j.minutos_trabajados == 8 * 60 + 40

    def test_las_demas_jornadas_siguen_esperando_a_las_cinco(self, usuario_factory):
        from apps.checador import services
        u = usuario_factory()
        services.checar_entrada(u, registrado_en=_aware(2026, 10, 1, 9))
        assert services.cerrar_jornadas_vencidas(ahora=_aware(2026, 10, 2, 0, 5)) == 0
        assert services.cerrar_jornadas_vencidas(ahora=_aware(2026, 10, 2, 5, 10)) == 1
        assert _jornada(u).salida_automatica


# ───────────────────── ubicación ─────────────────────

class TestUbicacion:
    def test_la_primera_es_la_de_la_entrada_y_la_ultima_queda_para_la_salida(self, usuario_factory):
        from apps.checador import actividad
        u = _con_actividad(usuario_factory())
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
        actividad.registrar_ubicacion(u, lat=19.40, lng=-99.10, ahora=_aware(2026, 10, 1, 9))
        j = actividad.registrar_ubicacion(u, lat=19.50, lng=-99.20, ahora=_aware(2026, 10, 1, 15))
        assert (j.entrada_lat, j.entrada_lng) == (19.40, -99.10)
        assert not j.entrada_sin_geo
        assert (j.actividad_lat, j.actividad_lng) == (19.50, -99.20)

    def test_la_entrada_a_mano_conserva_su_propia_ubicacion(self, usuario_factory):
        from apps.checador import actividad, services
        u = _con_actividad(usuario_factory())
        services.checar_entrada(u, registrado_en=_aware(2026, 10, 1, 9), geo={"lat": 1.0, "lng": 2.0})
        j = actividad.registrar_ubicacion(u, lat=19.5, lng=-99.2, ahora=_aware(2026, 10, 1, 9, 5))
        assert (j.entrada_lat, j.entrada_lng) == (1.0, 2.0)

    def test_se_mide_contra_las_sedes(self, usuario_factory):
        from apps.checador import actividad
        from apps.checador.models import ConfiguracionGeocerca, SedeLC
        SedeLC.objects.create(nombre="Oficina", lat=19.4326, lng=-99.1332, radio_m=100, activa=True)
        cfg = ConfiguracionGeocerca.obtener()
        cfg.modo = "restringido"
        cfg.save()
        u = _con_actividad(usuario_factory())
        actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
        j = actividad.registrar_ubicacion(u, lat=19.50, lng=-99.20, ahora=_aware(2026, 10, 1, 9))
        j.refresh_from_db()
        assert "fuera de las sedes" in j.notas

    def test_el_endpoint(self, client, usuario_factory):
        u = _con_actividad(usuario_factory())
        client.force_login(u)
        client.get("/checador/")  # la pantalla abre la jornada
        r = client.post("/checador/api/ubicacion", data=json.dumps({"lat": 19.4, "lng": -99.1}),
                        content_type="application/json")
        assert r.status_code == 204
        assert _jornada(u).entrada_lat == 19.4
        r = client.post("/checador/api/ubicacion", data=json.dumps({"lat": "x"}),
                        content_type="application/json")
        assert r.status_code == 400

    def test_el_endpoint_no_cuenta_como_actividad(self, client, usuario_factory):
        from lib import presencia
        assert "checador:api_ubicacion" in presencia.URL_NAMES_SONDEO
        from apps.checador.models import Jornada
        u = _con_actividad(usuario_factory())
        client.force_login(u)
        Jornada.objects.filter(usuario=u).delete()  # la abrió el login
        client.post("/checador/api/ubicacion", data=json.dumps({"lat": 19.4, "lng": -99.1}),
                    content_type="application/json")
        assert _jornada(u) is None


# ───────────────────── de punta a punta por la presencia ─────────────────────

class TestPorLaPresencia:
    def test_una_pantalla_del_taller_abre_la_jornada(self, client, usuario_factory):
        from apps.checador.models import Jornada
        u = _con_actividad(usuario_factory())
        client.force_login(u)
        Jornada.objects.filter(usuario=u).delete()  # la abrió el login: medir sólo la pantalla
        u.refresh_from_db()
        u.actividad_en = None
        u.save(update_fields=["actividad_en"])
        assert client.get("/checador/").status_code == 200
        j = _jornada(u)
        assert j is not None and j.entrada_por_actividad

    def test_sin_el_interruptor_no(self, client, usuario_factory):
        u = usuario_factory()
        client.force_login(u)
        client.get("/checador/")
        assert _jornada(u) is None

    def test_el_sondeo_no_abre_la_jornada(self, client, usuario_factory):
        from apps.checador.models import Jornada
        u = _con_actividad(usuario_factory())
        client.force_login(u)
        Jornada.objects.filter(usuario=u).delete()  # la abrió el login
        u.refresh_from_db()
        u.actividad_en = None  # sin tope de por medio: si contara, escribiría
        u.save(update_fields=["actividad_en"])
        client.get("/checador/", HTTP_X_DESPACHO_SONDEO="1")
        assert _jornada(u) is None

    def test_entrar_a_el_taller_ya_es_la_entrada(self, client, usuario_factory):
        """Sin esto la primera pantalla tras el login cae en el tope de 15 s de
        la presencia y la entrada se anotaba hasta la siguiente actividad."""
        u = _con_actividad(usuario_factory())
        client.force_login(u)
        assert _jornada(u).entrada_por_actividad

    def test_el_tablero_lo_dice_y_carga_el_script(self, client, usuario_factory):
        u = _con_actividad(usuario_factory())
        client.force_login(u)
        client.get("/checador/")
        html = client.get("/checador/").content.decode()
        assert "por actividad" in html
        assert "js/checador_actividad.js" in html

    def test_sin_el_interruptor_no_carga_el_script(self, client, usuario_factory):
        u = usuario_factory()
        client.force_login(u)
        assert "js/checador_actividad.js" not in client.get("/checador/").content.decode()

    def test_el_script_existe(self):
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[2]
        assert (raiz / "el-taller/static/js/checador_actividad.js").is_file()


# ───────────────────── El Chalán y el CSV ─────────────────────

def test_el_chalan_lo_lee(usuario_factory):
    from apps.checador import actividad

    from capacidades.lecturas import _h_mi_jornada_hoy
    from lib.fecha import ahora_mx
    u = _con_actividad(usuario_factory())
    actividad.registrar_actividad(u, ahora_mx())
    out = _h_mi_jornada_hoy({}, u)
    assert out["por_actividad"] is True
    assert out["entrada_por_actividad"] is True
    assert out["ultima_actividad"]


def test_el_csv_marca_la_actividad(usuario_factory):
    from apps.checador import actividad, exports
    u = _con_actividad(usuario_factory(), pausas=True, umbral=30)
    actividad.registrar_actividad(u, _aware(2026, 10, 1, 9))
    actividad.registrar_actividad(u, _aware(2026, 10, 1, 11))
    enc, filas = exports.filas_para("jornadas", {})
    fila = dict(zip(enc, filas[0], strict=False))
    assert fila["Entrada por actividad"] == "Sí"
    assert fila["Salida por actividad"] == "No"
    assert fila["Pausas descontadas (min)"] == 120
