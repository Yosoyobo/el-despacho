# Especificación Técnica: Ajuste de Márgenes y Header en Cotizaciones PDF

**Objetivo:** Ajustar el maquetado del PDF para acercar la alineación del encabezado y logo a la versión original de Pages, reduciendo márgenes superior/inferior para maximizar el área imprimible y prevenir páginas en blanco accidentales.

---

## 1. Encabezado y Logo (Ajuste Superior)

* **Reducción de Margen Superior (`margin-top` / `@page`):**
  * Disminuir el margen superior para empujar la fecha, el logo y el nombre del cliente/compañía más arriba, igualando la posición de la plantilla clásica de Pages.
* **Escalado del Logo:**
  * Incrementar el tamaño del logo central de Learning Center aproximadamente un **5%** para mejorar su presencia visual.
* **Alineación:**
  * Mantener la distribución horizontal del encabezado: `[Fecha]` a la izquierda, `[Logo]` al centro, y `[Nombre de Cliente / Empresa]` a la derecha.

---

## 2. Optimización del Área Imprimible (Ajuste Inferior)

* **Ampliación del Margen Inferior (`margin-bottom`):**
  * Empujar de forma invisible el límite inferior del área de contenido hacia abajo en aproximadamente un **10%**.
* **Prevención de Páginas Huérfanas / Vacías:**
  * Al aprovechar mejor el espacio vertical del documento, se evita que las notas al pie o totales empujen una segunda página vacía o con solo un par de líneas.

---

## 3. Elementos que se Mantienen Intactos

* Estructura de la tabla de conceptos (*Concepto, Cantidad, Precio Unitario, Subtotal*).
* Desglose de totales e impuestos (IVA, retenciones ISR/IVA).
* Bloque de notas al pie y políticas comerciales.
* Posicionamiento de la imagen ilustrativa del producto a la derecha.