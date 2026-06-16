"""S-LC-Feedback-V6 Bloque 10: eliminar el rol dueño — helpers de roles
efectivos y rol primario neutro 'miembro'."""

import pytest

pytestmark = pytest.mark.django_db


def _rol_dueno():
    from cuentas.models.rol import Rol
    return Rol.objects.get(nombre="dueno")


def test_miembro_con_rol_personalizado_dueno_es_admin(usuario_factory):
    """El corazón del Bloque 10: un 'miembro' con el Rol personalizado 'dueno'
    pasa los mismos checks que pasaba el rol duro."""
    from lib.permisos import es_admin, roles_efectivos, tiene_rol
    u = usuario_factory(rol="miembro")
    assert es_admin(u) is False
    u.roles_extra.add(_rol_dueno())
    assert roles_efectivos(u) == {"miembro", "dueno"}
    assert es_admin(u) is True
    assert tiene_rol(u, "dueno") is True
    assert tiene_rol(u, "contador") is False


def test_usuarios_con_rol_une_ambas_vias(usuario_factory):
    from lib.permisos import usuarios_con_rol
    legacy = usuario_factory(rol="dueno")                  # rol primario legacy
    moderno = usuario_factory(rol="miembro")               # rol personalizado
    moderno.roles_extra.add(_rol_dueno())
    otro = usuario_factory(rol="disenador")
    encontrados = set(usuarios_con_rol("dueno").values_list("pk", flat=True))
    assert legacy.pk in encontrados
    assert moderno.pk in encontrados
    assert otro.pk not in encontrados


def test_usuarios_con_rol_excluye_inactivos(usuario_factory):
    from lib.permisos import usuarios_con_rol
    u = usuario_factory(rol="dueno")
    u.is_active = False
    u.save(update_fields=["is_active"])
    assert u.pk not in set(usuarios_con_rol("dueno").values_list("pk", flat=True))


def test_form_directorio_sin_dropdown_de_rol():
    # S-Roles-V2: el dropdown de "rol primario" se eliminó. Los roles se asignan
    # en UN solo lugar (los checkboxes de Roles del panel de permisos).
    from apps.el_directorio.forms import UsuarioForm
    assert "rol" not in UsuarioForm().fields


def test_sincronizar_rol_primario_deriva_de_roles(usuario_factory):
    # Asignar el rol super_admin deriva Usuario.rol; quitarlo lo baja a miembro.
    from cuentas.models.rol import Rol
    from lib.permisos import sincronizar_rol_primario
    u = usuario_factory(rol="miembro")
    u.roles_extra.add(Rol.objects.get(nombre="super_admin"))
    assert sincronizar_rol_primario(u) == "super_admin"
    u.refresh_from_db()
    assert u.rol == "super_admin" and u.is_superuser is True
    u.roles_extra.clear()
    assert sincronizar_rol_primario(u) == "miembro"
    u.refresh_from_db()
    assert u.rol == "miembro" and u.is_superuser is False


def test_rol_miembro_sin_defaults_de_permisos(usuario_factory):
    """'miembro' es neutro: el signal de seed no le da ningún permiso."""
    from cuentas.models.permiso_usuario import PermisoUsuario
    u = usuario_factory(rol="miembro")
    assert PermisoUsuario.objects.filter(usuario=u, activo=True).count() == 0


def test_migracion_0024_dueno_a_miembro(usuario_factory):
    """Simula la data migration sobre un usuario dueno existente."""
    import importlib

    from django.apps import apps as django_apps
    u = usuario_factory(rol="dueno")
    mig = importlib.import_module("cuentas.migrations.0024_rol_miembro_dueno_legacy")
    mig.dueno_a_miembro(django_apps, None)
    u.refresh_from_db()
    assert u.rol == "miembro"
    assert "dueno" in set(u.roles_extra.values_list("nombre", flat=True))
    # Sigue siendo admin vía roles_efectivos.
    from lib.permisos import es_admin
    assert es_admin(u) is True
