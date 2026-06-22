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

## 1. Keystore de firma (UNA VEZ, fuera del repo)

```bash
keytool -genkeypair -v -keystore envoltorio-taller.keystore \
  -alias taller -keyalg RSA -keysize 2048 -validity 10000

# Fingerprint para assetlinks.json:
keytool -list -v -keystore envoltorio-taller.keystore -alias taller | grep SHA256
```

- **El keystore NUNCA va al repo** (está en .gitignore). Guárdalo en HAL:
  `/Volumes/RAID/Backups/el-despacho/envoltorio/` y el password en tu gestor.
- Si se pierde: se genera otro, se actualiza el fingerprint en el `Caddyfile`
  y los 5 usuarios reinstalan el APK. Molesto, no catastrófico.

## 2. Publicar el fingerprint (repo)

En el `Caddyfile`, bloque `taller.learningcenter.mx`, reemplaza
`REEMPLAZAR_CON_FINGERPRINT_SHA256` con el SHA256 del paso 1 (formato
`AA:BB:CC:...`). Commit + deploy. Verifica:

```bash
curl -s https://taller.learningcenter.mx/.well-known/assetlinks.json
```

Debe responder el JSON con tu fingerprint. **Sin esto la app abre con barra
de URL** (funciona, pero se nota que es web).

## 3. Generar el proyecto TWA (elige UN camino, ambos $0)

**A) PWABuilder (recomendado — cero tooling local):**
1. Ve a [pwabuilder.com](https://www.pwabuilder.com) → pega
   `https://taller.learningcenter.mx` → *Package for stores* → **Android**.
2. Package ID: `mx.learningcenter.taller`. Sube TU keystore del paso 1
   (o descarga y resguarda el que PWABuilder genere).
3. Descarga el `.apk` firmado.

**B) Bubblewrap (CLI repetible — requiere Node+JDK locales, NUNCA en CI):**
```bash
npx @bubblewrap/cli init --manifest=https://taller.learningcenter.mx/static/manifest.json
# package id: mx.learningcenter.taller · firma con el keystore del paso 1
npx @bubblewrap/cli build
```
El `twa-manifest.json` generado SÍ se commitea aquí (sin secretos); el
proyecto Android generado y los `.apk` NO.

## 4. Distribuir e instalar (5 usuarios, sin Play Store)

1. Pasa el APK a los Android del equipo (link privado o `adb install`).
2. Habilita "instalar apps de origen desconocido" para el origen usado.
3. **Verifica en el dispositivo:**
   - [ ] Abre full-screen SIN barra de URL (si sale barra → revisa el
         fingerprint/package del paso 2).
   - [ ] Push del Interfón llega con el app cerrada.
   - [ ] El Checador obtiene geolocalización al checar.
   - [ ] La cámara abre desde "Escanear recibo" (OCR).
   - [ ] Si ya había sesión en Chrome, el app abre logueado.

## Deuda diseñada

- Play Store si algún día se quiere ($25 USD una vez + revisión de Google).
- Wrapper iOS si Oscar decide pagar Apple Developer ($99/año) — revisar
  entonces el trade-off de push (WKWebView NO soporta Web Push; requeriría
  puente APNs, sprint dedicado).
