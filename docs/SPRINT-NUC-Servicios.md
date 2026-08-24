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

**Lo que eso decide:** la RAM no es el límite (ver §5). El disco sí.

**Sobre el cable de red — corrección del 2026-08-24.** Se dijo que era
requisito; medido, **no lo es**: el enlace está a **-38 dBm** en 5 GHz
con canal de 80 MHz, **866 Mbit/s** de bajada y **cero errores**. Con
555 peticiones por hora no se roza. Lo único que compra un cable es
**confiabilidad**, no velocidad: hoy el negocio entero depende de una
asociación WiFi, y si esa interfaz se cae, se cae todo. Como el NUC está
en una **ubicación temporal**, cablear ahora para recablear después es
trabajo doble: **se hace cuando se mude a su lugar definitivo.**

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
| Inventario: **«A y C, más C»** | Etiquetas con QR primero; existencias propias después, si se piden |
| Etiquetera **USB o red** | Habla TSPL/ZPL: camino directo por socket 9100 o CUPS |
| Respaldo offsite: **no, con HAL basta** | Riesgo señalado y aceptado. Dos copias, ambas en el país |
| **La Cobranza queda apagada por decisión** | Ningún sprint futuro la prende por su cuenta |
| **Fuera: la Bambu y Plex** (2026-08-24) | El NUC se queda como servidor de trabajo. Ni impresión 3D ni media |

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

### 3.4 OSRM — las rutas de verdad

**OSRM con `mexico-latest.osm.pbf`** (~1.3 GB). Distancias, tiempos y
orden de paradas por calles reales. El cambio está encapsulado en el
planeador (`ruta._distancia` / `largo_de`): es sustituir una función,
no rehacer el módulo.

- **El argumento fuerte** es la matriz: para ordenar N paradas hay que
  medir N×N trayectos. Contra un servicio público es imposible; contra
  un OSRM local es instantáneo.
- **Ojo con el preprocesado**: pide 6-8 G de RAM en el pico. Se corre de
  madrugada con lo demás quieto, o se procesa en HAL y se copia el
  resultado. Servir ya sólo cuesta ~2.2 G.

**Photon (geocodificar direcciones) queda como opcional, fase 2.** Es el
servicio más caro del plan —2 G— para lo que resuelve: capturar una
dirección nueva de vez en cuando. Con diez usuarios y el caché que ya
existe, Nominatim público alcanza. Se retoma el día que el límite de una
consulta por segundo estorbe de verdad.

### 3.5 Etiquetas — desarrollo chico, no instalación

La etiquetera genérica por USB o red habla TSPL o ZPL: se le manda la
etiqueta por el puerto 9100 y sale. No hace falta alojar nada.

- **Qué se etiqueta**: lotes y muestras de producción, e insumos y
  materia prima.
- **Sin existencias por ahora** (decisión «más C»): la etiqueta lleva un
  QR que abre ese lote o ese insumo en El Despacho. Nadie lleva la
  cuenta de cuánto queda —todavía—, pero la puerta a un módulo propio
  de inventario queda abierta y **no** se parte el catálogo en dos.

### 3.6 Las pantallas de pared

- **El Vigía ya está construido**: sólo hay que colgarlo. Falta resolver
  el aparato de la TV (Chrome en kiosco apuntando al NUC por la LAN).
- **Tablero de producción del día**: qué se entrega hoy, quién trae qué,
  qué va atrasado. Sale de lo que El Despacho ya sabe — es una pantalla
  más, no un servicio nuevo.

---

## 4. Lo que se descarta, y por qué

| Descartado | Razón |
|---|---|
| **Todo lo de la Bambu** | Fuera por decisión de Oscar (2026-08-24). El NUC se queda como servidor de trabajo |
| **Plex y cualquier media** | Fuera por la misma decisión. Además, su transcodificación por hardware pedía Plex Pass |
| **Photon** | 2 G para geocodificar de vez en cuando. Baja a fase 2; Nominatim público alcanza |
| **Obico** | La X1 ya detecta spaghetti, y de todos modos la impresora salió del plan |
| **InvenTree** | Partiría el catálogo en dos: dos verdades sobre el mismo rollo de vinil, y El Chalán ciego a la mitad |
| **Descarga masiva del SAT** | No hay e.firma a la mano. Se retoma el día que la haya |
| **Home Assistant con sensores del taller** | Descartado por Oscar. *(La humedad sí arruina vinil y sublimación; queda anotado por si algún día duele)* |
| **Respaldo fuera del país** | Descartado por Oscar. Dos copias, las dos en México |
| **La Cobranza** | Apagada por decisión explícita |
| **Ollama** | Ya descartado antes: no le gana a las API |
| **Uptime Kuma, Grafana, Netdata** | El Celador, El Vigía y El Site ya cubren esto |
| **Nextcloud, Immich, Syncthing** | Los archivos de diseño no salieron como dolor |

---

## 5. Presupuesto de RAM — medido, no estimado

Medido en el NUC el 2026-08-24 con `docker stats` y `pg_settings`.

### 5.1 Lo que hay hoy

| | Usa ahora | Techo comprometido |
|---|---|---|
| El Taller (**8 workers × 8 hilos**) | 543 MB | fijo |
| La Gerencia (**4 × 8**) | 327 MB | fijo |
| Postgres | 254 MB | **`shared_buffers` = 4 G** |
| Redis | 15 MB | **`maxmemory` = 3 G** |
| Portavoz + El Mostrador | 102 MB | fijo |
| Sistema, Docker, Tailscale | ~1.05 G | — |
| **Total** | **2.3 G de 14.8 G** | **~8.5 G si todo se llena** |

### 5.2 Los usuarios simultáneos casi no mueven la RAM

El Taller ya atiende **64 peticiones a la vez** (8 workers × 8 hilos) y
La Gerencia 32. Cada worker carga Django entero **al arrancar**, así que
atender a diez personas reutiliza exactamente los mismos workers que
atender a una. Ya está medido: en la prueba de esfuerzo de agosto, de 10
a 200 concurrentes la RAM se quedó clavada en 4.2 G y lo que subió fue
el CPU. Diez usuarios no rozan el techo de 275 peticiones por segundo.

**Cuidado al medir esto con `ps`**: la suma de RSS de los 27 backends de
Postgres da 798 MB, pero el contenedor entero usa 254 MB. `ps` cuenta la
memoria compartida una vez por proceso. Con gunicorn pasa igual: 721 MB
sumados contra 543 reales. **El número honesto es el de cgroups**
(`docker stats`), no la suma de RSS. Es la razón más común por la que se
sobredimensiona un servidor.

Lo que **sí** crece cuando hay diez personas trabajando a la vez:

| | Con 5 | Con 10 |
|---|---|---|
| Conexiones a Postgres (~2-3 MB privados c/u) | +60 MB | **+100 MB** |
| `work_mem`: 32 MB **por ordenamiento**, no por usuario | +500 MB | **+1 G** |
| **Gotenberg**: un Chromium **por PDF** (~300 MB) | +1.5 G | **+3 G, acotado a 2 G** |
| **Paperless**: el OCR carga el documento | +600 MB | **+900 MB, acotado a 2 G** |

### 5.3 Los escenarios, con diez usuarios

| Escenario | RAM | Libre |
|---|---|---|
| Hoy, sólo El Despacho | 2.3 G | 12.5 G |
| + los servicios nuevos, en reposo | 5.75 G | 9.0 G |
| + **10 usuarios haciendo lo peor a la vez** | **~10 G** | **~4.8 G** |

Cabe, y queda por encima del colchón de 4 G que
`lib/site/host.presion_memoria()` usa como línea de alarma — **pero sólo
con los dos ajustes de §5.4 aplicados**. Sin ellos, los techos de
Postgres y Redis se comen ese margen.

**Techo absoluto** (si los cuatro `mem_limit` se tocaran a la vez):
8 G de servicios nuevos + 4 G de El Despacho + 1 G de sistema = **13 G
de 14.8**. Eso queda por debajo del colchón, pero es un escenario que no
ocurre: los límites son cinturones individuales, no reservas, y que los
cuatro se activen en el mismo segundo es tan probable como que los
cuatro pasajeros de un coche choquen por separado.

### 5.3.1 Gotenberg pide una segunda tranca

Es el único servicio cuyo consumo escala **con la gente**, no con los
datos: un Chromium por PDF. Con diez personas exportando a la vez son
3 G de golpe.

- El `mem_limit` de 2 G es el respaldo duro, pero llegar ahí significa
  que Gotenberg muere a media conversión.
- Mejor **acotar cuántas conversiones corren a la vez** (cuatro basta):
  las demás se encolan. El pico se aplana a ~1.2 G y el problema deja de
  ser de memoria para volverse de espera — que es como debe ser.

**Y hay un efecto en sentido contrario que juega a favor**: hoy cada PDF
ocupa un hilo de gunicorn **varios segundos** esperando a que Google
convierta el documento. Con Gotenberg eso baja a milisegundos. Con diez
usuarios, instalarlo **sube** la capacidad efectiva de El Taller en vez
de bajarla.

### 5.4 El conflicto de fondo, y cómo se resuelve

**Postgres tiene 4 G de techo y Redis 3 G, para una base de 29 MB y una
cola de 15 MB.** Ese dimensionamiento se hizo en agosto para «no volver
en meses», y era correcto cuando el NUC sólo cargaba El Despacho. Ahora
esos 7 G de techo compiten con los servicios nuevos: **7 + 6 + 1 es más
de lo que hay.** Hoy no truena porque nadie toca esos techos, pero es
una bomba con fecha desconocida.

Dos ajustes lo resuelven sin perder nada real:

1. **Bajar los techos a la realidad**: `shared_buffers` a **2 G** (sigue
   siendo 70 veces la base actual) y Redis a **1 G** (65 veces la cola).
   Libera **4 G** de compromiso. Al aplicarlo hay que **recrear el
   contenedor y comprobar con `SHOW`** — editar el compose no basta.
2. **Photon fuera** (§3.4): libera **2 G**.

Con los dos, el peor escenario baja a **~8.3 G, con 6.5 G libres**.

### 5.5 ¿Cuándo aprietan de verdad los 14.8 G?

**Por número de usuarios, nunca** — y el cálculo lo dice sin ambigüedad.

Medido en producción el 2026-08-24: **555 peticiones en una hora** con
cinco usuarios, o sea **0.15 por segundo contra un techo de 275**. Es el
**0.06 %** de la máquina. Latencias: p50 39 ms, p90 143 ms, p99 602 ms.

El presupuesto, con todo instalado y los ajustes de §5.4 puestos:

| | |
|---|---|
| Base fija (sistema + El Despacho + los 4 servicios) | 5.74 G |
| Hasta la línea de alarma (14.8 − 4 de colchón) | 10.8 G |
| **Disponible para carga** | **5.06 G** |
| − Gotenberg con 4 conversiones | −1.05 G |
| − Paperless con 2 OCR | −0.6 G |
| **Queda para consultas concurrentes** | **3.4 G** |

Una consulta pesada cuesta **~40 MB** (medido en agosto: 60 consultas
movieron la RAM de 4.12 a 6.53 G). Entonces:

> **3.4 G ÷ 40 MB = 85 consultas pesadas concurrentes** antes de que
> suene la alarma. Y gunicorn sólo puede tener **96 peticiones en
> vuelo** (64 en El Taller + 32 en La Gerencia). Los dos números están
> **casi empatados**: el sistema no puede pedir mucho más de lo que la
> RAM aguanta. Está balanceado, pero con un pelo de margen.

Para sostener 85 consultas pesadas a la vez harían falta ~85 por
segundo. Al ritmo por usuario que se midió (0.031 peticiones/s), eso son
**del orden de 2,700 usuarios simultáneos si TODOS hicieran sólo
reportes pesados**, y unos 8,900 con el mix real de uso. El CPU se
rendiría mucho antes que la memoria.

**Learning Center tiene cinco personas. El margen es de tres órdenes de
magnitud.**

### 5.6 Lo que sí va a apretar, en orden de cercanía

| Cuándo | Qué | Cómo se evita |
|---|---|---|
| **La noche que se instale OSRM** | El preprocesado del mapa de México pide **6-8 G de pico**. Es el aprieto más cercano en el tiempo | Correrlo con lo demás quieto, o procesar en HAL y copiar el resultado ya cocido |
| **El día que se instale Gotenberg** | Sin tope de concurrencia, diez PDFs a la vez son **3 G de golpe** | Acotar a cuatro conversiones (§5.3.1). Una línea de configuración |
| **Al quinto o sexto servicio nuevo** | Quedan **~3 G** de margen para lo que venga después de estos cuatro | Cada servicio nuevo entra con `mem_limit` y sale de este presupuesto, no del aire |
| **Cualquier día, por descuido** | Subir workers, `work_mem` o `shared_buffers` «por si acaso». Así se llegó a los techos de 4 G y 3 G | Cambiar un parámetro y **comprobarlo con `SHOW`**, no con `docker compose config` |
| **Cualquier día, por una fuga** | Un flujo mal hecho en n8n puede crecer sin techo | Para eso es el `mem_limit`: que muera el juguete, no El Taller |
| **En años** | Que el working set de Postgres llene sus 2 G. La base son 29 MB: tiene que crecer **70 veces** | Nada. El aviso de `presion_memoria()` lo dirá con meses de anticipación |

**Y el orden en que truenan los recursos, para no vigilar el equivocado:**
primero el **disco** (92 G hoy; el SSD de 1 TB lo resuelve por años),
después el **CPU** (4 núcleos: los reportes concurrentes lo tocan antes
que la memoria), y **la RAM al final**. El WiFi no está en la lista
(§0).

### 5.7 Regla para todo lo que se aloje de aquí en adelante

**Todo servicio nuevo lleva `mem_limit` en el compose.** El NUC sostiene
el negocio: ningún juguete puede tumbarlo compitiendo por memoria. Si
Gotenberg se desboca con cinco PDFs, que muera Gotenberg — no El Taller.

| Servicio | Reposo | `mem_limit` sugerido |
|---|---|---|
| n8n | ~400 MB | 1 G |
| Gotenberg | ~150 MB | 2 G |
| Paperless-ngx | ~700 MB | 2 G |
| OSRM (México) | ~2.2 G | 3 G |
| **Suma en reposo** | **~3.5 G** | |

---

## 6. Orden de ejecución

0. **Bajar los techos de Postgres y Redis** (§5.4) — cinco minutos, y
   sin eso lo demás se monta sobre una bomba
1. **n8n + receta de CFDIs** — valor inmediato, y hace que el equipo lo compre
2. **Gotenberg** — mata deuda vieja y un punto de falla, con `mem_limit`
3. **Paperless-ngx** — el papeleo deja de perderse
4. **OSRM** — las rutas dejan de mentir
5. **Etiquetas** — desarrollo chico dentro de El Despacho
6. **Tablero en pared** — colgar El Vigía y armar la vista del día

El SSD antes del 3. **El cable de red no bloquea nada** (§0): se hace
cuando el NUC llegue a su lugar definitivo.

## 7. Lo que hace falta de tu lado

- **El cable de red** conectado (`eno1` sigue caído) y el **SSD de 1 TB**.
- **Visto bueno** a bajar los techos de Postgres y Redis (§5).
- **A qué buzón llegan los CFDIs**, y con qué credenciales leerlo.
- **Marca y modelo de la etiquetera**, para confirmar si habla TSPL o ZPL.
