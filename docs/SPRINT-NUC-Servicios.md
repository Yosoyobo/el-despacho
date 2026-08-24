# Qué más puede correr el NUC — plan de servicios

> Levantado el 2026-08-24 tras cuatro rondas de preguntas con Oscar.
> Este documento es el handoff: qué se aloja, en qué orden, qué se
> descartó y por qué. **Nada de esto está instalado todavía.**

---

## 0. El fierro, medido (no supuesto)

Reconocimiento del 2026-08-24, 08:40, contra `nuc-lc` por el tailnet:

| | |
|---|---|
| CPU | i5-10210U · 4 núcleos / 8 hilos · **carga 0.13 de 8** |
| RAM | 14 G totales · **11 G libres** (El Despacho usa 2.3 G) |
| Disco | 116 G · **92 G libres** · SSD de 1 TB **por llegar** |
| Video por hardware | `/dev/dri/renderD128` presente → **Quick Sync sirve** |
| Red | `eno1` **DOWN** — todo va por WiFi |

**Lo que eso decide:** la RAM no es el límite (caben 6-8 servicios más).
El disco y el cable sí lo son. **El cable de red deja de ser
mantenimiento pendiente y pasa a ser requisito**: con la cámara de la
Bambu, Plex y las consultas de ruteo, el WiFi es el cuello.

---

## 1. Lo que duele hoy, con números

Consultado en la base de producción el mismo día:

| | |
|---|---|
| Facturas en **borrador** | **32 de 36** — no generan cuenta por cobrar |
| Facturas con su **CFDI archivado** | **1 de 36** |
| La Cobranza | **apagada** desde que existe |
| Recordatorios de pago enviados **en toda la historia** | **0** |

Y en el código:

- **PDFs** → los arma Google Docs (`lib/google_drive.py:617`). De ahí
  salen `_ajustar_pagina`, `createFooter` y `preventOverflow`: peleas
  contra los caprichos del convertidor. El «1/1» que no avanza, el
  margen superior que Google ignora y el estimador de paginación que
  adivina son todos hijos de esa dependencia.
- **Rutas** → haversine, línea recta (`planeador.py:23`).
- **Direcciones** → Nominatim **público** (`lib/geocoding.py:17`), que
  es cortesía de OSM: una consulta por segundo y pueden bloquearnos.
- **CFDIs** → `almacenar_cfdi(pdf_file=, xml_file=)`: alguien los baja
  del PAC y los sube uno por uno. Por eso hay 1 de 36.

---

## 2. Decisiones de Oscar (no volver a abrirlas)

| Decisión | Consecuencia |
|---|---|
| PDFs **fuera de Google**, motor local | Entra Gotenberg |
| **No hay e.firma** a la mano | La descarga masiva del SAT queda fuera; los CFDIs entran por correo |
| Rutas por **calles reales, todo México** | Entra OSRM con el mapa completo |
| n8n **«A y B, más A. B con MUCHO GUARDRAIL MCP»** | Recetas listas + autoría del Chalán con preview y confirmación humana |
| La Bambu es **personal**, modelo **X1** | Ligarla a proyectos es opcional. **Obico se descarta**: la X1 ya detecta spaghetti |
| Inventario: **«A y C, más C»** | Etiquetas con QR primero; existencias propias después, si se piden |
| Etiquetera **USB o red** | Habla TSPL/ZPL: camino directo por socket 9100 o CUPS |
| Paraguas de sensores: **sólo lo de la Bambu** | Home Assistant entra **acotado**, sin sensores del taller |
| Respaldo offsite: **no, con HAL basta** | Riesgo señalado y aceptado. Dos copias, ambas en el país |
| **La Cobranza queda apagada por decisión** | Ningún sprint futuro la prende por su cuenta |
| Media: **Plex** | Con la advertencia del Pass (§6) |

---

## 3. Lo que se aloja, por orden de valor

### 3.1 n8n + la receta de los CFDIs — *primero*

Es lo más barato de alto impacto y lo único que hace que el equipo
**vea** para qué sirve n8n el primer día.

- El Portavoz lleva desde mayo encolando eventos hacia un n8n muerto.
  El cableado ya existe: eventos tipados, cola en Redis, firma HMAC,
  worker. **Sólo falta el destino.**
- **Receta 1 — CFDIs por correo:** n8n vigila el buzón donde llegan los
  CFDIs, extrae el XML adjunto, lo liga a su factura por UUID y monto,
  y la saca de borrador. Ataca de frente el «1 de 36».
- **Cómo se ve para quien no sabe usar n8n:** una lista en La Gerencia,
  una frase por receta y un interruptor. **Nadie abre n8n jamás.**

**Los guardrails de MCP** (lo que pidió Oscar). Se apoyan en lo que ya
existe — `capacidades/` como contrato único, y la regla §20 de
preview + confirmación:

- **Lectura** (`modo="lectura"`): El Chalán puede decir qué recetas hay,
  cuáles están prendidas, qué corrió anoche y qué falló.
- **Propuesta** (`modo="propuesta"`): puede *proponer* una receta nueva
  o un cambio. Se muestra en español llano —qué dispara, a quién le
  escribe, qué toca— y **no se prende hasta que un humano confirma**,
  igual que cualquier otra acción del Dictado.
- **Prohibido**: activar, borrar o editar un flujo vivo por su cuenta.
  Una receta prendida sola puede mandarle correos a clientes.

### 3.2 Gotenberg — los PDFs sin Google

Mata deuda documentada de un golpe. Chromium convierte el HTML: en vez
de pelearse con un convertidor ajeno, se usa CSS de verdad —`@page`,
numeración real de páginas, pie fijo— y desaparecen los siete quirks.

- **Además quita un punto de falla real**: el 21 de agosto el cliente
  OAuth cambió y las fotos de los productos se cayeron. Los PDFs
  colgaban del mismo hilo.
- **Migración sin riesgo**: se genera la misma cotización por los dos
  caminos, se comparan, y sólo entonces se cambia el default.
- Cuesta ~300 MB de RAM. La plantilla actual es de tablas *porque Docs
  lo exigía*; se puede modernizar después, sin prisa.

### 3.3 Paperless-ngx — el archivo con OCR

Contratos, remisiones, comprobantes, cotizaciones de proveedor. Se
escanea o se reenvía por correo y queda buscable por texto para
siempre. ~1 GB de RAM. Se lleva bien con la receta de n8n: el mismo
buzón puede alimentar los dos.

### 3.4 OSRM + geocodificador propio — las rutas de verdad

- **OSRM con `mexico-latest.osm.pbf`** (~1.3 GB). Distancias, tiempos y
  orden de paradas por calles reales. El cambio está encapsulado en el
  planeador (`ruta._distancia` / `largo_de`), así que es sustituir una
  función, no rehacer el módulo.
  - **Ojo con el preprocesado**: pide 6-8 G de RAM en el pico. Se corre
    de madrugada, o se procesa en HAL y se copia el resultado. Servir
    ya sólo cuesta ~2 GB.
- **Photon** para direcciones, en vez de Nominatim completo: mismo
  servicio, una fracción del peso (Nominatim con México pide su propio
  Postgres de decenas de GB). Adiós al límite de una consulta por
  segundo y al riesgo de que OSM nos bloquee.

### 3.5 La Bambu X1 — acotado

Home Assistant **sólo con la integración de Bambu**: es el vehículo más
corto para lo que se pidió, no el destino. Da estado, cola, avisos de
fin y falla, y la cámara por RTSP en modo LAN. Los avisos salen por El
Interfón como cualquier otra notificación. ~500 MB.

- **Requiere**: modo LAN activado en la impresora, con su código de
  acceso y número de serie.
- **Obico queda fuera**: la X1 ya detecta spaghetti de fábrica.
- Ligar horas y filamento a un proyecto queda **opcional**, porque la
  impresora es personal.

### 3.6 Etiquetas — desarrollo chico, no instalación

La etiquetera genérica por USB o red habla TSPL o ZPL: se le manda la
etiqueta por el puerto 9100 y sale. No hace falta alojar nada.

- **Qué se etiqueta**: lotes y muestras de producción, e insumos y
  materia prima.
- **Sin existencias por ahora** (decisión «más C»): la etiqueta lleva un
  QR que abre ese lote o ese insumo en El Despacho. Nadie lleva la
  cuenta de cuánto queda —todavía—, pero la puerta a un módulo propio
  de inventario queda abierta y **no** se parte el catálogo en dos.

### 3.7 Las pantallas de pared

- **El Vigía ya está construido**: sólo hay que colgarlo. Falta resolver
  el aparato de la TV (Chrome en kiosco apuntando al NUC por la LAN).
- **Tablero de producción del día**: qué se entrega hoy, quién trae qué,
  qué va atrasado. Sale de lo que El Despacho ya sabe — es una pantalla
  más, no un servicio nuevo.

### 3.8 Plex — al final

Con la advertencia: **la transcodificación por hardware requiere Plex
Pass**. Sin él funciona en *direct play* y el video se traba cuando el
aparato no aguanta el formato. Jellyfin da lo mismo gratis. Decisión de
Oscar, tomada sabiéndolo.

---

## 4. Lo que se descarta, y por qué

| Descartado | Razón |
|---|---|
| **Obico** | La X1 ya detecta spaghetti. Sería instalar algo pesado para duplicar |
| **InvenTree** | Partiría el catálogo en dos: dos verdades sobre el mismo rollo de vinil, y El Chalán ciego a la mitad |
| **Descarga masiva del SAT** | No hay e.firma a la mano. Se retoma el día que la haya |
| **Home Assistant con sensores del taller** | Descartado por Oscar. *(La humedad sí arruina vinil y sublimación; queda anotado por si algún día duele)* |
| **Respaldo fuera del país** | Descartado por Oscar. Dos copias, las dos en México |
| **La Cobranza** | Apagada por decisión explícita |
| **Ollama** | Ya descartado antes: no le gana a las API |
| **Uptime Kuma, Grafana, Netdata** | El Celador, El Vigía y El Site ya cubren esto |
| **Nextcloud, Immich, Syncthing** | Los archivos de diseño no salieron como dolor |

---

## 5. Presupuesto de recursos

| Servicio | RAM | Disco |
|---|---|---|
| n8n | ~500 MB | poco |
| Gotenberg | ~300 MB | poco |
| Paperless-ngx | ~1 G | crece con el papeleo |
| OSRM (México) | ~2 G | ~3 G |
| Photon (México) | ~1-2 G | ~3-8 G |
| Home Assistant | ~500 MB | poco |
| Plex | ~500 MB | **se come todo lo que le den** |
| **Suma** | **~6-7 G** | |

Quedan 11 G libres y El Despacho va a crecer: **cabe, pero ajustado**.
Si aprieta, OSRM es el que más pesa y se puede acotar a la zona
metropolitana sin tocar nada más. El SSD de 1 TB resuelve el disco.

---

## 6. Orden de ejecución

1. **n8n + receta de CFDIs** — valor inmediato, y hace que el equipo lo compre
2. **Gotenberg** — mata deuda vieja y un punto de falla
3. **Paperless-ngx** — el papeleo deja de perderse
4. **OSRM + Photon** — las rutas dejan de mentir
5. **La Bambu** — avisos y cámara
6. **Etiquetas** — desarrollo chico dentro de El Despacho
7. **Tablero en pared** — colgar El Vigía y armar la vista del día
8. **Plex** — cuando todo lo demás esté en pie

**Antes del 4, 5 y 8: el cable de red.** Y el SSD antes del 3 y el 8.

---

## 7. Lo que hace falta de tu lado

- **El cable de red** conectado (`eno1` sigue caído) y el **SSD de 1 TB**.
- **A qué buzón llegan los CFDIs**, y con qué credenciales leerlo.
- **Modo LAN de la X1**: código de acceso y número de serie.
- **Marca y modelo de la etiquetera**, para confirmar si habla TSPL o ZPL.
- **Decidir Plex Pass** o cambiar a Jellyfin.
