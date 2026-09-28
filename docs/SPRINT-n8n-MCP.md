# Sprint n8n + MCP — lo que acordamos en 5 rondas (2026-09-28)

> Handoff del sprint. Se armó en cinco rondas de preguntas con Oscar **antes de
> tocar código**, para que los dos viéramos lo mismo. Si una decisión de aquí se
> quiere cambiar, se cambia en este archivo primero.

## De dónde partimos (medido en el NUC el 2026-09-28, no supuesto)

- **n8n ya existe** en el NUC de Learning Center: `n8nio/n8n:1.70.1`, atado a la
  IP del tailnet (`http://100.121.244.5:5678`), base SQLite en `data/n8n`.
- **La llave de la API está puesta** en La Bóveda (`n8n_api_key`) y n8n contesta.
- **Cero flujos.** Su base no se escribe desde el 2026-08-24.
- **El Chalán ya habla con n8n** (S-NUC-Servicios / S-Papeleo-V1 / S-NUC-Cierre):
  ve, propone prender/apagar/quitar, crea desde 3 recetas (`lib/n8n_plantillas.py`),
  y todo nace apagado. Pantalla en Gerencia → Automatizaciones.
- **El Portavoz tiene 2,192 eventos acumulados** (27-ago → 10-sep) porque falta
  `n8n_webhook_url`. **1,305 son `proyecto.actualizado`** (autoguardado): ruido.
- **`archivo.sh` NO respalda `data/n8n`.** Hoy perder el disco del NUC borraría
  los flujos y sus credenciales.
- **n8n y Paperless estuvieron 10 días sin existir** (18 → 28 de septiembre). El
  NUC se reinició, Docker arrancó antes que Tailscale, no pudieron atarse a
  `100.121.244.5` («cannot assign requested address») y el `docker system prune`
  de La Optimización borró los contenedores fallidos. Nada avisó. Los levantó la
  sesión `eldespacho-a2` el 2026-09-28 a las 12:10 CST; los datos estaban intactos.
- El tailnet **ya tiene certificados HTTPS** habilitados
  (`CertDomains: nuc-learning-center.tailedd04d.ts.net`); no hay `tailscale serve`.

**El hallazgo que definió el plan:** el MCP **nativo** de n8n (instance-level,
`/mcp-server/http`) construye, edita, valida y prueba flujos desde la **2.13/2.14**
(abril 2026); n8n recomienda ≥ 2.18.4 y la estable al 2026-09-28 es la **2.40.7**.
n8n valida lo que arma el modelo (representación TypeScript que compila) antes de
guardarlo — justo lo que en agosto obligó a limitar al Chalán a recetas. Con cero
flujos, el salto de versión mayor cuesta casi nada **ahora**.

## Las decisiones (ronda por ronda)

| Ronda | Pregunta | Decisión de Oscar |
|---|---|---|
| 1 | ¿Quién platica con n8n? | **Ambos, Oscar primero**: Claude Code en HAL por el MCP nativo; después El Chalán para el equipo. |
| 1 | ¿Actualizar n8n? | **Sí, ya**, a la 2.x. |
| 1 | ¿Qué tan metido en El Despacho? | **Escucha y actúa**: recibe eventos y hace cosas hacia afuera. **No escribe datos del negocio** en El Despacho. |
| 2 | Primeras automatizaciones | Las **cuatro**: facturas de proveedor por correo · papeleo por correo → Paperless · avisos · Google Calendar/Sheets. |
| 2 | ¿A quién le hablan? | **Sólo al equipo interno.** Nada a clientes en esta etapa. |
| 2 | Cola vieja del Portavoz | **Archivar sin disparar** (como los 5,198 de agosto). |
| 3 | ¿Quién prende lo que arma Claude? | **Libertad total**: Claude arma, prueba y publica sin preguntar. (Sigue vigente «sólo al equipo».) |
| 3 | El Chalán del equipo | **También crea**, con el constructor nativo; **nace apagada**, un admin la publica. |
| 3 | Canal de avisos | **Push de El Despacho** (El Interfón), por una puerta chica. |
| 3 | IA dentro de n8n | **Sí, con tope de gasto.** |
| 4 | HTTPS | **Nombre del tailnet con certificado** (`https://nuc-learning-center.tailedd04d.ts.net`, Tailscale Serve). No sale a internet. |
| 4 | Cuenta de Google | **Una existente del despacho**: `hola@learningcenter.mx` (la que usa El Cartero). |
| 4 | Llaves de IA | **Pasando por El Despacho** (Los Chalanes; llaves en La Bóveda; bitácora y tope). |
| 4 | Push | **Por permiso o rol, con tope por hora**, categoría «Automatizaciones» silenciable. Nunca a un correo suelto. |
| 5 | Entrega | **Por fases, cada una su deploy.** |
| 5 | La otra sesión | **Claude le escribe antes de tocar el NUC**; el código va en su propio worktree. |
| 5 | Respaldo de flujos | **Base de n8n al respaldo + cada flujo exportado a JSON en el repo.** |
| 5 | Buzones | **`facturas@` (ya existe) para CFDI + `archivo@` (nuevo) para papeleo.** |

### Consecuencia de `facturas@`

`facturas@` es también el remitente de las facturas que se mandan a clientes, así
que sus **respuestas** caen en el mismo buzón que n8n lee. El flujo de CFDI no
puede tratar todo lo que llega como factura de proveedor: sólo toma correos con
**XML que parsee como CFDI y cuyo receptor sea el RFC de Learning Center**. Lo
demás se ignora (y la ingesta ya liga sólo cuando es inequívoco).

## Las fases

| # | Fase | Qué incluye | Toca el NUC |
|---|---|---|---|
| 0 | Terreno | Coordinación con la otra sesión. Respaldo de `data/n8n` antes de nada. Ensayo del salto 1.70→2.40.7 sobre una **copia** de la base, fuera de producción. | Sólo lectura |
| 1 | n8n 2.40.7 + HTTPS | Imagen fija `2.40.7`. **El puerto pasa a `127.0.0.1:5678`** y lo publica `tailscale serve`: así n8n ya no depende de que Tailscale haya levantado para arrancar (la causa de los 10 días caído) y `100.121.244.5:5678` deja de existir. Herramienta de migración de n8n antes. `tailscale serve` con el nombre del tailnet; `N8N_PROTOCOL/HOST/WEBHOOK_URL/N8N_EDITOR_BASE_URL` a https; se retira `N8N_SECURE_COOKIE=false`; `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true`. `archivo.sh` respalda `data/n8n` (la llave de cifrado va aparte). `lib/n8n.py` al modelo «publicar». | Sí |
| 2 | El MCP para Oscar | Activar MCP en n8n + token. Conectar Claude Code en HAL (`claude mcp add --transport http …`), token fuera del repo. Convención: cada flujo que arme Claude lleva la etiqueta **🤖 Claude**. | Sí (config n8n) |
| 3 | La Ventanilla | Puerta de El Despacho para n8n (nombre propuesto). Token en Los Ajustes; sin token → 404; `compare_digest`; se cierra sin token. Dos servicios: **aviso push** (destinatarios por permiso/rol, categoría «Automatizaciones», tope por hora en Redis, `InterfonoEntrega`, `tareas_fondo`) e **IA** (`lib.analistas.analizar` con estación propia, `sanear_contexto`, `AnalistaLog`, tope mensual). GUI en Gerencia → Automatizaciones. Capacidad MCP de lectura para El Chalán. | No |
| 4 | Eventos → n8n | **Va encima de `agent/pendientes-sep`** (sesión `eldespacho-a2`), que ya vacía la cola vieja a un respaldo y deja de encolar mientras no haya `n8n_webhook_url`. Filtro en origen del Portavoz (qué tipos se mandan, configurable en la GUI; fuera `proyecto.actualizado`). Archivar la cola vieja. `n8n_webhook_url` al webhook interno del flujo **recepcionista** (`http://n8n:5678/webhook/…`), que verifica la firma HMAC y reparte por tipo. | Sí |
| 5 | Los 4 casos | Flujos de n8n armados con Oscar por el MCP (no son código del repo; su JSON sí se versiona). | Sí (n8n) |
| 6 | El Chalán construye | El Taller se vuelve **cliente** del MCP de n8n (token en La Bóveda). El Chalán arma **borradores**; **publicar** es una propuesta que confirma quien tenga el permiso (§20). Deploy propio, al final. | No |

## Pasos manuales de Oscar

1. Activar el MCP y generar su token dentro de n8n (después de la fase 1).
2. Cliente OAuth «Interno» en Google Cloud con la dirección de regreso
   `https://nuc-learning-center.tailedd04d.ts.net/rest/oauth2-credential/callback`.
3. Alta del alias `archivo@learningcenter.mx` → `hola@` en Google Admin.
4. Conectar `hola@` en las credenciales de Google dentro de n8n (un clic de
   consentimiento).

## Riesgos ubicados

- **Publicar por API en la 2.x puede no registrar webhooks** (bug conocido del
  cambio «activar → publicar»). Verificar con la versión real; si pasa, esos
  flujos piden un clic en «Publicar».
- **La 2.x bloquea el entorno en los nodos de código** y trae task runners por
  default: la firma del Portavoz se verifica sin leer variables de entorno.
- **Google y el nombre `ts.net`**: hay casos que funcionan; se comprueba en vivo.
- **Las recetas de `lib/n8n_plantillas.py` se verificaron contra la 1.70**: sus
  `typeVersion` hay que revisarlas contra la 2.40.7.
- **Reparto con la sesión `eldespacho-a2`** (acordado por mensaje el 2026-09-28):
  ella toca `lib/portavoz*.py`, `capacidades/lecturas.py` (arregló
  `_h_listar_flujos(args, usuario)`), el guion de arranque
  `infra/scripts/arranque_nuc.sh` + `@reboot`, y las alarmas de «servicio esperado
  que no existe» en `lib/site/` y `lib/salud.py`. Este sprint toca
  `docker-compose.servicios.yml` (bloque n8n), `infra/scripts/archivo.sh`,
  `lib/n8n.py`, `lib/n8n_plantillas.py`, `data/n8n` y `tailscale serve`. Antes de
  desplegar el cambio de dirección de n8n, avisarle: su guion y su alarma sondean
  la dirección.
- **El `docker system prune -f` de `optimizar.sh` borra contenedores en `exited`**:
  cualquier contenedor que quede detenido desaparece en la siguiente corrida.

## Fuentes

- n8n Docs — Connect to n8n MCP server: https://docs.n8n.io/connect/connect-to-n8n-mcp-server
- n8n Blog — n8n's MCP server can now build workflows: https://blog.n8n.io/n8n-mcp-server/
- n8n Docs — Release notes 2.x: https://docs.n8n.io/changelog/release-notes-2.x
- n8n Help Center — Workflow publishing in 2.0: https://support.n8n.io/article/understanding-workflow-publishing-in-n-8-n-2-0
- czlonkowski/n8n-mcp #551 (activar ≠ publicar en 2.0): https://github.com/czlonkowski/n8n-mcp/issues/551
