# El Celador — cómo El Despacho le reporta al monitor del taller

> Implementación del contrato `ADOPTAR-EL-MONITOR.md`. Este archivo es lo que hay
> que leer antes de tocar `lib/salud.py`, `lib/celador.py` o `lib/salud_views.py`.
> Desarrollado por **[NoKo Devs](https://devs.noko.mx)** · © 2026 Learning Center.

El monitor **pregunta; nadie le reporta.** No corre ningún agente nuestro, no se
abrió ningún puerto y no hay que acordarse de nada al desplegar: el monitor pega un
`GET /salud` a la dirección que ya sirve y lee lo que contestemos.

## Qué decirle al taller

| Dato | Valor |
|---|---|
| Camino de salud | `/salud` |
| El Taller | `https://taller.learningcenter.mx/salud` |
| La Gerencia | `https://gerencia.learningcenter.mx/salud` |
| La Recepción | `https://recepcion.learningcenter.mx/salud` — contesta `apagado` (200) hasta S5 |
| Cabecera de credencial | `x-celador: <token>` |
| Código de caída | `503` **solo** cuando el conjunto está en `falla` |

El sitio de marketing (`learningcenter.mx`) corre en HAL y **no** es una app de El
Despacho: se queda en nivel 0 (contesta la raíz, sin `/salud`).

## Nivel 1 — la cara pública

```json
{
  "estado": "ok",
  "version": "2026.08.05",
  "app": "taller",
  "modulos": [
    { "modulo": "base",          "estado": "ok",       "detalle": "3 ms · 6 conexiones" },
    { "modulo": "cola",          "estado": "ok",       "detalle": "0 pendientes" },
    { "modulo": "correo",        "estado": "apagado",  "detalle": "sin canal configurado: los avisos no salen" },
    { "modulo": "ia",            "estado": "ok",       "detalle": "4 de 6 Chalanes con llave" },
    { "modulo": "integraciones", "estado": "degradado","detalle": "1 integración externa con problema" },
    { "modulo": "respaldo",      "estado": "ok",       "detalle": "de ayer" }
  ]
}
```

`app` no está en el contrato, y el monitor ignora lo que no conoce: se manda porque
las tres apps comparten la misma base de datos y el JSON tiene que decir **quién
contestó**.

### Qué mide cada módulo, y por qué está en ese estado

| Módulo | `ok` | `degradado` | `apagado` | `falla` |
|---|---|---|---|---|
| `base` | Postgres contesta `SELECT 1` | — | — | no contesta |
| `cola` | Redis vivo, cola corta | ≥ 200 pendientes, o algo en la bandeja de descartados | — | Redis no contesta |
| `correo` | El Cartero con canal | no se pudo saber el canal | sin canal configurado | — |
| `ia` | ≥ 1 Chalán con llave | no se pudo revisar | ningún Chalán con llave | — |
| `integraciones` | ninguna en rojo | ≥ 1 en rojo en el último chequeo de El Site | — | — |
| `respaldo` | ≤ 4 días | más viejo, o no se pudo determinar | — | — |

Solo dos cosas se reportan **`falla`**: que no responda Postgres o que no responda
Redis. Las dos dejan al despacho inservible (sin Redis no hay cola de eventos ni
límite de intentos de acceso) y las dos justifican una llamada a media noche.

Todo lo demás es a propósito. Una llave de IA que falta, El Cartero sin canal o una
integración externa caída **no despiertan a nadie**: `falla` es la única palabra que
lo hace, y un módulo que grita por una credencial opcional produce una alarma que
nadie puede cerrar. Cuatro de ésas entrenan a ignorar el tablero completo, y cuando
la quinta sea real ya nadie la va a mirar.

Si TODO sale `apagado`, el conjunto también (el caso de La Recepción hasta S5):
está así porque alguien lo decidió, no porque se rompiera.

## Nivel 2 — el desglose con credencial

Con `x-celador: <token>` válido, la misma respuesta trae dos llaves más:

```json
{
  "ia":  { "dias": 30, "llamadas": 249, "fallidas": 25,
           "tokensEntrada": 1220401, "tokensSalida": 1208691, "costoMicro": 1482500 },
  "uso": { "dias": 30, "ingresos": 84, "fallidos": 3, "cuentasActivas": 6,
           "registrandoDesde": "2026-08-08T18:02:11+00:00" }
}
```

- `costoMicro` va en **millonésimas de dólar, enteras**, para no guardar flotantes
  de dinero. Sale de `AnalistaLog`, que ya cobra token por token.
- `ingresos` cuenta **todos** los intentos de acceso que entraron y `fallidos` los
  que no — los dos por separado, porque un día con treinta fallidos y dos entradas
  significa algo muy distinto de treinta entradas.
- Con la credencial, los detalles de `integraciones` y `respaldo` dicen de más: los
  nombres de las plataformas en rojo y el archivo del último respaldo. En abierto va
  nada más el conteo y la antigüedad.

## De dónde sale el token

En este orden, y **sin ninguno de los dos NADIE pasa** — se cierra, no se abre:

1. **Los Ajustes** de La Gerencia, slot **El Celador — token del monitor**
   (`celador_token`, cifrado con La Bóveda). Es el camino normal: regla §4 #3 del
   proyecto, toda credencial se configura desde el GUI.
2. **El entorno**, `CELADOR_TOKEN` en el `.env` de La Sede. Es el respaldo del
   contrato del taller: sirve para arrancar antes de tener acceso al GUI y sobrevive
   si la base no responde, que es justo cuando `/salud` más importa.

Se comparan en tiempo constante con `hmac.compare_digest`: con `==`, el tiempo de la
comparación delata el token letra por letra. El token lo entrega el taller y **es el
mismo para todas las máquinas y desarrollos**, así que se trata como credencial: no
va al repo, no va a un log y no se refleja en un mensaje de error.

## Las tres reglas, y dónde viven

1. **`Cache-Control: no-store`** — lo pone `lib/salud_views.py`. Un monitor cacheado
   miente en verde: un tablero sano con datos de ayer se ve idéntico a uno sano de
   verdad.
2. **Sin datos de negocio en la cara pública.** Cualquiera puede leer `/salud`, así
   que ahí no hay conteos del negocio, ni nombres de proveedores, ni cifras de
   dinero. Todo eso vive detrás de la cabecera.
3. **Un hueco no es un cero.** Lo que no se pudo medir se omite o va en `null`. El
   respaldo que no se pudo consultar dice «no se pudo determinar», no «hace 0 días»;
   `uso.ingresos` va en `null` mientras la bitácora esté vacía, porque un `0` ahí se
   leería como «nadie entró» cuando la verdad es «todavía no se está midiendo».

Nada en `lib/salud.py` lanza: cada módulo se mide en su propio `try` y, si no se
puede medir, lo dice. Un extremo de salud que devuelve 500 no informa, solo agrega
ruido.

## Cuánto cuesta contestar

Cada petición vuelve a medir: unas 15 consultas cortas (todas por índice) y un ping a
Redis. **No hay memo a propósito** — la regla 1 del contrato es que el monitor no vea
datos viejos, y el costo queda por debajo del de `/sign-in`, que también es público y
ahí sí se calcula un hash de contraseña. Si un día hiciera falta amortiguar un flood,
el memo va en `lib/salud.py` (unos segundos), **nunca** en la cabecera HTTP.

## La bitácora de accesos

`cuentas.IntentoAcceso` (tabla `cuentas_intento_acceso`) guarda **cada** intento,
bueno y malo, desde los tres caminos de entrada: los logins de El Taller y La
Gerencia y el SSO de Google. Lo escribe `lib/auditoria_acceso.registrar`, que
**nunca lanza**: la bitácora no puede ser el motivo de que alguien no pueda entrar.

Se guardan dirección y navegador porque sin ellos no se distingue un usuario de
alguien probando contraseñas, pero **no salen de la tabla**: a `/salud` solo viajan
conteos y no hay pantalla que los muestre. (Es la misma razón por la que El Colador
redacta direcciones IP en los reportes de error, que sí se leen en la UI: ahí el
dato no aporta y aquí es el dato.)

## Niveles 3 y 4

- **Nivel 3 (el agente de la máquina)** lo instala el taller desde su propia máquina
  con un guion; no hay nada que hacer en este repo. Solo dos condiciones: que La Sede
  sea alcanzable por la red privada del taller y que el agente **jamás** escuche en
  `0.0.0.0`. Si algún día se apaga un proyecto para siempre, sus contenedores se
  ignoran con `CELADOR_IGNORAR=<prefijo>` en el entorno del agente.
- **Nivel 4 (el MCP del monitor)** es del lado del taller y es de lectura. Si se
  conecta al asistente de este repo, va como **paquete aislado**, fuera del espacio
  de trabajo del gestor de paquetes: dentro rompe la construcción de la imagen con
  `--frozen-lockfile`. Ya existe un servidor MCP propio (`mcp_despacho/`, ver
  `docs/MCP.md`) — son cosas distintas y no se mezclan.

## Lista para revisar antes de decir que ya

Cubierta por `tests/test_salud.py`:

- [x] `GET /salud` contesta JSON con `estado` y `modulos[]`.
- [x] `503` **solo** cuando el estado del conjunto es `falla`.
- [x] Ningún módulo se reporta `falla` por algo que está apagado a propósito.
- [x] `Cache-Control: no-store`.
- [x] La cara pública no trae conteos del negocio, nombres de proveedores ni cifras
      de dinero.
- [x] Un dato que no se pudo medir va como `null` u omitido, **nunca como `0`**.
- [x] El token se compara con `hmac.compare_digest` y **sin token nadie pasa**.
- [x] `CELADOR_TOKEN` está en el entorno (o en La Bóveda) y **no** en el repo.
- [x] Cada intento de ingreso queda registrado, bueno y malo.

## Si hay que agregar un módulo

Una función `_m_<algo>() -> {"modulo", "estado", "detalle"}` en `lib/salud.py` y su
entrada en la tupla de `modulos()`. Antes de elegir el estado, la pregunta es una
sola: **¿esto justifica despertar a alguien?** Si dudas entre `degradado` y `falla`,
es `degradado`.
