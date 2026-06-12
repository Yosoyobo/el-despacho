# RUNBOOK — Plan Menaje (mudar datos a La Bodega)

Ejecutar SOLO cuando OBO active el Plan Menaje y S-Menaje-Prep esté
cerrado. Tiempo estimado de ventana: **20-40 min de downtime**, ideal
fuera de horario del despacho. Con 5 usuarios internos, basta avisar
en Los Recados.

Prerrequisitos verificables antes de agendar:
- [ ] S-Menaje-Prep cerrado (perfiles compose, env parametrizado,
      Redis con password, scripts bi-server, ensayo en HAL verde).
- [ ] Backup de anoche verificado en HAL (restaurable, no solo presente).

---

## Fase 0 — Provisión de La Bodega (sin downtime, días antes)

1. Crear droplet DO 1 GB, **misma región que La Sede**, dentro de la
   misma VPC. Anotar IP privada (`10.x.x.x`).
2. Hardening base (mismo patrón que La Sede): usuario no-root, SSH por
   llave, ufw/firewall.
3. DO Cloud Firewall "la-bodega":
   - Inbound: 5432 y 6379 SOLO desde IP privada de La Sede ·
     22 solo desde IPs de administración.
   - Outbound: libre (updates, GHCR).
4. Instalar Docker + Compose. Correr `infra/scripts/habilitar_swap.sh`
   y `infra/scripts/habilitar_zram.sh` (de S-Menaje-Prep E8).
5. Clonar repo, `.env` mínimo de Bodega (`POSTGRES_PASSWORD`,
   `REDIS_PASSWORD` — los MISMOS que producción actual).
6. `docker compose --profile bodega up -d` con volúmenes vacíos.
   Verificar `pg_isready` y `redis-cli -a PASS ping` **desde La Sede**
   vía IP privada. Si esto no responde, parar aquí — es firewall/VPC.
7. Aplicar snippet `pg_hba.conf` (rango VPC) preparado en E3.
8. Opcional recomendado: subir `shared_buffers` a 128 MB en La Bodega
   (tiene la RAM para sí sola).

## Fase 1 — Congelar (inicia downtime)

1. Avisar en Los Recados. Esperar a que el portavoz-worker drene su
   cola (ver El Site / logs).
2. En La Sede: `docker compose stop la-gerencia el-taller portavoz-worker`
   (Caddy puede quedarse arriba sirviendo 503).

## Fase 2 — Mudar los datos

1. Dump final:
   `pg_dump -Fc` de la base completa → `menaje_final.dump`.
2. Redis: los datos son cache + colas ya drenadas. **Decisión: no se
   migra RDB; se arranca limpio.** (Si hubiera algo persistente
   inesperado, `--rdb` como plan B.)
3. Copiar dump a La Bodega por la VPC (`scp` a la IP privada).
4. Restore: `pg_restore -d despacho --no-owner` en el Postgres de
   La Bodega.
5. Verificación de integridad mínima:
   - `SELECT count(*)` en 4-5 tablas grandes vs. el conteo en La Sede.
   - Último `Asiento` y último `Mensaje` presentes.

## Fase 3 — Cutover

1. En `.env` de La Sede: descomentar bloque Plan Menaje
   (`POSTGRES_HOST=10.x.x.x`, `REDIS_URL=redis://:PASS@10.x.x.x:6379/0`).
2. `docker compose --profile sede up -d` (db y redis locales ya no
   arrancan).
3. Smoke test (checklist de E6): login Gerencia y Taller · crear
   recado · chat polling · registrar egreso y verificar asiento
   automático · push Interfón · El Site en verde incluyendo cuadrante
   La Bodega.
4. Avisar en Los Recados: de vuelta en línea.

## Fase 4 — Post-corte (mismos días, sin prisa)

1. Backups: confirmar esa noche que `archivo.sh` corrió contra La
   Bodega y el dump llegó a HAL.
2. `optimizar.sh`: cron de La Sede con `--apps`; cron nuevo en La
   Bodega con `--datos`.
3. Monitorear El Site 7 días (RAM de ambos, latencia `SELECT 1`).
4. **No borrar** los volúmenes viejos de Postgres/Redis en La Sede
   hasta cumplidos 7 días estables.
5. Día 8: `docker volume rm` de los volúmenes viejos. RAM liberada
   definitiva. BITACORA.md con el cierre del Menaje.

## Rollback (en cualquier punto antes de Fase 4.5)

Los volúmenes originales siguen intactos en La Sede:
1. Revertir `.env` (comentar bloque Menaje).
2. `docker compose up -d` SIN flag de profile (vuelve el modo
   todo-en-uno con los datos locales originales).
3. Si hubo escrituras post-cutover que importan, dump desde La Bodega
   y restore local antes de reabrir.

Costo del rollback: los mismos 10 minutos. Por eso el orden del
runbook nunca destruye el estado anterior antes del día 8.
