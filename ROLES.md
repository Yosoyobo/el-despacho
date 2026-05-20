# ROLES — El Despacho

Cuatro roles. Se asignan desde **El Directorio** en La Gerencia. El primer
`super_admin` se crea automáticamente desde la variable de entorno
`DESPACHO_SUPERADMIN_EMAIL` al arrancar.

## super_admin

- Acceso total.
- **Único** rol que puede ver y modificar **Los Ajustes** (regla #3).
- Gestiona usuarios desde El Directorio.
- Puede acceder a La Gerencia **y** El Taller.

## dueno

- Todo lo operativo del despacho + reportes ejecutivos.
- **No** accede a Los Ajustes (no toca llaves del sistema).
- Puede acceder a La Gerencia y El Taller.

## contador

- Solo módulos financieros: **La Contaduría, La Facturación, La Caja, La Cobranza**.
- Reportes financieros.
- Accede únicamente a El Taller.

## disenador

- Solo **Los Proyectos** y **El Pizarrón**, restringido a proyectos donde está asignado.
- Accede únicamente a El Taller.

## Matriz rápida

| Módulo                          | super_admin | dueno | contador | disenador |
|---------------------------------|:-----------:|:-----:|:--------:|:---------:|
| Los Ajustes                     | ✅          | ❌    | ❌       | ❌        |
| El Directorio                   | ✅          | ✅    | ❌       | ❌        |
| La Sala de Juntas               | ✅          | ✅    | ❌       | ❌        |
| La Cartera (clientes)           | ✅          | ✅    | ✅       | 👁 ver    |
| Los Proyectos                   | ✅          | ✅    | 👁 ver   | 🔒 propios |
| El Pizarrón (tareas/comments)   | ✅          | ✅    | 👁 ver   | 🔒 propios |
| Las Cotizaciones (S2)           | ✅          | ✅    | ✅       | 👁 ver    |
| La Facturación / Caja / Cobranza (S2) | ✅    | ✅    | ✅       | ❌        |
| La Contaduría (S3)              | ✅          | ✅    | ✅       | ❌        |
| Los Chalanes — Cuadro/Cadena    | ✅          | 👁 auditoría | ❌ | ❌        |
| Los Chalanes — uso (estaciones) | ✅          | ✅    | ✅       | ✅        |
| Los Recados (S2b)               | ✅          | ✅    | ✅       | ✅        |
| El Dictado (S2b)                | ✅ all      | ✅ all | 🔒 gastos | 🔒 tarea/proy |
| La Tesorería (S2b.3 ✅)         | ✅          | ✅    | ✅       | ❌        |
| Centros de costo (S2b.3 ✅)     | ✅          | 👁 read | 👁 read | ❌        |

Implementado en [`lib/permisos.py`](./lib/permisos.py) — decoradores
`@requires_role(...)` y helpers `puede_ver_*(...)`.

## Permisos granulares (Pre-S2b.1)

A partir de Pre-S2b.1 existe la tabla **`PermisoUsuario`** que permite que
un super_admin afine, por usuario, permisos individuales por encima del
default del rol. Defaults compilados de DOC_03 §5.1 + DOC_04 §5 + DOC_06
§11 viven en [`lib/permisos_defaults.py`](./lib/permisos_defaults.py) y
se siembran automáticamente:

- Al correr la migración `cuentas/0007_seed_permisos_defaults` (idempotente).
- Al crear un Usuario nuevo (signal `post_save` → `cuentas/signals.py`).

UI de gestión: `/directorio/<id>/permisos` en La Gerencia (solo super_admin).
Helper: `lib.permisos.puede(usuario, modulo, permiso)` — usuario inactivo
o anónimo siempre `False`. Eventos Portavoz: `permisos.actualizado`.
