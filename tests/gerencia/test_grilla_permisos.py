"""La grilla de permisos por persona de El Directorio reconoce los roles
asignados, y guardarla tal cual no le cambia a nadie ningún permiso.

El bug (2026-09-29, sonda de otra rama): la grilla marcaba cada casilla por la
fila `PermisoUsuario` o por los defaults del rol PRIMARIO, sin mirar
`roles_extra`, y al guardar escribía una fila por CADA acción del catálogo. Un
`miembro` con el rol Contador asignado tenía `contaduria.ver` pero lo veía
desmarcado, y «Guardar permisos» tal cual se lo apagaba (la fila apagada gana
sobre el rol). Igual al asignar un rol y guardar en el mismo clic.

Decisión (líder, alineada con Oscar: «se reconoce el rol asignado»): nadie gana
ni pierde acceso por guardar la grilla. La grilla enseña el permiso EFECTIVO
(lo que contesta `puede()`) y de dónde viene; al guardar sólo quedan filas donde
la persona difiere de sus roles.
"""

from __future__ import annotations

import importlib
import itertools
import re

import pytest

from lib import permisos
from lib.permisos import plan_de_grilla, puede
from lib.permisos_defaults import catalogo_permisos
from tests.test_permisos_sin_rol_literal import (
    ASIGNABLES,
    FOTO_ROLES,
    FOTO_USUARIOS,
    PRIMARIOS,
    _filas_de_la_foto,
)
from tests.test_puertas_decididas import MIGRACIONES

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]

UNIVERSO = [(m, a) for m, acciones in catalogo_permisos().items() for a in acciones]


# ── utilidades ───────────────────────────────────────────────────────────────


def _rol(clave):
    from cuentas.models.rol import Rol

    return Rol.objects.get(clave=clave)


def _fresco(u):
    """Instancia nueva (sin memo de permisos) del mismo usuario."""
    permisos.invalidar_cache_permisos()
    return type(u).objects.get(pk=u.pk)


def _efectivos(u) -> dict:
    u = _fresco(u)
    return {par: puede(u, *par) for par in UNIVERSO}


def _grilla(client, u, url="panel/permisos"):
    """(pares marcados, pks de roles marcados) tal como los pinta la pantalla."""
    html = client.get(f"/directorio/{u.pk}/{url}").content.decode()
    marcadas = re.findall(r'name="permisos" value="([^"]+)" checked', html)
    roles = re.findall(r'name="roles_extra" value="(\d+)" checked', html)
    return marcadas, roles, html


def _guardar_tal_cual(client, u, url="panel/permisos"):
    marcadas, roles, _ = _grilla(client, u, url)
    datos = {"permisos": marcadas}
    if url == "panel/permisos":
        datos["roles_extra"] = roles
    resp = client.post(f"/directorio/{u.pk}/{url}", datos)
    assert resp.status_code in (200, 302)


def _pares_del_rol(rol):
    return {(m, a) for m, acciones in (rol.permisos or {}).items() for a in acciones}


def _uno_que_no_da(rol):
    return next(par for par in UNIVERSO if par not in _pares_del_rol(rol))


@pytest.fixture
def admin(client, usuario_factory):
    a = usuario_factory(rol="super_admin", email="admin-grilla@ejemplo.com")
    client.force_login(a)
    return a


# ── 1. La sonda, como regresión ──────────────────────────────────────────────


def test_sonda_la_grilla_marca_lo_del_rol_asignado_y_guardarla_no_lo_apaga(client, admin, usuario_factory):
    contador = _rol("contador")
    u = usuario_factory(rol="miembro", email="m@x.com")
    u.roles_extra.add(contador)
    assert puede(_fresco(u), "contaduria", "ver")

    marcadas, _roles, html = _grilla(client, u)
    assert "contaduria.ver" in marcadas
    assert "por su rol " + contador.nombre in html

    client.post(f"/directorio/{u.pk}/panel/permisos",
                {"roles_extra": [contador.pk], "permisos": marcadas})
    assert puede(_fresco(u), "contaduria", "ver")


def test_la_casilla_dice_de_donde_viene(client, admin, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario

    contador = _rol("contador")
    dado = sorted(_pares_del_rol(contador) & set(UNIVERSO))[0]
    ajeno = _uno_que_no_da(contador)
    u = usuario_factory(rol="miembro")
    u.roles_extra.add(contador)
    PermisoUsuario.objects.create(usuario=u, modulo=dado[0], permiso=dado[1], activo=False)
    PermisoUsuario.objects.create(usuario=u, modulo=ajeno[0], permiso=ajeno[1], activo=True)
    from apps.el_directorio.views import _secciones_permisos

    casillas = {(m, c["permiso"]): c for m, cs in _secciones_permisos(_fresco(u)) for c in cs}
    assert casillas[dado]["activo"] is False and casillas[dado]["origen"] == "quitado"
    assert casillas[ajeno]["activo"] is True and casillas[ajeno]["origen"] == "mano"
    otro_dado = sorted(_pares_del_rol(contador) & set(UNIVERSO))[1]
    assert casillas[otro_dado]["origen"] == "rol"
    assert casillas[otro_dado]["roles"] == contador.nombre


# ── 2. Asignar / quitar un rol ───────────────────────────────────────────────


def test_asignar_un_rol_y_guardar_en_el_mismo_clic_da_lo_del_rol(client, admin, usuario_factory):
    contador = _rol("contador")
    u = usuario_factory(rol="miembro")
    marcadas, _roles, _ = _grilla(client, u)
    assert "contaduria.ver" not in marcadas
    client.post(f"/directorio/{u.pk}/panel/permisos",
                {"roles_extra": [contador.pk], "permisos": marcadas})
    efectivos = _efectivos(u)
    for par in _pares_del_rol(contador) & set(UNIVERSO):
        assert efectivos[par], par


def test_quitar_el_rol_en_el_mismo_clic_quita_lo_del_rol(client, admin, usuario_factory):
    contador = _rol("contador")
    u = usuario_factory(rol="miembro")
    u.roles_extra.add(contador)
    marcadas, _roles, _ = _grilla(client, u)
    client.post(f"/directorio/{u.pk}/panel/permisos", {"roles_extra": [], "permisos": marcadas})
    assert not puede(_fresco(u), "contaduria", "ver")


def test_quitar_el_rol_despues_quita_lo_del_rol_pero_no_lo_puesto_a_mano(client, admin, usuario_factory):
    """Una persona con filas sembradas que coinciden con su rol (como las dejó
    la migración 0047): guardar la grilla tal cual borra esas filas redundantes
    —sin cambiar nada hoy—, así que quitarle el rol después sí le quita lo que
    el rol le daba. Lo puesto a mano se queda."""
    from cuentas.models.permiso_usuario import PermisoUsuario

    contador = _rol("contador")
    ajeno = _uno_que_no_da(contador)
    u = usuario_factory(rol="miembro")
    u.roles_extra.add(contador)
    PermisoUsuario.objects.create(usuario=u, modulo="contaduria", permiso="ver", activo=True)
    antes = _efectivos(u)

    marcadas, _roles, _ = _grilla(client, u)
    marcadas.append(".".join(ajeno))  # esto sí lo pone a mano
    client.post(f"/directorio/{u.pk}/panel/permisos",
                {"roles_extra": [contador.pk], "permisos": marcadas})
    despues = _efectivos(u)
    assert {p for p in UNIVERSO if antes[p] != despues[p]} == {ajeno}
    assert not PermisoUsuario.objects.filter(usuario=u, modulo="contaduria", permiso="ver").exists()

    # Quitar el rol por la pantalla de roles (no toca filas).
    client.post(f"/directorio/{u.pk}/roles-extra", {"roles_extra": []})
    u = _fresco(u)
    assert not puede(u, "contaduria", "ver")
    assert puede(u, *ajeno)


# ── 3. Un cambio real sí persiste ────────────────────────────────────────────


def test_desmarcar_lo_del_rol_lo_quita_y_marcar_otro_lo_da(client, admin, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario

    contador = _rol("contador")
    ajeno = _uno_que_no_da(contador)
    u = usuario_factory(rol="miembro")
    u.roles_extra.add(contador)
    antes = _efectivos(u)
    marcadas, roles, _ = _grilla(client, u)
    marcadas.remove("contaduria.ver")
    marcadas.append(".".join(ajeno))
    client.post(f"/directorio/{u.pk}/panel/permisos", {"roles_extra": roles, "permisos": marcadas})
    despues = _efectivos(u)
    assert {p for p in UNIVERSO if antes[p] != despues[p]} == {("contaduria", "ver"), ajeno}
    assert not despues[("contaduria", "ver")] and despues[ajeno]
    assert PermisoUsuario.objects.get(usuario=u, modulo="contaduria", permiso="ver").activo is False
    assert PermisoUsuario.objects.get(usuario=u, modulo=ajeno[0], permiso=ajeno[1]).activo is True


def test_quitado_a_mano_sobrevive_a_reasignar_el_rol(client, admin, usuario_factory):
    """Lo apagado a mano se conserva aunque el mismo clic cambie los roles."""
    from cuentas.models.permiso_usuario import PermisoUsuario

    contador, disenador = _rol("contador"), _rol("disenador")
    u = usuario_factory(rol="miembro")
    u.roles_extra.add(contador)
    PermisoUsuario.objects.create(usuario=u, modulo="contaduria", permiso="ver", activo=False)
    marcadas, _roles, _ = _grilla(client, u)
    client.post(f"/directorio/{u.pk}/panel/permisos",
                {"roles_extra": [contador.pk, disenador.pk], "permisos": marcadas})
    assert not puede(_fresco(u), "contaduria", "ver")


# ── 4. Equivalencia: guardar sin cambiar nada no cambia ningún permiso ───────


def _assert_guardar_no_cambia(client, usuarios, url="panel/permisos"):
    from cuentas.models.permiso_usuario import PermisoUsuario

    distintos = []
    for u in usuarios:
        antes = _efectivos(u)
        failsafe_antes = permisos.es_super_admin(_fresco(u))
        roles_antes = set(u.roles_extra.values_list("pk", flat=True))
        marcadas, _roles, _ = _grilla(client, u, url)
        # La grilla enseña exactamente lo que contesta puede().
        assert set(marcadas) == {".".join(p) for p, v in antes.items() if v}, u.pk
        _guardar_tal_cual(client, u, url)
        despues = _efectivos(u)
        cambian = sorted(p for p in UNIVERSO if antes[p] != despues[p])
        if cambian:
            distintos.append(f"usuario {u.pk}: {cambian}")
        # El rol primario se re-deriva de los asignados (S-Roles-V2); lo que no
        # puede cambiar es el failsafe.
        assert permisos.es_super_admin(_fresco(u)) == failsafe_antes, u.pk
        assert set(u.roles_extra.values_list("pk", flat=True)) == roles_antes
        # Y un segundo guardado ya no escribe nada.
        filas = set(PermisoUsuario.objects.filter(usuario=u).values_list("modulo", "permiso", "activo"))
        _guardar_tal_cual(client, u, url)
        assert set(PermisoUsuario.objects.filter(usuario=u).values_list("modulo", "permiso", "activo")) == filas
    assert not distintos, "Guardar tal cual cambió permisos:\n" + "\n".join(distintos)


def _cargar_foto(con_migraciones: bool):
    from django.apps import apps as django_apps

    from cuentas.models.permiso_usuario import PermisoUsuario
    from cuentas.models.rol import Rol
    from cuentas.models.usuario import Usuario

    Rol.objects.all().delete()
    for rid, (clave, nombre, p) in FOTO_ROLES.items():
        Rol.objects.create(pk=rid, clave=clave, nombre=nombre, permisos=p)
    for uid, d in FOTO_USUARIOS.items():
        u = Usuario(pk=uid, email=f"foto{uid}@ejemplo.com", nombre_completo=f"Foto {uid}", rol=d["rol"])
        u.set_unusable_password()
        u.save()
        u.roles_extra.set(Rol.objects.filter(pk__in=d["roles"]))
    PermisoUsuario.objects.filter(usuario_id__in=FOTO_USUARIOS).delete()
    PermisoUsuario.objects.bulk_create([
        PermisoUsuario(usuario_id=uid, modulo=m, permiso=a, activo=activo)
        for (uid, m, a), activo in _filas_de_la_foto().items()
    ])
    if con_migraciones:
        for nombre in MIGRACIONES:
            importlib.import_module(f"cuentas.migrations.{nombre}").aplicar(django_apps, None)
    permisos.invalidar_cache_permisos()
    return list(Usuario.objects.filter(pk__in=FOTO_USUARIOS).order_by("pk"))


@pytest.mark.parametrize("con_migraciones", [True, False], ids=["como-produccion", "foto-cruda"])
def test_la_foto_de_produccion_guarda_sin_cambiar_nada(client, usuario_factory, con_migraciones):
    usuarios = _cargar_foto(con_migraciones)
    assert any(u.roles_extra.exists() for u in usuarios)
    client.force_login(usuario_factory(rol="super_admin", email="admin-foto@ejemplo.com"))
    _assert_guardar_no_cambia(client, usuarios)


def test_la_foto_en_la_pagina_completa_guarda_sin_cambiar_nada(client, usuario_factory):
    usuarios = _cargar_foto(True)
    client.force_login(usuario_factory(rol="super_admin", email="admin-foto@ejemplo.com"))
    _assert_guardar_no_cambia(client, usuarios, url="permisos")


def test_roles_asignados_y_filas_a_mano_guardan_sin_cambiar_nada(client, admin, usuario_factory):
    """Cada rol primario × cada combinación de roles asignados, con filas
    sembradas por el signal (las del primario) y dos puestas a mano: una
    apagada sobre algo que un rol da y una encendida sobre algo que no."""
    from cuentas.models.permiso_usuario import PermisoUsuario

    roles = {c: _rol(c) for c in ASIGNABLES}
    usuarios = []
    for i, (primario, n) in enumerate(itertools.product(PRIMARIOS, range(len(ASIGNABLES) + 1))):
        for extra in itertools.combinations(ASIGNABLES, n):
            if primario == "super_admin" and "super_admin" not in extra:
                # Primario super_admin SIN el rol asignado: estado de antes de
                # S-Roles-V2 que ya no existe en producción (la foto lo
                # confirma). El panel, desde entonces, le re-deriva `miembro` al
                # guardar —con o sin este arreglo—; aquí no se mide eso.
                continue
            u = usuario_factory(rol=primario)
            if extra:
                u.roles_extra.add(*(roles[c] for c in extra))
                dado = sorted(set().union(*(_pares_del_rol(roles[c]) for c in extra)) & set(UNIVERSO))
                if dado:
                    m, a = dado[i % len(dado)]
                    PermisoUsuario.objects.update_or_create(
                        usuario=u, modulo=m, permiso=a, defaults={"activo": False})
            m, a = UNIVERSO[(i * 7) % len(UNIVERSO)]
            PermisoUsuario.objects.update_or_create(usuario=u, modulo=m, permiso=a, defaults={"activo": True})
            usuarios.append(u)
    _assert_guardar_no_cambia(client, usuarios)


def test_un_bloqueado_ve_sus_casillas_y_guardarlas_no_le_apaga_nada(client, admin, usuario_factory):
    """`puede()` contesta False a un usuario inactivo; la grilla no: si lo
    usara, guardarla le escribiría filas apagadas que le durarían al volver."""
    from cuentas.models.permiso_usuario import PermisoUsuario

    u = usuario_factory(rol="miembro")
    u.roles_extra.add(_rol("contador"))
    u.is_active = False
    u.save(update_fields=["is_active"])
    marcadas, roles, _ = _grilla(client, u)
    assert "contaduria.ver" in marcadas
    client.post(f"/directorio/{u.pk}/panel/permisos", {"roles_extra": roles, "permisos": marcadas})
    assert not PermisoUsuario.objects.filter(usuario=u, activo=False).exists()
    u.is_active = True
    u.save(update_fields=["is_active"])
    assert puede(_fresco(u), "contaduria", "ver")


def test_restablecer_deja_lo_de_sus_roles_y_los_universales(client, admin, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    from lib.permisos_defaults import PERMISOS_UNIVERSALES

    contador = _rol("contador")
    ajeno = _uno_que_no_da(contador)
    u = usuario_factory(rol="miembro")
    u.roles_extra.add(contador)
    PermisoUsuario.objects.create(usuario=u, modulo="contaduria", permiso="ver", activo=False)
    PermisoUsuario.objects.create(usuario=u, modulo=ajeno[0], permiso=ajeno[1], activo=True)
    client.post(f"/directorio/{u.pk}/permisos", {"restablecer": "1"})
    efectivos = _efectivos(u)
    universales = {(m, a) for m, acciones in PERMISOS_UNIVERSALES.items() for a in acciones}
    esperado = (_pares_del_rol(contador) | universales) & set(UNIVERSO)
    assert {p for p, v in efectivos.items() if v} == esperado


# ── 5. La regla pura, caso por caso ──────────────────────────────────────────


@pytest.mark.parametrize("fila,antes,despues,elegido",
                         list(itertools.product((None, True, False), (True, False), (True, False), (True, False))))
def test_plan_de_grilla_caso_por_caso(fila, antes, despues, elegido):
    par = ("m", "a")
    filas = {} if fila is None else {par: fila}
    escribir, borrar = plan_de_grilla(filas, {par} if antes else set(), {par} if despues else set(),
                                      {par} if elegido else set(), [par])
    nueva = filas.get(par)
    if par in borrar:
        nueva = None
    if par in escribir:
        nueva = escribir[par]
    efectivo = nueva if nueva is not None else despues
    visto = fila if fila is not None else antes
    if elegido != visto:
        assert efectivo == elegido           # lo que se cambió, queda
    elif fila is not None and fila != antes:
        assert efectivo == fila              # lo puesto a mano, se conserva
    else:
        assert efectivo == despues           # lo demás sigue a sus roles
    assert nueva is None or nueva != despues  # nunca queda una fila redundante
