"""El Celador — la credencial con la que el monitor del taller pide de más.

El monitor **pregunta; nadie le reporta**: pega a `GET /salud` por la dirección
pública y lee lo que contestemos. Sin credencial ve la cara pública (nivel 1);
con la cabecera `x-celador: <token>` ve el desglose (nivel 2: gasto de IA y uso).

De dónde sale el token, en este orden:

1. **La Bóveda**, slot `celador_token` (regla §4 #3 del proyecto: TODA credencial
   se configura desde Los Ajustes, cifrada). Es el camino normal.
2. **El entorno**, `CELADOR_TOKEN` — el que pide el contrato del taller. Sirve
   para arrancar antes de tener acceso al GUI, y sobrevive si la base no
   responde (justo cuando `/salud` importa más).

**Sin token configurado, NADIE pasa.** Se cierra, no se abre: un extremo que al
faltarle la credencial deja entrar a todos es peor que uno sin credencial, porque
da la impresión de estar protegido.
"""

from __future__ import annotations

import hmac
import os

SLOT_BOVEDA = "celador_token"
ENV_TOKEN = "CELADOR_TOKEN"
CABECERA = "x-celador"


def _token_boveda() -> str:
    """Token guardado en Los Ajustes. Cadena vacía si no hay, si la base no
    responde o si La Bóveda no puede descifrarlo — nunca lanza."""
    try:
        from ajustes.models.credencial import Credencial

        return (Credencial.obtener(SLOT_BOVEDA) or "").strip()
    except Exception:  # noqa: BLE001 — la salud nunca depende de que la base esté viva
        return ""


def _token_entorno() -> str:
    return (os.environ.get(ENV_TOKEN) or "").strip()


def tokens_configurados() -> list[str]:
    """Los tokens aceptados, sin vacíos. Lista vacía = nadie pasa."""
    return [t for t in (_token_boveda(), _token_entorno()) if t]


def esta_configurado() -> bool:
    return bool(tokens_configurados())


def token_valido(dado: str | None) -> bool:
    """Compara en tiempo constante contra cada token aceptado.

    `hmac.compare_digest` no delata el contenido letra por letra como haría un
    `==` (el tiempo de la comparación se vuelve un oráculo). Tolera largos
    distintos, así que no hace falta comparar longitudes aparte.
    """
    dado = (dado or "").strip()
    if not dado:
        return False
    aceptados = tokens_configurados()
    if not aceptados:
        return False
    # Se recorren TODOS los aceptados (sin cortar al primer acierto) para no
    # filtrar por tiempo cuál de los dos orígenes casó.
    ok = False
    for bueno in aceptados:
        if hmac.compare_digest(dado.encode("utf-8"), bueno.encode("utf-8")):
            ok = True
    return ok


def es_de_la_casa(request) -> bool:
    """True si la petición trae la cabecera `x-celador` con un token válido."""
    try:
        dado = request.headers.get(CABECERA)
    except Exception:  # noqa: BLE001 — request exótico (tests, WSGI raro)
        return False
    return token_valido(dado)


__all__ = [
    "CABECERA",
    "ENV_TOKEN",
    "SLOT_BOVEDA",
    "es_de_la_casa",
    "esta_configurado",
    "token_valido",
    "tokens_configurados",
]
