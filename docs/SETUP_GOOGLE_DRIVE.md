# Setup Google Drive para El Despacho

> **¿Eres el administrador no técnico?** No necesitas este documento.
> Entra a La Gerencia → **Ajustes → Conectar Google Drive** y sigue el
> asistente guiado de 7 pasos. Hace lo mismo que esta guía pero con
> botones, enlaces directos y un botón "Probar conexión" que te avisa si
> quedó bien. Este archivo es la referencia técnica equivalente.

> **Estado:** wrapper escrito (S2b.1.5), asistente de configuración + prueba
> de conexión en vivo (S-Drive-Setup). Pendiente cablear la subida de
> adjuntos en S2b.1b. Sigue esta guía (o el asistente) cuando estés listo
> para que Los Recados (y módulos futuros como Las Cotizaciones) guarden
> adjuntos en una carpeta corporativa de Drive que el contador pueda auditar.

Una vez completes los 8 pasos, el slot `google_drive_service_account_json`
en Los Ajustes tendrá el JSON cifrado, el slot `google_drive_carpeta_raiz_id`
tendrá el ID de la carpeta raíz, y el wrapper `lib.google_drive.drive`
instanciará el cliente API. Lo que falta en ese punto es **cablear**
los handlers que suben adjuntos (sprint S2b.1b).

---

## Paso 1 · Crear proyecto en Google Cloud Console

1. Entra a https://console.cloud.google.com con la cuenta corporativa
   (ideal: `oscar@bautista.mx` o una cuenta admin del workspace).
2. Click en el selector de proyecto arriba a la izquierda → **"Nuevo proyecto"**.
3. Nombre: `El Despacho — Learning Center`. Organización: la que aplique.
4. **Crear** y espera ~30s. Selecciona el proyecto nuevo.

## Paso 2 · Habilitar la Drive API

1. Menú lateral → **APIs y servicios → Biblioteca**.
2. Busca **"Google Drive API"** → click → **Habilitar**.
3. Espera a que diga "API habilitada".

## Paso 3 · Crear Service Account

1. Menú lateral → **IAM y administración → Cuentas de servicio**.
2. **+ Crear cuenta de servicio**.
   - Nombre: `el-despacho-drive`
   - ID: `el-despacho-drive` (auto-generado, déjalo)
   - Descripción: `Wrapper de Google Drive para adjuntos del CRM`
3. Click **Crear y continuar**. **Sin roles** (en este paso) → **Continuar** →
   **Listo**. La cuenta de servicio se crea con email tipo
   `el-despacho-drive@el-despacho-XXXX.iam.gserviceaccount.com`. Cópialo —
   lo usas en el paso 6.

## Paso 4 · Descargar el JSON de credenciales

1. En la lista de cuentas de servicio, click en `el-despacho-drive`.
2. Pestaña **Claves** → **Agregar clave → Crear clave nueva**.
3. Tipo: **JSON** → **Crear**. Se descarga un archivo
   `el-despacho-XXXX-abc123.json`. **NO lo subas al repo.**
4. Ábrelo y copia el contenido completo (incluyendo `{` y `}`) al portapapeles.

## Paso 5 · Crear la carpeta raíz en Drive

1. Entra a https://drive.google.com con la cuenta corporativa.
2. **+ Nuevo → Carpeta** → nombre: `El Despacho - Adjuntos`.
3. Doble click en la carpeta para entrar. Copia el ID de la URL:
   ```
   https://drive.google.com/drive/folders/1A2b3C4d5E6f7G8h9I0j_ABCDEF
                                          └────────── ID ──────────┘
   ```
   Ese es tu `google_drive_carpeta_raiz_id`.

## Paso 6 · Compartir la carpeta con la Service Account

1. Click derecho en la carpeta `El Despacho - Adjuntos` → **Compartir**.
2. Pega el email de la service account (del paso 3) en el campo "Agregar
   personas y grupos".
3. Permiso: **Editor**. Desmarca "Notificar a las personas" (no tiene buzón).
4. **Enviar / Compartir**.

> ⚠️ Sin este paso la service account no ve la carpeta y el wrapper
> falla en su primer upload con `403 File not found`.

## Paso 7 · Configurar los slots en La Bóveda

En el panel de La Gerencia, como `super_admin`:

1. Entra a **Ajustes** (`/ajustes/`).
2. Busca el slot **"Google Drive — Service Account JSON (Inactivo)"**.
   Pega el JSON completo del paso 4 → **Guardar**.
3. Busca el slot **"Google Drive — Carpeta raíz ID (Inactivo)"**.
   Pega el ID del paso 5 → **Guardar**.

Los Ajustes cifra ambos valores con La Bóveda; nadie los ve en claro
después de guardarlos.

## Paso 8 · Validar el wrapper

SSH al droplet o local en HAL:

```bash
docker compose exec la-gerencia python manage.py shell
```

```python
>>> from lib.google_drive import drive
>>> drive.esta_configurado()
True
>>> drive.carpeta_raiz_id
'1A2b3C4d5E6f7G8h9I0j_ABCDEF'
>>> drive.service
<googleapiclient.discovery.Resource object at 0x...>
>>> # Verifica acceso a la carpeta:
>>> drive.service.files().get(fileId=drive.carpeta_raiz_id, fields='id,name').execute()
{'id': '1A2b...', 'name': 'El Despacho - Adjuntos'}
```

Si las 4 líneas devuelven sin error, **estás listo**.

Si `drive.service` lanza `NoConfiguradoError`, revisa los slots del paso 7.
Si la última línea lanza `403`, revisa el paso 6 (compartir).

---

## Activación final

Cuando los 8 pasos están verdes, abre un issue / avisa al equipo Claude
Code para arrancar **sprint S2b.1b — Los Recados + Drive**. Ese sprint:

1. Implementa los métodos `subir_archivo()`, `crear_carpeta()` y
   `obtener_o_crear_carpeta()` (hoy `raise NotImplementedError`).
2. Cablea el botón 📎 del form de Los Recados al endpoint de upload.
3. Agrega `RecadoAdjunto` (modelo + migración + UI).
4. Routing por carpeta del proyecto si el recado menciona `#PRY-XXXXXX`,
   sino general `Los Recados / yyyy-mm/`.
5. Fallback gracioso: si Drive cae, el recado se envía sin adjunto y
   se emite `recado.adjunto_fallo` por Portavoz.

S2b.1b es ~1.5h porque toda la plomería está hecha — solo falta el
cableado.

---

## Apéndice — Por qué Service Account y no OAuth de usuario

- **No requiere consentimiento humano** en cada deploy.
- **No expira el refresh token** silenciosamente.
- **Audit trail** propio: los archivos los crea
  `el-despacho-drive@...iam.gserviceaccount.com`, lo que aclara que
  son del sistema, no de un humano.
- **Quota** propia, separada de la del usuario que configuró.

Trade-off: la service account no puede usar el "Mi unidad" personal de
nadie; necesita una carpeta corporativa compartida explícitamente.
Eso es lo que hace el paso 5+6.

---

## Apéndice — Costos

Google Drive API es gratuita hasta los límites del workspace
(usualmente generosos). El JSON de la service account no cobra.
El único "costo" es el almacenamiento en la carpeta de Drive, que se
descuenta del quota del workspace donde vive (típicamente 30 GB / 2 TB
según el plan de Google Workspace del cliente).

Si el quota se acota, el wrapper recibirá `403 storageQuotaExceeded` y
el sprint S2b.1b debe emitir alerta vía Portavoz.
