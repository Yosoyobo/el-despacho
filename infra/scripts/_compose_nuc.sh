#!/usr/bin/env bash
# Qué archivos de compose (y qué profiles) forman El Despacho en el NUC.
#
# Se SOURCEA, no se ejecuta: deja `COMPOSE_FILES` y `COMPOSE_PROFILES` en el
# entorno de quien lo llama. Lo usan `deploy_nuc.sh` (cada deploy) y
# `arranque_nuc.sh` (cada vez que el NUC prende): si cada uno armara su propia
# lista, el día que se agregue un servicio uno de los dos lo olvidaría y ese
# servicio no volvería tras un reinicio — que es justo lo que pasó el 2026-09-18.
#
# Requiere estar parado en la raíz del proyecto (`cd /mnt/el-despacho`).

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
if [ -f docker-compose.site.yml ]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.site.yml"
fi
# El overlay del NUC saca a El Portero del stack (Caddy vive en la
# ventana) y publica los puertos 8200/8201 que la ventana consume por
# el tailnet. También sube el tuning de Postgres y Redis, que en el
# compose base está calibrado para el droplet de 1 GB.
if [ -f docker-compose.nuc.yml ]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.nuc.yml"
fi
# Los servicios auxiliares (Gotenberg, OSRM, n8n, Paperless). Van al final para
# que sus mem_limit no puedan ser pisados por un overlay anterior. Piden dos
# variables en el .env; si faltan, `up -d` aborta el stack COMPLETO —incluido El
# Despacho— así que se comprueba antes y, si no están, se despliega sin ellos.
if [ -f docker-compose.servicios.yml ]; then
  if grep -q "^N8N_ENCRYPTION_KEY=" .env && grep -q "^PAPERLESS_ADMIN_PASSWORD=" .env; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.servicios.yml"
    # n8n corre como el usuario 1000 y Docker crea los volúmenes como root: sin
    # esto se queda en «EACCES» reiniciando en bucle.
    mkdir -p data/n8n data/paperless/redis data/osrm
    # El chown va DESDE UN CONTENEDOR: el usuario del NUC no tiene sudo sin
    # contraseña, pero el demonio de Docker sí corre como root. Es el camino
    # que funciona en cualquier máquina, con sudo o sin él.
    docker run --rm -v "$(pwd)/data/n8n:/d" alpine:3 chown -R 1000:1000 /d >/dev/null 2>&1 || true
    # El Redis de Paperless escribe con SU usuario (999). Con otro dueño no
    # puede guardar y bloquea todas las escrituras: Paperless da 500 sin decir
    # por qué. No meter esta carpeta en el chown de arriba.
    mkdir -p data/paperless/redis
    docker run --rm -v "$(pwd)/data/paperless/redis:/d" alpine:3 chown -R 999:999 /d >/dev/null 2>&1 || true
    # OSRM sólo se levanta cuando su mapa está cocido; si no, no puede arrancar.
    if [ -f data/osrm/mexico-latest.osrm.properties ]; then
      COMPOSE_PROFILES="${COMPOSE_PROFILES:+$COMPOSE_PROFILES,}osrm"
      export COMPOSE_PROFILES
      echo "OSRM: mapa presente, se levanta."
    else
      echo "OSRM: sin mapa cocido en data/osrm; queda apagado (las rutas siguen en línea recta)."
    fi
    # El de bicicleta es un SEGUNDO mapa: el perfil de OSRM se hornea al
    # cocinarlo, no se elige en la petición. La variable se llena sólo cuando
    # el mapa existe; vacía, la app sabe que no hay bici y lo dice en pantalla
    # en vez de medir en coche fingiendo que mide en bici.
    mkdir -p data/osrm-bici
    if [ -f data/osrm-bici/mexico-latest.osrm.properties ]; then
      COMPOSE_PROFILES="${COMPOSE_PROFILES:+$COMPOSE_PROFILES,}osrm-bici"
      export COMPOSE_PROFILES
      export OSRM_URL_BICI="http://osrm-bici:5000"
      echo "OSRM bicicleta: mapa presente, se levanta."
    else
      export OSRM_URL_BICI=""
      echo "OSRM bicicleta: sin mapa (./infra/scripts/cocinar_mapa.sh bicycle para prepararlo)."
    fi
  else
    echo "AVISO: faltan N8N_ENCRYPTION_KEY o PAPERLESS_ADMIN_PASSWORD en .env;"
    echo "       los servicios auxiliares NO se despliegan (El Despacho sí)."
  fi
fi

