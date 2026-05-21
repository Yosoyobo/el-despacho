FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Tailwind CLI standalone (sin Node)
ARG TAILWIND_VERSION=v3.4.17
RUN curl -fsSL -o /usr/local/bin/tailwindcss \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64" \
    && chmod +x /usr/local/bin/tailwindcss

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Código compartido + app
COPY lib/ /app/lib/
COPY cuentas/ /app/cuentas/
COPY ajustes/ /app/ajustes/
COPY buzon/ /app/buzon/
COPY interfono/ /app/interfono/
COPY auth_google/ /app/auth_google/
COPY proximamente/ /app/proximamente/
COPY referencias/ /app/referencias/
COPY chalanes/ /app/chalanes/
# S2b.3: la app `apps.tesoreria` vive en El Taller, pero La Gerencia
# importa el modelo CentroDeCosto + el form para su CRUD admin en
# /catalogos/. Y como Tesorería tiene FK a `cartera.Cliente` y
# `proyectos.Proyecto`, ambos apps tienen que estar instalados para
# que el grafo de FKs cierre (system check E300). Copia explícita —
# regla §14 Bug A.
COPY el-taller/apps/la_cartera/ /app/apps/la_cartera/
COPY el-taller/apps/los_proyectos/ /app/apps/los_proyectos/
COPY el-taller/apps/tesoreria/ /app/apps/tesoreria/
# S2b.cotizaciones-v1 + S2b.facturacion-v1 + S3.contaduria-v1/v2:
# cierran el grafo de FKs (Bug A). tesoreria.Ingreso.factura →
# facturacion.Factura → cotizaciones.Cotizacion. Gerencia no expone
# URLs de estos, pero Django necesita los modelos registrados para
# que el system check no tire E300 al arrancar.
COPY el-taller/apps/el_catalogo/ /app/apps/el_catalogo/
COPY el-taller/apps/cotizaciones/ /app/apps/cotizaciones/
COPY el-taller/apps/facturacion/ /app/apps/facturacion/
COPY el-taller/apps/contaduria/ /app/apps/contaduria/
COPY la-gerencia/ /app/

# Compilar Tailwind si hay config
RUN if [ -f tailwind.config.js ]; then \
        tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css --minify; \
    fi

RUN mkdir -p /data/credenciales /app/staticfiles

EXPOSE 8001

ENTRYPOINT ["./entrypoint.sh"]
