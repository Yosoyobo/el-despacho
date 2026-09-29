"""La Carga Contable (S-Carga-Contable).

Subir de un jalón la contabilidad que se llevó fuera de El Despacho para que,
a partir de ahí, todo cuadre. Tres piezas:

- `esquema`   — las hojas y columnas de la plantilla (una sola fuente: la usan
                quien la genera y quien la lee, así no divergen).
- `plantilla` — genera el Excel con listas desplegables del catálogo vivo.
- `lectura`   — lo lee tolerando lo que pega una persona (fechas «3/2/26»,
                montos «$1,200.00», acentos, mayúsculas).
- `motor`     — planea, ejecuta (vista previa que se deshace o aplicación de
                verdad: el mismo código), y deshace una carga aplicada.
"""
