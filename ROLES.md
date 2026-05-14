# ROLES — El Despacho

Cuatro roles. Se asignan desde **El Directorio** en La Dirección. El primer
`super_admin` se crea automáticamente desde la variable de entorno
`DESPACHO_SUPERADMIN_EMAIL` al arrancar.

## super_admin

- Acceso total.
- **Único** rol que puede ver y modificar **Los Ajustes** (regla #3).
- Gestiona usuarios desde El Directorio.
- Puede acceder a La Dirección **y** El Taller.

## dueno

- Todo lo operativo del despacho + reportes ejecutivos.
- **No** accede a Los Ajustes (no toca llaves del sistema).
- Puede acceder a La Dirección y El Taller.

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
| Los Analistas — config (S4)     | ✅          | ❌    | ❌       | ❌        |
| Los Analistas — uso (S4)        | ✅          | ✅    | ✅       | ✅        |

Implementado en [`lib/permisos.py`](./lib/permisos.py) — decoradores
`@requires_role(...)` y helpers `puede_ver_*(...)`.
