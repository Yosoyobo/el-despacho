# S-MCP-V1 — 2026.07.09

Fecha: 15 de julio de 2026.

Se agregó un servidor MCP local por `stdio` sobre el ORM de El Taller. Expone
identidad, clientes, proyectos y tareas en modo de sólo lectura. La identidad se
selecciona con `DESPACHO_MCP_USUARIO_EMAIL`; todas las herramientas exigen
`mcp.usar` más el permiso de lectura del dominio y conservan el alcance por
asignación. Los montos de proyecto requieren `tesoreria.ver`.

Decisiones durables:

- No publicar HTTP sin OAuth 2.1.
- No agregar tools de escritura sin confirmación humana y auditoría.
- MCP es una entrada técnica externa y no forma parte de El Chalán.
- SDK estable fijado en `mcp==1.27.2`.

Verificación: 6 pruebas MCP verdes, tool registry correcto y Ruff completo
verde. La suite local dejó 1,823 pass, 9 skip y 3 fallos ambientales porque
Redis no estaba disponible en localhost; CI sí levanta Redis.
