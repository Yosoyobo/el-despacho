"""Fixtures locales para tests de La Gerencia. Cambian el ROOT_URLCONF al
mapa de URLs de la-gerencia para que `client.get('/directorio/...')` resuelva.
"""

import pytest


@pytest.fixture(autouse=True)
def _urls_gerencia(settings):
    settings.ROOT_URLCONF = "tests.urls_gerencia"
