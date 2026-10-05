"""Las entradas y salidas del equipo son de quien dirige (2026-10-05).

Oscar: «No encuentro donde ver el registro de chequeo de entrada y salida de los
empleados. Veo su actividad, pero también debería ver ESA actividad» · «Solo los
directores pueden ver esa actividad» · «No se entiende tu botón».

1. `checador.ver_equipo` = quien dirige: super_admin y dueño de arranque; abre
   las horas de TODO el equipo, no sólo de los subordinados directos.
2. El contador lo pierde y conserva `exportar` (el CSV para la nómina).
3. La página «Actividad de <persona>» trae la entrada y salida del día, en las
   dos apps, sólo para quien puede ver esas horas.
4. El tablero del Checador lleva a «Entradas y salidas del equipo» con su nombre.
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _dt(fecha, h, m):
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(h, m)))


def _jornada_hoy(persona):
    from apps.checador import services
    hoy = timezone.localdate()
    services.checar_entrada(persona, registrado_en=_dt(hoy, 9, 7))
    services.checar_salida(persona, registrado_en=_dt(hoy, 17, 42))
    return hoy


# ── 1 · quién ve las horas ──────────────────────────────────────────────────

class TestQuienDirige:
    def test_defaults(self):
        from lib.permisos_defaults import defaults_de
        assert "ver_equipo" in defaults_de("super_admin")["checador"]
        assert "ver_equipo" in defaults_de("dueno")["checador"]
        for rol in ("contador", "disenador"):
            assert "ver_equipo" not in defaults_de(rol).get("checador", []), rol
        assert "exportar" in defaults_de("contador")["checador"]

    def test_el_dueno_ve_las_horas_de_quien_no_le_reporta(self, usuario_factory):
        from lib.permisos import puede_ver_horas_trabajadas_de
        empleado = usuario_factory(rol="disenador")
        assert empleado.jefe_directo_id is None
        assert puede_ver_horas_trabajadas_de(usuario_factory(rol="dueno"), empleado)
        assert not puede_ver_horas_trabajadas_de(usuario_factory(rol="contador"), empleado)
        assert not puede_ver_horas_trabajadas_de(usuario_factory(rol="disenador"), empleado)

    def test_el_jefe_directo_las_sigue_viendo_sin_el_permiso(self, usuario_factory):
        from lib.permisos import puede_ver_horas_trabajadas_de
        jefe = usuario_factory(rol="disenador")
        empleado = usuario_factory(rol="disenador")
        empleado.jefe_directo = jefe
        empleado.save(update_fields=["jefe_directo"])
        assert puede_ver_horas_trabajadas_de(jefe, empleado)

    def test_revocarlo_a_un_dueno_le_cierra_las_horas(self, usuario_factory):
        from cuentas.models.permiso_usuario import PermisoUsuario
        from lib.permisos import puede_ver_horas_trabajadas_de
        dueno = usuario_factory(rol="dueno")
        PermisoUsuario.objects.update_or_create(
            usuario=dueno, modulo="checador", permiso="ver_equipo", defaults={"activo": False})
        assert not puede_ver_horas_trabajadas_de(dueno, usuario_factory(rol="disenador"))

    def test_el_dueno_ve_las_jornadas_en_la_pantalla_de_la_persona(self, client, usuario_factory):
        empleado = usuario_factory(rol="disenador")
        _jornada_hoy(empleado)
        client.force_login(usuario_factory(rol="dueno"))
        texto = client.get(f"/checador/equipo/{empleado.pk}/").content.decode()
        assert "Jornadas" in texto and "17:42" in texto
        assert "Tiempo por proyecto" in texto


# ── 2 · el contador ─────────────────────────────────────────────────────────

class TestElContador:
    def test_no_entra_a_la_pantalla_del_equipo(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="contador"))
        assert client.get("/checador/equipo/").status_code == 403

    def test_baja_el_csv_desde_su_historial(self, client, usuario_factory):
        empleado = usuario_factory(rol="disenador")
        hoy = _jornada_hoy(empleado)
        client.force_login(usuario_factory(rol="contador"))
        texto = client.get("/checador/historial/").content.decode()
        assert "Descargar jornadas del equipo" in texto
        r = client.get(f"/checador/equipo/export?vista=jornadas&desde={hoy}&hasta={hoy}")
        assert r.status_code == 200
        assert r["Content-Type"].startswith("text/csv")

    def test_quien_dirige_no_ve_el_bloque_del_contador(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="dueno"))
        assert "Descargar jornadas del equipo" not in client.get("/checador/historial/").content.decode()

    def test_la_migracion_se_lo_quita_y_se_lo_da_a_los_directores(self, usuario_factory):
        """La 0056 corre sobre los usuarios que YA existían: se simula el estado
        de antes (contador con la fila, dueño sin ella) y se vuelve a aplicar."""
        import importlib

        from django.apps import apps

        from cuentas.models.permiso_usuario import PermisoUsuario
        from cuentas.models.rol import Rol
        mig = importlib.import_module("cuentas.migrations.0056_checador_ver_equipo_directores")
        contador, dueno, disenador = (usuario_factory(rol=r) for r in ("contador", "dueno", "disenador"))
        PermisoUsuario.objects.filter(usuario=dueno, modulo="checador", permiso="ver_equipo").delete()
        PermisoUsuario.objects.create(usuario=contador, modulo="checador", permiso="ver_equipo", activo=True)
        mig.aplicar(apps, None)
        con = set(PermisoUsuario.objects.filter(modulo="checador", permiso="ver_equipo", activo=True)
                  .values_list("usuario_id", flat=True))
        assert dueno.pk in con
        assert contador.pk not in con and disenador.pk not in con
        assert PermisoUsuario.objects.filter(usuario=contador, modulo="checador", permiso="exportar").exists()
        for rol in Rol.objects.filter(clave="contador"):
            assert "ver_equipo" not in rol.permisos.get("checador", [])
        for rol in Rol.objects.filter(clave__in=("super_admin", "dueno")):
            assert "ver_equipo" in rol.permisos.get("checador", [])
        mig.aplicar(apps, None)  # idempotente
        assert PermisoUsuario.objects.filter(usuario=dueno, modulo="checador", permiso="ver_equipo").count() == 1


# ── 3 · la entrada y salida en «Actividad de <persona>» ─────────────────────

class TestEnLaActividad:
    def test_el_dueno_la_ve_en_el_taller(self, client, usuario_factory):
        empleado = usuario_factory(rol="disenador")
        _jornada_hoy(empleado)
        client.force_login(usuario_factory(rol="dueno"))
        r = client.get(f"/directorio/{empleado.pk}/actividad/")
        assert r.status_code == 200
        texto = r.content.decode()
        assert "Entrada y salida" in texto
        assert "09:07" in texto and "17:42" in texto
        assert "checada a mano" in texto
        assert f"/checador/equipo/{empleado.pk}/" in texto  # «Todas sus entradas y salidas»

    def test_y_en_la_gerencia_sin_enlace_al_checador(self, client, settings, usuario_factory):
        settings.ROOT_URLCONF = "tests.urls_gerencia"
        empleado = usuario_factory(rol="disenador")
        _jornada_hoy(empleado)
        client.force_login(usuario_factory(rol="super_admin"))
        texto = client.get(f"/directorio/{empleado.pk}/actividad").content.decode()
        assert "Entrada y salida" in texto and "17:42" in texto
        assert "Todas sus entradas y salidas" not in texto

    def test_un_dia_sin_checar_lo_dice(self, client, usuario_factory):
        empleado = usuario_factory(rol="disenador")
        client.force_login(usuario_factory(rol="dueno"))
        assert "No checó entrada este día" in client.get(f"/directorio/{empleado.pk}/actividad/").content.decode()

    def test_quien_ve_la_actividad_pero_no_dirige_no_ve_las_horas(self, client, usuario_factory):
        """`equipo.ver_historial` abre la página; las horas piden más."""
        from cuentas.models.permiso_usuario import PermisoUsuario
        miron = usuario_factory(rol="disenador")
        PermisoUsuario.objects.update_or_create(
            usuario=miron, modulo="equipo", permiso="ver_historial", defaults={"activo": True})
        empleado = usuario_factory(rol="disenador")
        _jornada_hoy(empleado)
        client.force_login(miron)
        r = client.get(f"/directorio/{empleado.pk}/actividad/")
        assert r.status_code == 200
        texto = r.content.decode()
        assert "Entrada y salida" not in texto and "17:42" not in texto

    def test_la_propia_si(self, client, usuario_factory):
        yo = usuario_factory(rol="disenador")
        _jornada_hoy(yo)
        client.force_login(yo)
        assert "Entrada y salida" in client.get("/perfil/actividad/").content.decode()


# ── 4 · el acceso en el tablero ─────────────────────────────────────────────

class TestElAcceso:
    def test_el_tablero_lo_ofrece_a_quien_dirige(self, client, usuario_factory):
        client.force_login(usuario_factory(rol="dueno"))
        assert "Entradas y salidas del equipo" in client.get("/checador/").content.decode()

    def test_y_a_nadie_mas(self, client, usuario_factory):
        for rol in ("contador", "disenador"):
            client.force_login(usuario_factory(rol=rol))
            assert "Entradas y salidas del equipo" not in client.get("/checador/").content.decode(), rol
