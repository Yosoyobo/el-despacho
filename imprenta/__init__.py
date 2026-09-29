"""La Imprenta — cómo se arman los documentos PDF de El Despacho.

App raíz compartida (patrón de `portal/`, `papeleo/`): la usan El Taller, que
genera los documentos, y La Gerencia, que los configura y los previsualiza —y
corre su migración (§14 Bug B)—. Ver `imprenta.esquema` para qué se ajusta y
`imprenta.config` para cómo se resuelve.
"""
