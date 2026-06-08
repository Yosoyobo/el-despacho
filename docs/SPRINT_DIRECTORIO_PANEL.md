# SPRINT `S-Directorio-Panel-V1` — Handoff

> **Estado:** ✅ IMPLEMENTADO (2026-06-08). Origen: Oscar pidió replicar el
> layout de gestión de usuarios de La Cocina/Stove, adaptado a El Despacho.
> Entregado junto al hotfix del Buzón two-pane y el toggle Ocultar/Mostrar de
> Estados de proyecto y de Buzón. Pendiente de este sprint: **El Resguardo**
> (backup offsite a DO, §12) queda sin implementar — requiere setup manual en
> el Droplet (rclone + Space + llaves); se hace cuando Oscar lo habilite.

## Objetivo

Rediseñar **La Gerencia → El Directorio** a un panel tipo TailAdmin:
**lista compacta** (chips de Proveedor IA + badge de rol + gasto IA 30d) y
un **modal único de detalle con tabs** (Datos · IA · Permisos), donde el
super_admin edita datos, **fija los Chalanes/modelos por estación de
cualquier usuario**, ve el consumo de IA y selecciona permisos granulares.

## Decisiones congeladas (confirmadas por Oscar)

1. **Sin Tiers ni Caja Chica/Fichas** (El Despacho no es SaaS, regla §2).
   Equivalente que SÍ se construye: **presupuesto IA en USD por usuario** +
   **panel de uso** (7/30/90 d).
2. **Política al rebasar el presupuesto: configurable POR USUARIO desde el
   modal** — `alertar` (default) o `topar`. No es global.
3. **UI: lista + un modal único** con tabs (no drawer). La selección granular
   de permisos vive como tab del modal.
4. **El super_admin edita la IA (ChalanAsignado) de cualquier usuario** desde
   El Directorio. El autoservicio en El Taller `/perfil/chalanes/` se conserva.
5. **Fila compacta** muestra: chips de Proveedor IA · badge de rol primario ·
   gasto IA 30d. (Permisos solo en el modal.)

### Pendiente de confirmar al arrancar (no bloquea)
- Chip de fila: "Auto" (sin overrides) vs "Mixto" (estaciones con proveedores
  distintos) — propuesta: mostrar ambos estados honestamente.
- Tab IA: dropdown de **modelo editable** por estación (como el screenshot de
  Stove) vs solo proveedor con modelo al default del adapter.

## Fuera de alcance V1
- Cuotas por nº de llamadas/tokens (se eligió presupuesto USD).
- Edición de IA por `dueno` (solo `super_admin`; ampliable en V2).
- Drawer lateral.
- Tope global del despacho (solo per-usuario).

---

## Estado actual del código (radiografía previa)

- **Lista usuarios:** `la-gerencia/apps/el_directorio/views.py::lista` (~L19-53)
  + `templates/directorio/lista.html` + `_filas.html`. Columnas: nombre, email,
  rol, estado, acciones. Todo en páginas separadas (sin modal/drawer).
- **Permisos granulares:** `views.py` (~L114-165) + `templates/directorio/permisos.html`.
  Grilla módulo×acción → `PermisoUsuario` (`cuentas/models/permiso_usuario.py`,
  `update_or_create(usuario,modulo,permiso,{activo})`). UniqueConstraint
  (usuario,modulo,permiso). Solo super_admin.
- **Roles personalizados:** `cuentas/models/rol.py` (`Rol.permisos` JSON
  `{modulo:[acciones]}`, `sistema` bool) + `Usuario.roles_extra` M2M. UI
  `/directorio/roles/` y `/directorio/<id>/roles-extra` (views.py ~L168-281).
- **Override IA por usuario (¡ya existe!):** `chalanes/models/chalan_asignado.py`
  `ChalanAsignado(usuario, estacion, proveedor, modelo)` UniqueConstraint
  (usuario,estacion). Resolución en `lib/analistas/registry.py::cadena_de(estacion,
  usuario_id)`: ChalanAsignado → CuadroChalanes → CadenaFallback → hardcoded.
  UI autoservicio: `el-taller/apps/perfil_chalanes/views.py` (`/perfil/chalanes/`).
  Estaciones: `chalanes/estaciones.py` (9: cotizaciones, gastos, comunicacion,
  precio, cliente, dictado, taller_chat, ocr_recibo, smoke).
- **Log IA con usuario:** `ajustes/models/analistas_log.py` tiene `actor` FK +
  `costo_usd_estimado`, `prompt_tokens`, `completion_tokens`, `provider`,
  `creado_en`. → gasto por usuario es posible. Helpers en `lib/analistas/stats.py`
  (`estadisticas_proveedores`, `tarjetas_chalanes`, `resumen_global`).
- **Inventario módulos×acciones** (`lib/permisos_defaults.py::DEFAULTS_POR_ROL`,
  `lib/permisos.py::puede`): cartera, proyectos, pizarron, buzon, recados,
  tesoreria, dictado, contaduria, catalogo, cotizaciones, facturacion, chalan,
  gerencia.

---

## Plan de implementación

### 1. Modelos / migraciones
Nuevo `cuentas/models/presupuesto_ia.py`:
```
PresupuestoIA
  usuario        OneToOne(Usuario, CASCADE)
  tope_usd       Decimal(10,2)   # 0 = sin tope
  politica       Char choices: "alertar" | "topar"   default "alertar"
  activo         Bool default True
  alerta_mes     Char(7) blank   # "YYYY-MM" deduplica la alerta
  actualizado_por FK(Usuario, SET_NULL) ; actualizado_en auto_now
```
- Migración `cuentas/00XX_presupuesto_ia.py` (solo tabla, sin seed; ausencia de
  fila = sin tope).
- NO se toca ChalanAsignado, PermisoUsuario, Rol ni AnalistaLog.

### 2. Servicios / helpers (raíz, reusables)
`chalanes/services.py` (nuevo, patrón shared §6):
- `overrides_de(usuario) -> {estacion:(proveedor,modelo)}`
- `set_override(usuario, estacion, proveedor, modelo, actor)`
- `forzar_proveedor(usuario, proveedor, actor)` → upsert las 9 estaciones al
  mismo proveedor (modelo default del adapter). Emite Portavoz.
- `limpiar_overrides(usuario, actor)` → borra ChalanAsignado (vuelve a "Auto").
- `proveedores_configurados() -> [str]` → solo proveedores con llave válida
  (`adapter.esta_configurado()`), para pintar los chips.
- *Refactor:* `perfil_chalanes/views.py::guardar()` pasa a usar estos helpers (DRY).

`lib/analistas/stats.py` (extender):
- `uso_por_usuario(usuario_id) -> {"7d":{llamadas,tokens,costo_usd},"30d":...,"90d":...}`
  filtrando `AnalistaLog.actor_id`.
- `gasto_mes_usuario(usuario_id) -> Decimal` (mes en curso, para presupuesto).

`cuentas/servicios_presupuesto.py`:
- `evaluar(usuario) -> {tope, gastado_mes, rebasado, porcentaje}`.

### 3. Gate de presupuesto (lo que agrega "topar")
- En `lib/analistas.analizar(...)` (que ya recibe `usuario_id`): ANTES de
  invocar al Chalán, si `PresupuestoIA(activo, tope_usd>0, politica="topar")` y
  `gasto_mes_usuario >= tope_usd` → levanta **`PresupuestoIAExcedido`** sin
  llamar al modelo. `politica="alertar"` NO usa el gate.
- `gasto_mes_usuario` cacheado ~60s por usuario en Redis (no pegarle a
  AnalistaLog en cada llamada).
- **Callers** (Dictado, chat El Chalán, OCR) capturan `PresupuestoIAExcedido` y
  muestran mensaje claro ("Este usuario alcanzó su tope de IA del mes; el admin
  puede ampliarlo en El Directorio"). Nunca rompe la operación no-IA.
- Emite `presupuesto_ia.topado` al rechazar.

### 4. Alerta (cron, para AMBAS políticas)
- Command `cuentas/management/commands/evaluar_presupuestos_ia.py`: recorre
  `PresupuestoIA(activo, tope>0)`, compara gasto_mes vs tope; si rebasa y
  `alerta_mes != mes_actual` → emite `presupuesto_ia.rebasado` + push Interfón a
  super_admin/dueño, setea `alerta_mes`. Idempotente.
- Crontab diario en La Sede (§10).
- En la lista el semáforo rojo se calcula al vuelo (no depende del cron).

### 5. Backend — El Directorio (todos super_admin)
Ampliar `la-gerencia/apps/el_directorio/views.py`:
- `lista`: añadir por usuario `{proveedor_efectivo, chips, gasto_30d_usd, rebasado}`.
  `proveedor_efectivo` = uniforme / "Auto" (sin overrides) / "Mixto".
- Modal con tabs lazy (patrón Wave 5 `#modal-slot` + `_componentes_tailadmin/_tabs.html`):
  - `GET /directorio/<id>/panel/` → shell + tab **Datos** (reusa `UsuarioForm`).
  - `GET /directorio/<id>/panel/ia/` (HTMX) → tab **IA**: chips proveedor, tabla
    9 estaciones (default global + dropdown proveedor + modelo), panel uso
    7/30/90 d, input presupuesto USD + segmentado "Al rebasar: Alertar/Topar" +
    semáforo.
  - `POST /directorio/<id>/panel/ia/` → guarda overrides por estación.
  - `GET /directorio/<id>/panel/permisos/` (HTMX) → tab **Permisos**: grilla
    módulo×acción (reusa lógica L114-165) + checkboxes roles_extra (L168-281).
  - `POST /directorio/<id>/panel/permisos/` → persiste PermisoUsuario + roles_extra.set().
  - Acciones rápidas: `POST .../ia/forzar/` (proveedor), `POST .../ia/auto/`,
    `POST .../presupuesto/` (tope+politica).
  - Patrón HTMX: GET HTMX → fragmento; POST éxito → 204 + HX-Redirect/HX-Trigger
    para refrescar fila; POST inválido → reinyecta fragmento con errores.
- Gating: `@requires_role("super_admin")` en todo lo nuevo.

### 6. UI / Templates
- `templates/directorio/lista.html` + `_filas.html`: fila clickeable (modal
  HTMX), columna chips IA (proveedores_configurados, activo resaltado), badge
  rol, gasto 30d, punto rojo si rebasado.
- `_modal_panel.html` (shell + `_tabs.html`), `_tab_datos.html`, `_tab_ia.html`,
  `_tab_permisos.html`. Tabs IA/Permisos con `hx-get` lazy.
- Reutiliza `_form_campo`, `_switch`, `_kpi_card_hero` (uso IA), `_empty_state`.
  Vanilla + HTMX, sin libs nuevas.

### 7. Eventos Portavoz nuevos (`lib/portavoz_eventos.py`)
`usuario.chalan_overrides_forzados`, `usuario.chalan_override_actualizado`,
`usuario.presupuesto_ia_actualizado`, `presupuesto_ia.rebasado`,
`presupuesto_ia.topado`.

### 8. Tests (`tests/gerencia/test_directorio_panel.py`)
Modal carga + tabs lazy; `forzar_proveedor` crea 9 ChalanAsignado; `auto` los
borra; presupuesto guarda (tope+politica); permisos+roles_extra persisten desde
el modal; gating no-super_admin → 403; `uso_por_usuario` agrega por `actor`;
`politica="topar"` + gasto≥tope → `analizar` levanta `PresupuestoIAExcedido` y
NO registra AnalistaLog de llamada real; `politica="alertar"` con gasto≥tope →
la llamada procede; `evaluar_presupuestos_ia` emite una sola vez por mes (dedupe
`alerta_mes`); gate respeta el caché. Fixture on_commit inmediato (Bug E §14).
Revisar `tests/urls_gerencia.py` si algún `{% url %}` nuevo lo requiere.

### 9. Cierre (memorias del proyecto)
- Actualizar `docs/DOC_05_MANUAL_USUARIO.md` ANTES del push (regla §10):
  subsección "Panel de usuarios" en lenguaje llano.
- Bump `lib/version.py` (AÑO.MES.ITERACIÓN).
- Footer "Desarrollado por NoKo Devs" intacto.

### 10. Post-deploy
- Migración corre en El Mensajero.
- Crontab `evaluar_presupuestos_ia` diario en La Sede.
- Verificar Tailwind (chips/semáforo: utilities en safelist).

### 11. Deuda diseñada (V2)
- Cuota por nº de llamadas/tokens (hoy solo USD).
- Tope global del despacho además del per-usuario.
- Edición de IA por `dueno`.
- Surface de "usuarios sobre presupuesto" en El Site (panel Chalanes).
- Resumen de permisos en la fila (hoy solo en modal).

---

## 12. Extra (infra, paralelo) — El Resguardo: backup offsite a DigitalOcean

**Objetivo:** tercer destino offsite del backup, **tratado igual que HAL** (§16),
para sobrevivir a pérdida total de La Sede + HAL.

- **Destino:** DigitalOcean **Spaces** (S3-compatible).
- **Mecánica (paridad 1:1 con HAL):** mismo origen (`$OUT_DIR/` completo, db +
  credenciales); reconciliación sin `--delete` (sube solo lo faltante; corrida
  saltada se pone al día); retención `RESGUARDO_RETENER=30` (= `HAL_RETENER`),
  rotando por serie. Local sigue en 5.
- **Backfill de arranque:** como DO hoy está vacío, la primera corrida (o un
  `--backfill` manual) copia el set existente de **HAL → DO** vía rclone (remoto
  SFTP a HAL por Tailscale + remoto S3 a DO), para que DO tenga ya lo mismo que
  HAL. Después ambas se mantienen desde el mismo origen.
- **Disparo:** SOLO por el cron existente de `archivo.sh` (cada 3 días, §10).
  Hook best-effort al final (tras el rsync a HAL, junto a `optimizar.sh`),
  `SKIP_RESGUARDO=1` para saltar. Si DO falla, local y HAL siguen válidos.
- **Implementación:** `infra/scripts/resguardo.sh` (nombre "El Resguardo")
  usando `rclone` (S3 remote a DO + SFTP remote a HAL para el backfill); hook en
  `infra/scripts/archivo.sh` tras la sección HAL.
- **Trazabilidad:** registrar en `site_backup_remoto` con plataforma `do_spaces`
  reusando `registrar_backup_remoto` (§16) → aparece en El Site → Servicios
  internos junto al de HAL.
- **Credenciales (en `.env` de La Sede, no Bóveda — es bash):** `DO_SPACES_KEY`,
  `DO_SPACES_SECRET`, `DO_SPACES_BUCKET`, `DO_SPACES_REGION`, `DO_SPACES_ENDPOINT`.
- **Post-deploy:** crear el Space + llaves en DO, poblar vars en `.env`,
  instalar/configurar `rclone` en el Droplet con los dos remotes (HAL-SFTP +
  DO-S3). El cron lo dispara; primera corrida hace backfill.

---

## Apéndice — Hotfix Buzón two-pane (hecho aparte, 2026-06-08)

No es parte de este sprint. Tras el deploy de S-Estados-Buzón, la lista del
Buzón en El Taller (`el-taller/templates/buzon/lista.html` + `_filas.html`)
apilaba la tabla ancha completa + el panel debajo (pantalla entera). Se
reescribió a layout tipo Gmail de **dos columnas** (lista compacta izq ~40%
scroll propio · panel `#buzon-pane` der ~60% sticky; en móvil colapsa a una
columna). El Buzón admin de La Gerencia no se tocó (abre detalle en página
aparte). Sin cambios de vista ni migraciones. 31 tests del Buzón verdes.
