# Handoff de merge — S-Estados-Color-HEX ↔ sprint paralelo (voz/preludio + egreso↔proyecto)

> **Fecha:** 2026-06-07 · **Autor:** sprint S-Estados-Color-HEX (color HEX +
> dark mode + permiso del Chalán).
> **Para:** el sprint en paralelo (voz/preludio del Chalán + egreso↔proyecto en
> Tesorería), que cierra el merge.

## TL;DR

Mientras corría el sprint **S-Estados-Color-HEX**, un `git add -A` arrastró
**21 archivos a medio escribir del sprint paralelo** dentro de mi commit
`789927f`, y se empujaron a `origin/main`. **No hay que separar ni hacer
force-push**: el sprint paralelo ya encadenó su migración `proyectos/0015`
sobre mi `proyectos/0014`, así que la integración es **lineal**. El único
bloqueo es el **CI en rojo** por un import desordenado (ruff) en un archivo
del sprint paralelo. Para cerrar: arreglar ese ruff, commitear los 4 tests
sueltos, y push.

## Estado de `origin/main` (en sync con local)

Tres commits encima del último estado conocido (`9cf4f76` pin digests del bot):

| Commit | Contenido | Pertenencia |
|---|---|---|
| `b38f03d` | **S-Estados-Color-HEX** completo (color HEX en estados/categorías, dark mode con `color-mix`, permiso `chalan/usar`). 36 archivos. | S-Estados-Color-HEX (revisado, **618 tests pass**) |
| `56f6d43` | Fix de orden de import en `los_proyectos/models/__init__.py` (ruff I001). | S-Estados-Color-HEX |
| `789927f` | **Mezclado.** Mi migración `0014` reordenada **+ 21 archivos del sprint paralelo**. | Mixto ⚠️ |

### Qué es de cada sprint dentro de `789927f`

**De S-Estados-Color-HEX (1 archivo):**
- `el-taller/apps/los_proyectos/migrations/0014_estado_color_hex.py`
  (AlterField + RunPython; **reordenado** para convertir `badge-*`→HEX antes
  de encoger la columna a `varchar(7)` — el orden original reventaba en
  Postgres con `value too long`).

**Del sprint paralelo (21 archivos) — voz/preludio del Chalán + egreso↔proyecto:**
- `chalanes/voz.py`, `chalanes/models/prompt_voz.py`, `chalanes/models/__init__.py`,
  `chalanes/signals.py`, `chalanes/migrations/0007_prompt_voz.py`
- `la-gerencia/apps/los_chalanes/{urls,views}.py`,
  `la-gerencia/templates/los_chalanes/{panel,prompts}.html`
- `el-taller/apps/el_dictado/{herramientas,prompt_chat,services}.py`
- `el-taller/apps/taller_home/services_kpi_chalan.py`  ← **causa del CI rojo**
- `el-taller/apps/tesoreria/{ocr.py,models/egreso.py,migrations/0006_egreso_origen_proyecto.py}`
- `el-taller/apps/los_proyectos/{apps.py,models/producto.py,signals_egresos.py,migrations/0015_producto_egreso.py}`
- `lib/portavoz_eventos.py`

**Sin commitear (working tree) — 4 tests del sprint paralelo:**
- `tests/gerencia/test_prompts_voz.py`
- `tests/taller/test_proyecto_egresos.py`
- `tests/taller/test_voz_builders.py`
- `tests/test_prompt_voz.py`

## Migraciones — orden e integración (sin conflicto)

El sprint paralelo ya construyó **encima** de mi migración:

```
proyectos: … → 0013_estado_cerrado → 0014_estado_color_hex (MÍO)
                                    → 0015_producto_egreso (PARALELO, depende de 0014 + tesoreria.0006)
tesoreria: … → 0005_iva_y_proveedor → 0006_egreso_origen_proyecto (PARALELO)
chalanes:  … → 0006_ocr_recibo_estacion → 0007_prompt_voz (PARALELO)
cuentas:   … → 0015_rename_dueno_admin_labels → 0016_seed_permisos_chalan (MÍO)
el_catalogo: … → 0005_proveedor → 0006_categoria_color (MÍO)
```

`proyectos/0015_producto_egreso` declara `dependencies = [("proyectos",
"0014_estado_color_hex"), ("tesoreria", "0006_egreso_origen_proyecto")]`.
**Ya está linealizado correctamente** — no hay ramas de migración que
reconciliar.

## CI en rojo — causa única y fix

`ruff==0.8.4` (job "Ruff" de El Mensajero) falla con **I001** en un archivo
del sprint paralelo:

```
el-taller/apps/taller_home/services_kpi_chalan.py:72  I001 Import block is un-sorted or un-formatted
```

El bloque dentro de `nl_a_dsl()` quedó así:
```python
    from lib.analistas import analizar

    from chalanes.voz import preludio
    prompt = preludio("kpi_dsl") + _system_prompt() + …
```

**Fix:** `ruff check --fix .` lo deja ordenado y contiguo:
```python
    from chalanes.voz import preludio
    from lib.analistas import analizar

    prompt = preludio("kpi_dsl") + _system_prompt() + …
```

> Nota: el CI local pasa con SQLite y este lint sólo se ve con `ruff==0.8.4`.
> Antes de pushear, corre `ruff check .` con esa versión.

## Pasos para cerrar el merge (en el sprint paralelo)

1. `ruff check --fix .` y verificar `ruff check .` limpio (arregla
   `services_kpi_chalan.py`).
2. Revisar y commitear los **4 tests sueltos** del working tree (son del
   sprint paralelo; ahora mismo quedan como `??`).
3. Confirmar que la suite pasa (`pytest tests/taller tests/gerencia` + raíz).
   Mi trabajo ya aporta 618 pass; sumar los tests de voz/egreso.
4. `git add -A && git commit && git push origin main`. El Mensajero corre
   verde y **ambos sprints quedan integrados** en `main` sin reescribir
   historia.

## Lo que NO hay que hacer

- **No force-push** ni `git reset` sobre `main`: la historia es lineal y
  correcta; separar mi migración del resto ya no aporta nada (el paralelo
  depende de ella).
- **No re-crear** las migraciones `0014`/`0015`/`0006`/`0007`/`0016`/`0006_categoria_color`
  — ya están congeladas y encadenadas.

## Resumen de S-Estados-Color-HEX (mi sprint, ya en main y probado)

- `EstadoProyecto.color` y `CategoriaServicio.color` → HEX libre `#RRGGBB`
  (`RegexValidator`, default `#667085`). Migraciones `proyectos/0014` y
  `el_catalogo/0006`.
- Editor en popover poco intrusivo:
  `_componentes_tailadmin/_campo_color_hex.html` (dual-copy) + JS en `ui.js`
  (dual-copy).
- Dark mode con custom property `--ec` + `color-mix` en `input.css`
  (dual-copy): `.badge-hex` y `.estado-chip`. `color_estado` devuelve HEX;
  `borde_estado`/`estado_text_clase` eliminados.
- Permiso `chalan/usar` (default activo a los 4 roles, `cuentas/0016`),
  gateado en sidebar + Dashboard + las 7 vistas de `views_chat.py`.
- Tests: `tests/taller/test_color_hex_y_chalan_permiso.py` + ampliación de
  `tests/gerencia/test_estados_proyecto.py`. Manual de usuario y
  `lib/version.py` (`2026.06.21`) actualizados; bitácora en CLAUDE.md.
