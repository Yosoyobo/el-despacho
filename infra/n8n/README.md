# n8n — la copia de los flujos

Las automatizaciones viven en n8n, en el NUC de Learning Center
(`https://nuc-learning-center.tailedd04d.ts.net`, sólo por el tailnet). Esta
carpeta es su **espejo en el repo**: un JSON por flujo, para ver en la historia
de git qué cambió y cuándo, y para poder rehacer uno aunque la base de n8n se
pierda.

No es el respaldo — la base completa de n8n entra al respaldo de cada tres días
(`infra/scripts/archivo.sh`, serie `n8n-*.tar.gz`). Esto es la versión legible.

## Exportar (después de armar o cambiar una automatización)

Desde cualquier máquina del tailnet, con la llave de la API de n8n:

```bash
N8N_API_KEY=… python3 infra/n8n/exportar_flujos.py
git add infra/n8n/flujos && git commit -m "n8n: <qué cambió>"
```

El guion escribe `flujos/<nombre>-<id>.json` y **retira** el archivo de un flujo
que ya no existe (o que se archivó). Renombrar un flujo reemplaza su archivo: el
id va al final del nombre justo para eso.

## Qué trae cada JSON y qué no

- **Sí:** nombre, descripción, si está publicado, los nodos con sus parámetros,
  las conexiones, los ajustes y las etiquetas.
- **No:** credenciales (n8n las guarda aparte y cifradas; en el flujo sólo va el
  nombre de la credencial que usa cada nodo) ni lo que cambia solo
  (`updatedAt`, `versionId`, `staticData`), que ensuciaría cada diff.

## Rehacer un flujo desde aquí

Con el MCP de n8n (lo normal): pedirle a Claude que lo reconstruya a partir del
JSON. A mano: en n8n, *Workflows → Import from file*. Nace sin publicar, como
todo flujo nuevo; hay que volver a conectarle sus credenciales.
