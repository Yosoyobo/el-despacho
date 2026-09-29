# Etapa de apoyo: aparta La Caja SI existe (ver más abajo). Así la imagen final no
# carga una copia entera de `el-taller/apps` sólo para preguntar por una carpeta.
FROM alpine:3 AS opcionales
COPY el-taller/apps/ /src/
RUN mkdir -p /opt/caja && if [ -d /src/caja ]; then cp -r /src/caja/. /opt/caja/; fi

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Tailwind CLI standalone (sin Node), igual que El Taller y La Gerencia.
ARG TAILWIND_VERSION=v3.4.17
RUN curl -fsSL -o /usr/local/bin/tailwindcss \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64" \
    && chmod +x /usr/local/bin/tailwindcss

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Código compartido. Cada app de `INSTALLED_APPS` de `la_recepcion/settings.py`
# tiene su COPY aquí (§14 Bug A: si falta, la imagen se construye y el
# contenedor truena al arrancar; el smoke test del CI lo caza).
COPY lib/ /app/lib/
COPY cuentas/ /app/cuentas/
COPY ajustes/ /app/ajustes/
COPY interfono/ /app/interfono/
COPY portal/ /app/portal/
# El Chalán: lee la Constancia de Situación Fiscal que sube el cliente.
COPY chalanes/ /app/chalanes/
# Los MODELOS de El Taller que el portal lee (sin sus pantallas). Es el mismo
# grafo de llaves foráneas que instala La Gerencia: facturas → cotizaciones →
# catálogo, proyectos ↔ pizarrón ↔ checador, tesorería → contaduría.
COPY el-taller/apps/la_cartera/ /app/apps/la_cartera/
COPY el-taller/apps/los_proyectos/ /app/apps/los_proyectos/
COPY el-taller/apps/el_pizarron/ /app/apps/el_pizarron/
COPY el-taller/apps/el_catalogo/ /app/apps/el_catalogo/
COPY el-taller/apps/tesoreria/ /app/apps/tesoreria/
COPY el-taller/apps/cotizaciones/ /app/apps/cotizaciones/
COPY el-taller/apps/facturacion/ /app/apps/facturacion/
COPY el-taller/apps/contaduria/ /app/apps/contaduria/
COPY el-taller/apps/checador/ /app/apps/checador/
# La Caja es OPCIONAL a propósito (contrato del sprint): si su app ya existe en
# el repo, entra a la imagen y el portal enseña «Pagar»; si todavía no —vive en
# otra rama—, la imagen se construye igual y el portal funciona sin botón. Un
# COPY directo de una carpeta que no existe tumbaría el build.
# Sin La Caja la carpeta queda vacía y `settings` no la instala (pregunta por
# `apps.caja.apps`, no por la carpeta).
COPY --from=opcionales /opt/caja/ /app/apps/caja/
COPY la-recepcion/ /app/

# Compilar Tailwind (el CSS commiteado sólo sirve para desarrollo local).
RUN if [ -f tailwind.config.js ]; then \
        tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css --minify; \
    fi

RUN mkdir -p /data/credenciales /app/staticfiles

EXPOSE 8002

ENTRYPOINT ["./entrypoint.sh"]
