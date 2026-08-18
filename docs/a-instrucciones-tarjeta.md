# Especificación Técnica: Escalas de Volumen en Producto

**Objetivo:** Implementar el sistema de escalas de volumen (Opción B, C...) dentro de la tarjeta de producto, respetando el diseño UI y las reglas de heredabilidad y visibilidad.

---

## 1. Lógica de Selección y Visibilidad

* **Radio Button (`•`):** * Selecciona cuál opción calcula el total general del proyecto.
  * **Regla de negocio:** Solo puede haber **1 opción activa** por tarjeta.
  * Al aprobar un proyecto, el sistema fuerza la selección de una sola cantidad.
* **Ícono Ojo (`👁`):**
  * Controla si la opción se imprime/muestra en la propuesta en PDF.
  * Debe reflejar un cambio visual claro (estado tenue/gris u opaco) cuando esté deshabilitado (OFF).

---

## 2. Heredabilidad de Datos (Por Defecto)

* **Proveedor:** Heredar automáticamente el proveedor seleccionado en la opción principal (Opción A).
* **Costos:** Si los campos `COSTO UNIT.` o `COSTO IMPRESIÓN` en la Opción B se dejan vacíos o en `0.00`, el sistema debe heredar automáticamente los valores configurados en la Opción A.

---

## 3. Estructura de UI y Maquetación

* **Indentación y Jerarquía:**
  * Incluir una ligera sangría y el conector `↳` al inicio de la sub-fila de la Opción B para denotar jerarquía visual.
* **Campos por Sub-fila:**
  * Elementos: `↳ [ ] Radio`, `CANTIDAD (B)`, `MERMA`, `PRECIO UNIT.`, `COSTO UNIT.`, `IMPRESIÓN`, `[/p] por pieza` y botón eliminar `[X]`.
  * Resumen inferior individual: Muestra del `Costo de producción` y `MONTO` propios de esa escala, junto a su ícono de ojo `👁`.

---

## 4. Procesos Adicionales Dinámicos

* Al accionar `+ Proceso`, la columna de costo adicional debe insertarse de forma **dinámica inline** en el mismo renglón usando CSS Grid/Flexbox.
* Los anchos de los campos deben ajustarse proporcionalmente sin romper el maquetado horizontal ni generar salto de línea.