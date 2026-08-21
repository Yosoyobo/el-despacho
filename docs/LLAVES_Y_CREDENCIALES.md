# Llaves y credenciales — cómo se genera cada una

> Inventario completo de El Despacho: qué llave necesita cada módulo, de dónde
> sale, dónde se pega y cómo se comprueba. Escrito para el super_admin.

---

## Las dos casas de una credencial

Hay **exactamente dos lugares** donde puede vivir un secreto, y no es negociable
(regla §4 #3 de CLAUDE.md):

| Casa | Qué vive ahí | Por qué |
|---|---|---|
| **El `.env` del Droplet** | Sólo los secretos de **arranque**: `BOVEDA_MASTER_KEY`, `DJANGO_SECRET_KEY`, la conexión a Postgres/Redis, y las llaves de El Resguardo | La Bóveda no puede descifrarse a sí misma, y `archivo.sh` es bash en el host: no tiene forma de abrir La Bóveda, que vive dentro del contenedor |
| **La Bóveda** (Gerencia → Ajustes) | **Todo lo demás**: Google, correo, los 6 Chalanes, n8n, notificaciones, DigitalOcean | Cifrado AES-256-GCM, con auditoría de quién la cambió y cuándo, y sin necesidad de entrar por SSH ni reiniciar nada |

La consecuencia práctica: **cambiar una llave de La Bóveda no requiere deploy ni
reinicio.** Se pega en la GUI y toma efecto en la siguiente petición. Cambiar una
del `.env` sí requiere entrar al Droplet y levantar los contenedores.

---

## Parte 1 · Las que se generan aquí (no las da nadie)

### `BOVEDA_MASTER_KEY` y `DJANGO_SECRET_KEY` — `.env`

Son 32 bytes al azar, en hexadecimal. Se generan con Python, sin instalar nada:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Corre el comando **dos veces** — una para cada variable, nunca la misma en las
dos. Van al `.env` del Droplet:

```
BOVEDA_MASTER_KEY=<los 64 caracteres del primer comando>
DJANGO_SECRET_KEY=<los 64 caracteres del segundo>
```

**Lo que hay que entender de `BOVEDA_MASTER_KEY`:** es la llave con la que se
cifró **todo** lo que hay en La Bóveda. Si se pierde, no hay forma de recuperar
ninguna credencial guardada — hay que volver a pegarlas todas a mano. Si cambia,
lo ya guardado deja de descifrarse. La app se niega a arrancar si falta o si no
son 64 caracteres hexadecimales (regla §4 #2): es a propósito, para que el error
salga al arrancar y no a medio día con las credenciales en silencio.

Va en el respaldo de credenciales que hace `archivo.sh` cada 3 días, y ése es el
que hay que poder recuperar.

**Rotarla no es un botón.** Existe el helper `lib.boveda.rotar()` que re-cifra un
valor bajo una llave nueva, pero **no hay comando de management que recorra toda
la tabla**. Rotar hoy significa escribir un script que lea cada `Credencial` con
la llave vieja y la reescriba con la nueva, o pegar todo de nuevo a mano. Si
llega a hacer falta, mejor pedir el comando que improvisar en producción.

### Notificaciones al celular (VAPID) — sí hay comando

Las llaves de Web Push **las genera El Despacho**, no Google ni nadie. Hay un
comando que las crea y las guarda en La Bóveda de una vez:

```bash
cd /opt/el-despacho && docker compose \
  -f docker-compose.yml -f docker-compose.prod.yml exec -T la-gerencia \
  python manage.py interfono_generar_vapid
```

Llena tres slots: `vapid_public_key`, `vapid_private_key` y, si está vacío,
`vapid_email` con `mailto:soporte@learningcenter.mx` (el correo de contacto que
va en la cabecera; los servicios de push lo usan para avisar si algo va mal).

**El comando se niega a correr si ya hay llaves**, a propósito: regenerarlas
**invalida TODAS las suscripciones existentes** y todo el equipo tendría que
volver a dar permiso de notificaciones en su teléfono. Para regenerar de verdad
hay que borrarlas primero a mano desde Los Ajustes.

### El secreto de n8n — lo eliges tú

`n8n_webhook_secret` **no lo da n8n**: es el secreto compartido con el que El
Portavoz firma cada evento que sale (HMAC-SHA256), para que n8n pueda comprobar
que viene de nosotros. Lo generas igual que las de arriba:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Y lo pegas en **dos lados**: en Ajustes → Credenciales → *n8n — Webhook Secret*,
y en el workflow de n8n como el secreto que valida la firma. Si no coinciden,
n8n rechaza los eventos y se quedan encolados en Redis (no se pierden, pero no
llegan).

`n8n_webhook_url` es la dirección del webhook que te da n8n al crear el
workflow, y `n8n_health_url` es su endpoint de salud (algo como
`http://hal.tailedd04d.ts.net:5678/healthz`), que El Site pinguea.

---

## Parte 2 · Las que da un proveedor

### Google SSO (entrar con Google)

Tres slots: `google_oauth_client_id`, `google_oauth_client_secret` y
`google_oauth_project_id` (este último opcional, sólo para logs).

Se sacan de Google Cloud Console creando un **ID de cliente de OAuth → Aplicación
web**. El paso a paso completo, con los URI de redirección exactos que hay que
registrar y los dos modos de falla del login, está en
**[MIGRACION_WORKSPACE_LEARNINGCENTER.md](MIGRACION_WORKSPACE_LEARNINGCENTER.md)**.

Es la única credencial con **prueba de verdad**: el botón «Probar» del slot hace
un round-trip real contra Google. «Credenciales válidas» = listo.

### Google Drive (PDFs, fotos, adjuntos)

Es un flujo aparte, con asistente propio en `/ajustes/google-drive/`, porque no
es una llave que se pega: es un **refresh token** que se obtiene dando permiso
con una cuenta de Google. Paso a paso en
**[SETUP_GOOGLE_DRIVE.md](SETUP_GOOGLE_DRIVE.md)**.

> ⚠️ Drive puede usar el cliente OAuth **del login** si no tiene uno propio. Antes
> de reemplazar el cliente del SSO, lee la advertencia del runbook: cambiarlo
> sin aislar Drive le quita a la app el acceso a todo lo ya subido, **en
> silencio**.

### Correo saliente

**No hay llave que pegar, y SMTP no sirve en producción.** DigitalOcean tiene
bloqueada la salida SMTP del Droplet: los puertos 25, 465, 587 y 2525 se caen por
timeout mientras el 443 va perfecto (medido desde el host y desde el contenedor).
Así que `smtp.gmail.com` es inalcanzable, y `smtp-relay.gmail.com` lo sería igual.

El canal que entrega es la **API de Gmail**, por HTTPS/443. No se pega ninguna
contraseña: se **autoriza una vez** con la cuenta del Workspace desde
Gerencia → Ajustes → **El Cartero** → «Autorizar Gmail», y el permiso queda
cifrado en La Bóveda (`gmail_api_oauth_refresh_token`). Lo único que se escribe a
mano es el **correo remitente** (`gmail_api_remitente`), que debe ser la cuenta
autorizada o un alias suyo dado de alta en «Enviar como».

El scope es `gmail.send` — sólo enviar, nunca leer. Google lo clasifica como
**sensible**: un cliente OAuth «Interno» no necesita verificación, uno «Externo»
sí. Paso a paso y el detalle de esa decisión en el
**[runbook](MIGRACION_WORKSPACE_LEARNINGCENTER.md#paso-4--el-correo-por-la-api-de-gmail-no-por-smtp)**.

Ojo con el acoplamiento: usa **el cliente OAuth del login**, así que reemplazar
ese cliente invalida también el correo (no sólo Drive) y hay que volver a
autorizar.

Los slots `smtp_*` se conservan para desarrollo local, donde sí hay salida SMTP.
Con Google Workspace la contraseña ahí sería una **contraseña de aplicación de 16
caracteres**, no la del correo.

### Los seis Chalanes (IA)

Cada uno es una API key que se saca de la consola del proveedor y se pega en
Ajustes → Credenciales. Todos son opcionales e independientes: **si a uno le
falta la llave, El Reemplazo lo salta** y sigue con el siguiente de la cadena.

| Chalán | Slot | Dónde se saca la llave | Modelo por default |
|---|---|---|---|
| **Claudio** (Anthropic) | `chalan_anthropic_api_key` | console.anthropic.com → API Keys (`sk-ant-…`) | `claude-haiku-4-5` |
| **GPT** (OpenAI) | `chalan_openai_api_key` | platform.openai.com → API keys (`sk-…`) | `gpt-4o-mini` |
| **Chino** (Deepseek) | `chalan_deepseek_api_key` | platform.deepseek.com → API keys | `deepseek-chat` |
| **Gemini** (Google) | `chalan_gemini_api_key` | aistudio.google.com → Get API key | `gemini-2.5-flash` |
| **MiMo** (Xiaomi) | `chalan_mimo_api_key` | consola de Xiaomi MiMo | `mimo-v2.5-pro` |
| **Grok** (xAI) | `chalan_grok_api_key` | console.x.ai → API Keys (`xai-…`) | `grok-4.5` |

Ojo con Gemini: la llave sale de **AI Studio**, que es un producto distinto del
Cloud Console del SSO aunque los dos sean de Google. No se reutiliza el cliente
OAuth.

**Dónde se comprueban:** no en Los Ajustes, sino en **Gerencia → Chalanes**
(`/chalanes/`). Ahí cada Chalán tiene su tarjeta con botón **«Probar conexión»**,
que hace una llamada real de 1 token (cuesta menos de un centavo) y guarda el
resultado. Esa misma pantalla muestra el gasto de los últimos 30 días por
proveedor y permite consultar saldo donde el proveedor lo expone (hoy sólo
Deepseek).

**Al guardar la llave, el proveedor entra solo a la cadena de fallback.** Hay un
signal que lo agrega con la siguiente prioridad libre, así que no hay que
acordarse de nada.

### DigitalOcean — API token

`do_api_token` (`dop_v1_…`). Se genera en la consola de DigitalOcean → API →
Generate New Token. **Con permiso de sólo lectura alcanza**: El Site nada más lee
las especificaciones y el consumo de red del Droplet. Si falta, El Site degrada
con gracia y muestra ese cuadrante vacío.

### El Resguardo — llaves del Space

`DO_SPACES_KEY` / `DO_SPACES_SECRET`. **Estas van al `.env`, no a La Bóveda**,
porque el que las usa es `archivo.sh`, que es bash corriendo en el host y no
puede abrir La Bóveda. Paso a paso en **[SETUP_RESGUARDO.md](SETUP_RESGUARDO.md)**.
Si están vacías, el respaldo offsite queda dormido y `archivo.sh` lo salta sin
fallar.

### El Celador — token del monitor

`celador_token`. **Éste no se genera aquí: lo entrega el taller** que opera el
monitor, y es el mismo para todas las máquinas. Trátalo como credencial.

Sin token, `/salud` contesta sólo la cara pública (el estado de cada pieza); con
él, agrega el desglose de gasto de IA y de uso. **Vacío significa que nadie pasa**
— se cierra, no se abre. Se puede pegar en Los Ajustes o, como respaldo del
contrato del taller, en `CELADOR_TOKEN` del `.env`. Detalle en
**[MONITOR_SALUD.md](MONITOR_SALUD.md)**.

### El Envoltorio — keystore de Android

No es una credencial del sistema sino la **firma de la app** de El Taller para
Android. Se genera con `keytool` y **nunca va al repo**: se guarda en HAL. Si se
pierde, hay que generar otra y actualizar el fingerprint en el `Caddyfile`.
Instrucciones en **[../envoltorio/README.md](../envoltorio/README.md)**.

---

## Parte 3 · Lo que parece llave y no lo es

- **`rfc_empresa`** — es un dato, no un secreto: el RFC de Learning Center, que
  se usa en el export fiscal XML (Anexo 24). Vive en La Bóveda por comodidad.
  Confírmalo con el contador antes de presentar nada al SAT.

- **Stripe y MercadoPago** — los cuatro slots (`stripe_secret_key`,
  `stripe_webhook_secret`, `mercadopago_access_token`,
  `mercadopago_webhook_secret`) **están declarados pero ningún código los lee
  todavía**: La Caja no está implementada. Pegarlos hoy no habilita nada. Se
  dejaron listos para cuando entre ese sprint.

- **`anthropic_api_key` y `openai_api_key`** — slots **legacy**, de antes de que
  existieran Los Chalanes. Los reemplazan `chalan_anthropic_api_key` y
  `chalan_openai_api_key`. Se pueden borrar desde la UI una vez confirmado que
  los nuevos funcionan.

---

## Parte 4 · Cómo comprobar que quedó bien

**El botón «Probar» de Los Ajustes es un stub.** Sólo confirma que el valor se
puede descifrar y te dice su longitud — **no pega a la API del proveedor**. Sirve
para descartar que se pegó basura o que se guardó cortado, nada más.

Las pruebas de verdad son tres, y están en otro lado:

| Qué | Dónde | Qué hace |
|---|---|---|
| **Google OAuth** | Ajustes → botón «Probar» del slot | Round-trip real contra Google |
| **Cada Chalán** | Gerencia → Chalanes → «Probar conexión» | Llamada real de 1 token, guarda el resultado |
| **Correo (Gmail)** | Ajustes → El Cartero → «Probar conexión» | Comprueba el permiso sin mandar nada. Un **403** al leer el perfil es ÉXITO: el scope es sólo-enviar |
| **Correo (envío)** | Ajustes → El Cartero → «Probar envío» | Manda un correo de prueba de verdad |

Para el resto, la comprobación es usar la función: sube una foto de producto para
Drive, mira el cuadrante del Droplet en El Site para el token de DigitalOcean,
manda una notificación de prueba para VAPID.

**El Site (`/site/`) es el tablero de todo esto.** Tiene una tabla de
integraciones externas con el estado de cada plataforma y un botón «Probar ahora»
por fila, y un cron diario a las 3:30 que las revisa solo y emite
`site.integracion_fallo` cuando algo se cae.

---

## Parte 5 · Rotar y revocar

El orden importa: **primero pega la nueva, después revoca la vieja.** Al
contrario deja una ventana con el sistema sin credencial.

- **Llaves de La Bóveda** (Google, Chalanes, DigitalOcean, SMTP, n8n): se pegan
  encima en la GUI, toman efecto de inmediato, sin deploy. Después revoca la
  anterior en la consola del proveedor.
- **La contraseña SMTP en blanco NO borra la guardada.** Para quitarla hay que
  marcar explícitamente «Borrar contraseña guardada».
- **VAPID**: rotar invalida todas las suscripciones. Todo el equipo tiene que
  volver a autorizar notificaciones. No se rota sin motivo.
- **Refresh token de Drive**: se revoca desde la cuenta de Google
  (Seguridad → Acceso de terceros) o desconectando desde el asistente. Ojo con
  la advertencia de arriba antes de reconectar con otra cuenta.
- **`BOVEDA_MASTER_KEY`**: no hay comando. Ver la advertencia de la Parte 1.
- **Cualquier cosa del `.env`**: requiere entrar al Droplet y levantar los
  contenedores de nuevo.
