"""Los documentos nuevos de La Imprenta (Deploy 3 en adelante).

Cada módulo declara un `Documento` (su definición de ajustes, su plantilla, de
dónde salen los datos y quién lo puede ver) y `imprenta.documentos.base` los
dibuja, les pone su hoja y los convierte a PDF, todos igual. Así un documento
nuevo es un archivo aquí y una plantilla, no una vista más en cada app.
"""
