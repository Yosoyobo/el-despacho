"""Context processors que sólo cobran lo que la plantilla usa.

Django ejecuta **todos** los context processors en cada petición que renderiza
una plantilla, aunque la plantilla no toque ni una de sus variables. En El
Despacho eso se volvió caro: son 16, varios consultan la base, y el polling de
HTMX (banner de deploy y semáforo cada 10 s, bandeja cada 15 s, mensajes cada
5 s) pide fragmentos que no pintan sidebar, ni badges, ni permisos — pero los
pagaban igual. Medido en producción el 2026-08-24: el banner de deploy hacía
**65 consultas para devolver un div vacío**.

`perezoso` envuelve las variables en `SimpleLazyObject`: el cuerpo del context
processor no corre hasta que alguien las toca de verdad. Un fragmento que no
las menciona no paga nada; una página completa paga exactamente lo de antes.

    @perezoso("permisos_modulos")
    def permisos_modulos(request):
        ...   # el cuerpo no cambia

Los contadores declaran su tipo, porque su envoltorio tiene que seguir
comportándose como un número (`>= 1`, `+ 1`, `int(...)`), no sólo pintarse:

    @perezoso("buzon_no_leidos_count", tipo=int)
    def buzon_no_leidos(request):
        ...

Las variables de UN mismo context processor comparten el cálculo: tocar una
resuelve todas las suyas, que es justo lo que se quiere cuando salen de la
misma consulta.

**No lo uses en un context processor con efectos secundarios.** `formato_hora`
fija un thread-local que el filtro `hfmt` lee aunque la plantilla nunca nombre
la variable; volverlo perezoso dejaría las horas en el formato equivocado. Si
el context processor hace algo además de devolver datos, tiene que seguir
corriendo siempre.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from django.utils.functional import SimpleLazyObject, lazy


def perezoso(*claves: str, tipo: type | None = None) -> Callable:
    """Difiere el cuerpo de un context processor hasta que se use una de `claves`.

    `claves` son los nombres de las variables que el context processor mete en
    el contexto. Hay que declararlas porque el contexto se arma antes de saber
    qué va a usar la plantilla.

    `tipo` declara de qué son los valores. Sin él, el envoltorio sabe pintarse,
    decir si es verdadero y dejarse indexar — de sobra para un dict, un texto o
    una bandera. Un CONTADOR necesita además comparar y sumar (`>= 1`, `+ 1`),
    así que va con `tipo=int`; si no, quien lo compare se lleva un TypeError.
    """

    def decorador(fn: Callable) -> Callable:
        @wraps(fn)
        def envoltura(request):
            memo: dict = {}

            def calcular():
                if "valor" not in memo:
                    memo["valor"] = fn(request) or {}
                return memo["valor"]

            # `clave=clave` captura el valor de esta vuelta del bucle: sin eso
            # todas las lambdas verían la última clave.
            def envolver(clave: str):
                traer = lambda clave=clave: calcular().get(clave)  # noqa: E731
                if tipo is None:
                    return SimpleLazyObject(traer)
                return lazy(traer, tipo)()

            return {clave: envolver(clave) for clave in claves}

        envoltura._perezoso_claves = claves  # para los tests
        return envoltura

    return decorador


__all__ = ["perezoso"]
