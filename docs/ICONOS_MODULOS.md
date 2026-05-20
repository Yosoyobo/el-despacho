# Iconos reservados para módulos de El Despacho

> **Versión:** 1.1 · creado en S-TailAdmin-2, actualizado en S-TailAdmin-3 (15 mayo 2026)
> **Propósito:** asignar de antemano qué icono representa visualmente a cada
> módulo, presente o futuro, para que cuando un sprint lo implemente no se
> elija el icono ad-hoc. Consistencia visual a través del tiempo.
>
> **Cambios v1.1:** El Interfón pasó a "vivo" (facelift completo en S-3).
> Partial `interfono/_panel_suscripcion.html` agregado a la lista de partials
> reusables del arco. Avatar del Chalán existe ya en `_avatar_chalan.html`
> con contrato `chalan='claudio|gpt|chino|gemini'` (hoy genérico).

Todos los iconos son SVG inline (path `viewBox="0 0 24 24"`, `stroke="currentColor"`,
`stroke-width="1.5"`). NO se importan de una librería de iconos externa — son
adaptaciones del set "feather"/TailAdmin Pro embebidas directamente en los
templates.

## Convención de uso

- En el sidebar: `class="h-5 w-5"` con `stroke-width="1.5"`.
- En tarjetas/headers grandes: `class="h-6 w-6"` o `h-8 w-8`.
- En botones inline: `class="h-4 w-4"` o `h-3.5 w-3.5`.
- Color: `currentColor` siempre, lo hereda el contexto.

## Módulos vivos (S-TailAdmin-2)

| Módulo | Sidebar | Descripción del path |
|---|---|---|
| Sala de Juntas / Inicio | 🏠 casa | `M3 12 12 3l9 9M5 10v10h14V10` |
| El Site | ☰ líneas | tres líneas horizontales |
| El Directorio | 👥 personas | silueta de dos personas |
| El Catálogo | 📖 marcador | libro abierto con marcapáginas |
| El Buzón | ✉️ sobre | sobre con triángulo de pestaña |
| El Interfón | 🔔 campana | campana con badge inferior |
| Los Ajustes | ⚙️ engrane | engrane con pétalos |
| Tasas | 📈 grafo | línea ascendente |
| La Cartera | 👥 clientes | silueta de personas (mismo que Directorio, contexto diferencia) |
| Los Proyectos | 📁 carpeta | folder con pestaña |
| El Pizarrón | (no tiene entrada propia en sidebar — vive dentro de Proyectos) | — |
| Notificaciones (perfil) | 🔔 campana | igual a Interfón |

## Módulos reservados (futuros)

| Módulo | Sprint | Sidebar | Descripción del path |
|---|---|---|---|
| Los Recados | S2b.1 ✅ | 💬 flecha-burbuja | `M21 12a9 9 0 1 1-3.2-6.9L21 4v6h-6` (refresh-message) |
| La Tesorería | S2b.3 ✅ | 💰 caja registradora | `M3 7h18v10H3zM7 7v10M17 7v10M12 10v4` |
| Los Chalanes | pre-S2b ✅ | 🤖 robot | `M7 7h10a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H7…` |
| El Dictado (historial) | S2b.2 ✅ | 🎙️ micrófono | vivo bajo `/dictado/historial/` |
| Sistema de Referencias | pre-S2b ✅ | 🔗 cadena | autocomplete `@/#/$` |
| Centros de costo | S2b.3 ✅ | 📂 carpetas | vive en La Gerencia → Catálogos |
| Cotizaciones | S2 | 📄 documento | reservado |
| Facturación | S2 | 📃 documento con $ | reservado |
| La Caja (Stripe + MP) | S2 | 💳 tarjeta | reservado |
| La Cobranza | S2 | ⏰ reloj | reservado |
| La Contaduría | S3 | 📊 gráfica | reservado |

## Avatares de los Chalanes (DOC_02)

Hoy todos los Chalanes comparten el SVG genérico de `_avatar_chalan.html`:
silueta de robot con dos "ojos" puntuales + boca lineal. En sprint pre-S2b
se diferenciarán visualmente:

| Chalán | Proveedor | Color sugerido | Sello distintivo (pendiente diseño) |
|---|---|---|---|
| Claudio | Anthropic | brand-500 | tilde sutil sobre la cabeza |
| GPT | OpenAI | success-500 | flor de 4 pétalos |
| Chino | DeepSeek | warning-500 | media luna |
| Gemini | Google | error-500 (?) | doble triángulo |

El componente acepta `chalan='claudio|gpt|chino|gemini'` desde S-TailAdmin-2 —
hoy todos renderizan idéntico pero el contrato está cerrado.

## Adición de nuevos módulos

Si un sprint futuro necesita un módulo que no esté listado, el procedimiento es:

1. Antes de tocar templates, agregar fila a este documento con el icono asignado.
2. Si es módulo placeholder coming-soon, registrarlo en `proximamente/views.py`
   en el dict `MODULOS` (slug, nombre, icono emoji, descripción, sprint, doc ref).
3. Si tiene sidebar propio, agregar entrada en `_componentes_tailadmin/sidebar.html`
   de Gerencia y Taller (las dos copias).

Esto evita la deriva visual y permite que un sprint nuevo herede una semántica
ya decidida.
