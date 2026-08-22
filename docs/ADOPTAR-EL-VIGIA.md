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
| `apps/el_site/views_vivo.py` | Los seis paneles + el candado de acceso | **los paneles de negocio** |
| `templates/site/vivo.html` + `vivo/*.html` | La cara | los títulos |
| `infra/vigia/` | Que se abra sola al iniciar sesión | tal cual |

Dependencias: **Redis** (para las series) y el **socket de Docker** montado en
lectura. Nada más. Si no hay Redis, las gráficas salen vacías y el resto funciona.

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

## 4. Las trampas ya pagadas

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

## 5. Cómo se adapta a otro proyecto

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

## 6. Lo que se lleva incluso sin copiar la pantalla

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

## 7. Lo que le falta

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

---

Desarrollado por [NoKo Devs](https://devs.noko.mx) · © 2026 Learning Center
