"""Las puertas que decidían por ROL pasan a permiso granular — «como hoy».

S-Deuda-Permisos (2026-09-28). Regla §4 #20: ninguna puerta decide por el nombre
de un rol; el único rol duro es el failsafe `super_admin`. Hasta aquí,
`lib.permisos` tenía helpers como `es_admin` (super_admin|dueño) o
`puede_ver_finanzas` (super_admin|dueño|contador) que no se podían delegar desde
El Directorio. Ahora cada uno pregunta por una acción del catálogo.

**Decisión de Oscar (literal): «Como hoy».** Al pasar a granular nadie gana ni
pierde acceso. Esta migración es la que lo garantiza sobre los DATOS: para cada
usuario y cada acción que ahora abre una de esas puertas, calcula lo que el ROL
le daba (la regla vieja, congelada abajo en `OBJETIVOS`) y deja su permiso igual.

Sólo datos, sin esquema (Bug I). Tres pasos:

1. **JSON de los cuatro roles del sistema** (`super_admin`, `dueno`, `contador`,
   `disenador`, por `clave`): cada acción de `OBJETIVOS` queda presente sii la
   regla vieja se la daba a ese rol. Eso le quita `proyectos.editar` al
   diseñador (lo traía «sólo donde asignado», pero la puerta era el rol y nunca
   editó nada) y le suma `proyectos.ver_todos` al contador, entre otras.
   Lo lee «ver como rol» y lo hereda quien reciba el rol mañana.
   Los roles personalizados (p. ej. «Administrativo») NO se tocan: su contenido
   es configuración de Oscar; a sus miembros de HOY los cubre el paso 3.

2. **Comentarios: `pizarron.ver_comentarios` y `pizarron.ver_internos` salen del
   JSON de TODOS los roles.** La regla vieja de comentarios leía el rol PRIMARIO
   (`user.rol`), no los roles asignados: quien tiene «Director» sobre un rol
   primario `miembro` no leía comentarios. Para que siga así, estas dos acciones
   sólo se siembran por persona (paso 3) y por default del rol primario (signal).
   `ver_internos` no lo leía nadie hasta hoy (acción muerta): quitarla no cambia
   nada que se viera.

3. **Una fila por persona donde haga falta** (`PermisoUsuario`):
   - la regla vieja le daba la puerta y no tiene la fila encendida → fila
     `activo=True`. Así también la ve marcada la grilla de El Directorio (que
     muestra fila o default del rol PRIMARIO): sin fila, guardar el panel la
     escribiría apagada y la persona perdería la puerta en silencio.
   - la regla vieja NO se la daba pero el permiso nuevo sí (por una fila vieja
     o por el JSON de un rol personalizado) → fila `activo=False`. Es
     exactamente «lo que hoy no tenía efecto».

Con los datos de producción del 2026-09-28 (respaldo de HAL) el paso 3 apaga
tres filas —y ninguna cambia lo que la persona puede hacer hoy—:
   · usuario 5 (rol «Administrativo»): `cartera.ver` y `proyectos.ver`. Tenía las
     dos encendidas, pero su rol no era de los cuatro: Clientes le daba 403 y su
     lista de proyectos salía vacía. Sólo le quedaba el renglón del menú.
   · usuario 4 (rol «Director» sobre `miembro`): `pizarron.ver_internos`, que
     nadie leía; y no lee comentarios (rol primario `miembro`).
Todo lo demás son altas de acciones nuevas a quien el rol ya se las daba.
`tests/test_permisos_sin_rol_literal.py` corre este plan sobre esa foto
(anonimizada) y compara, persona por persona, la puerta vieja contra la nueva.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion` (0046 lo documenta: tumbó el arranque en producción el 2026-08-22).

Idempotente. Reversa: no-op — el código anterior no lee las acciones nuevas, así
que sus filas quedan inertes; las tres filas apagadas no se re-encienden (no
tenían efecto).
"""

from __future__ import annotations

from django.db import migrations

# ── La regla VIEJA, congelada ────────────────────────────────────────────────
#
# Copia de lo que decidían los helpers de `lib/permisos.py` antes de este
# sprint. `p` es el rol primario (`Usuario.rol`); `e` son los roles efectivos
# (primario ∪ claves de `roles_extra`), igual que `roles_efectivos()`.

_R_ADMIN = frozenset({"super_admin", "dueno"})
_R_FIN = frozenset({"super_admin", "dueno", "contador"})
_R_TODOS = frozenset({"super_admin", "dueno", "contador", "disenador"})
ROLES_SISTEMA = ("super_admin", "dueno", "contador", "disenador")


def _efectivo(conjunto):
    return lambda p, e: bool(e & conjunto)


# (modulo, permiso) → (regla vieja, ¿la regla miraba los roles EFECTIVOS?)
OBJETIVOS = {
    # puede_ver_proyecto / _proyectos_visibles: diseñador → sus asignados.
    ("proyectos", "ver"): (_efectivo(_R_TODOS), True),
    # …y super_admin/dueño/contador → todos (también todas las tareas).
    ("proyectos", "ver_todos"): (_efectivo(_R_FIN), True),
    # puede_editar_proyecto = es_admin.
    ("proyectos", "editar"): (_efectivo(_R_ADMIN), True),
    # puede_archivar_proyecto = es_admin.
    ("proyectos", "archivar"): (_efectivo(_R_ADMIN), True),
    # puede_ver_cartera / puede_editar_cartera.
    ("cartera", "ver"): (_efectivo(_R_FIN), True),
    ("cartera", "editar"): (_efectivo(_R_ADMIN), True),
    # puede_ver_finanzas (también la puerta de La Tesorería).
    ("tesoreria", "ver"): (_efectivo(_R_FIN), True),
    # puede_ver_comentario leía el rol PRIMARIO: los cuatro roles leen…
    ("pizarron", "ver_comentarios"): (lambda p, e: p in _R_TODOS, False),
    # …y super_admin/dueño/contador leen también los internos ajenos.
    ("pizarron", "ver_internos"): (lambda p, e: p in _R_FIN, False),
    # Marcar interno: `es_admin(user) or user.rol == "contador"` (primario).
    ("pizarron", "comentar_interno"): (lambda p, e: bool(e & _R_ADMIN) or p == "contador", None),
    # Borrar tareas ajenas, ver todos los mandados, borrar del Buzón, API de
    # El Site: es_admin / tiene_rol(super_admin, dueno).
    ("pizarron", "eliminar"): (_efectivo(_R_ADMIN), True),
    ("pizarron", "ver_todos_mandados"): (_efectivo(_R_ADMIN), True),
    ("buzon", "eliminar"): (_efectivo(_R_ADMIN), True),
    ("site", "api"): (_efectivo(_R_ADMIN), True),
}

# Las dos acciones que la regla vieja decidía SÓLO por rol primario: fuera del
# JSON de todos los roles (paso 2).
_SOLO_PRIMARIO = {par for par, (_regla, efectivo) in OBJETIVOS.items() if efectivo is False}


def _regla_para_json(par, clave: str) -> bool:
    """¿El rol `clave`, por sí solo, abría esta puerta? (paso 1).

    Para `comentar_interno` el camino por rol ASIGNADO era sólo `es_admin`: el
    contador lo tenía por ser su rol PRIMARIO, así que su JSON no lo lleva.
    """
    regla, efectivo = OBJETIVOS[par]
    if efectivo is False:
        return False
    if par == ("pizarron", "comentar_interno"):
        return clave in _R_ADMIN
    return regla("", frozenset({clave}))


def planear(usuarios, roles, filas):
    """Plan puro (sin base) — lo usan la migración y su prueba.

    `usuarios`: [{"id", "rol", "roles": [rol_id, …]}]
    `roles`:    [{"id", "clave", "permisos": {modulo: [acciones]}}]
    `filas`:    {(usuario_id, modulo, permiso): activo}

    Devuelve `(json_nuevo, filas_nuevas)`:
      `json_nuevo`: {rol_id: permisos} sólo de los roles que cambian;
      `filas_nuevas`: [(usuario_id, modulo, permiso, activo)] a escribir.
    """
    json_nuevo: dict[int, dict] = {}
    permisos_por_rol: dict[int, dict] = {}
    for rol in roles:
        mapa = {m: list(a) for m, a in (rol["permisos"] or {}).items()}
        original = {m: sorted(a) for m, a in mapa.items()}
        for (modulo, permiso) in OBJETIVOS:
            acciones = set(mapa.get(modulo) or [])
            if rol["clave"] in ROLES_SISTEMA:
                debe = _regla_para_json((modulo, permiso), rol["clave"])
            elif (modulo, permiso) in _SOLO_PRIMARIO:
                debe = False
            else:
                continue  # rol personalizado: se respeta tal cual
            if debe:
                acciones.add(permiso)
            else:
                acciones.discard(permiso)
            if acciones:
                mapa[modulo] = sorted(acciones)
            else:
                mapa.pop(modulo, None)
        final = {m: sorted(a) for m, a in mapa.items()}
        permisos_por_rol[rol["id"]] = final
        if final != original:
            json_nuevo[rol["id"]] = final

    claves = {r["id"]: r["clave"] for r in roles}
    filas_nuevas = []
    for u in usuarios:
        primario = u["rol"] or ""
        efectivos = frozenset({primario} | {claves[r] for r in u["roles"] if r in claves})
        por_rol = set()
        for rid in u["roles"]:
            for modulo, acciones in (permisos_por_rol.get(rid) or {}).items():
                por_rol.update((modulo, a) for a in acciones)
        for par, (regla, _efectivo_) in OBJETIVOS.items():
            vieja = regla(primario, efectivos)
            fila = filas.get((u["id"], *par))
            if vieja:
                if fila is not True:
                    filas_nuevas.append((u["id"], *par, True))
                continue
            nueva = fila if fila is not None else (par in por_rol)
            if nueva:
                filas_nuevas.append((u["id"], *par, False))
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
    modulos = {m for m, _p in OBJETIVOS}
    filas = {
        (uid, m, p): activo
        for uid, m, p, activo in PermisoUsuario.objects.filter(modulo__in=modulos)
        .values_list("usuario_id", "modulo", "permiso", "activo")
    }

    json_nuevo, filas_nuevas = planear(usuarios, roles, filas)

    for rol in Rol.objects.filter(pk__in=list(json_nuevo)):
        rol.permisos = json_nuevo[rol.pk]
        rol.save(update_fields=["permisos"])

    for uid, modulo, permiso, activo in filas_nuevas:
        PermisoUsuario.objects.update_or_create(
            usuario_id=uid, modulo=modulo, permiso=permiso,
            defaults={"activo": activo},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0046_seed_permiso_equipo_actividad")]
    operations = [migrations.RunPython(aplicar, noop)]
