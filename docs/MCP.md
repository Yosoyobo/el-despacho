# MCP — El Despacho

El Despacho incluye un servidor MCP de **sólo lectura** para consultar clientes,
proyectos y tareas desde un cliente compatible. Usa el SDK oficial de MCP y el
transporte local `stdio`; no abre un puerto público.

## Seguridad

- La identidad se fija con `DESPACHO_MCP_USUARIO_EMAIL`.
- El usuario debe estar activo y tener `mcp.usar`.
- Cada herramienta exige además el permiso del módulo (`cartera.ver`,
  `proyectos.ver` o `pizarron.ver`).
- La visibilidad por asignación de proyectos y tareas se conserva.
- Los importes de proyecto sólo aparecen con `tesoreria.ver`.
- No existen herramientas de creación, edición, envío ni eliminación.

El correo identifica al usuario, pero **no es una credencial remota**. Este
servidor sólo debe ejecutarse mediante `stdio` en una máquina o contenedor bajo
control del despacho. Para publicarlo por HTTP se debe agregar OAuth 2.1 antes.

## Ejecutar

Dentro del entorno Python del repositorio:

```bash
DESPACHO_MCP_USUARIO_EMAIL=usuario@learningcenter.mx python -m mcp_despacho
```

Con el contenedor de El Taller ya iniciado:

```bash
docker compose exec -T \
  -e DESPACHO_MCP_USUARIO_EMAIL=usuario@learningcenter.mx \
  el-taller python -m mcp_despacho
```

Ejemplo de configuración de un cliente MCP local:

```json
{
  "mcpServers": {
    "el-despacho": {
      "command": "docker",
      "args": [
        "compose",
        "--project-directory",
        "/ruta/absoluta/ElDespacho",
        "exec",
        "-T",
        "-e",
        "DESPACHO_MCP_USUARIO_EMAIL=usuario@learningcenter.mx",
        "el-taller",
        "python",
        "-m",
        "mcp_despacho"
      ]
    }
  }
}
```

## Herramientas

- `identidad_actual`
- `buscar_clientes`
- `buscar_proyectos`
- `obtener_proyecto`
- `listar_tareas`

Para habilitar a alguien que no sea super_admin, concede `MCP → usar` desde
La Gerencia y conserva únicamente los permisos de lectura necesarios.
