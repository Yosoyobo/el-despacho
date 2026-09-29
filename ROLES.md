# ROLES — El Despacho

**Lo que alguien puede hacer lo deciden sus permisos, no el nombre de su rol.**
Un permiso es un par `módulo.acción` (`cotizaciones.aprobar`, `tesoreria.ver`).
Un rol es sólo un **paquete de permisos** con nombre, para no marcarlos uno por
uno. Ninguna pantalla pregunta «¿es dueño?»: pregunta «¿puede aprobar
cotizaciones?» (regla §4 #20 de `CLAUDE.md`).

## El único rol duro: `super_admin`

`super_admin` es el failsafe contra quedarse fuera del sistema: una vista con
`@requiere_permiso(...)` siempre lo deja pasar, aunque le falte la fila del
permiso, y es el único rol que el código nombra (`lib.permisos.es_super_admin`).
Ojo: `lib.permisos.puede()` **no** tiene ese failsafe. Una acción nueva que se
consulte con `puede()` (plantillas, `|puede:"mod.accion"`, El Chalán) necesita
estar en `DEFAULTS_POR_ROL["super_admin"]` **y** sembrarse con una migración
`seed_permisos_*`, o ni el super_admin la verá.

El primer super_admin nace de `DESPACHO_SUPERADMIN_EMAIL` al arrancar
(`bootstrap_superadmin`, idempotente).

## De dónde sale un permiso

Para cada `módulo.acción`, `puede()` mira en este orden y se queda con lo primero
que encuentre:

1. **Fila de la persona apagada** (`PermisoUsuario`, `activo=False`) → **no**.
   Una revocación individual le gana a cualquier rol.
2. **Fila de la persona encendida** (`activo=True`) → **sí**.
3. **Alguno de sus roles asignados** (`roles_extra`) trae la acción en su JSON
   (`Rol.permisos`) → **sí**.
4. Nada de lo anterior → **no**.

Las piezas en el código (`lib/permisos_defaults.py`):

- **`CATALOGO_PERMISOS`** — todas las acciones de cada módulo. Es la grilla que
  se ve en El Directorio; una acción que no esté aquí no se puede delegar.
- **`DEFAULTS_POR_ROL`** — qué trae cada rol del sistema de fábrica (tabla abajo).
- **`PERMISOS_UNIVERSALES`** — lo que **toda** persona trae desde que nace, sea
  cual sea su rol: hoy `equipo.ver_actividad` (ver quién está en línea). Se
  revoca por persona, no por rol.

## Roles del sistema, roles personalizados y rol primario

- **Roles del sistema**: `super_admin`, `dueno` (en producción se llama
  **«Director»**), `contador`, `disenador` y **«Runner»** (único que trae
  `runner.recibir` + `rutas.ver`; así sólo quien lo tiene aparece para repartir).
  Su identidad es la `clave`, que no cambia; el **nombre** se puede renombrar en
  El Directorio sin romper nada. Sólo `super_admin` no se puede borrar.
- **Roles personalizados**: los que se crean en **El Directorio → Roles**
  (permiso `directorio.roles`) marcando casillas del catálogo. Nacen con los
  permisos universales incluidos.
- **Roles asignados** (`Usuario.roles_extra`): una persona puede tener varios, y
  sus permisos se suman. Es la única forma de dar un rol desde la interfaz.
- **Rol primario** (`Usuario.rol`): ya no se elige; se **deriva** de los
  asignados (`sincronizar_rol_primario`): `super_admin` si tiene ese rol, si no
  `miembro` (rol neutro, sin permisos propios). Los valores viejos `dueno`,
  `contador` y `disenador` siguen en datos antiguos y en pruebas como primario
  «legacy». Ojo: el primario **no** aporta permisos por sí mismo; lo que valen
  es por las filas que se le sembraron a la persona al crearla
  (`defaults_de(rol)`, signal de `cuentas/signals.py`).

Para destinatarios de avisos o grupos de recados «por rol» se usa
`usuarios_con_rol(...)`, que cuenta el primario **y** los asignados. Para decidir
una puerta, nunca: ahí va un permiso.

## Qué trae cada rol por default

`todo` = todas las acciones del módulo en el catálogo; `—` = ninguna. Es lo que
dice el **código**; el JSON de cada rol en la base nació de aquí y lo mantienen
las migraciones, pero se puede editar en El Directorio → Roles, así que en
producción manda lo que diga esa pantalla.

<!-- tabla-roles:inicio · la genera infra/scripts/tabla_roles.py, no editar a mano -->
| Módulo | super_admin | dueno (Director) | contador | disenador |
|---|---|---|---|---|
| `cartera` | todo | ver, crear, editar, archivar | ver | — |
| `proyectos` | todo | todo | ver, ver_todos | ver |
| `pizarron` | todo | todo | ver, ver_internos, ver_comentarios, comentar_interno | ver, crear, editar, completar, ver_comentarios |
| `buzon` | todo | ver_propios, responder, eliminar | ver_propios, responder | ver_propios, responder |
| `recados` | todo | todo | ver, crear, editar_propios, adjuntar_drive | ver, crear, editar_propios, adjuntar_drive |
| `tesoreria` | todo | todo | todo | — |
| `dictado` | todo | todo | registrar_ingreso, registrar_egreso | actualizar_proyecto, crear_tarea |
| `contaduria` | todo | todo | todo | — |
| `catalogo` | todo | ver_nombres, ver_precios, crear, editar, editar_precios, archivar | ver_nombres, ver_precios | ver_nombres |
| `cotizaciones` | todo | ver, crear, editar, enviar, aprobar, rechazar, anular | ver, crear, editar, enviar | — |
| `facturacion` | todo | todo | todo | — |
| `caja` | todo | todo | todo | — |
| `chalan` | todo | todo | todo | todo |
| `analisis` | todo | — | — | — |
| `checador` | todo | todo | checar, ver_equipo, exportar | checar |
| `comunicacion` | todo | — | — | — |
| `runner` | — | — | — | — |
| `rutas` | todo | — | — | — |
| `papeleo` | todo | — | — | — |
| `gerencia` | todo | todo | — | — |
| `ajustes` | todo | — | — | — |
| `directorio` | todo | ver, gestionar | — | — |
| `chalanes` | todo | ver | — | — |
| `site` | todo | todo | — | — |
| `catalogos` | todo | — | — | — |
| `interfono` | todo | todo | — | — |
| `mcp` | todo | — | — | — |
| `equipo` | todo | todo | todo | todo |
| `recepcion` | todo | todo | — | — |
<!-- tabla-roles:fin -->

La tabla la genera `python3 infra/scripts/tabla_roles.py --escribir`;
`tests/test_roles_md.py` falla si deja de coincidir con `DEFAULTS_POR_ROL`.

## Cómo se delega (La Gerencia → El Directorio)

1. Abre a la persona → pestaña **Permisos** (hace falta `directorio.permisos`).
2. Arriba, **Roles**: marca uno o varios. Con eso basta en la mayoría de los casos.
3. Abajo, la **grilla**: marca una casilla para conceder algo que sus roles no
   traen, desmárcala para quitárselo sólo a ella.
4. Para cambiar a todos los de un rol a la vez, edita el rol en
   **El Directorio → Roles**, no a cada persona.

## La trampa: la grilla no ve los roles asignados

La grilla marca cada casilla según **la fila de la persona** o, si no hay fila,
según **el default de su rol primario**. **No mira los roles asignados.** Y al
guardar escribe una fila por **cada** acción del catálogo, con lo que esté
marcado.

Consecuencia: si una acción le llega a alguien **sólo** por un rol asignado
(p. ej. «Director» sobre un primario `miembro`), la grilla la muestra
**desmarcada**, y «Guardar permisos» la **apaga** — la fila apagada le gana al
rol. Pasa también al asignar un rol y guardar en el mismo clic.

- **En el día a día**: antes de guardar la grilla de alguien cuyo acceso viene
  de un rol, marca las casillas de ese rol (o asigna el rol y no toques la grilla).
- **Al programar**: cuando una acción nueva **reemplaza una puerta que antes
  decidía el rol**, no basta con meterla al JSON del rol: se **siembra por
  persona** (una fila `PermisoUsuario` activa a cada quien hoy pasa esa puerta),
  como hicieron `cuentas/0047_permisos_sin_rol_literal` y `0048_puertas_decididas`.
  Si no, el primer «Guardar» en El Directorio se la quita sin que nadie lo note.
- **Módulo nuevo** (§4 #20): acción en `CATALOGO_PERMISOS` + en
  `DEFAULTS_POR_ROL` de los roles que deban traerla + migración `seed_permisos_*`
  (esquema **o** datos, nunca las dos — §14 Bug I) + `@requiere_permiso` en las
  vistas + el menú + verificar que aparezca en la grilla.

## Probar como otro

En El Taller, un super_admin puede **«ver como rol»** (evalúa sólo el JSON de
ese rol) o **impersonar** a una persona concreta. «Ver como rol» no ve filas
individuales: si alguien tiene permisos sueltos, impersónalo a él.
