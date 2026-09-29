"""Las puertas que Oscar decidió el 2026-09-28 — sobre los DATOS.

Sólo datos, sin esquema (Bug I). Idempotente. Reversa: no-op. Dos pasos:
comentarios (esto SÍ cambia a alguien, a propósito) y las tres acciones de
proyectos que estaban muertas (esto NO cambia a nadie: «como hoy»).

**Comentarios: quien tiene por `roles_extra` un rol del sistema los lee como
ese rol.** La regla vieja de comentarios (hasta 2026.09.04) leía el rol PRIMARIO
(`Usuario.rol`), no los roles asignados, y la 0047 lo conservó «como hoy»:
`pizarron.ver_comentarios` / `ver_internos` sólo se sembraron por rol primario.
Así, un «Director» (clave `dueno`) sobre primario `miembro` no leía ningún
comentario. Decisión de Oscar: que los lea.

Regla general (no por pk ni por correo), una por acción:

  · `ver_comentarios` — la regla vieja se la daba a los cuatro roles del
    sistema (super_admin, dueño, contador, diseñador). Quien NO tiene uno de
    ellos de primario pero SÍ asignado recibe la fila encendida.
  · `ver_internos` — la regla vieja se la daba a super_admin, dueño y contador
    (leen los internos ajenos; el diseñador sólo los suyos). Mismo criterio.

`ver_internos` también, y no sólo `ver_comentarios`, porque «leer como el rol
que tiene» es leer como dueño: con sólo `ver_comentarios` el Director vería los
públicos y sus propios internos, menos que cualquier dueño. Además el rol
«Director» de producción traía `pizarron.ver_internos` en su JSON (Oscar se lo
había puesto); la 0047 lo quitó —y apagó la fila de la persona— sólo porque
entonces nadie leía esa acción.

Se ENCIENDE aunque haya una fila apagada: la grilla de El Directorio escribe
una fila por cada acción del catálogo al guardarse, así que una fila apagada no
distingue «lo quitó Oscar» de «nadie lo marcó». La decisión de Oscar es
explícita, así que gana.

Con la foto de producción del 2026-09-28 sólo toca al usuario 4 (Director sobre
`miembro`): `ver_comentarios` y `ver_internos` encendidas.
`tests/test_puertas_decididas.py` fija el antes/después por persona.

**Proyectos: `crear`, `asignar` y `cambiar_estado` dejan de ser decoración.**
Estaban en el catálogo pero ninguna puerta las leía: crear, asignar y cambiar de
estado pedían `proyectos.editar`. Ahora cada pantalla y cada ejecutor del Chalán
pregunta por la suya. Decisión de Oscar: «como hoy» — nadie gana ni pierde:

  1. JSON de los cuatro roles del sistema: cada una de las tres queda presente
     sii el rol trae `editar` («ver como rol» y quien reciba el rol mañana).
     Los roles personalizados no se tocan (configuración de Oscar); a sus
     miembros de hoy los cubre el paso 2.
  2. Una fila por persona (trampa de CLAUDE.md §8: la grilla de El Directorio
     muestra fila o default del rol primario, y guardarla apagaría lo que sólo
     viniera del rol):
       · quien HOY tiene `editar` efectivo (super_admin, fila encendida o algún
         rol que lo traiga, sin fila que lo apague) → fila encendida;
       · quien no lo tiene pero la acción nueva sí le abriría la puerta (fila
         encendida vieja o el JSON de un rol) → fila apagada.

Con la foto de producción este paso no escribe nada: los cuatro usuarios ya
tenían las tres acciones igual que `editar` (1, 3 y 4 encendidas; 5 apagadas) y
los JSON ya iban parejos.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion` (0046 lo documenta).
"""

from __future__ import annotations

from django.db import migrations

ROLES_SISTEMA = ("super_admin", "dueno", "contador", "disenador")
_R_FIN = frozenset({"super_admin", "dueno", "contador"})
_R_TODOS = frozenset(ROLES_SISTEMA)

# (modulo, permiso) → roles a los que la regla vieja se lo daba.
COMENTARIOS = {
    ("pizarron", "ver_comentarios"): _R_TODOS,
    ("pizarron", "ver_internos"): _R_FIN,
}


def planear_comentarios(usuarios, roles, filas):
    """Plan puro (sin base) — lo usan la migración y su prueba.

    `usuarios`: [{"id", "rol", "roles": [rol_id, …]}]
    `roles`:    [{"id", "clave"}]
    `filas`:    {(usuario_id, modulo, permiso): activo}

    Devuelve [(usuario_id, modulo, permiso, True)] a escribir.
    """
    claves = {r["id"]: r["clave"] for r in roles}
    out = []
    for u in usuarios:
        primario = u["rol"] or ""
        asignados = {claves[r] for r in u["roles"] if r in claves}
        for (modulo, permiso), conjunto in COMENTARIOS.items():
            if primario in conjunto or not (asignados & conjunto):
                continue
            if filas.get((u["id"], modulo, permiso)) is not True:
                out.append((u["id"], modulo, permiso, True))
    return out


PROYECTOS_NUEVAS = ("crear", "asignar", "cambiar_estado")


def _acciones(permisos_rol, modulo):
    return set((permisos_rol or {}).get(modulo) or [])


def planear_proyectos(usuarios, roles, filas):
    """Plan puro (sin base) del paso de proyectos.

    `usuarios`: [{"id", "rol", "roles": [rol_id, …]}]
    `roles`:    [{"id", "clave", "permisos": {modulo: [acciones]}}]
    `filas`:    {(usuario_id, modulo, permiso): activo}

    Devuelve `(json_nuevo, filas_nuevas)` como la 0047.
    """
    json_nuevo: dict[int, dict] = {}
    permisos_por_rol: dict[int, dict] = {}
    for rol in roles:
        mapa = {m: sorted(a) for m, a in (rol["permisos"] or {}).items()}
        if rol["clave"] in ROLES_SISTEMA:
            acciones = _acciones(mapa, "proyectos")
            tiene_editar = "editar" in acciones
            for a in PROYECTOS_NUEVAS:
                (acciones.add if tiene_editar else acciones.discard)(a)
            nuevo = {**mapa}
            if acciones:
                nuevo["proyectos"] = sorted(acciones)
            else:
                nuevo.pop("proyectos", None)
            if nuevo != mapa:
                json_nuevo[rol["id"]] = nuevo
            mapa = nuevo
        permisos_por_rol[rol["id"]] = mapa

    claves = {r["id"]: r["clave"] for r in roles}
    filas_nuevas = []
    for u in usuarios:
        asignados = {claves[r] for r in u["roles"] if r in claves}
        por_rol = set()
        for rid in u["roles"]:
            por_rol |= _acciones(permisos_por_rol.get(rid), "proyectos")
        fila_editar = filas.get((u["id"], "proyectos", "editar"))
        # `puede_gestionar_proyectos` de hoy: failsafe, o fila, o algún rol.
        editar_hoy = ("super_admin" in ({u["rol"] or ""} | asignados)
                      or (fila_editar if fila_editar is not None else "editar" in por_rol))
        for a in PROYECTOS_NUEVAS:
            fila = filas.get((u["id"], "proyectos", a))
            if editar_hoy:
                if fila is not True:
                    filas_nuevas.append((u["id"], "proyectos", a, True))
                continue
            abriria = fila if fila is not None else (a in por_rol)
            if abriria:
                filas_nuevas.append((u["id"], "proyectos", a, False))
    return json_nuevo, filas_nuevas


def aplicar(apps, schema_editor):
    Rol = apps.get_model("cuentas", "Rol")
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")

    roles = [{"id": r.pk, "clave": r.clave, "permisos": r.permisos or {}}
             for r in Rol.objects.all().order_by("pk")]
    usuarios = [
        {"id": u.pk, "rol": u.rol,
         "roles": list(u.roles_extra.values_list("pk", flat=True))}
        for u in Usuario.objects.all().order_by("pk")
    ]
    filas = {
        (uid, m, p): activo
        for uid, m, p, activo in PermisoUsuario.objects.filter(modulo__in=("pizarron", "proyectos"))
        .values_list("usuario_id", "modulo", "permiso", "activo")
    }
    # Proyectos primero: lee los datos tal como los dejó la 0047 (el paso de
    # comentarios no toca `proyectos`, así que el orden no cambia el resultado).
    json_nuevo, filas_proyectos = planear_proyectos(usuarios, roles, filas)
    for rol in Rol.objects.filter(pk__in=list(json_nuevo)):
        rol.permisos = json_nuevo[rol.pk]
        rol.save(update_fields=["permisos"])
    for uid, modulo, permiso, activo in [*filas_proyectos,
                                         *planear_comentarios(usuarios, roles, filas)]:
        PermisoUsuario.objects.update_or_create(
            usuario_id=uid, modulo=modulo, permiso=permiso,
            defaults={"activo": activo},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0047_permisos_sin_rol_literal")]
    operations = [migrations.RunPython(aplicar, noop)]
