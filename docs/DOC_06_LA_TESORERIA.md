# Diseño — La Tesorería

> **Versión:** 1.1 · 15 mayo 2026 (revisión: andamiaje visual TailAdmin disponible + ubicación)
> **Status:** Diseño aprobado, listo para implementación · andamiaje visual entregado en S-TailAdmin-2
> **Audiencia:** Claude Code / desarrollo
> **Dependencias:** Sistema de Referencias `@/#/$` (DOC_01), Los Chalanes (DOC_02), El Dictado (DOC_04), Google Drive wrapper (S2b), Los Permisos
> **Dependientes:** Manual de Usuario, Sala de Juntas (los KPIs financieros leen de aquí)

## Andamiaje visual disponible (cierre arco TailAdmin, 2026-05-15)

- **Item "Pronto · La Tesorería"** en sidebar de El Taller con badge
  `warning`. **Gated por rol estricto** (§11 de este documento):
  visible solo para `super_admin`, `dueno` y `contador`. El diseñador
  NO ve siquiera el placeholder — consistente con la regla "información
  contable no es visible para diseñadores ni siquiera por curiosidad".
- **Página `/proximamente/tesoreria/`** activa con descripción
  "Ingresos, egresos, cuentas por cobrar y por pagar, reembolsos y
  reportes de flujo de caja. Incluye OCR de recibos y dictado de
  gastos por El Chalán" — sprint=`S2b`.
- **`_preview_acciones.html`** disponible para el dictado de gastos
  (§7) — mismo partial que El Dictado de Sala de Juntas (DOC_04), ya
  que comparten backend según §7.3 ("Ambos viven bajo el mismo módulo
  de El Dictado en código, solo cambia la UI de entrada y el system
  prompt"). El partial soporta confianza `<0.7` con chip ⚠️ usado por
  el OCR cuando los datos extraídos del recibo no son confiables (§6.1
  punto 4 — "Si confianza < 0.7 → marcar con ⚠️ en preview").
- **`_chip_referencia.html`** tipo `cliente` ($) y tipo `proyecto` (#)
  disponibles para usar en listados de ingresos/egresos donde la
  columna "Proyecto" o "Cliente" debe ser clickeable y consistente
  con el resto del sistema.
- **`_filtros_lista.html`** y **`_tabla.html`** disponibles para las
  vistas de lista de ingresos/egresos/CxC/CxP con filtros estándar
  (rango fechas, cliente, proyecto, método de pago, centro de costo).

**Slot `chalan_*_api_key`**: el dictado de gastos (§7) y el OCR
de recibos (§6) requieren llaves de Anthropic y/o OpenAI vía Los
Chalanes. Hoy esos slots viven como `anthropic_api_key` y
`openai_api_key` en Los Ajustes (legacy, módulo Los Analistas).
DOC_02 los renombra/expande en pre-S2b. La Tesorería debe levantarse
DESPUÉS de pre-S2b para usar la cascada de Los Chalanes v2 directo.

**Slot Google Drive**: el OCR de recibos (§6) guarda el archivo
original en Drive. El wrapper de Google Drive llega en S2b junto
con La Caja, Cotizaciones y Facturación. Hoy Los Ajustes tiene
`google_oauth_client_id` / `google_oauth_client_secret` /
`google_oauth_project_id` (SSO de Google para login — sprint S2a).
Drive requiere flow distinto (Service Account o OAuth con scope
`drive.file`); slots nuevos a definir en S2b junto con el wrapper.

Lo que falta (S2b): migraciones `centro_de_costo` + `ingreso` +
`egreso` + `egreso_ocr_log` + CxC + CxP + reembolsos (§4), CRUD UI
(§5), pipeline OCR completo (§6), dictado de gasto integrado (§7),
reportes y exportación CSV/Sheets (§8), eventos Portavoz (§10),
permisos granulares por rol (§11), tests (§12). DOC_01 + DOC_02
+ DOC_04 son prerequisitos.

---

## 1. Propósito

Módulo de **flujo de dinero real** del despacho. Captura lo que entró y lo que salió, cuándo, por qué proyecto, quién lo pagó, quién lo solicitó, en qué centro de costo. Alimenta los KPIs ejecutivos de la Sala de Juntas.

**Lo que NO es:**
- **No es Cotizaciones** (promesa de venta — vive en módulo separado)
- **No es Facturación** (bisagra contable formal — módulo separado, S2b/S2c)
- **No es contabilidad de partida doble** completa (eso es S3 si llega)
- **No es timbrado CFDI** (el contador lo hace aparte con su sistema, decisión cerrada)

---

## 2. Ubicación y acceso

- **Vive en El Taller** (taller.ninomeando.com → sidebar → La Tesorería)
- **Acceso por rol:**
  - `super_admin` ✅ todo
  - `dueno` ✅ todo
  - `contador` ✅ todo (es su área principal)
  - `disenador` ❌ no aparece en su sidebar
- **Granularidad futura:** si más adelante hace falta, se pueden definir sub-permisos (ej. "lectura financiera para nuevo rol auditor"). V1: 3 roles ven todo de Tesorería, 1 no la ve.

---

## 3. Estructura del módulo

```
/tesoreria/
├── /                    ← landing con KPIs propios + accesos rápidos
├── /ingresos/           ← lista + alta + detalle
├── /egresos/            ← lista + alta + detalle (incluye OCR y dictado IA)
├── /por-cobrar/         ← cuentas por cobrar (lo que clientes deben)
├── /por-pagar/          ← cuentas por pagar (lo que el despacho debe a proveedores/empleados)
├── /centros-de-costo/   ← link a Gerencia → Catálogos (read-only desde Tesorería)
└── /reportes/           ← reportes mensuales exportables
```

---

## 4. Modelo de datos

### 4.1. Tabla `centro_de_costo`

Editable desde **La Gerencia → Catálogos → Centros de costo** (no desde Tesorería). Tesorería solo los lee.

```python
class CentroDeCosto(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)  # para referencia y autocomplete
    descripcion = models.CharField(max_length=300, blank=True)

    naturaleza = models.CharField(max_length=20, choices=[
        ('proyecto', 'Asociable a proyecto'),
        ('operativo', 'Operación general'),
        ('mixto', 'Cualquiera'),
    ], default='mixto')

    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey('cuentas.Usuario', null=True, on_delete=models.SET_NULL)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['activo']),
        ]
```

**Seed inicial sugerido** (super_admin puede editar después):

| nombre | naturaleza | descripción |
|---|---|---|
| Insumos de proyecto | proyecto | Materiales específicos de un proyecto |
| Impresión y maquila | proyecto | Costos de producción externa |
| Nómina | operativo | Sueldos y prestaciones |
| Honorarios externos | mixto | Freelancers, asesores |
| Renta y servicios | operativo | Oficina, internet, luz |
| Software y suscripciones | operativo | Licencias, SaaS |
| Viáticos | mixto | Transporte, comidas, hospedaje |
| Marketing | operativo | Anuncios, eventos |
| Impuestos y comisiones | operativo | SAT, bancarias |
| Otros | mixto | Catch-all |

### 4.2. Tabla `ingreso`

```python
class Ingreso(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=20, unique=True)  # ING-2026-0001 autogenerado

    monto = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.CharField(max_length=3, default='MXN')
    fecha = models.DateField()

    descripcion = models.CharField(max_length=300)

    # Relaciones
    cliente = models.ForeignKey('cartera.Cliente', null=True, blank=True, on_delete=models.SET_NULL, related_name='ingresos')
    proyecto = models.ForeignKey('proyectos.Proyecto', null=True, blank=True, on_delete=models.SET_NULL, related_name='ingresos')
    factura = models.ForeignKey('facturacion.Factura', null=True, blank=True, on_delete=models.SET_NULL, related_name='ingresos_aplicados')  # S2b/S2c

    # Origen del cobro
    metodo = models.CharField(max_length=30, choices=[
        ('transferencia', 'Transferencia'),
        ('deposito', 'Depósito'),
        ('efectivo', 'Efectivo'),
        ('cheque', 'Cheque'),
        ('stripe', 'Stripe'),
        ('mercadopago', 'MercadoPago'),
        ('otro', 'Otro'),
    ], default='transferencia')

    referencia_externa = models.CharField(max_length=100, blank=True)  # núm. operación bancaria, ID Stripe, etc.

    # Auditoría
    creado_por = models.ForeignKey('cuentas.Usuario', null=True, on_delete=models.SET_NULL, related_name='ingresos_capturados')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Soft delete (no se borran nunca, solo se anulan)
    anulado = models.BooleanField(default=False)
    anulado_por = models.ForeignKey('cuentas.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='ingresos_anulados')
    anulado_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=300, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['cliente', '-fecha']),
            models.Index(fields=['proyecto', '-fecha']),
            models.Index(fields=['anulado']),
        ]
```

### 4.3. Tabla `egreso`

```python
class Egreso(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=20, unique=True)  # EGR-2026-0001

    monto = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.CharField(max_length=3, default='MXN')
    fecha = models.DateField()

    descripcion = models.CharField(max_length=300)
    proveedor_nombre = models.CharField(max_length=200, blank=True)  # texto libre — no hay catálogo de proveedores en V1

    # Centros de costo / proyecto
    centro_de_costo = models.ForeignKey(CentroDeCosto, on_delete=models.PROTECT, related_name='egresos')
    proyecto = models.ForeignKey('proyectos.Proyecto', null=True, blank=True, on_delete=models.SET_NULL, related_name='egresos')

    # Quién pagó, quién solicitó
    pagado_por = models.ForeignKey('cuentas.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='egresos_que_pague')
    solicitado_por = models.ForeignKey('cuentas.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='egresos_que_solicite')

    # Estado del pago
    estado_pago = models.CharField(max_length=20, choices=[
        ('pagado', 'Pagado (saldado)'),
        ('por_reembolsar', 'Por reembolsar al empleado'),
        ('pendiente', 'Pendiente de pago'),
    ], default='pagado')

    # Método
    metodo = models.CharField(max_length=30, choices=[
        ('transferencia', 'Transferencia empresa'),
        ('tarjeta_empresa', 'Tarjeta empresa'),
        ('tarjeta_personal', 'Tarjeta personal (reembolso)'),
        ('efectivo', 'Efectivo'),
        ('cheque', 'Cheque'),
        ('otro', 'Otro'),
    ], default='transferencia')

    # Recibo / comprobante
    drive_file_id = models.CharField(max_length=100, blank=True)  # archivo en Drive si se subió
    drive_url_view = models.URLField(max_length=500, blank=True)
    drive_url_thumbnail = models.URLField(max_length=500, blank=True)
    tiene_comprobante = models.BooleanField(default=False)

    # Origen del registro
    origen = models.CharField(max_length=20, choices=[
        ('manual', 'Captura manual'),
        ('ocr', 'OCR de recibo'),
        ('dictado', 'Dictado El Chalán'),
        ('sala_juntas', 'Dictado desde Sala de Juntas'),
    ], default='manual')

    # IA: si fue procesado por OCR/dictado, qué confianza
    confianza_ia = models.FloatField(null=True, blank=True)  # 0.0-1.0 solo si origen != manual

    # Auditoría
    creado_por = models.ForeignKey('cuentas.Usuario', null=True, on_delete=models.SET_NULL, related_name='egresos_capturados')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Soft delete
    anulado = models.BooleanField(default=False)
    anulado_por = models.ForeignKey('cuentas.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='egresos_anulados')
    anulado_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=300, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['proyecto', '-fecha']),
            models.Index(fields=['centro_de_costo', '-fecha']),
            models.Index(fields=['estado_pago']),
            models.Index(fields=['pagado_por', 'estado_pago']),
            models.Index(fields=['anulado']),
        ]
```

### 4.4. Tabla `egreso_ocr_log`

Registro técnico de cada OCR procesado (para auditoría, debugging y aprendizaje).

```python
class EgresoOcrLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    egreso = models.ForeignKey(Egreso, null=True, blank=True, on_delete=models.SET_NULL, related_name='ocr_logs')  # null si se descartó

    drive_file_id = models.CharField(max_length=100)
    nombre_original = models.CharField(max_length=300)
    tamano_original_bytes = models.BigIntegerField()
    tamano_optimizado_bytes = models.BigIntegerField()
    mime_type = models.CharField(max_length=100)

    # Resultado IA
    chalan_usado = models.CharField(max_length=30)  # 'anthropic', 'openai', ...
    modelo = models.CharField(max_length=80)
    raw_extraccion = models.JSONField(default=dict)  # JSON crudo de la IA

    # Métricas
    latencia_ms = models.IntegerField()
    costo_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0)

    # Corrección humana
    fue_corregido = models.BooleanField(default=False)  # ¿el usuario cambió algún campo antes de guardar?
    correcciones = models.JSONField(default=dict, blank=True)  # qué campos cambió

    creado_por = models.ForeignKey('cuentas.Usuario', null=True, on_delete=models.SET_NULL)
    creado_en = models.DateTimeField(auto_now_add=True)
```

**Uso del log:** además de auditoría, alimenta el sistema de aprendizaje (los `correcciones` se vuelven `DictadoAprendizaje` cuando hay patrones repetidos — el contador siempre corrige "Papelería La Sirena" del centro "Otros" a "Insumos de proyecto", eso se aprende).

### 4.5. Cuentas por cobrar y por pagar

**No son tablas nuevas.** Son **vistas filtradas**:

- **Cuentas por cobrar:** facturas emitidas (S2b/S2c) con saldo > 0 que aún no tienen `Ingreso` aplicado completo. Hasta que llegue Facturación, se simula con `Proyecto.monto_facturado - Proyecto.monto_cobrado > 0`.
- **Cuentas por pagar:** `Egreso.estado_pago IN ('por_reembolsar', 'pendiente')`.

Implementadas como managers de Django con queries específicas.

---

## 5. Captura manual

Form clásico Django para crear/editar ingreso o egreso. Campos según modelo. Validaciones:

- Monto > 0
- Fecha no futura (warning si lo es, pero permitido para registros adelantados)
- Si `tarjeta_personal` y no `por_reembolsar`, mensaje sugiriendo cambiar estado
- Adjuntar comprobante: opcional pero recomendado (con OCR automático si se sube imagen/PDF)

---

## 6. OCR de recibos

### 6.1. Flujo

1. **Usuario sube imagen/PDF** desde el form de nuevo egreso (botón "📷 Subir recibo")
2. **Backend recibe el archivo** en `/tesoreria/egresos/ocr/`
3. **Optimización local antes de Drive:**
   - Si es imagen: recompresión a JPEG 1200px ancho max, calidad 75%, target <500KB
   - Si es PDF 1 página: convertir a JPEG optimizado
   - Si es PDF multi-página: dejar como PDF (no se reformatea)
   - Nombre normalizado: `<fecha>_<proveedor-slug-tentativo>_<monto>.jpg` (el slug y monto vienen del OCR; mientras tanto usa hash temporal)
4. **Subir a Drive:**
   - Carpeta destino: `Tesorería/Recibos/yyyy-mm/` (estructura por mes)
   - Si el OCR detecta `#proyecto` o el usuario lo asocia desde el form, se duplica el link (no el archivo) en `Activos de proyecto/<proyecto-codigo>/Recibos/`
5. **Procesamiento OCR con Los Chalanes:**
   - Estación: `ocr_recibo` (requiere VISION)
   - Chalanes elegibles: Claudio, GPT, Gemini (cuando se active). Chino (Deepseek) excluido por falta de visión.
   - Prompt: extraer en JSON estructurado:
     ```json
     {
       "proveedor": "Papelería La Sirena",
       "fecha": "2026-05-14",
       "monto_total": 850.00,
       "moneda": "MXN",
       "items_detalle": [...],
       "iva_detectado": 117.24,
       "rfc_emisor": "PAS950101ABC",
       "es_factura_fiscal": true | false,
       "confianza": 0.92,
       "notas_chalan": "..."
     }
     ```
6. **Sugerencia de centro de costo:**
   - El Chalán propone uno basado en proveedor + items + aprendizajes históricos
   - Si confianza < 0.7 → marcar con ⚠️ en preview
7. **Preview al usuario:**

```
┌──────────────────────────────────────────────────────────────┐
│ 📷 Recibo procesado                                          │
├──────────────────────────────────────────────────────────────┤
│ Proveedor:        Papelería La Sirena               [editar] │
│ Fecha:            14 mayo 2026                      [editar] │
│ Monto total:      $850.00 MXN                       [editar] │
│ IVA detectado:    $117.24                           [editar] │
│ RFC emisor:       PAS950101ABC                      [editar] │
│ Tipo:             Factura fiscal                             │
│                                                              │
│ Centro de costo:  Insumos de proyecto ⚠️ (76% conf)  [▼]    │
│ Proyecto:         Sin proyecto asignado             [▼]      │
│ Pagado por:       @maria-gonzalez                   [▼]      │
│ Solicitado por:   (vacío)                           [▼]      │
│ Estado:           Por reembolsar                    [▼]      │
│                                                              │
│ Comprobante:      ✅ Guardado en Drive (340 KB)              │
├──────────────────────────────────────────────────────────────┤
│                          [Cancelar]   [Guardar egreso]      │
└──────────────────────────────────────────────────────────────┘
```

8. **Usuario revisa, edita lo necesario, guarda.** Las correcciones se registran en `EgresoOcrLog.correcciones` para aprendizaje.

### 6.2. Manejo de errores

- **Imagen no legible / OCR confuso:** el Chalán retorna campos vacíos con `confianza < 0.3`. Sistema dice "No pude leer este recibo. Captúralo manualmente o sube una foto más clara." Pero **el archivo SÍ se guarda** en Drive — no se desperdicia.
- **Los Chalanes con visión caídos:** mensaje "El Chalán está ocupado. Captura manual disponible." Archivo se sube a Drive igual.
- **Archivo >25 MB:** rechazo con mensaje claro.
- **MIME no permitido:** rechazo (whitelist igual que Recados: JPG/PNG/PDF).

### 6.3. Defaults inteligentes

Cuando el OCR no llena un campo, el sistema propone defaults:

- **Pagado por:** el usuario que sube el recibo (override editable)
- **Solicitado por:** vacío (el contador lo llena después si aplica)
- **Estado del pago:**
  - Si método inferido es "tarjeta personal" (el OCR detecta últimos 4 dígitos de tarjeta no registrada en la empresa) → "Por reembolsar"
  - Si no → "Pagado"
- **Proyecto:** si el contexto del Dictado/OCR menciona `#proyecto`, asignado; si no, vacío
- **Fecha:** la del recibo si OCR la extrajo; si no, fecha de subida

---

## 7. Cuadro de texto IA (dictado de gastos)

Como El Dictado de Sala de Juntas, pero específico para Tesorería. Vive en `/tesoreria/egresos/dictar/` y también es invocable como acción desde El Dictado general.

### 7.1. UX

```
┌──────────────────────────────────────────────────────────────┐
│ 🎙️ Dictar gasto                                              │
├──────────────────────────────────────────────────────────────┤
│ Cuéntame el gasto en lenguaje natural. Puedes mencionar      │
│ @personas, #proyectos y $clientes.                           │
│                                                              │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Acabo de pagar $850 de insumos al proveedor "Papelería  │ │
│ │ La Sirena" para el #PRY-000123 del menú de              │ │
│ │ $heladeria-michoacana, lo pagó @maria con tarjeta       │ │
│ │ personal.                                                │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│ 📷 Adjuntar recibo (opcional)                                │
│                              [Cancelar]   [Procesar]         │
└──────────────────────────────────────────────────────────────┘
```

### 7.2. Flujo interno

1. Usuario teclea + opcionalmente adjunta recibo
2. Si hay recibo: corre OCR primero (sección 6) y combina con el dictado
3. El Chalán interpreta el texto (estación `dictado_gasto`) y propone:
   ```
   Registrar egreso:
   - Monto: $850
   - Descripción: Insumos para menú de Heladería Michoacana
   - Proveedor: Papelería La Sirena
   - Centro de costo: Insumos de proyecto
   - Proyecto: #PRY-000123
   - Pagado por: @maria-gonzalez
   - Solicitado por: (vacío)
   - Estado: Por reembolsar  ⚠️ (porque "tarjeta personal")
   - Método: tarjeta_personal
   - Recibo: ✅ adjunto

   [Confirmar]  [Editar]  [Cancelar]
   ```
4. Igual que El Dictado normal: usuario confirma, se guarda.

### 7.3. Diferencia con El Dictado de Sala de Juntas

El Dictado de Sala de Juntas puede generar **múltiples acciones de distintos tipos** (actualizar proyecto + crear tarea + crear recado + registrar gasto, todo en un solo dictado).

El "dictar gasto" de Tesorería es **más específico**: solo registra ingresos/egresos. Más rápido y enfocado para flujos contables intensivos.

Ambos viven bajo el mismo módulo de El Dictado en código (`/dictado/` endpoints reutilizados), solo cambia la UI de entrada y el system prompt de Los Chalanes.

---

## 8. Reportes y exportación

### 8.1. `/tesoreria/reportes/`

Reportes mensuales standard:

- **Estado de resultados simplificado:** ingresos totales - egresos totales = utilidad bruta del mes
- **Desglose por centro de costo:** cuánto se gastó en cada uno
- **Top 10 proveedores por monto:** quiénes son los gastos más grandes
- **Pendientes de reembolso:** lista de empleados con dinero por cobrar de gastos personales
- **Ingresos por cliente:** quiénes pagaron más
- **Comparativa mensual:** mes actual vs mes anterior vs promedio últimos 6 meses

### 8.2. Exportación bajo demanda (decisión cerrada 15 mayo 2026)

**El Despacho es la única fuente de verdad.** Los exports son snapshots para uso externo (entregar al fiscal, manipular en Excel/Sheets, archivo histórico). NO hay sincronización automática con Google Sheets.

#### 8.2.1. Formatos de export

Cada vista exportable ofrece **dos botones**:

- **📥 Descargar CSV** — descarga directa al navegador
- **📊 Crear hoja en Drive** — crea Google Sheet nueva en Drive y abre URL en pestaña nueva

#### 8.2.2. Qué se puede exportar

Por endpoint dedicado, cada uno con filtros propios:

| Endpoint | Filtros disponibles | Columnas |
|---|---|---|
| `GET /tesoreria/exportar/ingresos.csv` | rango fechas, cliente, proyecto, método | codigo, fecha, monto, moneda, descripcion, cliente, proyecto, metodo, referencia_externa, creado_por, anulado, motivo_anulacion |
| `GET /tesoreria/exportar/egresos.csv` | rango fechas, centro de costo, proyecto, estado_pago, pagado_por | codigo, fecha, monto, descripcion, proveedor, centro_de_costo, proyecto, pagado_por, solicitado_por, estado_pago, metodo, origen, tiene_comprobante, drive_url_view, creado_por, anulado |
| `GET /tesoreria/exportar/cxc.csv` | (sin filtros, snapshot actual) | factura, cliente, proyecto, monto_facturado, monto_cobrado, saldo_pendiente, fecha_emision, dias_vencido |
| `GET /tesoreria/exportar/cxp.csv` | filtro por estado | codigo, fecha, proveedor, monto, pagado_por, estado_pago, dias_pendiente |
| `GET /tesoreria/exportar/reembolsos.csv` | (sin filtros) | empleado, total_pendiente, num_gastos, oldest_fecha |
| `GET /tesoreria/exportar/movimientos.csv` | rango fechas (default mes actual) | **VISTA UNIFICADA** ingresos+egresos en una sola tabla con columna "tipo" |

#### 8.2.3. Endpoint genérico CSV

```python
def exportar_csv(request, vista):
    """
    vista: 'ingresos' | 'egresos' | 'cxc' | 'cxp' | 'reembolsos' | 'movimientos'
    """
    queryset = _aplicar_filtros(vista, request.GET)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')  # BOM para Excel
    nombre = f"tesoreria_{vista}_{date.today().isoformat()}.csv"
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'

    writer = csv.writer(response)
    writer.writerow(COLUMNAS[vista])  # encabezados localizados español
    for row in queryset:
        writer.writerow(_serializar(row, vista))

    # Telemetry
    Portavoz.emitir('tesoreria.exportado', {
        'vista': vista,
        'formato': 'csv',
        'filas': queryset.count(),
        'actor_id': request.user.id,
        'filtros': dict(request.GET),
    })

    return response
```

**Decisiones técnicas:**

- **Encoding UTF-8 con BOM** (`utf-8-sig`) para que Excel abra acentos correctamente sin tener que cambiar configuración
- **Encabezados localizados en español:** "Código", "Fecha", "Monto", "Centro de costo"... no `codigo`, `fecha`, etc.
- **Fechas en formato `YYYY-MM-DD`** (ISO 8601, universal y ordenable). No `15/05/2026` que se confunde con `05/15/2026`
- **Montos como número decimal con punto** (`1234.56`), no `$1,234.56` ni `1.234,56`. Excel/Sheets reconocen el formato como número directo
- **Booleanos como `Sí/No`** (no `True/False`), localizado
- **Campos vacíos como string vacía**, no `null` ni `None`
- **Centro de costo como nombre legible** ("Insumos de proyecto"), no como ID
- **Referencias a proyecto/cliente como código** (`PRY-000123`, no ID 42)
- **Sin límite de filas hardcoded** (CSV maneja millones sin problema; si el queryset es enorme, el navegador es el que se queja, no nosotros)

#### 8.2.4. Endpoint genérico Sheets

```python
def exportar_sheets(request, vista):
    """
    Crea Google Sheet nueva en Drive y retorna URL.
    """
    queryset = _aplicar_filtros(vista, request.GET)

    nombre = f"Tesorería — {vista.title()} — {date.today().isoformat()}"
    carpeta_destino_id = _obtener_carpeta_exports()  # 'Tesorería / Exports'

    try:
        sheet = sheets_wrapper.crear_hoja(
            nombre=nombre,
            carpeta_id=carpeta_destino_id,
            encabezados=COLUMNAS[vista],
            filas=[_serializar(row, vista) for row in queryset],
        )
    except SheetsError as e:
        Portavoz.emitir('tesoreria.export_fallido', {
            'vista': vista, 'formato': 'sheets', 'motivo': str(e),
            'actor_id': request.user.id,
        })
        return JsonResponse({
            'error': 'Google Sheets no disponible. Intenta descarga CSV.',
            'detalle': str(e),
        }, status=503)

    Portavoz.emitir('tesoreria.exportado', {
        'vista': vista, 'formato': 'sheets',
        'sheet_id': sheet.id, 'sheet_url': sheet.url,
        'filas': queryset.count(),
        'actor_id': request.user.id,
        'filtros': dict(request.GET),
    })

    return JsonResponse({'url': sheet.url, 'sheet_id': sheet.id})
```

**Decisiones técnicas:**

- **Carpeta destino:** `Tesorería / Exports / YYYY/` (estructura por año para no acumular cientos de archivos sueltos)
- **Permisos del Sheet creado:** mismo nivel que la carpeta — los usuarios del Workspace de Learning Center lo ven; nadie más
- **Formato de números aplicado:** moneda MXN en columna de montos (Google Sheets API soporta `userEnteredFormat`); fechas como tipo fecha; booleanos como string (más simple)
- **Encabezados con formato bold** y fondo gris claro
- **Auto-resize de columnas** al crear (mejor presentación)
- **Si Sheets falla:** mensaje claro al usuario "Descarga CSV en su lugar" — el botón sigue siendo redundante

#### 8.2.5. UX en la interfaz

Cada lista en `/tesoreria/` tiene barra de filtros + dos botones de export:

```
┌─────────────────────────────────────────────────────────────┐
│ Egresos                                                     │
├─────────────────────────────────────────────────────────────┤
│ Filtros: [Fechas: este mes ▾] [Centro: todos ▾] [Buscar...]│
│                                                              │
│                      [📥 Descargar CSV] [📊 Crear hoja Drive]│
├─────────────────────────────────────────────────────────────┤
│ (tabla de egresos)                                          │
└─────────────────────────────────────────────────────────────┘
```

Los botones exportan **respetando los filtros activos**. Lo que ves es lo que descargas.

#### 8.2.6. Telemetry

Cada export queda registrado en el evento `tesoreria.exportado` con `vista`, `formato`, `filas`, `actor`, `filtros`. Útil para auditoría — saber quién descargó qué y cuándo.

No hay almacenamiento perpetuo del export: el CSV es ephemeral (el navegador lo guarda donde el usuario decide), el Sheet vive en Drive (la URL queda registrada en el evento por si hay que rastrear "¿quién creó este Sheet?").

#### 8.2.7. Permisos para exportar

| Acción | super_admin | dueno | contador | disenador |
|---|---|---|---|---|
| Exportar ingresos | ✅ | ✅ | ✅ | ❌ |
| Exportar egresos | ✅ | ✅ | ✅ | ❌ |
| Exportar cxc/cxp/reembolsos | ✅ | ✅ | ✅ | ❌ |
| Exportar movimientos consolidados | ✅ | ✅ | ✅ | ❌ |

Igual que el acceso al módulo. Diseñador no entra a Tesorería, no exporta.

---

## 9. KPIs que alimenta a la Sala de Juntas

La Tesorería es **fuente de datos** para los KPIs ejecutivos:

| KPI en Sala de Juntas | Calculado de |
|---|---|
| Ingresos del mes | `Ingreso` no anulados con fecha en mes actual |
| Egresos del mes | `Egreso` no anulados con fecha en mes actual |
| Utilidad bruta del mes | Diferencia |
| Cuentas por cobrar totales | Suma de saldos pendientes |
| Cuentas por pagar totales | Suma de `Egreso.estado_pago != 'pagado'` |
| Proyección 30 días | Ingresos esperados (proyectos `fecha_ingreso_esperado` en rango) - egresos recurrentes promedio |
| Top 5 centros de costo | `Egreso` agrupados por centro de costo |
| Reembolsos pendientes a empleados | `Egreso.estado_pago='por_reembolsar'` agrupado por `pagado_por` |

---

## 10. Eventos Portavoz

| Evento | Cuándo | Payload |
|---|---|---|
| `tesoreria.ingreso_registrado` | Nuevo Ingreso creado | `{ingreso_id, monto, cliente_id, proyecto_id, origen}` |
| `tesoreria.egreso_registrado` | Nuevo Egreso creado | `{egreso_id, monto, centro_de_costo_id, proyecto_id, origen}` |
| `tesoreria.ocr_procesado` | OCR completado | `{egreso_id?, chalan_usado, latencia_ms, confianza, fue_corregido?}` |
| `tesoreria.reembolso_pendiente` | Egreso con `por_reembolsar` creado | `{egreso_id, pagado_por_id, monto}` — dispara push a contador y al pagador |
| `tesoreria.ingreso_anulado` | Anulación de ingreso | `{ingreso_id, motivo, anulado_por_id}` |
| `tesoreria.egreso_anulado` | Anulación de egreso | `{egreso_id, motivo, anulado_por_id}` |
| `tesoreria.cuentas_por_pagar_alta` | Cuando CxP > umbral configurable | `{total_cxp, num_pendientes}` |
| `tesoreria.exportado` | Export exitoso (CSV o Sheets) | `{vista, formato, filas, actor_id, filtros, sheet_url?}` |
| `tesoreria.export_fallido` | Sheets API falló | `{vista, formato, motivo, actor_id}` |

---

## 11. Permisos

| Acción | super_admin | dueno | contador | disenador |
|---|---|---|---|---|
| Ver módulo Tesorería | ✅ | ✅ | ✅ | ❌ |
| Capturar ingreso | ✅ | ✅ | ✅ | ❌ |
| Capturar egreso (manual) | ✅ | ✅ | ✅ | ❌ |
| Subir recibo OCR | ✅ | ✅ | ✅ | ❌ |
| Dictar gasto | ✅ | ✅ | ✅ | ❌ |
| Anular ingreso/egreso | ✅ | ✅ | ✅ | ❌ |
| Ver reportes | ✅ | ✅ | ✅ | ❌ |
| Descargar CSV de cualquier vista | ✅ | ✅ | ✅ | ❌ |
| Crear hoja en Drive | ✅ | ✅ | ✅ | ❌ |
| Configurar centros de costo (vive en Gerencia) | ✅ | ❌ (read-only) | ❌ | ❌ |

**Nota sobre diseñadores y gastos:** los diseñadores **no capturan gastos en Tesorería**. Si tienen un gasto reembolsable (pagaron insumos de su bolsa), usan El Dictado en Sala de Juntas o Los Recados para avisarle al contador, quien lo registra. Esto centraliza la captura financiera.

---

## 12. Tests requeridos

| Test | Cubre |
|---|---|
| `test_crear_ingreso_basico` | Captura manual |
| `test_crear_egreso_con_proyecto` | Egreso asociado a #proyecto |
| `test_crear_egreso_operativo_sin_proyecto` | Egreso de operación general |
| `test_codigo_correlativo_unico` | ING-2026-0001, ING-2026-0002... |
| `test_no_borrar_solo_anular` | DELETE no existe; anular preserva auditoría |
| `test_ocr_optimiza_imagen_antes_drive` | Foto 4MB → JPEG <500KB |
| `test_ocr_archivo_se_guarda_aunque_chalan_falle` | Drive sí, OCR no |
| `test_ocr_correcciones_se_guardan_en_log` | Si usuario cambia campo, se anota |
| `test_ocr_sugerencia_centro_costo` | Aprendizaje de centros similares |
| `test_ocr_confianza_baja_marca_visual` | <0.7 → ⚠️ |
| `test_dictado_gasto_crea_egreso_correcto` | Dictado → preview → guardar |
| `test_estado_pago_default_tarjeta_personal` | Tarjeta personal → "Por reembolsar" |
| `test_evento_reembolso_pendiente_dispara_push` | Notifica contador y pagador |
| `test_cuentas_por_pagar_query` | Manager regresa correctos |
| `test_reporte_estado_resultados` | Cálculo ingresos - egresos del mes |
| `test_permisos_disenador_no_ve_tesoreria` | 403 / no aparece en sidebar |
| `test_permisos_contador_ve_y_edita` | Acceso completo |
| `test_anular_requiere_motivo` | Validación |
| `test_centro_costo_no_se_borra_si_tiene_egresos` | PROTECT en FK |
| `test_export_csv_egresos_respeta_filtros` | Filtro por fechas + centro de costo → solo esos en CSV |
| `test_export_csv_encoding_utf8_bom` | Acentos sobreviven Excel |
| `test_export_csv_fechas_iso_8601` | Formato YYYY-MM-DD |
| `test_export_csv_montos_decimal_punto` | 1234.56 no $1,234.56 |
| `test_export_sheets_crea_hoja_en_drive` | Mock Sheets API |
| `test_export_sheets_falla_responde_503` | Sheets caído → mensaje claro |
| `test_export_emite_telemetry` | Evento `tesoreria.exportado` con filtros |
| `test_export_movimientos_unifica_ingresos_egresos` | Vista consolidada |

Mínimo 27 tests.

---

## 13. Roadmap de implementación

**Pre-requisitos:**
- Sistema de Referencias (DOC_01)
- Los Chalanes v2 con estación `ocr_recibo` y `dictado_gasto` configuradas
- Google Drive wrapper
- El Dictado base (DOC_04) — el `dictar gasto` es subset de El Dictado

**Orden dentro del sprint La Tesorería:**

1. Migraciones: `centro_de_costo`, `ingreso`, `egreso`, `egreso_ocr_log` + seed inicial de centros de costo
2. CRUD de centros de costo en La Gerencia → Catálogos
3. CRUD manual de ingresos y egresos en El Taller
4. Subida de archivos a Drive con optimización
5. OCR de recibos vía Chalanes (estación `ocr_recibo`)
6. Dictado de gastos vía Chalanes (subset de El Dictado)
7. Vistas de Cuentas por cobrar y por pagar
8. Reportes mensuales + export a Sheets
9. Eventos Portavoz + handlers de push
10. Tests

**Tiempo estimado:** 3-4 horas de Claude Code activo.

---

## 14. Decisiones cerradas

- ✅ Vive en El Taller, acceso para super_admin/dueño/contador
- ✅ Diseñador no entra a Tesorería
- ✅ Centros de costo editables desde Gerencia → Catálogos (B)
- ✅ AI asigna su mejor adivinanza con marca de confianza baja (A)
- ✅ Recibos se guardan en Drive optimizados, "Tesorería/Recibos/yyyy-mm" + duplicado en carpeta de proyecto si aplica (A optimizada)
- ✅ "Pagado por" + "Solicitado por" + "Estado del pago" como 3 campos separados (C + estado adicional)
- ✅ Egresos pueden ser de proyecto o de operación general (B)
- ✅ Cotizaciones y Facturas viven aparte de Tesorería (B)
- ✅ Optimización de imágenes: recompresión a JPEG 1200px / 75% calidad, target <500KB; PDF 1 página → JPEG; PDF multi-página preservado
- ✅ Recibos viejos podrían moverse a archivo frío en V2 (decisión futura)
