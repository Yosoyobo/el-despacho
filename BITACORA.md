# BITÁCORA — Sesión 1 (S1a)

> Cierre de sesión del **2026-05-14**. Estado del repo: commit `f48a9a2` en `main`.
> Esta sesión cubrió **S1a** (infra + lib + auth + El Directorio + Los Ajustes).
> **S1b** (La Cartera + Los Proyectos + El Pizarrón) queda como puente antes de S2.

---

## 1. Módulos entregados

### Núcleo de seguridad (`lib/`) — ✅ completo

| Módulo | Estado | Notas |
|---|---|---|
| `boveda.py` (AES-256-GCM) | ✅ | Eager check al import; round-trip + rotar + tamper-detection. |
| `portavoz.py` + `portavoz_eventos.py` + `portavoz_worker.py` | ✅ | Eventos tipados + HMAC-SHA256; encolado en Redis; worker dedicado con re-encolado si n8n no responde o falta config. |
| `permisos.py` | ✅ | 4 roles + decoradores `@requires_role` + helpers `puede_ver_*`. |
| `sesion.py` (`getAuth → ContextoUsuario`) | ✅ | Dataclass frozen con `.es_admin` / `.es_super_admin`. |
| `sanear.py` (`sanear_contexto`) | ✅ | Strip script/iframe/on-handlers/js: + escape HTML + truncate. |
| `ratelimit.py` | ✅ | Sliding window en Redis (ZADD/ZREMRANGEBYSCORE). |
| `google_oauth.py` | ✅ funcional, 🟡 sin probar contra Google real | Lee credenciales de Los Ajustes; 503-graceful si faltan. |
| `errors.py`, `fecha.py` | ✅ | Excepciones tipadas + tz_mx helpers. |

### Apps Django compartidas — ✅ completo

| App | Estado | Notas |
|---|---|---|
| `cuentas/` (Usuario AUTH_USER_MODEL) | ✅ | Email como `USERNAME_FIELD`, roles `(super_admin, dueno, contador, disenador)`, migración inicial congelada. |
| `ajustes/` (Credencial cifrada) | ✅ | KV con 14 slots predefinidos; `.obtener()` / `.guardar()` automáticos via Bóveda. |

### La Gerencia (puerto 8001) — ✅ completo para alcance S1a

| Módulo | Estado | Notas |
|---|---|---|
| `auth_gerencia` (login email/pwd + Google SSO + rate-limit) | ✅ | Solo `super_admin` y `dueno`. |
| `el_directorio` (CRUD Usuario) | ✅ | Lista + crear + editar + bloquear; emite eventos `usuario.creado` / `usuario.bloqueado`. |
| `los_ajustes` (UI credenciales cifradas) | ✅ | Solo super_admin; emite `ajuste.credencial_guardada`. "Probar" actualmente solo valida descifrado — pruebas reales contra APIs llegan en S2+. |
| `gerencia_home` (Sala de Juntas) | 🟡 placeholder | 4 tarjetas: salud Bóveda, conteo credenciales configuradas, conteo usuarios activos, "próximos módulos". KPIs reales en S3. |
| `legal` (privacidad/términos LFPDPPP) | ✅ | Texto base; legal/contador puede refinar contenido en S2. |

### El Taller (puerto 8000) — ✅ andamio S1a

| Módulo | Estado | Notas |
|---|---|---|
| `auth_taller` (login los 4 roles + Google SSO + rate-limit) | ✅ | |
| `taller_home` | 🟡 placeholder | Sin CRUDs todavía. |
| `legal` | ✅ | Mismo contenido que La Gerencia. |
| **La Cartera, Los Proyectos, El Pizarrón** | ⏳ pendiente S1b | |

### La Recepción (puerto 8002) — 🟡 stub

| Módulo | Estado | Notas |
|---|---|---|
| `recepcion_stub` | 🟡 | Página "Próximamente" + `/ping`. UI completa en **S5**. |

### Infra — ✅ completo

| Pieza | Estado |
|---|---|
| Docker Compose (7 servicios) | ✅ |
| Dockerfiles con Tailwind CLI standalone | ✅ (CLI baja pero **no compila** en S1a porque no hay `tailwind.config.js` — uso Tailwind CDN por ahora) |
| Caddyfile multi-host | ✅ |
| Scripts (`mudanza.sh`, `archivo.sh`, `limpieza.sh`, `despacho.sh`) | ✅ |
| El Mensajero (GHA): tests + ruff + build matrix → GHCR | ✅ |
| La Limpieza (GHA cron semanal) | ✅ |

---

## 2. Tablas Postgres creadas

Se aplicaron en el arranque inicial vía `migrate`. Las tablas Django built-in (`auth_group`, `auth_permission`, `django_session`, `django_migrations`, `django_content_type`) también están — no las listo.

### `cuentas_usuario` (regla #10 — única tabla de identidad)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | bigserial PK | |
| `password` | varchar(128) | Hash Django. |
| `last_login` | timestamptz null | |
| `is_superuser` | bool | |
| `email` | varchar(254) UNIQUE INDEX | `USERNAME_FIELD`, lowercased al guardar. |
| `nombre_completo` | varchar(200) | |
| `rol` | varchar(20) INDEX | choices: `super_admin / dueno / contador / disenador` (default `disenador`). |
| `google_sub` | varchar(64) INDEX | `""` si no hay SSO vinculado. |
| `avatar_url` | varchar(200) | |
| `is_active` | bool | |
| `is_staff` | bool | |
| `creado_en` | timestamptz auto_now_add | |
| `actualizado_en` | timestamptz auto_now | |
| `ultimo_acceso_en` | timestamptz null | Actualizado en cada login. |
| `groups`, `user_permissions` | M2M | Heredados de `PermissionsMixin`. |

### `ajustes_credencial` (KV cifrado)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | bigserial PK | |
| `clave` | slug(80) UNIQUE | Ej. `stripe_secret_key`, `n8n_webhook_url`. |
| `valor_cifrado` | text | base64 URL-safe de `nonce(12) ‖ AES-GCM-ciphertext`. |
| `actualizada_en` | timestamptz auto_now | |
| `actualizada_por_id` | bigint FK→`cuentas_usuario` ON DELETE SET NULL | Auditoría. |

### Tablas pendientes (llegan en sesiones siguientes)

**S1b:** `cartera_cliente`, `proyectos_proyecto`, `proyectos_asignacion`, `pizarron_tarea`, `pizarron_comentario`.
**S2:** `cotizaciones_cotizacion`, `facturacion_factura`, `caja_pago`, `cobranza_recordatorio`.
**S3:** `contaduria_movimiento`, `contaduria_cuenta`.

---

## 3. Endpoints expuestos por app

### La Gerencia (`gerencia.ninomeando.com` · 8001)

| Método | Path | Vista | Auth |
|---|---|---|---|
| GET/POST | `/sign-in` | `auth_gerencia.sign_in` | público |
| GET | `/sign-out` | `auth_gerencia.sign_out` | login |
| GET | `/auth/google/start` | inicia OAuth | público (503 si no configurado) |
| GET | `/auth/google/callback` | callback OAuth | — |
| GET | `/` | Sala de Juntas | login |
| GET | `/ping` | liveness probe | público |
| GET | `/directorio/` | lista usuarios | super_admin / dueno |
| GET/POST | `/directorio/nuevo` | crear usuario | super_admin / dueno |
| GET/POST | `/directorio/<id>/editar` | editar usuario | super_admin / dueno |
| POST | `/directorio/<id>/bloquear` | toggle activo | super_admin / dueno |
| GET | `/ajustes/` | panel credenciales | **super_admin only** |
| POST | `/ajustes/guardar` | upsert credencial | super_admin |
| POST | `/ajustes/<clave>/probar` | smoke test descifrado | super_admin |
| GET | `/legal/privacidad`, `/legal/terminos` | legales | público |

### El Taller (`taller.ninomeando.com` · 8000)

| Método | Path | Vista | Auth |
|---|---|---|---|
| GET/POST | `/sign-in` | login los 4 roles | público |
| GET | `/sign-out` | logout | login |
| GET | `/auth/google/start`, `/auth/google/callback` | SSO | público |
| GET | `/` | home placeholder | login |
| GET | `/ping` | liveness | público |
| GET | `/legal/privacidad`, `/legal/terminos` | legales | público |

**Pendiente S1b:** `/cartera/...`, `/proyectos/...`, `/pizarron/...`.

### La Recepción (`recepcion.ninomeando.com` · 8002)

| Método | Path | Vista |
|---|---|---|
| GET | `/` | "Próximamente" |
| GET | `/ping` | liveness (`estado: stub`) |

---

## 4. Eventos del Portavoz definidos

Catálogo en `lib/portavoz_eventos.py`. Cada evento es un `EventoPortavoz` con la forma:

```json
{
  "tipo": "<EventoTipo>",
  "actor_id": 1,
  "actor_email": "oscar@bautista.mx",
  "payload": { ... específico ... },
  "emitido_en": "2026-05-14T12:34:56-06:00",
  "schema_version": 1
}
```

Firmado con `X-Despacho-Signature: <HMAC-SHA256-hex>` (secret en `Credencial.n8n_webhook_secret`).

| `tipo` (Literal) | Emisor en S1a | Payload típico |
|---|---|---|
| `usuario.creado` | `el_directorio.crear` | `{usuario_id, email, rol}` |
| `usuario.bloqueado` | `el_directorio.bloquear` | `{usuario_id, email}` |
| `ajuste.credencial_guardada` | `los_ajustes.guardar` | `{clave}` (nunca el valor) |
| `cliente.creado` | ⏳ S1b | `{cliente_id, razon_social, rfc}` |
| `proyecto.creado` | ⏳ S1b | `{proyecto_id, cliente_id, estado}` |
| `proyecto.status_cambiado` | ⏳ S1b | `{proyecto_id, anterior, nuevo}` |
| `tarea.creada`, `tarea.completada` | ⏳ S1b | `{tarea_id, proyecto_id}` |
| `cotizacion.enviada` | ⏳ S2 | `{cotizacion_id, cliente_id, total}` |
| `factura.emitida` | ⏳ S2 | `{factura_id, cliente_id, total}` |
| `pago.recibido` | ⏳ S2 | `{factura_id, monto, fuente: 'stripe'|'mp'}` |
| `pago.recordatorio` | ⏳ S2 | `{factura_id, cliente_email, dias_vencido}` |

Todos los `tipo` están en el `Literal` de `EventoTipo` — agregar uno nuevo requiere editar `portavoz_eventos.py` (intencional, evita typos).

---

## 5. Tests pasando

```
$ pytest -q tests/
............................                                             [100%]
28 passed, 1 warning in 0.22s
```

| Suite | Tests | Cobertura aproximada |
|---|---|---|
| `tests/test_boveda.py` | 8 | round-trip · unicode · nonce aleatorio · blob vacío · tampered · base64 inválido · tipo no-string · rotar. **~95% de `lib/boveda.py`.** |
| `tests/test_portavoz.py` | 6 | Serialización JSON · firma HMAC estable · firma distinta por secret · verificar acepta/rechaza · firmar sin secret. **~80% de `lib/portavoz.py`** (no se prueba `emitir()` real porque toca Redis — es trivial y se cubre en CI con el service `redis` levantado, pero el test no existe todavía). |
| `tests/test_sanear.py` | 8 | Script · iframe · `javascript:` · on-handlers · escape HTML · truncate · no-string · control chars. **~95% de `lib/sanear.py`.** |
| `tests/test_permisos.py` | 6 | Matriz 4 roles × {es_admin, es_super_admin, puede_ver_ajustes, puede_ver_finanzas}. **~70% de `lib/permisos.py`** — falta probar el decorador `@requires_role` end-to-end con un `request` falso. |

**Sin cobertura todavía** (todas pendientes en S1b o cuando haya Django levantado para tests):
- `lib/ratelimit.py` (necesita Redis levantado — CI lo tiene como service, pero no escribí test).
- `lib/sesion.py` (`getAuth`) — trivial pero merece una prueba con `request` falso.
- `lib/google_oauth.py` — el flujo OAuth real es difícil de mockear; al menos vale un test de `esta_configurado()`.
- `lib/portavoz_worker.py` — loop principal.
- `cuentas/`, `ajustes/` — modelos no testados (necesita pytest-django).
- Las vistas Django no tienen tests — llegarán con S1b cuando haya CRUDs reales.

---

## 6. Decisiones tomadas sobre la marcha (no estaban en el prompt)

### Naming y estructura

- **Apps Django compartidas en la raíz del repo** (`cuentas/`, `ajustes/`) en lugar de `apps_compartidos/` con sub-paquetes. Justificación: imports limpios (`from cuentas.models.usuario import Usuario`) y ambos Django projects (La Gerencia y El Taller) las incluyen en `INSTALLED_APPS` sin gimnasia de paths.
- **Las apps de cada Django project viven bajo `apps/`** (ej. `la-gerencia/apps/el_directorio/`) con `app_label` explícito (`label = "el_directorio"`). Esto permite tener dos apps `legal/` (una en cada project) con `label="legal_gerencia"` y `label="legal_taller"` para que no choquen en la DB de `django_content_type` cuando ambos projects comparten Postgres.
- **`container_name` con prefijo `despacho-*`** — para coexistir con El Corporativo que ya corre en HAL bajo `la-gerencia`, `el-portero`, `la-oficina`. **No estaba en el prompt** pero era obligatorio para que `docker compose up` funcionara en HAL.
- **Puertos de Caddy `19080/19443`** — El Corporativo ya usa `18080/18443`. Si esto va a producción en otro Droplet, el `.env` debería volver a `80/443` o `18080/18443`. Documentado en `.env.example` los defaults para HAL.

### Modelo Usuario

- **Usé `AbstractBaseUser + PermissionsMixin`** en lugar de `AbstractUser`. Justificación: `AbstractUser` arrastra `username` que no necesitamos (usamos email) — `AbstractBaseUser` da control completo. Cost: tuve que escribir `UsuarioManager` propio.
- **`rol` indexado** porque las consultas "todos los contadores" / "todos los disenadores" son comunes.
- **`google_sub` empty-string por default** (no NULL) para evitar índice parcial. UNIQUE no aplicado a `google_sub` (admite vacío repetido).
- **`USERNAME_FIELD = "email"` + `REQUIRED_FIELDS = ["nombre_completo"]`** — un `createsuperuser` interactivo pide ambos. El bootstrap automático pasa `nombre_completo="Super Admin"` por default.

### Credencial / Los Ajustes

- **14 slots predefinidos en `SLOTS_CREDENCIAL`** (Google OAuth ×4, Stripe ×2, MercadoPago ×2, Anthropic, OpenAI, n8n ×2, VAPID ×2). Agregar slot nuevo = editar la lista en `ajustes/models/credencial.py` y el formulario lo recoge solo.
- **Slots desconocidos requieren `permitir_custom=on` en el POST** — defensa en profundidad contra typos. No expuesto en la UI todavía; la lista cubre lo planeado para S2-S4.
- **Vaciar el campo y guardar elimina la entrada** (en vez de guardar string vacío cifrado). Más limpio para `esta_configurado()`.
- **"Probar" en S1a es un smoke test** (¿descifra el valor sin error?). Pruebas reales contra cada API (ping a Stripe, intercambio dummy con Google, etc.) llegan en S2+ cuando esos clientes existan.

### Auth

- **La Gerencia rechaza `contador` y `disenador`** en el sign-in (403). Ellos entran solo por El Taller. Esto **no estaba explícito en el prompt** — interpreté que La Gerencia = "panel de mando" implica admin-only.
- **Cookies nombradas distintas** (`gerencia_session` vs `taller_session`) para permitir doble login simultáneo desde el mismo navegador en el mismo dominio raíz.
- **Bootstrap super_admin idempotente**: si el usuario existe, solo actualiza rol/is_active/is_staff/is_superuser. **No** sobreescribe el password — si ya lo cambiaste tras el primer login, sigue funcionando.

### Portavoz

- **Worker como servicio Docker separado** (`despacho-portavoz-worker`). Comparte la imagen de La Gerencia porque necesita Django setup para leer `Credencial`.
- **Re-encolado al final de la cola** si n8n no responde. Backoff fijo de 10s tras fallo, 30s si faltan credenciales. **No hay dead-letter queue todavía** — un evento podría reciclar infinitamente. Marcado abajo como deuda.

### Infra

- **Tailwind CLI standalone se descarga en el Dockerfile pero NO se invoca** porque no hay `tailwind.config.js` en S1a — el `RUN if [ -f tailwind.config.js ]; then ...` lo salta. Uso CDN por ahora. Compilación real llega en S1b.
- **Whitenoise para servir static** en lugar de pedirle a Caddy que lo sirva. Más simple para el monorepo (cada container es autosuficiente). Caddy solo hace reverse proxy.
- **`collectstatic --clear` en cada arranque** — está bien para HAL/dev, considerar quitarlo de prod si los tiempos de arranque crecen.

---

## 7. Deuda técnica / TODOs

> Marcados también con `🟡` arriba donde aplica.

### Crítico / antes de S2

- **Migración inicial de `cuentas` tiene `managers=[("objects", django.contrib.auth.models.UserManager())]`** — pero el modelo usa `UsuarioManager`. Django ignora el manager en migraciones para resolución de queries (usa el del modelo), pero el código de la migración debería referenciar `cuentas.managers.UsuarioManager` por consistencia. **Bug latente** si en algún momento se hace `auth_user_model.objects.create_user(username=...)` desde una migración. Corrección: una migración hueca (`migrations.AlterModelManagers`) o simplemente editar `0001_initial.py` y dejar `managers=[]`.
- **`docker-compose.prod.yml` referencia `ghcr.io/yosoyobo/el-despacho-*:latest`** pero esas imágenes no existen aún en GHCR — el primer push a `main` con el repo creado las publica.
- **La rama `main` no tiene remoto.** Falta `git remote add origin git@github.com:Yosoyobo/el-despacho.git && git push -u origin main`. CI no corre hasta entonces.

### Mediano (S1b o cuando convenga)

- **No hay tests de `lib/ratelimit.py`** (necesita Redis levantado en pytest).
- **No hay tests de `lib/sesion.py` ni `lib/google_oauth.esta_configurado()`** — triviales pero faltan.
- **No hay tests de vistas Django.** Cuando lleguen CRUDs en S1b, agregar `pytest-django` a `requirements.txt` y un `DJANGO_SETTINGS_MODULE` en pyproject.toml.
- **Portavoz worker no tiene dead-letter queue ni límite de retries** — un evento corrupto recicla infinitamente. Mínimo: contador en el JSON y descarte tras N intentos a un `portavoz:fallidos`.
- **No hay healthcheck en los containers de Django** — solo postgres y redis lo tienen. Agregar `healthcheck: curl -f http://localhost:8001/ping` (requiere instalar curl en la imagen o usar python).
- **Tailwind CDN** — bonito para iterar, pero en prod hay que compilar. La Cocina/El Corporativo ya tienen ese patrón resuelto, copiar config.
- **Iconos PWA / manifest** — no se generaron (regla #12 los pide). Llegan con S1b cuando haya UI sustantiva.
- **`la-gerencia/templates/directorio/form.html` tiene un `<style>` inline con `@apply`** que NO se compila sin PostCSS — por ahora los inputs heredan estilos del browser. Visualmente funcional pero no pulido.

### Bajo / nice-to-have

- **`SLOTS_CREDENCIAL` está hardcoded.** Si los stakeholders piden agregar slots desde UI, hay que mover a una tabla `ajustes_slot` o un YAML.
- **`Credencial.guardar()` con valor vacío silenciosamente borra.** Tal vez quieres un endpoint explícito `eliminar` para no confundir.
- **El Mensajero corre `ruff check .`** — la base de código S1a pasa pero no lo verifiqué con `--fix`. Habrá uno que otro nit al primer push.
- **`docker-compose.yml` mezcla `expose:` y `ports:` sin ports en las apps Django** — está bien porque Caddy es el único acceso externo, pero en HAL si quieres `curl http://localhost:8001/ping` directo necesitas un `ports:` temporal o `docker exec`. (Lo verifiqué con `docker exec`).
- **`.dockerignore` no excluye `__tests__/`** — los Dockerfiles las copiarán a las imágenes de prod. Cost: ~few KB. Ignorable, pero limpio sería excluirlas.

---

## 8. Recomendaciones antes de arrancar S2

> Asumo que **S1b ocurre primero** (La Cartera + Los Proyectos + El Pizarrón). Si decides saltar directo a S2, varias recomendaciones se vuelven obligatorias.

### Antes de S1b (corto)

1. **Push del repo a GitHub** y verifica que El Mensajero queda verde en la PR / push a main. Esto valida el setup de CI sin que esperes hasta S2.
2. **Fix de la migración de `cuentas`**: ajusta `managers=` en `0001_initial.py` o agrega una migración `AlterModelManagers`. 2 minutos, pero quita un footgun.
3. **Crea las imágenes en GHCR** (push a main lo hace solo) y verifica que `docker-compose.prod.yml` referencia tags válidos.
4. **Decide el enum de estados de Los Proyectos** — propuse `prospecto / en_diseno / en_produccion / entregado / cancelado`. Confirmar antes de S1b para no rehacer migraciones.
5. **Healthchecks** en los containers Django (curl/python a `/ping`). Caddy y Compose se beneficiarán para `depends_on: condition: service_healthy`.

### Antes de S2 (mediano)

6. **Compila Tailwind en build**: agrega `tailwind.config.js` con paths a templates de cada app, `static/css/input.css` con `@tailwind base/components/utilities`, y deja que el Dockerfile lo invoque (ya está el `RUN if [ -f tailwind.config.js ]`). Para S2 vas a tener formularios complejos (cotizaciones, facturación) y el `<style>@apply` inline no escala.
7. **Pytest-django** instalado y un `DJANGO_SETTINGS_MODULE` configurado para correr tests de vistas/modelos. S2 trae Stripe webhooks, OCR, integración Google — sin tests Django esto se vuelve frágil.
8. **Define la estructura de PDFs vía Google Docs antes de codear cotizaciones.** El prompt dice "templates de Google Docs" — necesitas un Doc plantilla con placeholders `{{cliente}}`, `{{lineas}}`, etc. y un wrapper en `lib/google_docs.py`. Pídeselo al usuario en S2 kick-off antes de escribir código.
9. **Stripe + MercadoPago en sandbox primero**. Pide al usuario que cree cuentas test y guarde llaves de sandbox en Los Ajustes antes de cualquier integración real.
10. **Tailscale + n8n**: confirma con el usuario que su n8n está accesible vía Tailscale desde el container `portavoz-worker`. Si Tailscale corre en el host, el worker necesita `network_mode: host` o un sidecar Tailscale en el compose.
11. **Backup automático**: `archivo.sh` está listo pero no se invoca. Considera agregarlo a un cron en La Sede o un job dedicado en GHA.
12. **Rota `BOVEDA_MASTER_KEY` y `DJANGO_SECRET_KEY` antes de prod.** El `.env` actual en HAL tiene secrets aleatorios — buenos para dev, pero el `.env` de La Sede debe ser distinto y nunca commiteado. (Ya está en `.gitignore`).

### Antes de prod (cuando deploy a DO)

13. **Cambia `CADDY_HTTP_PORT/HTTPS_PORT` a 80/443** en el `.env` del Droplet.
14. **DNS de los 3 hosts** (`taller/gerencia/recepcion.ninomeando.com`) apuntando al Droplet — sin eso Let's Encrypt no emite cert.
15. **Configura los secrets de GHA** para que El Mensajero pueda invocar La Mudanza vía SSH (`SEDE_HOST`, `SEDE_USER`, `SEDE_SSH_KEY`).
16. **Revisa `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`** — están parametrizados por env var pero hay que poblarlos con los dominios reales.
17. **Considera un `init` job que corra `bootstrap_superadmin` solo en La Sede** y no en cada arranque — idempotente está bien, pero un job dedicado deja un audit trail más claro.

---

**Cierre:** S1a deja un esqueleto operativo, probado en HAL, con CI verde local (`pytest -q tests/` → 28/28). El próximo turno empieza leyendo `CLAUDE.md` + `BITACORA_S1.md` + `git log -1`.

---

# BITÁCORA — Sesión 1 (S1-final)

> Cierre del **2026-05-14**, mismo día que S1a. Comenzó con repo `Yosoyobo/el-despacho` no creado en GitHub y termina con CI verde pushando a GHCR.
> Cubrió: rename masivo (La Dirección → La Gerencia + oficina → taller), Tailwind compilado, S1b completo (La Cartera + Los Proyectos + El Pizarrón), Portavoz DLQ, suite de tests Django, healthchecks, PWA, y auto-pin de digests en CI.

## 1. Módulos entregados sobre S1a

### Rename completo (decisión correctiva, no estaba "feature")

| Token (antes) | Token (después) | Alcance |
|---|---|---|
| `la-direccion/` directorio | `la-gerencia/` | repo entero |
| `la_direccion` módulo Py | `la_gerencia` | settings, asgi, wsgi, manage, urls |
| `direccion_home` app | `gerencia_home` | label + templates |
| `auth_direccion` app | `auth_gerencia` | label + views + URL |
| `legal_direccion` label | `legal_gerencia` | apps.py |
| `direccion_session` / `_csrftoken` | `gerencia_session` / `_csrftoken` | settings |
| `direccion.ninomeando.com` | `gerencia.ninomeando.com` | Caddyfile, env |
| `DIRECCION_ALLOWED_HOSTS` | `GERENCIA_ALLOWED_HOSTS` | env vars |
| `despacho-la-direccion` container | `despacho-gerencia` | compose |
| `ghcr.io/.../el-despacho-direccion` | `…/el-despacho-gerencia` | workflows + compose.prod |
| `oficina.ninomeando.com` | `taller.ninomeando.com` | Caddyfile, env, refs en docs |

Los apps renombrados no tenían modelos → 0 rows en `django_content_type` / `django_migrations` que migrar. No fue necesaria data migration.

### S1b — núcleo operativo de El Taller

| Módulo | Estado | Notas |
|---|---|---|
| `apps.la_cartera` | ✅ | CRUD clientes B2B + soft delete + búsqueda · vista de archivados solo admin. Eventos `cliente.creado/actualizado`. |
| `apps.los_proyectos` | ✅ | Proyectos con código auto `PRY-NNNNNN`, enum expandido (prospecto/cotizado/en_diseno/revision_cliente/en_produccion/entregado/en_pausa/cancelado), asignaciones M2M con rol enum (líder/diseñador/producción/revisor). Eventos `proyecto.creado/status_cambiado`. |
| `apps.el_pizarron` | ✅ | Tareas (estado+prioridad+asignación opcional) y comentarios polimórficos (tarea XOR proyecto) con CheckConstraint. Comentarios internos ocultos a diseñador no-autor. Eventos `tarea.creada/completada`. |
| `taller_home` con KPIs reales | ✅ | Clientes activos + proyectos recientes filtrados por rol + tareas pendientes propias. |

### Núcleo de seguridad y operación

| Pieza | Estado |
|---|---|
| Portavoz DLQ + max_intentos=5 | ✅ `lib/portavoz_worker.py` con `_reencolar_con_intento()`. JSON corrupto → DLQ inmediato. Falta de creds NO consume intento. |
| Comando `portavoz_fallidos` | ✅ `ajustes/management/commands/portavoz_fallidos.py` con `--listar/--reencolar/--descartar/--vaciar`. |
| Tailwind compilado real | ✅ per-app: `la-gerencia/` y `el-taller/` con `tailwind.config.js` + `static/css/input.css` + `.campo-form` clase. CDN eliminado en ambas apps. La Recepción usa CSS inline mínimo. |
| `cuentas/0001_initial.py` fix | ✅ `managers=[]`, ya no referencia UserManager de auth. |
| Healthchecks Django | ✅ los 3 servicios con `/ping` via urllib (no curl). Caddy `depends_on: service_healthy`. |
| `.dockerignore` ampliado | ✅ excluye `tests/`, `.github/`, `BITACORA_*`, `.env*`. |
| `collectstatic --clear` gated | ✅ solo si `DESPACHO_ENV != production` en ambos entrypoints. |
| PWA El Taller | ✅ `manifest.json` (any + maskable), 4 iconos PNG, apple-touch-icon, theme_color. Script `scripts/generar_iconos_pwa.py` (Pillow, idempotente). |
| El Mensajero auto-pin digests | ✅ nuevo job `actualizar_digests` resuelve sha256 desde GHCR y reescribe `docker-compose.prod.yml`. Bot commit + paths-ignore para evitar loop. |

## 2. Tablas Postgres creadas (S1b)

| Tabla | Campos clave |
|---|---|
| `cartera_cliente` | razon_social, rfc (UNIQUE parcial ≠""), estado (prospecto/activo/inactivo), activo (soft delete), creado_por FK |
| `proyectos_proyecto` | codigo UNIQUE, cliente FK PROTECT, estado (enum 8), fechas (inicio/compromiso/real_entrega), monto_estimado |
| `proyectos_asignacion` | proyecto FK, usuario FK, rol_en_proyecto enum, UNIQUE(proyecto,usuario) |
| `pizarron_tarea` | proyecto FK, asignada_a FK SET_NULL, estado, prioridad, fecha_compromiso, completada_en |
| `pizarron_comentario` | tarea FK null / proyecto FK null + CHECK(uno xor otro), autor FK PROTECT, es_interno bool |

## 3. Endpoints expuestos (El Taller — nuevos)

| Método | Path | Vista | Auth |
|---|---|---|---|
| GET | `/cartera/` | lista (filtros, archivados solo admin) | login + (admin/dueno/contador) |
| GET/POST | `/cartera/nuevo` | crear | admin only |
| GET | `/cartera/<id>/` | detalle + lista de proyectos | login + ver_cartera |
| GET/POST | `/cartera/<id>/editar` | editar | admin only |
| POST | `/cartera/<id>/archivar` | toggle soft delete | admin only |
| GET | `/proyectos/` | lista filtrada por rol | login |
| GET/POST | `/proyectos/nuevo` | crear | admin only |
| GET | `/proyectos/<id>/` | detalle + tareas | login + ver_proyecto |
| GET/POST | `/proyectos/<id>/editar` | editar | admin only |
| GET/POST | `/proyectos/<id>/cambiar-estado` | mutar estado + fecha_real_entrega | admin only |
| GET/POST | `/proyectos/<id>/asignar` | agregar/quitar miembros del equipo | admin only |
| GET/POST | `/proyectos/<id>/tareas/nueva` | crear tarea | ver_proyecto |
| POST | `/proyectos/<id>/comentar` | comentario a nivel proyecto | ver_proyecto |
| GET | `/tareas/<id>/` | detalle + comentarios visibles | ver_tarea |
| GET/POST | `/tareas/<id>/editar` | editar tarea | ver_tarea |
| POST | `/tareas/<id>/comentar` | comentario a nivel tarea + sanear_contexto | ver_tarea |
| POST | `/tareas/<id>/completar` | marca completada + completada_en | ver_tarea |

`/admin/` (Django admin) montado en El Taller.

## 4. Eventos del Portavoz emitidos en S1b

- `cliente.creado` (en `/cartera/nuevo`)
- `cliente.actualizado` (en `/cartera/<id>/editar`) — **agregado al Literal**
- `proyecto.creado` (en `/proyectos/nuevo`)
- `proyecto.status_cambiado` (en `/proyectos/<id>/cambiar-estado`)
- `tarea.creada` (en `/proyectos/<id>/tareas/nueva`)
- `tarea.completada` (en `/tareas/<id>/completar`)

Todos van por la cola Redis → worker con DLQ.

## 5. Tests pasando

```
$ pytest -q tests/
71 passed, 0 skipped en CI (con redis service)
62 passed, 9 skipped en HAL (sin redis local)
```

| Suite | Tests | Cobertura |
|---|---|---|
| `tests/test_boveda.py` | 8 | (S1a) |
| `tests/test_portavoz.py` | 6 | (S1a) |
| `tests/test_sanear.py` | 8 | (S1a) |
| `tests/test_permisos.py` | 6 | (S1a) |
| `tests/test_ratelimit.py` ✨ | 5 | sliding window, aislamiento, ventana corta. Redis-marked. |
| `tests/test_sesion.py` ✨ | 5 | getAuth con/sin user, anónimo, super_admin / dueno / disenador. |
| `tests/test_google_oauth.py` ✨ | 4 | esta_configurado + url_autorizacion. |
| `tests/test_portavoz_worker.py` ✨ | 4 | _reencolar_con_intento, descarte a DLQ, JSON corrupto. Redis-marked. |
| `tests/taller/test_cartera.py` ✨ | 8 | roles, CRUD, RFC inválido, soft delete. |
| `tests/taller/test_proyectos.py` ✨ | 9 | visibilidad por rol, asignar/quitar, cambiar_estado, crear. |
| `tests/taller/test_pizarron.py` ✨ | 8 | CHECK polimórfico, comentarios internos por rol, diseñador asignado completa tarea. |

Setup: `tests/django_settings.py` (merge El Taller + SQLite in-memory), `tests/urls_taller.py`, conftest con autouse-fixture que monkeypatcha `emitir` a noop cuando Redis ausente y marca skip a tests `@pytest.mark.redis`.

## 6. Decisiones aprobadas por Oscar (decir antes de codear, sección 5 del prompt)

1. **Estados de Proyecto expandidos** — 8 valores incluyendo `cotizado`, `revision_cliente`, `en_pausa`. No agregué `en_espera_de_pago` (queda en La Cobranza S2).
2. **Comentarios polimórficos** — Tarea XOR Proyecto con `models.CheckConstraint(condition=...)`.
3. **`rol_en_proyecto` enum** — líder / diseñador / producción / revisor.
4. **Cliente soft delete** — `activo=False`. PROTECT sobre proyectos. Manager `Cliente.activos` vs `Cliente.objects`.

## 7. CI — El Mensajero (cierre de sesión)

- Jobs verdes en `main`: `pruebas` (71 verdes con Redis service) + `lint` (ruff 0.8.4 clean) + `build` (matrix 3 apps push a GHCR) + `actualizar_digests` (login GHCR, `imagetools inspect`, reescritura de `docker-compose.prod.yml`, auto-commit por bot).
- Repo: `https://github.com/Yosoyobo/el-despacho` privado.
- Imágenes publicadas: `ghcr.io/yosoyobo/el-despacho-{gerencia,taller,recepcion}:{latest,<sha>}` + manifest digests fijados en `docker-compose.prod.yml`.

## 8. Deuda técnica / TODOs (al cierre de S1-final)

### Mediano

- **Tests de vistas de La Gerencia** (Directorio, Ajustes). Markers `@pytest.mark.gerencia` listo en pyproject, falta escribirlos. El setup actual (`tests/urls_taller.py`) está sesgado a El Taller; un `tests/urls_gerencia.py` paralelo sería trivial.
- **Despacho a La Sede (deploy SSH)** — secrets `SEDE_HOST`, `SEDE_USER`, `SEDE_SSH_KEY` aún no configurados. El job `actualizar_digests` deja el repo listo, pero `mudanza.sh` se invoca manual. En S1-deploy se activa.
- **`la-recepcion` sin Tailwind** — usa CSS inline. Cuando llegue S5 conviene agregarle `tailwind.config.js`.
- **`bootstrap_superadmin` solo en La Gerencia** — falta documentar que el `entrypoint.sh` lo corre cada arranque (es idempotente, no pisa password si el usuario existe).

### Bajo

- **Iconos PWA con letra "D"** son placeholder; reemplazar cuando haya logo de Learning Center.
- **Subdominios `direccion.*` y `oficina.*`** podrían quedar como redirects 301 → nuevos durante la transición DNS, pero como aún no hay deploy en producción no aplica.
- **`apps/.../templatetags/proyectos_extras.py`** vive bajo `los_proyectos/`. Si más adelante se usan los mismos colores en otros módulos (Cotizaciones, Facturación), conviene moverlos a una app `template_helpers/` compartida.

## 9. Recomendaciones para S1-deploy (próxima sesión)

1. **Configurar secrets de GHA** (`SEDE_HOST`, `SEDE_USER`, `SEDE_SSH_KEY`) y agregar el job `mudanza` que SSH-ea a La Sede y corre `mudanza.sh`.
2. **DNS** — antes de cualquier deploy: `gerencia.ninomeando.com`, `taller.ninomeando.com`, `recepcion.ninomeando.com` apuntando al Droplet. Sin eso Let's Encrypt no emite cert.
3. **`.env` de producción** con `DESPACHO_ENV=production`, `CADDY_HTTP_PORT=80`, `CADDY_HTTPS_PORT=443`, llaves nuevas (no las de HAL), bootstrap superadmin.
4. **Smoke test post-deploy** — pedir las 3 URLs HTTPS desde HAL y verificar `/ping` JSON y `/sign-in` 200.
5. **Backup automático** — agendar `archivo.sh` en cron de La Sede o un job GHA programado.

---

**Cierre:** S1-final entrega CRM operativo (clientes + proyectos + tareas + comentarios) con permisos por rol, eventos tipados con DLQ, Tailwind compilado, PWA andamio, healthchecks y CI con auto-pin de digests. El próximo turno empieza leyendo este archivo + `CLAUDE.md` + `git log -1`.

---

# BITÁCORA — Sesión 1 (S1-deploy)

> Cierre del **2026-05-14**, mismo día que S1a/S1-final. Esta sesión deja **El Despacho vivo en producción** con las 3 URLs HTTPS contestando 200 y el pipeline `git push → main → docker pull → up` corriendo solo en cada commit.

## 1. Acción central: REBUILD del Droplet existente

- **Droplet:** `learning-center` (ID `570849473`, IP `157.230.48.232`, nyc1, 1 vCPU / 1 GB RAM / 25 GB).
- **Operación:** `doctl compute droplet-action rebuild --image ubuntu-24-04-x64`. **17 segundos.** IP preservado, disco reinstalado, código de El Corporativo borrado.
- **DNS:** los 3 hosts (`gerencia/taller/recepcion.ninomeando.com`) seguían apuntando a `157.230.48.232` — no se tocó nada.
- **OS resultante:** Ubuntu 24.04.3 LTS / kernel 6.8.0-71-generic.

## 2. Camino del SSH key

`doctl droplet-action rebuild` no acepta `--ssh-keys`. Para inyectar la llave dedicada (`~/.ssh/el-despacho-sede`, ed25519, ID DO `56324640`) usé el flujo:

1. `doctl compute droplet-action password-reset` → DO envía email con password temporal de root.
2. Como Ubuntu 24.04 fuerza cambio de password al primer login (PAM `pam_unix`/`administrator enforced`) y SSH no-TTY rechaza el flujo, usé `expect` con `ssh -tt` para responder los 3 prompts (`Current` / `New` / `Retype`). Costó 3 intentos: los 2 primeros se quemaron porque el primer `expect` mezcló patrones (`*urrent*?assword*` también matcheaba "New") y el segundo tiró timeout esperando el cierre que nunca llegó porque PAM había soltado el shell. El 3ro fue robusto: patrones literales con anclas (`-re "(C|c)urrent password:\\s*\$"`), step de cierre tolerante a `Connection to`, EOF y shell prompt; **además dejé toda la lógica de inyección en una sola invocación bash**, sin `unset` de la NEW_PW hasta confirmar key-login.
3. Inyecté `el-despacho-sede.pub` a `/root/.ssh/authorized_keys`, validé `ssh -i` sin password, descarté la NEW_PW.

Lección para futuros operadores: si DO obliga cambio de password al primer login, **siempre** usar `expect` con patrones anclados (`\\s*\$`) y poner el inject-key + validate-key en el **mismo proceso** que tiene la NEW_PW viva.

## 3. Hardening

```
apt update && apt upgrade -y
apt install -y docker.io docker-compose-v2 git curl ufw fail2ban htop ca-certificates
systemctl enable --now docker fail2ban
ufw default deny incoming / allow outgoing
ufw allow 22/tcp 80/tcp 443/tcp
ufw --force enable
adduser despacho + groups docker,sudo + /etc/sudoers.d/despacho NOPASSWD
cp ~/.ssh/authorized_keys → /home/despacho/.ssh/
sed PermitRootLogin → no · PasswordAuthentication → no · KbdInteractive → no
sshd_config.d/*.conf patcheados (cloud-init suele re-habilitar password en drop-ins)
systemctl reload ssh
```

Validé `despacho@…` con `sudo whoami → root` y `docker ps` **antes** de deshabilitar root.

> **Nota importante de Ubuntu 24.04:** el paquete del plugin compose v2 ya **no se llama** `docker-compose-plugin` (eso era de Docker oficial / Ubuntu 22.04 universe), sino **`docker-compose-v2`**. Si copias este flujo a otro Droplet, ajusta.

## 4. Bootstrap del stack

- `/opt/el-despacho` clonado como `despacho` (chown explícito).
- `.env` de **producción** generado in-situ (todos los secretos vía `openssl rand`, **nunca pasaron por HAL ni por logs**):
  - `BOVEDA_MASTER_KEY` 64 hex
  - `DJANGO_SECRET_KEY` 64 hex
  - `POSTGRES_PASSWORD` 40 chars
  - `DESPACHO_SUPERADMIN_EMAIL=oscar@bautista.mx` (elección del usuario)
  - `DESPACHO_SUPERADMIN_PASSWORD` 28 chars
  - `CADDY_HTTP_PORT=80` / `CADDY_HTTPS_PORT=443`
  - `DESPACHO_ENV=production`
  - `*_ALLOWED_HOSTS=<host>.ninomeando.com,localhost,127.0.0.1` (el `localhost` es **obligatorio** para los healthchecks Django, ver §5).
- `docker compose pull` desde GHCR. Imágenes **públicas** (gerencia/taller/recepcion) — fine-grained PAT no soporta GHCR, así que el usuario las marcó públicas vía UI. Sigue OK porque el `.env` no vive en la imagen.

## 5. Bugs encontrados en el primer arranque (y fix)

### Bug A: `el-taller` crashea con `LookupError: No installed app with label 'admin'`

En S1b agregué `path("admin/", admin.site.urls)` a [el-taller/el_taller/urls.py](el-taller/el_taller/urls.py) pero el Django project de El Taller **no** tiene `django.contrib.admin` en INSTALLED_APPS (sí lo tiene La Gerencia). Los tests de S1b pasaron porque `tests/django_settings.py` es independiente y nunca instanció El Taller con sus URLs reales.

**Fix** (commit `730e2ba`): quitar el `path("admin/", ...)` de `el_taller/urls.py`. CI verde, digest auto-pineado por bot, pull en La Sede.

### Bug B: healthchecks rechazaron `localhost:8001/ping` con `DisallowedHost`

Mi `.env` inicial puso `GERENCIA_ALLOWED_HOSTS=gerencia.ninomeando.com` (sin `localhost,127.0.0.1` que sí estaba en `.env.example`). El healthcheck del container Docker hace `urllib.request.urlopen('http://localhost:8001/ping')` desde dentro del propio container, y Django respondía 400.

**Fix:** sed inline en el `.env` del Droplet agregando `,localhost,127.0.0.1` a los 3 hosts. `up -d --force-recreate --no-deps la-gerencia la-recepcion` → healthy en 27s.

## 6. Endpoints públicos vivos

| URL | HTTP | Cert |
|---|---|---|
| https://gerencia.ninomeando.com/ping | 200 `{"ok": true, "app": "la-gerencia"}` | Let's Encrypt válido |
| https://taller.ninomeando.com/ping | 200 `{"ok": true, "app": "el-taller"}` | Let's Encrypt válido |
| https://recepcion.ninomeando.com/ping | 200 `{"ok": true, "app": "la-recepcion", "estado": "stub"}` | Let's Encrypt válido |
| https://gerencia.ninomeando.com/sign-in | 200 | — |
| https://taller.ninomeando.com/sign-in | 200 | — |

Caddy negoció los 3 certs en ~3s (HTTP-01 challenge, retries por todas las regiones de LE simultáneas — comportamiento normal).

## 7. CI/CD: `🚚 La Mudanza`

- Secrets configurados con `gh secret set` en `Yosoyobo/el-despacho`:
  - `SEDE_HOST=157.230.48.232`
  - `SEDE_USER=despacho`
  - `SEDE_SSH_KEY` = contenido de `~/.ssh/el-despacho-sede` (privada ed25519)
- Job nuevo en `.github/workflows/el-mensajero.yml`: `mudanza` corre tras `actualizar_digests`. Usa `appleboy/ssh-action@v1.2.0`. Ejecuta `git pull --ff-only && docker compose pull && up -d` + smoke `/ping` interno.
- **Primer auto-deploy verde end-to-end en 1m24s** (run `25892349320`). Confirmado con `curl https://gerencia/...` post-mudanza.

Pipeline completo ahora:
```
git push main
  → pruebas (71 tests)
  → ruff
  → build matrix (gerencia/taller/recepcion → GHCR)
  → actualizar_digests (sha256 → docker-compose.prod.yml, bot commit)
  → 🚚 mudanza (SSH a La Sede → pull + up)
```

## 8. Backup

- Cron de `despacho`: `0 3 * * 0 cd /opt/el-despacho && ./infra/scripts/archivo.sh >> /var/log/archivo.log 2>&1` (domingo 03:00).
- Test manual ya generó `backups/db-20260514-235259.sql.gz` (5.5K) y `credenciales-20260514-235259.tar.gz`.

## 9. Deuda al cierre de S1-deploy

### Crítico para los próximos sprints (no para esta sesión)

- **Droplet de 1 GB RAM es ajustado.** Postgres + 4 procesos gunicorn + Redis + Caddy + worker = ~70-80% mem en idle. Con 2-3 usuarios simultáneos funcionará; bajo carga real (10+) OOM es plausible. Resize a `s-1vcpu-2gb` ($12/mes, downtime ~5 min) cuando aprueben.
- **Backups en disco local.** `./backups/` vive en el mismo disco del Droplet — si el Droplet muere, se pierden. S2 sería un buen momento para rclone/borg → DO Spaces.
- **Job `mudanza` sin rollback automático.** Si el deploy nuevo levanta unhealthy, `up -d` deja containers en bad state. La salida actual es manual: SSH al Droplet y revisar logs. Considerar `healthcheck` post-deploy en el job que haga rollback si falla.

### Bajo

- **`docker-compose-plugin` → `docker-compose-v2`** en el README cuando documentemos deploy desde cero.
- **`tests/conftest.py`** parcha emitir para tests Django (Redis fixture), pero **agregamos `apps.el_directorio.views` y `apps.los_ajustes.views`** a la lista de módulos a parchar — son de La Gerencia, no de El Taller. El parche `try/except ImportError` los salta silenciosamente, pero el día que escribamos tests de Gerencia hay que recordarlo.
- **`SUPERADMIN_PASSWORD` solo vive en `/opt/el-despacho/.env`** (chmod 600, dueño `despacho`). El usuario debe cambiarlo en primer login si quiere algo memorable.

## 10. Recomendaciones para S2

1. **Antes de Stripe/MercadoPago en sandbox:** crear las credenciales en Los Ajustes (la-gerencia/ajustes/) — La Bóveda ya las cifra. Probar el flujo de webhooks vía n8n requiere primero levantar n8n en alguna parte (¿Droplet aparte, $4/mes? ¿VPN Tailscale al laptop?).
2. **PDF de Cotizaciones vía Google Docs templates:** el usuario debe crear un Doc plantilla con placeholders `{{cliente}}`, `{{lineas}}`, etc. y compartirlo con un Service Account. Pedir el ID del Doc + el JSON del Service Account ANTES de empezar a codear.
3. **Resize del Droplet a 2GB** justo antes de que Stripe webhooks empiecen a llegar de verdad — un timeout de webhook por OOM se convierte en pago no registrado.
4. **Monitor de uptime externo** (UptimeRobot gratis): si Caddy o gunicorn se caen, el usuario quiere saberlo antes que el cliente.

---

**Cierre:** S1-deploy entrega El Despacho **vivo en producción** con HTTPS válido, auto-deploy de `git push` a Droplet en ~1.5 min, backup semanal, root SSH cerrado y password auth deshabilitado. El próximo turno (S2) empieza leyendo este archivo + `CLAUDE.md` + `git log -1`.
