# Deploy manual — Sprint S-Chalanes-Roles-Correos (VERSION 2026.06.44)

Guía de respaldo si **El Mensajero** (CI/CD) falla y hay que desplegar a mano
en **La Sede** (Droplet), o revertir. Este sprint trae 4 cambios:

1. Modelos del Cuadro de Chalanes (dropdown dependiente + anti cross-wiring).
2. Endurecimiento del redactor asistido (comentario ≠ reporte).
3. Roles con checkboxes (form de Rol) + grilla por-usuario completa.
4. **Campañas de correo movidas de Gerencia → Taller** (la app `campanas`
   pasó a ser app raíz compartida).

> Lo normal: hacer `git push` a `main`, El Mensajero corre tests + build +
> `migrate` (solo en la-gerencia) + sube imágenes a GHCR + La Mudanza hace
> `pull && up -d`. Esta guía es **solo para cuando eso falla**.

---

## 0. Pre-requisitos

```bash
ssh -i ~/.ssh/el-despacho-sede despacho@157.230.48.232
cd /opt/el-despacho
```

Todos los comandos asumen el stack productivo:
`-f docker-compose.yml -f docker-compose.prod.yml` (+ `-f docker-compose.site.yml`
para comandos de la-gerencia que tocan El Site).

---

## 1. Migración de base de datos (única de este sprint)

Hay **una sola migración nueva**: `chalanes/0012_enderezar_modelos_cuadro`
(data migration, idempotente, reversible). Endereza las filas del Cuadro que
quedaron con un modelo de otro proveedor (ej. Deepseek + `claude-haiku-4-5`).

**El movimiento de Campañas NO crea migración** — la app `campanas` conserva su
`app_label` y los nombres de tabla (`campanas_correo`, `campanas_envio`), así
que la fila `(campanas, 0001_initial)` en `django_migrations` sigue siendo
válida. No se recrean tablas, no se pierden datos.

```bash
# migrate corre SOLO en la-gerencia (regla Bug B §14)
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T la-gerencia python manage.py migrate --noinput
```

Salida esperada: aplica `chalanes.0012_enderezar_modelos_cuadro`. Si dice
"No migrations to apply", ya estaba aplicada (idempotente, sin problema).

### Verificar que el cross-wiring quedó resuelto

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T la-gerencia python manage.py shell -c \
  "from chalanes.models import CuadroChalanes; [print(c.estacion, c.proveedor, c.modelo) for c in CuadroChalanes.objects.all()]"
```

Cada modelo debe pertenecer a su proveedor (deepseek→`deepseek-*`,
anthropic→`claude-*`, gemini→`gemini-*`, openai→`gpt-*`/`o*`, mimo→`mimo-*`).

---

## 2. Despliegue de imágenes

Si El Mensajero subió las imágenes a GHCR pero La Mudanza falló:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Build local de emergencia (si GHCR no tiene las imágenes nuevas)

El server prod NO compila por regla (§4 #4). Solo en emergencia absoluta:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build el-taller la-gerencia
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

> **Importante (Campañas):** ambas imágenes (`el-taller` y `la-gerencia`)
> deben incluir `COPY campanas/ /app/campanas/` (ya está en los dos
> Dockerfiles). Si una imagen vieja no la tiene, el contenedor falla al
> arrancar con `ModuleNotFoundError: No module named 'campanas'`. La solución
> es rebuild de esa imagen (no editar a mano dentro del contenedor).

---

## 3. Smoke test post-deploy

```bash
for h in taller gerencia; do
  echo -n "$h: "; curl -s -o /dev/null -w "%{http_code}\n" https://$h.learningcenter.mx/ping
done
```

Ambos deben dar `200`. Luego, manual en navegador:

- **Gerencia → Chalanes** (`/chalanes/`): el Cuadro muestra el **modelo como
  dropdown**; al cambiar el Chalán de una fila, la lista de modelos cambia.
  Ya **no** aparece "Campañas de correo" en el sidebar de Gerencia.
- **Gerencia → Directorio → Roles → Nuevo rol**: los permisos son
  **checkboxes** por módulo (no un textarea JSON).
- **Gerencia → Directorio → (un usuario) → Permisos**: la grilla muestra
  **todos** los módulos (incluso para un `miembro`).
- **Taller**: aparece **"Campañas de correo"** en el sidebar para quien tenga
  el permiso `(comunicacion, campanas)` (por default solo super_admin). La ruta
  `/campanas/` responde en el Taller.

---

## 4. Reglas de Chalanes que dependen de credenciales (sin acción de código)

- La lista de modelos del dropdown se llena consultando la API de cada
  proveedor con la llave configurada en **Los Ajustes**. Sin llave, el adapter
  cae a una lista corta curada. El resultado se cachea ~1h; para refrescar:
  botón **"↻ Refrescar lista de modelos"** en `/chalanes/` (super_admin).
- Si Deepseek seguía fallando con 400, tras el `migrate` del paso 1 la fila
  queda en `deepseek-chat` y el fallback (mimo) deja de dispararse.

---

## 5. Rollback

### Opción A — revertir al deploy anterior (rápido)

La Mudanza guarda `docker-compose.prod.yml.previo` y el commit anterior:

```bash
cp docker-compose.prod.yml.previo docker-compose.prod.yml   # si existe
git reset --hard <commit_previo>
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Opción B — revertir solo la migración de Chalanes

La `0012` es reversible (su `reverse` es no-op: no restaura los modelos viejos
cross-wired, que de todos modos estaban rotos). Para volver al estado de
migración anterior:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T la-gerencia python manage.py migrate chalanes 0011 --noinput
```

> El rollback de migración NO es necesario para volver atrás el código: la
> tabla `CuadroChalanes` no cambió de esquema, solo se corrigieron valores.
> Reinstalar la imagen vieja + dejar los datos corregidos es seguro.

### Opción C — Campañas: volver a Gerencia

Si hubiera que revertir SOLO el movimiento de campañas, basta con desplegar
las imágenes del commit anterior (la app vuelve a `apps.campanas` en Gerencia).
Las tablas `campanas_*` no se tocaron, así que los datos de campañas previas
quedan intactos en cualquiera de los dos sentidos.

---

## 6. Notas

- Tablas de datos involucradas: ninguna se recrea ni se borra en este sprint.
- `BOVEDA_MASTER_KEY` y credenciales: sin cambios.
- Crontab de La Sede: sin cambios.
- Suite de tests: verde (campañas, analistas, panel de Chalanes, roles,
  permisos, redactor, + nuevos `test_modelo_cuadro` y `test_rol_checkboxes`).
