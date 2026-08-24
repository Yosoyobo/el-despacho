# Los CFDI que entran solos por correo

> La primera receta de n8n. Escrita el 2026-08-24.

## Por qué existe

Medido ese día en la base de producción:

| | |
|---|---|
| Facturas emitidas | 36 |
| Facturas con su **CFDI archivado** | **1** |

El lugar donde guardarlo existe desde julio. Lo que no ocurre es que alguien
baje el comprobante del PAC y lo suba una por una. Esta receta lo hace sola.

Y es la que Oscar puso como condición para revivir n8n: que el equipo **vea el
beneficio el primer día**, sin tener que aprender la herramienta.

---

## Cómo funciona

```
correo a facturas@  →  n8n saca el XML  →  El Despacho lo lee y lo liga
                                             │
                                             ├── coincidencia única → se liga solo
                                             └── dudas → queda pendiente, decide una persona
```

**La regla del ligado: sólo cuando es inequívoco.** Se busca la factura por
cliente y por monto exacto entre las que aún no tienen comprobante. Si aparece
UNA, se liga sola. Si aparecen dos o ninguna, queda pendiente con el motivo
escrito en español.

Adivinar sería peor que no ligar: dejaría la contabilidad apoyada en una
suposición que nadie revisó.

---

## Lo que hay que configurar (una vez)

### 1. El token

En **La Gerencia → Los Ajustes**, slot **«CFDI por correo — token de entrada»**.
Invéntalo largo. Es lo único que sostiene esa puerta: sin token configurado
**no pasa nadie** (se cierra, no se abre).

### 2. El flujo en n8n

n8n vive en `http://100.121.244.5:5678` — **sólo por el tailnet**, nunca desde
internet, porque guarda credenciales del negocio.

Tres nodos:

| Nodo | Qué hace |
|---|---|
| **Email Trigger (IMAP)** | Vigila `facturas@learningcenter.mx`. Servidor `imap.gmail.com`, puerto 993, SSL. La contraseña es la **misma contraseña de aplicación** que ya usa El Cartero para enviar — no hay que generar otra. |
| **Filter / IF** | Deja pasar sólo los adjuntos que terminan en `.xml`. |
| **HTTP Request** | `POST` a `https://taller.learningcenter.mx/facturacion/api/cfdi-entrante/` con la cabecera `x-cfdi-token: <el token>` y el XML en el cuerpo. |

El endpoint acepta el XML de tres formas, para que no haya que pelearse con la
configuración de n8n: crudo en el cuerpo, como archivo subido (`archivo`), o
envuelto en JSON (`{"xml": "...", "base64": true}`).

### 3. Qué contesta

Siempre JSON, nunca una traza — del otro lado hay un robot:

```json
{"ok": true, "estado": "ligado", "uuid": "…", "mensaje": "Ligado a FAC-2026-0012.", "factura": "FAC-2026-0012"}
{"ok": true, "estado": "pendiente", "mensaje": "Hay 2 facturas que coinciden (…)"}
{"ok": false, "estado": "rechazado", "mensaje": "El XML no es un comprobante fiscal."}
```

---

## Lo que ya está cuidado

- **Reenviar el mismo correo no archiva dos copias.** El folio fiscal es único
  en todo México, y eso lo garantiza la base, no la confianza en que el flujo
  no se repita.
- **Una factura de proveedor no se cuela como ingreso.** Si nos la emitieron a
  nosotros es un gasto, y ligarla a una factura nuestra metería una compra en
  los ingresos. Se archiva aparte.
- **Un comprobante sin timbrar no se archiva.** Sin folio fiscal el SAT no lo
  reconoce; archivarlo dejaría la contabilidad apoyada en un papel que no vale.
- **El XML viene de fuera.** Al buzón puede escribir cualquiera, así que se
  rechaza todo archivo con `<!DOCTYPE` o `<!ENTITY`: el parser de Python expande
  entidades, y un kilobyte puede inflarse a gigabytes y tumbar el proceso. Un
  CFDI legítimo nunca las lleva.

---

## Lo que falta

- **La pantalla de pendientes.** Hoy los CFDI que no se pudieron ligar quedan
  registrados con su motivo, pero no hay una vista para resolverlos desde la
  interfaz. Es lo siguiente.
- **Los gastos de proveedor.** Se archivan, pero no generan el egreso solos:
  eso pide decidir centro de costo y forma de pago, que es de quien captura.
- **El aviso.** Cuando algo queda pendiente, nadie se entera hasta que entra a
  mirar. Un push del Interfón cerraría el círculo.
