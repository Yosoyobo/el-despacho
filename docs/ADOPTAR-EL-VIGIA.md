# Adoptar El Vigía

**Una pantalla de pared que dice, en vivo, qué está haciendo un servidor y qué
está haciendo el negocio que corre en él.** Nació para el NUC de Learning Center
(agosto 2026) y está escrita para portarse: Django + HTMX + Tailwind, sin
frameworks, sin build de Node, sin servicios extra.

Este documento es para llevarla a otro proyecto. No es una guía de uso — eso está
en [`infra/vigia/README.md`](../infra/vigia/README.md).

---

## 1. Qué resuelve, y qué no

**Resuelve** el hueco entre «el sistema está caído» y «el sistema va bien»: el
rato largo en que algo se está degradando y nadie se enteraría hasta que duela.
Una pared que se mira de paso convierte eso en algo que se nota sin buscarlo.

**No resuelve** alertas, ni histórico, ni post-mortems. No guarda series largas
(ocho minutos), no manda avisos, no tiene login. Si hace falta eso, hace falta
Prometheus/Grafana y esto no lo sustituye. Lo que da a cambio es que **cabe en una
tarde** y no añade un servicio que a su vez haya que vigilar.

**Cuándo vale la pena:** hay una máquina, hay una pantalla física o alguien que la
puede dejar abierta, y ya existe un Django corriendo ahí. Si falta cualquiera de
las tres, esto es más trabajo que provecho.

---

## 2. Lo que hay que copiar

Cinco piezas. Las de `lib/site/` no dependen de Django (se pueden probar sueltas);
la vista y las plantillas sí.

| Archivo | Qué hace | ¿Se adapta? |
|---|---|---|
| `lib/site/host.py` | CPU, memoria, disco, actividad del disco, presión de memoria | tal cual |
| `lib/site/contenedores.py` | Docker: qué corre y cuánto consume, con nombres del proyecto | **el mapa de nombres** |
| `lib/site/actividad.py` | El flujo de peticiones, leído de los logs de Docker | **los servicios** |
| `lib/site/acciones.py` | Traduce una ruta a lo que la persona está haciendo | **el mapa entero** |
| `lib/site/pulso.py` | La serie corta que dibujan las gráficas (en Redis) | tal cual |
| `lib/site/limpieza.py` | El botón que suelta caché, RAM y disco | **los pasos** |
| `apps/el_site/views_vivo.py` | Los seis paneles + el candado de acceso | **los paneles de negocio** |
| `templates/site/vivo.html` + `vivo/*.html` | La cara | los títulos |
| `infra/vigia/` | Que se abra sola al iniciar sesión | tal cual |

Dependencias: **Redis** (para las series y para recordar la última limpieza) y el
**socket de Docker**. Nada más. Si no hay Redis, las gráficas salen vacías y el
resto funciona.

Ojo con el socket: se monta `:ro` por costumbre, pero **eso no impide escribir por
él** —el botón de La Limpieza lo aprovecha a propósito, ver §4.1— así que montarlo
es entregar el demonio completo al contenedor.

Los montajes que hacen falta en el contenedor que sirve la página:

```yaml
environment:
  SITE_PROC_ROOT: /host/proc
  SITE_DOCKER_SOCK: /var/run/docker.sock
volumes:
  - /proc:/host/proc:ro
  - /var/run/docker.sock:/var/run/docker.sock:ro
  - /:/host:ro          # para leer el disco y encontrar los respaldos
```

---

## 3. Las tres decisiones que no hay que deshacer

Cada una parece una limitación y es a propósito. Las tres se pagaron con un bug.

### 3.1 El acceso son dos candados, no una sesión

```python
def _es_local(request) -> bool:
    host = (request.get_host() or "").split(":")[0].strip().lower()
    if host not in _LOCALES:
        try:
            if not ipaddress.ip_address(host).is_private:
                return False
        except ValueError:
            return False
    return not request.META.get("HTTP_X_FORWARDED_FOR")
```

**No pide sesión porque no puede.** En producción `SESSION_COOKIE_SECURE = True`,
así que la cookie no viaja por `http://localhost` — que es exactamente cómo la abre
el navegador de la propia máquina. Y una pantalla que arranca sola tras un reinicio
no tiene quién escriba una contraseña.

Lo que la protege: el `Host` tiene que ser local **y** la petición no puede traer
`X-Forwarded-For` (que un proxy inverso siempre pone). El segundo candado
sobrevive a que alguien agregue el dominio público a la lista por error. Y devuelve
**404, no 403**: desde fuera la ruta no existe siquiera.

La página es de **sólo lectura**. Ni un POST. Eso es parte del contrato: si algún
día alguien quiere un botón ahí, el modelo de acceso deja de alcanzar.

### 3.2 Cada panel se refresca por su cuenta

Seis peticiones HTMX independientes, cada una a su ritmo (2 s el flujo, 30 s la
puerta a internet). No hay un sondeo del que dependa todo: si el socket de Docker
se cae, ese panel se queda quieto y los demás siguen.

Y **el reloj es local, en JavaScript**. No pasa por el servidor a propósito: si el
servidor se cae, el reloj sigue corriendo y el aviso de «sin respuesta» —que
aparece a los dos fallos seguidos— es lo que delata la caída. Un reloj congelado y
un tablero congelado se ven igual, y no son lo mismo.

### 3.3 Todo lo de fuera va vendoreado

HTMX y DaisyUI se sirven del propio proyecto, no de un CDN. La pantalla arranca
sola cuando la máquina se reinicia, y si en ese momento no hay internet, una
librería que no baja deja la pared congelada **sin decir por qué**.

De DaisyUI sólo se trae `styled.min.css` (139 KB), no `full.css` (3.1 MB): la
diferencia son sus 30 temas, que no se usan porque el tema se define con la paleta
del proyecto.

---

## 4. El botón de La Limpieza

La pantalla dice cómo está la máquina; este botón es lo único que la **mueve**.
Suelta lo que se acumuló —caché, RAM y disco— sin entrar por SSH, que es
justamente lo que se quiere cuando alguien está mirando los anillos desde una
pared o desde el celular. Vive en `lib/site/limpieza.py` + el partial
`templates/site/vivo/_limpieza.html` + la vista `vivo_limpieza`.

**Seis pasos, y cada uno reporta lo suyo:** borrar las llaves del caché de la
aplicación · compactar el registro de Redis y pedirle que devuelva memoria al
sistema · `VACUUM (ANALYZE)` · podar lo que Docker dejó tirado · reciclar los
trabajadores de gunicorn · soltar el caché de páginas del sistema.

### 4.1 Se puede escribir por un socket de Docker montado `:ro`

Y conviene saberlo en las dos direcciones. El `:ro` de
`- /var/run/docker.sock:/var/run/docker.sock:ro` **no es una barrera**: el flag del
montaje limita operaciones del sistema de archivos, y conectarse a un socket no lo
es. Verificado contra un demonio real: crear un exec devolvió 201, arrancarlo 200,
y el comando corrió dentro del contenedor objetivo.

Eso es lo que hace posible este botón sin instalar nada en el host — y también
significa que **quien tenga ese socket tiene el demonio completo**. La barrera de
verdad es que sólo dos funciones escriben por ahí (`podar` y
`reciclar_trabajadores`) y que la vista que las llama está gateada.

### 4.2 La señal a gunicorn va POR DENTRO, nunca con `docker kill`

Es la trampa más caleja del asunto y ya se pagó una vez (§5). `docker kill` le
cuelga al contenedor el marcador de «detenido a mano» **aunque el proceso
sobreviva a la señal**, y desde ese momento `restart: unless-stopped` ya no lo
levanta tras un apagón, sin un solo error en la bitácora. Lo correcto es un `exec`
adentro:

```python
_post(f"/v1.44/containers/{cid}/exec", {"Cmd": ["sh", "-c", "kill -HUP 1"]})
_post(f"/v1.44/exec/{exec_id}/start", {"Detach": True, "Tty": False})
```

Gunicorn lee el HUP como «recárgate»: levanta trabajadores nuevos y a los viejos
les pide que se retiren cuando terminen. No hay corte, y **la petición que disparó
el botón también termina** — el trabajador de gthread espera a sus peticiones en
vuelo antes de irse. El contenedor que atiende esa petición se recicla al final.

Y el worker de eventos **no** entra en la lista aunque comparta la imagen: su PID 1
es Python, y para Python la acción por default de SIGHUP es morir.

### 4.3 Nunca `cache.clear()`, nunca `FLUSHDB`

`RedisCache.clear()` de Django hace `FLUSHDB`. Si el caché comparte base de datos
con una cola de trabajo que no caduca —aquí, la del Portavoz— un `clear()` se
lleva los pendientes sin dejar rastro. Se borran sólo las llaves con el prefijo de
Django, sacando el patrón del propio caché (`cache.make_key("*")` → `:1:*`), así
que un `KEY_PREFIX` futuro lo sigue solo. Las sesiones también se borran y **nadie
se sale de su sesión**: `cached_db` lee de la base cuando el caché no la tiene.

### 4.4 El tiempo es parte del diseño

Gunicorn mata al trabajador que no contesta en 30 s (su default), y quedarse sin
trabajador significa que el usuario ve un error **aunque la limpieza sí haya
corrido**: el peor de los dos mundos. Así que hay un presupuesto de 24 s, y tres
detalles que lo hacen funcionar:

- **No se arranca un paso que no cabe.** El presupuesto se mide contra lo que UNA
  llamada más podría tardar, no contra lo transcurrido; si se midiera así, empezar
  algo justo antes del límite sumaría un tiempo de espera entero por encima.
- **Se APARTA un pedazo para el reciclado** (6 s de los 24). Es el último paso y a
  la vez el único que devuelve RAM: repartir por orden de llegada dejaría que una
  poda lenta se comiera justo el paso que le da sentido al botón.
- **El `VACUUM` va con `statement_timeout` de 10 s, y ese tope se devuelve en un
  `finally` obligatoriamente**: con `CONN_MAX_AGE > 0` la conexión se reusa, y un
  tope olvidado se le aplicaría durante un minuto a consultas que no tienen nada
  que ver — el síntoma sería «a veces un reporte truena».

Y una trampa de redacción, no de tiempo: `pg_size_pretty` devuelve **texto**, así
que comparar «9 MB» con «31 MB» como cadenas dice que la base bajó cuando creció.
Los bytes son para comparar; el texto, para mostrar.

### 4.5 Lo que NO se puede desde el contenedor

Soltar el caché de páginas del sistema (`/proc/sys/vm/drop_caches`), porque `/proc`
va montado en sólo-lectura y dejarlo escribible sólo para esto le abriría al
contenedor todos los parámetros del kernel. El paso se reporta como «no se puede
desde aquí» en vez de fingir que se hizo; el guion nocturno, que corre en el host
como root, sí lo suelta. **Reportar un hueco como hueco es la mitad del valor de un
tablero.**

### 4.6 La puerta, cuando la pantalla no tiene sesión

Una pared sin sesión no puede traer token de CSRF: la cookie es `Secure` y no viaja
por `http://localhost`. La salida no es apagar la comprobación, es partirla en dos:

- **Desde la máquina** (la pared): se exige la cabecera `HX-Request`. Un formulario
  de otro sitio SÍ puede apuntar a `http://localhost:PUERTO/…` desde el navegador
  de esa misma máquina, pero **no puede poner cabeceras propias**, y un `fetch` que
  sí las pone choca con el permiso previo de CORS que el servidor nunca concede.
- **Desde la aplicación con sesión**: el token, como en cualquier otro POST. La
  vista está exenta a nivel de decorador, así que la comprobación se invoca a mano
  —la **de Django**, no una propia— para no acabar con dos versiones de la regla.

Y la pregunta de confirmación va **sólo fuera de la pared**: `hx-confirm` usa
`window.confirm`, que **bloquea el JavaScript de la página**. Si alguien la abre en
el muro y se va, la pantalla se queda congelada —sin refrescar un solo panel y sin
poder ni avisar de que está congelada— hasta que alguien vuelva. En una pantalla
que se pica físicamente, un toque ya es deliberado; y lo peor que puede pasar es
una limpieza de más, que no borra nada.

### 4.7 El resultado se guarda, no se devuelve

El reporte se escribe en Redis y el partial lo LEE en cada pintado. Si viviera sólo
en la respuesta del POST, el siguiente refresco automático lo borraría de la
pantalla a los pocos segundos. Como efecto secundario, las dos pantallas cuentan la
misma historia y cualquiera puede ver qué se hizo y cuándo.

---

## 5. Las trampas ya pagadas

Están aquí para no volver a pagarlas. Todas se descubrieron **mirando la pantalla**,
no leyendo el código, y todas pasaban las pruebas.

**Del protocolo de Docker:**

- El endpoint `/containers/{id}/logs` devuelve un stream **multiplexado** cuando el
  contenedor no tiene TTY: tramas de 8 bytes `[tipo,0,0,0,tamaño BE(4)]`. Leerlo
  plano mete bytes de basura al inicio de cada renglón.
- Cada app escribe con su propio reloj (gunicorn en hora local con offset, Caddy en
  UTC). Se piden los logs con `timestamps=1` y **la marca de Docker es el reloj
  común**; mezclarlos por la propia es pedir un desorden silencioso.
- `/stats?stream=false` **tarda ~1 segundo por contenedor** porque toma dos
  muestras para el CPU. Con seis son seis segundos, inservible para algo «en vivo».
  `one-shot=true` responde al instante pero deja `precpu_stats` en cero: hay que
  guardar la muestra anterior en el proceso y calcular el delta, que es lo que hace
  `docker stats`. Y la memoria descuenta `inactive_file`, o se reporta como usado
  el caché que el kernel puede soltar.

**De Django y sus plantillas:**

- **`{% static %}` a un archivo inexistente es un 500 en producción** —
  `CompressedManifestStaticFilesStorage` revienta al RENDERIZAR— y **no lo caza ni
  la suite** (en pruebas el storage es el simple) **ni un smoke test** que no
  renderice la página. Candado:
  `tests/site/test_vigia.py::TestLosEstaticosQueReferenciaExisten`.
- **Django no silencia los ARGUMENTOS de filtro.** `{{ x|add:y.z }}` con `y.z`
  ausente levanta `VariableDoesNotExist` y tumba la página; `{{ y.z }}` a secas
  sale vacío. Pasó con un dict que en su primera lectura no traía la llave, o sea
  que fallaba **sólo en el primer refresco tras recrear el contenedor**. Las
  cadenas se arman en la vista.
- **`|default` se aplica a valores falsy, y `0.0` es falsy.** Un contenedor en
  reposo mostraba «—» como si no se pudiera medir. `default_if_none` es el que
  distingue «cero» de «no se sabe».
- **`{# … #}` multilínea se renderiza como texto.** En este proyecto hay un candado
  (`test_no_renderiza_comentarios`) y **hay que correrlo DESPUÉS de tocar
  plantillas, no antes**: en el sprint original cazó cuatro y uno llegó a la
  pantalla por correrlo demasiado pronto.
- **El grid del panel manda sobre el del esqueleto.** HTMX reemplaza el placeholder
  por el partial, así que cambiar las columnas en la página no sirve.

**De CSS:**

- **`display:none` no aplica a `<col>`.** La especificación sólo le deja `width`,
  `visibility`, `background` y `border`. Una columna «escondida» seguía reservando
  su ancho, la tabla medía más que el teléfono, y **ese desborde hacía que el grid
  de arriba se calculara sobre el ancho desbordado**. Los anchos van en las celdas
  (con `table-fixed` el navegador toma los de la primera fila).
- **Un desborde en una esquina descuadra la página entera.** Ver el punto anterior:
  cuatro anillos salían apretujados en fila por una tabla ancha en otro panel.
- **Los componentes de una librería no siguen un tema propio.** El `<progress>` de
  DaisyUI colorea su riel con la variable de SU tema, que no cambia con el
  `data-tema` de esta pantalla — en claro seguía oscuro. Lo que tenga que cambiar
  de color con el tema se hace con tokens propios.

**Del método:**

- **Una pantalla se revisa MIRÁNDOLA.** Sin estar enfrente: Chrome headless por la
  red interna, con `--virtual-time-budget=20000` para que carguen los paneles HTMX.
- **Chrome headless tiene un viewport mínimo de 500 px**: `--window-size=390`
  renderiza a 500 y **recorta la imagen**, y ese recorte se lee como desborde. Para
  medir de verdad hay que inyectar un detector en la página que reporte
  `scrollWidth` y **qué elemento** se sale. Antes de arreglar un desborde, medirlo.

---

## 6. Cómo se adapta a otro proyecto

Cuatro cosas, en este orden.

**1. Los nombres de las piezas** (`contenedores.py`). Los nombres de contenedor son
estériles y no le dicen nada a quien mira la pared. Cada pieza lleva su nombre y su
**oficio**, porque el nombre solo tampoco explica:

```python
_PIEZAS = (
    ("el-taller",  "El Taller",    "donde trabaja el equipo"),
    ("postgres",   "El Archivero", "guarda todo"),
    ("redis",      "La Libreta",   "notas rápidas y la cola"),
)
```

Una pieza sin bautizar sale con su nombre técnico, feo y visible — que es la señal
correcta para venir a agregarla, no un nombre inventado que oculte el hueco.

**2. El mapa de acciones** (`acciones.py`). Es lo que convierte una lista de URLs
en **lo que la gente está haciendo**, y es lo que hace la pantalla legible desde
tres metros:

```python
(r"^/proyectos/kanban", "Tablero de proyectos"),
(r"^/proyectos/\d+/",   "Ficha de proyecto"),
(r"^/proyectos/",       "Proyectos"),
```

Se recorre **en orden**, de lo específico a lo general, así una ruta nueva cae en
la regla de su módulo. Si nada casa, sale la ruta cruda: inventar un nombre para
algo que no se reconoce sería peor que enseñar la verdad.

**3. El panel de negocio** (`views_vivo._trabajo_del_despacho`). Es la parte que no
se puede copiar: son las cifras que importan en ESE negocio. En El Despacho son
proyectos vivos, por cotizar, tareas atrasadas, por cobrar y perdidos del mes. En
otro proyecto serán otras. La regla que sí se copia: **primero el negocio, después
la infraestructura** — en una pared de taller, cuántos proyectos hay vivos importa
más que la cola de una tabla.

**4. Los hosts locales** (`views_vivo._LOCALES`) y la variable `VIGIA_HOSTS` para
sumar otros. **El dominio público jamás va ahí.**

---

## 7. Lo que se lleva incluso sin copiar la pantalla

Tres piezas sirven solas:

- **`host.presion_memoria()`** con un colchón declarado. Existe para que nadie
  tenga que volver a un servidor headless a adivinar si le falta memoria: el anillo
  se pinta **por el colchón, no por el porcentaje** (un 70% de 15 G deja 4.5 G y
  está perfecto; un 70% de 4 G no), y lo mismo reporta el extremo de salud. Se
  reporta **degradado**, no falla, cuando el colchón se estrecha: el sistema sigue
  de pie y lo que hace falta es planear, no correr. Una alarma que despierta a
  alguien sin que haya nada que hacer esa noche entrena a ignorar el tablero.
- **`pulso.py`**: series cortas en Redis, escritas por quien las lee. No hay cron
  muestreando, así que si nadie mira no se acumula nada. Y **la escala es la
  decisión**: un eje de 0 a 100 es honesto para un porcentaje pero aplasta lo que
  se mueve poco (una memoria oscilando medio punto sale recta); `relieve=True`
  ajusta el eje a la propia serie y no engaña, porque el número absoluto va al
  lado. Un hueco **no** se dibuja como cero: diría «bajó a 0».
- **`actividad.py`**: leer el flujo de los logs en vez de instrumentar la
  aplicación. Un middleware sería una escritura extra en el camino caliente de cada
  petición para alimentar una pantalla que casi nadie mira; los logs ya están
  escritos y el socket ya está montado.

---

## 8. Lo que le falta

Dicho para que nadie lo descubra en producción:

- **No muestra los crons corriendo.** No hay registro de sus corridas más allá de
  sus propios logs.
- **El flujo lee las últimas N líneas por servicio**, así que en un pico muy alto
  puede perder algo entre refrescos. Para una pared está bien; para auditar, no.
- **Las llamadas a la IA no distinguen persona de cron.** Los avisos automáticos se
  cargan al usuario destinatario, así que en la pared parecen peticiones suyas.
  Arreglarlo pide un campo nuevo en el log de IA.
- **Depende de que la máquina tenga sesión de escritorio.** Si se vuelve headless,
  la pantalla se ve desde otra máquina de la red interna, que ya está permitido.
- **El botón de La Limpieza no suelta el caché de páginas del sistema** (`/proc` va
  en sólo-lectura, ver §4.5), y su antes/después de RAM se mide al terminar, cuando
  los trabajadores nuevos apenas están tomando el relevo: la memoria baja unos
  segundos DESPUÉS del número que se ve. El paso lo dice con palabras.

---

Desarrollado por [NoKo Devs](https://devs.noko.mx) · © 2026 Learning Center
