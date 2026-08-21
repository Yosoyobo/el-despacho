# Migración de credenciales al dominio y Workspace de learningcenter.mx

> Guía operativa. **Las credenciales NO viven en el repo** (regla §4 #3 de
> CLAUDE.md): se pegan en la GUI de La Gerencia y quedan cifradas en La Bóveda.
> Este documento dice qué pegar, dónde, en qué orden y qué se rompe si el orden
> se invierte.

---

## Resumen: qué cambia y qué no

| Pieza | ¿Hay credencial? | Dónde se cambia |
|---|---|---|
| **Google SSO** | Sí — `google_oauth_client_id` / `_secret` / `_project_id` | Gerencia → Ajustes (`/ajustes/`) |
| **Correo** | Sí — consentimiento OAuth con scope `gmail.send` | Gerencia → Ajustes → El Cartero (`/ajustes/cartero/`) |
| **SMTP** | Los 6 slots `smtp_*` siguen ahí, pero **no entregan en producción** | ídem — ver Paso 4 |
| **Mapas** | **No existe ninguna** | — nada que hacer |
| **Google Drive** | Sí, pero **fuera del alcance de este cambio** | ver la advertencia de abajo |

**Los mapas ya son gratis y sin llave.** Lo embebido es OpenStreetMap con
Leaflet (regla «gratis o abortamos») y lo de Google Maps son sólo enlaces
profundos del tipo `google.com/maps/search/?api=1&query=lat,lng`, que no llevan
API key. No hay credencial de mapas que migrar. Cambiar a la API de Google Maps
sería un producto de paga y necesitaría autorización explícita de Oscar.

---

## ⚠️ Antes de tocar el SSO: leer esto sobre Drive

Drive **no tiene cliente OAuth propio** por default: cae al del login
([lib/google_drive.py:123-124](../lib/google_drive.py#L123-L124)).

```python
cid = _credencial("google_drive_oauth_client_id") or _credencial("google_oauth_client_id")
sec = _credencial("google_drive_oauth_client_secret") or _credencial("google_oauth_client_secret")
```

El scope es `drive.file`, que sólo da acceso a los archivos que la app creó
**con ese cliente y esa cuenta**. Consecuencia: si se reemplaza el cliente del
SSO y Drive sigue cayendo a él, Drive pierde acceso a todo lo ya subido —
**PDFs de cotizaciones y facturas, XML de CFDI, fotos de producto, adjuntos de
Mensajes y Buzón, avatares, comprobantes de egreso**. Y degrada en silencio
(fallback gracioso), así que no sale un error: sale un hueco donde estaba la
foto y un PDF que no se genera.

**Cómo aislarlo (2 minutos, sólo GUI):** antes de reemplazar el cliente del
SSO, pega el cliente OAuth **actual** en los slots dedicados de Drive
(`google_drive_oauth_client_id` / `_secret`) desde el asistente
`/ajustes/google-drive/`. El código los prefiere sobre los del login, así que
Drive se queda anclado a su cliente de siempre y el SSO puede migrar sin
efectos colaterales. El asistente muestra qué `client_id` está usando hoy.

> Oscar decidió **no tocar Drive en este cambio**. Queda constancia: mientras
> Drive no esté aislado, cambiar el cliente del SSO lo tumba.

---

## Paso 1 — Cliente OAuth en Google Cloud Console

1. Crea (o elige) el proyecto de Cloud dentro de la organización de
   **learningcenter.mx**.
2. **Pantalla de consentimiento OAuth.** Los scopes que usa el login son
   `openid`, `email`, `profile` — **no son sensibles**, así que no hace falta
   verificación de Google en ninguno de los dos modos:
   - **Interno**: sólo entran cuentas `@learningcenter.mx`. Elígelo únicamente
     si **todos** los que usan «Continuar con Google» ya tienen cuenta del
     Workspace. Ojo: el super_admin del Directorio es hoy `oscar@bautista.mx`,
     y con «Interno» esa cuenta **no podría** usar SSO (el login con contraseña
     sigue funcionando).
   - **Externo**: acepta cualquier cuenta de Google que además exista en El
     Directorio. Es lo más tolerante durante la transición.
3. **Credenciales → ID de cliente de OAuth → Aplicación web.** Registra estos
   **URI de redirección autorizados** (el sistema los arma solo desde el host,
   por eso los 3 hosts comparten un solo cliente):

   ```
   https://taller.learningcenter.mx/auth/google/callback
   https://gerencia.learningcenter.mx/auth/google/callback
   https://recepcion.learningcenter.mx/auth/google/callback
   ```

   El de Recepción no se usa hasta S5, pero registrarlo desde ahora no cuesta
   nada y evita volver a la consola. Para desarrollo en HAL agrega también
   `http://localhost:8000/auth/google/callback` (Taller) y `:8001` (Gerencia).

   **Orígenes de JavaScript autorizados: no hacen falta.** El flujo es
   server-side (redirección + intercambio de `code` en el backend), no hay JS
   pidiendo tokens.

4. **Pantalla de consentimiento → App domain.** Estos son los valores, y los tres
   enlaces responden **200 sin sesión** (importa: Google los rastrea y los
   muestra al usuario, así que detrás del login no sirven):

   | Campo | Valor |
   |---|---|
   | Application home page | `https://taller.learningcenter.mx/acerca/` |
   | Application privacy policy link | `https://taller.learningcenter.mx/legal/privacidad` |
   | Application terms of service link | `https://taller.learningcenter.mx/legal/terminos` |
   | Authorized domains | `learningcenter.mx` (una sola entrada) |

   **Authorized domains pide el dominio raíz**, no subdominios: con
   `learningcenter.mx` quedan cubiertos los tres hosts. Registrar
   `taller.learningcenter.mx` sería rechazado.

   **Ojo con la home page — aquí ya se falló una vez.** Apuntarla al sitio de
   marketing (`https://learningcenter.mx`) hace que la verificación se rechace
   con *«Your home page does not explain the purpose of your app»*: ese sitio
   describe los servicios de Learning Center a sus clientes, no lo que hace
   este sistema ni por qué pide entrar con Google. Por eso existe
   **`/acerca/`**, una página pública dentro de El Despacho que sí lo explica —
   qué es la app, quién la usa, que no hay registro abierto, y qué permisos de
   Google pide (incluido que `drive.file` sólo alcanza los archivos que la
   propia app creó). Tampoco sirve apuntarla a la raíz de El Taller: devuelve
   302 a `/sign-in`, y Google rechaza páginas de login como home page.

   Si la verificación vuelve a objetar la home page, se edita
   `templates/legal/_acerca_body.html` (**en las dos apps**, regla §18) — no se
   cambia el campo en la consola.

---

## Paso 2 — Pegar las credenciales del SSO

En **La Gerencia → Ajustes** (`/ajustes/`, requiere `ajustes.acceder`):

| Slot | Qué pegar |
|---|---|
| `google_oauth_client_id` | El Client ID del cliente nuevo (`...apps.googleusercontent.com`) |
| `google_oauth_client_secret` | El Client Secret |
| `google_oauth_project_id` | El ID del proyecto de Cloud. Opcional, sólo para logs |

Guarda y usa el botón **«Probar»** del slot de Google OAuth. Lee así el
resultado ([lib/google_oauth.py:188-227](../lib/google_oauth.py#L188-L227)):

- **«Credenciales válidas»** → listo. Google rechazó un `code` de mentiras, que
  es exactamente lo que se espera.
- **«client_id o client_secret incorrectos»** → algo se pegó mal.

Si el botón «Continuar con Google» desaparece del login, es que falta uno de
los dos slots: el sistema esconde el botón a propósito para no dejarlo roto.

---

## Paso 3 — Verificar el login y los dos modos de falla

El SSO **no crea cuentas** (regla §4 #7): vincula por correo contra El
Directorio. Hay dos formas de quedarse fuera, y conviene saber cuál es cuál.

**El `sub` de Google es estable por cuenta de Google, no por cliente OAuth.**
Cambiar sólo el cliente **no** rompe los vínculos existentes. Lo que rompe es
que las **personas** cambien de cuenta de Google.

1. **«Esta cuenta de Google no está registrada».** El correo del perfil de
   Google no existe como usuario activo en El Directorio. Pasa cuando alguien
   pasa de `@gameplanet.com` o `@bautista.mx` a `@learningcenter.mx`: hay que
   **actualizar primero su correo en El Directorio** (`/directorio/`), y después
   que entre.

2. **«Ya vinculado a otra cuenta».** El usuario ya tiene un `google_sub` de su
   cuenta de Google anterior y ahora entra con otra distinta. El sistema **no
   sobreescribe** el vínculo a propósito
   ([auth_google/servicios.py:54-56](../auth_google/servicios.py#L54-L56)), y
   **no hay pantalla para desvincular**. Se resuelve en La Sede:

   ```bash
   cd /opt/el-despacho && docker compose \
     -f docker-compose.yml -f docker-compose.prod.yml exec -T la-gerencia \
     python manage.py shell -c "
   from cuentas.models.usuario import Usuario
   u = Usuario.objects.get(email='persona@learningcenter.mx')
   u.google_sub = None; u.google_email = ''; u.save()
   print('desvinculada:', u.email)"
   ```

   En el siguiente intento vuelve a vincular sola, ya con la cuenta nueva.

**Recomendación de orden:** actualiza los correos en El Directorio **antes** de
cambiar el cliente, y deja al menos un super_admin con contraseña funcionando
por si el SSO queda a medias.

---

## Paso 4 — El correo: por la API de Gmail, NO por SMTP

> ⚠️ **SMTP no funciona en La Sede y no es cosa de credenciales.** DigitalOcean
> tiene bloqueada la salida SMTP del Droplet. Medido desde el host y desde el
> contenedor:
>
> | Puerto | Resultado |
> |---|---|
> | 25, 465, 587, 2525 | **timeout** (los paquetes se descartan) |
> | 443 | abierto |
>
> Por eso `smtp.gmail.com` es inalcanzable — y `smtp-relay.gmail.com` lo sería
> igual: no es el sabor de SMTP, es que **este Droplet no puede hablar SMTP con
> nadie**. La API de Gmail va por HTTPS/443 y esquiva el bloqueo sin pedirle
> nada a DigitalOcean.
>
> Un detalle que confunde el diagnóstico: el error que reporta la app es
> `[Errno 101] Network is unreachable`, no un timeout. Es porque el DNS de
> `smtp.gmail.com` devuelve IPv6 primero, el contenedor no tiene ruta IPv6 y
> falla al instante, tapando el timeout real de IPv4.

### 4.1 Por qué OAuth y no una cuenta de servicio

Lo natural sería una cuenta de servicio con delegación de dominio — no tocaría
la pantalla de consentimiento y por lo tanto no afectaría la verificación del
SSO. **No se puede:** la organización tiene activada
`iam.disableServiceAccountKeyCreation`, que bloquea la creación de llaves JSON
(la misma razón por la que Drive usa OAuth, ver
[SETUP_GOOGLE_DRIVE.md](SETUP_GOOGLE_DRIVE.md)).

Así que el camino es el mismo patrón de Drive: consentimiento una vez, refresh
token cifrado en La Bóveda, y canje por un access token de corta vida en cada
envío.

**El scope es `gmail.send`** — sólo enviar; no puede leer, buscar ni borrar
correo. Ojo: Google lo clasifica como **sensible**, así que:

- Cliente OAuth **«Interno»** (sólo cuentas del Workspace) → **no necesita
  verificación**; lo autoriza el admin de la organización.
- Cliente OAuth **«Externo»** → sí necesita verificación para ese scope. Si el
  cliente ya está en revisión por otra cosa, esto la complica.

Si todos los que usan el sistema tienen cuenta `@learningcenter.mx`, pasar el
cliente a «Interno» resuelve de un golpe la verificación **y** este scope. El
costo es que `oscar@bautista.mx` no podría usar «Continuar con Google» (el login
con contraseña sigue igual).

### 4.2 En Google Cloud Console

1. Habilita la **Gmail API** en el proyecto.
2. Agrega el URI de regreso del asistente al cliente OAuth:

   ```
   https://gerencia.learningcenter.mx/ajustes/cartero/gmail/callback
   ```

   (El panel de El Cartero lo muestra en pantalla para copiarlo.)

### 4.3 En La Gerencia → Ajustes → El Cartero (`/ajustes/cartero/`)

1. **Canal activo → «Gmail API (Google Workspace)»**.
2. **Correo remitente**: la dirección desde la que sale el correo, ej.
   `hola@learningcenter.mx`. Tiene que ser la cuenta que vas a autorizar **o un
   alias suyo** dado de alta en Gmail → Configuración → Cuentas → «Enviar como»;
   si no, Gmail lo reescribe en silencio.
3. **Guardar**.
4. **«Autorizar Gmail»** → te manda a Google. Autoriza con la cuenta desde la
   que quieres que salga el correo.
5. **«Probar conexión»** comprueba el permiso sin mandar nada. Un 403 leyendo el
   perfil **es lo correcto**: significa que el token sirve y que el scope es el
   mínimo (sólo enviar).
6. **«Probar envío»** manda un correo de verdad.

No se pega ninguna contraseña: no hay contraseña de aplicación ni llave. El
permiso queda cifrado en La Bóveda.

### 4.4 Acoplamiento con el SSO

Este canal usa **el cliente OAuth del login**, así que reemplazar ese cliente
**invalida también el correo**, no sólo Drive. Después de cambiarlo hay que
volver a autorizar desde el asistente. Es la misma trampa de la advertencia de
Drive, con un consumidor más.

### 4.5 Los slots SMTP se quedan

No se borran: sirven para desarrollo local, donde sí hay salida SMTP. El panel
marca el canal SMTP con la advertencia de que en producción no entrega.

## Lo que este cambio NO tocó

- **`DESPACHO_SUPERADMIN_EMAIL` en el `.env`** sigue en `oscar@bautista.mx`, a
  propósito. `bootstrap_superadmin` busca **por correo**
  ([cuentas/management/commands/bootstrap_superadmin.py:22](../cuentas/management/commands/bootstrap_superadmin.py#L22)),
  así que cambiarlo **no renombra** la cuenta: crearía un **segundo**
  super_admin en el siguiente arranque. Si Oscar cambia de correo, se edita su
  usuario en El Directorio y después se actualiza la variable.
- **Google Drive** — ver la advertencia de arriba.
- **Los correos de prueba de la suite** siguen usando `@bautista.mx`: son datos
  de mentiras, no configuración.

## Lo que sí cambió en el código

- Aviso de privacidad de El Taller y La Gerencia: el correo de derechos ARCO
  pasó a `soporte@learningcenter.mx` (es texto visible al usuario final).
- Contacto VAPID del Interfón (respaldo en `lib/interfono.py` y la semilla del
  comando `interfono_generar_vapid`) y el ejemplo del slot en Los Ajustes.
- Correo de ACME del `Caddyfile` (el que usa Let's Encrypt para avisos de
  expiración). Caddy registra una cuenta ACME nueva la próxima vez que emita;
  los certificados ya emitidos no se tocan.
- Los textos de ayuda de los 6 slots SMTP, ahora escritos para este caso
  concreto (Workspace + contraseña de aplicación) en lugar de genéricos.
