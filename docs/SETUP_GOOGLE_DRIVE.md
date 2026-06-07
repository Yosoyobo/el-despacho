# Setup Google Drive para El Despacho

> **¿Eres el administrador no técnico?** No necesitas este documento.
> Entra a La Gerencia → **Ajustes → Conectar Google Drive** y sigue el
> asistente guiado. Hace todo esto con botones y un "Probar conexión" que te
> avisa si quedó bien. Este archivo es la referencia técnica equivalente.

> **Estado:** conexión activa vía OAuth sin clave (sprint S-Drive-Setup).
> Pendiente cablear la subida de adjuntos en S2b.1b.

## Por qué OAuth con refresh token y NO una cuenta de servicio

La organización de Google Workspace de Learning Center tiene activada la
política `iam.disableServiceAccountKeyCreation`, que **bloquea la creación de
archivos de clave (JSON) de cuentas de servicio** — por seguridad, para evitar
claves filtradas. Por eso NO usamos una service account.

En su lugar usamos **OAuth 2.0 con token de actualización (refresh token)**:

- Reutilizamos el **mismo cliente OAuth del login con Google** (slots
  `google_oauth_client_id` / `google_oauth_client_secret` en La Bóveda).
- El admin da consentimiento **una vez** con la cuenta corporativa.
- Guardamos el `refresh_token` cifrado en La Bóveda
  (`google_drive_oauth_refresh_token`).
- El wrapper `lib/google_drive.py` canjea ese refresh token por un access
  token de corta vida cada vez que llama a la API de Drive.

**Alcance (scope):** `https://www.googleapis.com/auth/drive.file` — el sistema
solo ve y toca los archivos/carpetas que **él mismo crea**. No es un scope
sensible, así que **no requiere verificación de Google**. El sistema crea su
propia carpeta raíz `El Despacho - Adjuntos` en la "Mi unidad" de la cuenta que
dio consentimiento, y guarda su ID en `google_drive_carpeta_raiz_id`.

---

## Paso 1 · Habilitar la Drive API

1. Entra a https://console.cloud.google.com/apis/library/drive.googleapis.com
   con la cuenta corporativa.
2. Selecciona el proyecto de Google del sistema (el mismo del login con Google).
3. **Habilitar**. Espera a que diga "API habilitada".

## Paso 2 · Registrar el redirect URI del callback

El flujo OAuth necesita una "dirección de regreso" registrada en el cliente
OAuth. Es la misma por cada host (gerencia):

```
https://gerencia.learningcenter.mx/ajustes/google-drive/oauth/callback
```

(En HAL local: `http://localhost:PUERTO/ajustes/google-drive/oauth/callback`.)

1. Entra a https://console.cloud.google.com/apis/credentials
2. Abre el cliente OAuth 2.0 del sistema (el del login con Google).
3. En **"URIs de redireccionamiento autorizados"** → **+ Agregar URI** → pega
   la dirección de arriba → **Guardar**. Puede tardar unos minutos en activar.

> El asistente en `/ajustes/google-drive/` muestra la URI exacta del host
> actual para copiar — úsala en vez de escribirla a mano.

## Paso 3 · (Recomendado) Pantalla de consentimiento Interna

Si la pantalla de consentimiento OAuth está marcada como **Interna** (solo
usuarios de la organización), cualquier empleado del Workspace puede dar
consentimiento sin que Google pida verificación ni listarlo como "usuario de
prueba". Revísalo en https://console.cloud.google.com/apis/credentials/consent

## Paso 4 · Conectar la cuenta

En La Gerencia, como `super_admin`:

1. Entra a **Ajustes → Conectar Google Drive** (`/ajustes/google-drive/`).
2. Botón **"Conectar mi cuenta de Google"** → consiente con la cuenta
   corporativa. Google regresa al callback, se guarda el refresh token cifrado
   y el sistema **crea la carpeta** `El Despacho - Adjuntos` automáticamente.
3. Botón **"Probar conexión"** → debe quedar en 🟢.

---

## Validación manual (opcional, vía shell)

```bash
docker compose exec la-gerencia python manage.py shell
```

```python
>>> from lib.google_drive import drive
>>> drive.esta_conectado()
True
>>> drive.probar()
{'ok': True, 'estado': 'ok', 'mensaje': '¡Listo! ...', 'carpeta_id': '...'}
```

Si `probar()` devuelve `no_conectado`, falta el consentimiento (paso 4).
Si devuelve `sin_acceso`, revisa que la Drive API esté habilitada (paso 1) y
reconecta.

---

## Activación de adjuntos (S2b.1b)

Con la conexión en 🟢, el sprint **S2b.1b** implementa `subir_archivo()` (hoy
lanza `NotImplementedError`), agrega `RecadoAdjunto` (modelo + UI) y cablea el
botón 📎 del form de Recados. Toda la plomería de auth ya está hecha.

---

## Revocar / rotar

- Desde el asistente: botón **"Desconectar"** borra el refresh token y el ID de
  carpeta de La Bóveda (la carpeta sigue en Drive). Reconectar pide
  consentimiento de nuevo.
- Desde Google: https://myaccount.google.com/permissions → revoca el acceso de
  la app. El siguiente `probar()` quedará 🔴 con mensaje de reconectar.
