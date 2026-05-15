FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG TAILWIND_VERSION=v3.4.17
RUN curl -fsSL -o /usr/local/bin/tailwindcss \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64" \
    && chmod +x /usr/local/bin/tailwindcss

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY lib/ /app/lib/
COPY cuentas/ /app/cuentas/
COPY ajustes/ /app/ajustes/
COPY buzon/ /app/buzon/
COPY el-taller/ /app/

RUN if [ -f tailwind.config.js ]; then \
        tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css --minify; \
    fi

RUN mkdir -p /data/credenciales /app/staticfiles

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
