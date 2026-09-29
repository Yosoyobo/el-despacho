# El Envoltorio — app Android nativa (TWA) de El Taller

> Desarrollado por **NoKo Devs** ([devs.noko.mx](https://devs.noko.mx)) · © 2026 Learning Center.

Wrapper nativo **gratuito** ($0) de la PWA de El Taller para Android, vía
**TWA (Trusted Web Activity)**. La TWA corre sobre Chrome: conserva **push del
Interfón, geolocalización del Checador y cámara del OCR** completos, comparte
sesión con Chrome, y abre full-screen **sin barra de URL** cuando la
verificación de Digital Asset Links pasa.

**iOS: ABORTADO** por la regla "gratis o abortamos" (TestFlight exige Apple
Developer $99/año; el sideload gratis caduca cada 7 días). El equipo iPhone
usa la PWA instalada desde Safari (Compartir → "Añadir a pantalla de inicio"),
que conserva los push (iOS 16.4+).

La TWA muestra la web viva: las features llegan solas con cada deploy. Solo se
re-buildea el APK si cambia el ícono, el nombre o el manifest.

---

## Estado (2026-09-28): llave, huella y APK YA existen

| Pieza | Dónde |
|---|---|
| Llave de firma (de trabajo) | `~/.android-llaves/el-despacho/envoltorio-taller.keystore` en HAL (PKCS12, alias `taller`, RSA 2048, 10000 días) |
| Respaldo de la llave | `/Volumes/RAID/Backups/el-despacho/envoltorio/envoltorio-taller.keystore` (misma llave, byte a byte) |
| Contraseña | `LEEME-contrasena.txt` junto a cada copia (permisos 600). **Pásala a tu gestor.** |
| Huella SHA-256 | `77:C2:7B:44:E1:F7:F0:CD:87:6F:F3:0E:1C:4B:7E:C5:2E:C7:F0:0F:E2:7D:A8:C6:03:05:C7:F2:0D:C1:64:F3` |
| Huella publicada | `Caddyfile`, bloque `taller.learningcenter.mx` → `/.well-known/assetlinks.json` |
| Receta del APK | `envoltorio/twa-manifest.json` (en el repo; sin secretos ni rutas absolutas) |
| APK firmado | `/Volumes/RAID/Backups/el-despacho/envoltorio/el-taller-2026-09-28.apk` (+ `.aab` del mismo build) |

- **La llave NUNCA va al repo**: `.gitignore` excluye `*.keystore`, `*.jks`,
  `*.apk`, `*.aab`, `*.idsig`, `LEEME-contrasena.txt` y el proyecto Android
  generado. `tests/test_envoltorio.py` lo exige.
- **NUNCA la regeneres.** Una llave nueva cambia la huella: hay que actualizar el
  `Caddyfile`, `twa-manifest.json` y **reinstalar la app en todos los teléfonos**
  (Android no deja actualizar una app firmada con otra llave). Si la de HAL se
  pierde, se restaura la del RAID.
- El respaldo del RAID vive en `envoltorio/`, fuera de las series `db-*` y
  `credenciales-*` que rota `archivo.sh`: no se borra solo.

## 1. Herramientas (ya instaladas en HAL, todo $0)

- **JDK 17**: `/usr/local/opt/openjdk@17` (el `/usr/bin/java` de macOS NO sirve).
- **Android SDK**: `/Volumes/RAID/android-sdk` con `build-tools;36.1.0` y
  `platforms;android-36` (los que pide Bubblewrap 1.25). Lleva un symlink
  `tools → cmdline-tools/latest` porque Bubblewrap exige `tools/` o `bin/` en la
  raíz del SDK para darlo por bueno.
- **Bubblewrap**: `npx @bubblewrap/cli` (1.25.0). Su configuración está en
  `~/.bubblewrap/config.json`:
  ```json
  {"jdkPath":"/usr/local/opt/openjdk@17/libexec/openjdk.jdk","androidSdkPath":"/Volumes/RAID/android-sdk"}
  ```
  (en macOS `jdkPath` es la carpeta que contiene `Contents/Home`).

Si falta un componente del SDK:
```bash
export JAVA_HOME=/usr/local/opt/openjdk@17 PATH=/usr/local/opt/openjdk@17/bin:$PATH
yes | /Volumes/RAID/android-sdk/cmdline-tools/latest/bin/sdkmanager \
  --sdk_root=/Volumes/RAID/android-sdk "build-tools;36.1.0" "platforms;android-36"
```

## 2. Reconstruir el APK (sólo si cambia ícono, nombre, color o manifest)

Se construye en una carpeta temporal, **nunca dentro del repo ni en CI**
(El Mensajero no tiene ni debe tener la llave).

```bash
export JAVA_HOME=/usr/local/opt/openjdk@17 PATH=/usr/local/opt/openjdk@17/bin:$PATH
mkdir -p /tmp/envoltorio && cd /tmp/envoltorio
cp /Volumes/RAID/VSCode/ElDespacho/envoltorio/twa-manifest.json .

# Sube appVersionCode/appVersionName en twa-manifest.json si el APK va a
# reemplazar uno ya instalado (Android rechaza un versionCode igual o menor).
npx @bubblewrap/cli update --skipVersionUpgrade      # genera el proyecto Android

PW='<la de LEEME-contrasena.txt>'
BUBBLEWRAP_KEYSTORE_PASSWORD="$PW" BUBBLEWRAP_KEY_PASSWORD="$PW" \
  npx @bubblewrap/cli build --skipPwaValidation \
  --signingKeyPath="$HOME/.android-llaves/el-despacho/envoltorio-taller.keystore" \
  --signingKeyAlias=taller
# → app-release-signed.apk  y  app-release-bundle.aab

cp app-release-signed.apk /Volumes/RAID/Backups/el-despacho/envoltorio/el-taller-$(date +%F).apk
```

`twa-manifest.json` lleva `signingKey.path` relativo a propósito: la ruta real
se pasa con `--signingKeyPath`. Si cambiaste el manifest, copia de vuelta el
`twa-manifest.json` a `envoltorio/` y commitéalo.

**Comprobar la firma** (la huella debe ser la del `Caddyfile`, en minúsculas y
sin dos puntos):
```bash
/Volumes/RAID/android-sdk/build-tools/36.1.0/apksigner verify --print-certs \
  /Volumes/RAID/Backups/el-despacho/envoltorio/el-taller-2026-09-28.apk
# Signer #1 certificate SHA-256 digest: 77c27b44e1f7f0cd876ff30e1c4b7ec52ec7f00fe27da8c60305c7f20dc164f3
```

## 3. La huella en El Portero

Ya está en el `Caddyfile` (bloque `taller.learningcenter.mx`). Llega con el
deploy normal (La Mudanza recrea `el-portero` si el Caddyfile de adentro difiere
del del repo, §14 Bug F). Tras el deploy:

```bash
curl -s https://taller.learningcenter.mx/.well-known/assetlinks.json
```

Debe responder el JSON con la huella de arriba y `mx.learningcenter.taller`.
**Sin esto la app abre con barra de URL** (funciona, pero se nota que es web).
Google también lo puede validar:
`https://digitalassetlinks.googleapis.com/v1/statements:list?source.web.site=https://taller.learningcenter.mx&relation=delegate_permission/common.handle_all_urls`.

## 4. Instalar en los teléfonos (5 usuarios, sin Play Store)

1. Pasa el APK (`el-taller-2026-09-28.apk`) al teléfono: por un link privado de
   Drive, por WhatsApp a uno mismo, o con cable: `adb install el-taller-2026-09-28.apk`
   (`adb` está en `/Volumes/RAID/android-sdk/platform-tools/`).
2. Ábrelo en el teléfono. Android pide permitir «instalar apps desconocidas» para
   la app desde la que lo abriste (Drive, Archivos, WhatsApp): acéptalo.
3. Debe estar instalado **Chrome** (la app corre sobre él) y al día.
4. Abre «El Taller» desde el cajón de apps e inicia sesión (si ya había sesión
   en Chrome, entra sola).
5. Acepta los permisos cuando los pida: **notificaciones** (avisos del Interfón)
   y **ubicación** (El Checador).

## 5. Lista de verificación en cada teléfono

- [ ] Abre a pantalla completa **SIN barra de URL** (si sale barra → revisar
      que el deploy con la huella ya esté en producción, paso 3).
- [ ] El push del Interfón llega con la app cerrada.
- [ ] El Checador obtiene la ubicación al checar.
- [ ] La cámara abre desde «Escanear recibo» (OCR).
- [ ] Si ya había sesión en Chrome, la app abre con sesión.
- [ ] El ícono del sol de Learning Center se ve bien en el cajón de apps.

## Deuda diseñada

- Play Store si algún día se quiere ($25 USD una vez + revisión de Google).
- Wrapper iOS si Oscar decide pagar Apple Developer ($99/año) — revisar
  entonces el trade-off de push (WKWebView NO soporta Web Push; requeriría
  puente APNs, sprint dedicado).
- Las actualizaciones del APK se reparten a mano (no hay tienda que las empuje).
  Casi nunca hace falta: la app muestra la web viva.

---

> Desarrollado por **[NoKo Devs](https://devs.noko.mx)** · © 2026 Learning Center.
