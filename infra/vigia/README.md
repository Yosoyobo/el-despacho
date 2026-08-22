# El Vigía — la pantalla de pared del NUC

Una página a pantalla completa, en el navegador **del propio NUC**, que muestra en
vivo: el fierro (CPU, memoria, disco, contenedores), las peticiones conforme
llegan, el consumo por contenedor y el trabajo que el sistema está haciendo por el
despacho (Los Chalanes, la cola de El Portavoz, el respaldo, El Almacén).

    http://localhost:8201/site/vivo/

## Por qué no se puede abrir desde internet

**No pide sesión, y no es un descuido.** En producción `SESSION_COOKIE_SECURE` está
en `True`, así que la cookie de sesión no viaja por `http://localhost` — que es
exactamente cómo la abre el navegador del NUC. Y una pantalla de kiosco que pidiera
login tendría que loguearse sola tras cada reinicio, lo cual es peor que no pedirlo.

Lo que la protege son **dos candados a la vez**, los dos en
`la-gerencia/apps/el_site/views_vivo.py`:

1. El `Host` de la petición tiene que ser local (loopback, la LAN o el tailnet). El
   dominio público no está en la lista, así que `gerencia.learningcenter.mx/site/vivo/`
   responde **404** — desde fuera la ruta no existe siquiera.
2. La petición **no puede traer `X-Forwarded-For`**. El Portero siempre lo pone al
   proxear, así que su ausencia significa «llegó directo al contenedor». Es el
   candado que sobrevive a que alguien, algún día, agregue el dominio a la lista.

La página es de **sólo lectura**: no hay un solo POST.

## Instalar el kiosco

En el NUC, **con la sesión de escritorio abierta** (no por SSH a secas):

    bash /mnt/el-despacho/infra/vigia/instalar.sh --autologin

Eso deja tres cosas:

| Qué | Dónde | Para qué |
|---|---|---|
| Autostart del escritorio | `~/.config/autostart/vigia.desktop` | abre el navegador en kiosco al iniciar sesión |
| Ahorro de pantalla y bloqueo apagados | `gsettings` de la sesión | que la pared no se ponga negra a los diez minutos |
| Inicio de sesión automático | `/etc/gdm3/custom.conf` | que la pantalla **vuelva sola** tras un corte de luz |

En **este** NUC el autologin ya venía activado de fábrica
(`AutomaticLoginEnable=True`, usuario `linux`), así que `--autologin` no hace falta:
la pantalla ya vuelve sola. Se comprueba con
`grep AutomaticLogin /etc/gdm3/custom.conf`.

Sin `--autologin` la pantalla vuelve sólo cuando alguien escribe la contraseña.
**Es el precio de que vuelva sola:** quien tenga acceso físico al NUC se encuentra
una sesión abierta. La pantalla en sí no deja hacer nada (es de sólo lectura y el
navegador va en kiosco, sin barra de direcciones), pero la decisión es real.

Para deshacerlo:

    bash /mnt/el-despacho/infra/vigia/instalar.sh --quitar
    sudo sed -i '/^AutomaticLogin/d' /etc/gdm3/custom.conf

## Lo que hace el lanzador y no es obvio

`vigia-kiosco.sh` no sólo abre el navegador:

- **Espera a que la aplicación conteste** antes de abrir. Tras un reinicio el
  escritorio está listo mucho antes que Docker; si abriera de inmediato, la pared
  se quedaría con una página de error hasta que alguien la recargara — y nadie
  recarga una pared. Espera hasta 5 minutos (`VIGIA_ESPERA_MAX`) y, si no
  responde, abre igual: el propio Vigía avisa en pantalla cuando no hay respuesta.
- **Reabre el navegador si se muere.** Un kiosco tiene que aguantar solo.
- **Deja bitácora** en `~/.vigia.log`. Es el primer lugar donde mirar si la
  pantalla no abrió.

Prefiere Chrome o Chromium (su `--kiosk` es el más limpio) y cae a **Firefox**, que
es el que viene instalado en este NUC. Para salir del kiosco: `Alt+F4`, o
`Ctrl+Alt+F3` para una consola.

Con Firefox usa `--new-instance` y un **perfil propio** (`~/.vigia-firefox`), y eso
no es cosmético: si ya hay un Firefox abierto en la sesión, un `firefox <url>` a
secas le pasa la URL a esa instancia y **termina al instante**, con lo que el bucle
de «reabre si se muere» se vuelve una reapertura cada cinco segundos para siempre.
Pasó al probarlo. Por eso el bucle además lleva freno: tres arranques de menos de
diez segundos y el reintento se separa a un minuto, dejando dicho en la bitácora
qué está pasando. Una pared parpadeando toda la noche es peor que una apagada.

## Variables

| Variable | Default | Para qué |
|---|---|---|
| `VIGIA_URL` | `http://localhost:8201/site/vivo/` | qué abre el kiosco |
| `VIGIA_ESPERA_MAX` | `300` | segundos que aguanta esperando la app antes de abrir igual |
| `VIGIA_LOG` | `~/.vigia.log` | bitácora del lanzador |
| `VIGIA_HOSTS` | — | hosts extra que pueden pedir la página (coma-separados). El dominio público **jamás** va aquí |

---

Desarrollado por [NoKo Devs](https://devs.noko.mx) · © 2026 Learning Center
