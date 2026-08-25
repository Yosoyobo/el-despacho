"""Candados de la ronda de latencia del 2026-08-24.

El disparador fue una captura de El Vigía: enviar un mensaje tardaba 2832 ms y
guardar un proyecto 1275 ms. Medido contra producción, eran tres causas
distintas, y estos tests fijan las tres para que no vuelvan por descuido.

Las tres se verificaron contra el código SIN arreglar: revertir cualquiera de
los cambios pone en rojo a su test.
"""

from __future__ import annotations

import inspect
import threading

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

pytestmark = pytest.mark.django_db


@pytest.fixture
def jefa(django_user_model):
    return django_user_model.objects.create_user(
        email="jefa@latencia.mx", password="x",
        rol="super_admin", nombre_completo="Jefa LC",
    )


# ── 1. El peaje de permisos ──────────────────────────────────────────────────


class TestPermisosNoCobranPorModulo:
    """`puede()` hacía DOS consultas por llamada, y el sistema la llama decenas
    de veces por petición: el menú recorre los ~23 módulos del catálogo y encima
    vistas y plantillas vuelven a preguntar. Medido en producción, el detalle de
    un proyecto gastaba 60 de sus 231 consultas en la tabla de permisos."""

    def test_muchas_preguntas_cuestan_una_sola_lectura(self, jefa):
        from lib.permisos import invalidar_cache_permisos, puede
        from lib.permisos_defaults import CATALOGO_PERMISOS

        modulos = list(CATALOGO_PERMISOS)[:20]
        assert len(modulos) >= 10, "el catálogo debería traer módulos de sobra"

        invalidar_cache_permisos()
        with CaptureQueriesContext(connection) as capturadas:
            for modulo in modulos:
                puede(jefa, modulo, "ver")

        # Dos: los permisos propios del usuario y los de sus roles. Sin caché
        # serían dos POR MÓDULO — cuarenta para estos veinte.
        assert len(capturadas) <= 2, (
            f"{len(capturadas)} consultas para {len(modulos)} módulos: "
            "el caché de permisos dejó de funcionar"
        )

    def test_el_menu_completo_cuesta_dos_consultas(self, jefa, rf):
        from cuentas.context_processors import permisos_modulos
        from lib.permisos import invalidar_cache_permisos

        invalidar_cache_permisos()
        peticion = rf.get("/")
        peticion.user = jefa

        with CaptureQueriesContext(connection) as capturadas:
            # El valor es perezoso: hay que tocarlo para que se calcule.
            dict(permisos_modulos(peticion)["permisos_modulos"])

        assert len(capturadas) <= 2, f"{len(capturadas)} consultas para armar el menú"

    def test_cambiar_un_permiso_se_nota_de_inmediato(self, jefa):
        """El memo vive lo que dura la petición, así que la única forma de que
        mienta es una vista que CAMBIE permisos y vuelva a leerlos — el panel de
        El Directorio. Los signals cierran esa ventana."""
        from cuentas.models.permiso_usuario import PermisoUsuario
        from lib.permisos import puede

        PermisoUsuario.objects.filter(
            usuario=jefa, modulo="cartera", permiso="ver"
        ).delete()
        fila = PermisoUsuario.objects.create(
            usuario=jefa, modulo="cartera", permiso="ver", activo=False
        )
        assert puede(jefa, "cartera", "ver") is False

        fila.activo = True
        fila.save()
        assert puede(jefa, "cartera", "ver") is True, (
            "el memo sirvió el permiso viejo tras guardarlo"
        )

        fila.delete()
        assert puede(jefa, "cartera", "ver") is False

    def test_revocar_gana_sobre_el_rol(self, jefa):
        """La precedencia de siempre: un `activo=False` individual revoca aunque
        un rol conceda. El caché no puede cambiar esa regla."""
        from cuentas.models.permiso_usuario import PermisoUsuario
        from cuentas.models.rol import Rol
        from lib.permisos import puede

        rol = Rol.objects.create(
            clave="prueba-latencia", nombre="Prueba", permisos={"cartera": ["ver"]},
        )
        jefa.roles_extra.add(rol)
        PermisoUsuario.objects.update_or_create(
            usuario=jefa, modulo="cartera", permiso="ver",
            defaults={"activo": False},
        )
        assert puede(jefa, "cartera", "ver") is False

        PermisoUsuario.objects.filter(
            usuario=jefa, modulo="cartera", permiso="ver"
        ).delete()
        assert puede(jefa, "cartera", "ver") is True, "el rol debía conceder"

    def test_conceder_por_rol_extra_se_nota(self, jefa):
        from cuentas.models.permiso_usuario import PermisoUsuario
        from cuentas.models.rol import Rol
        from lib.permisos import puede

        PermisoUsuario.objects.filter(
            usuario=jefa, modulo="cartera", permiso="ver"
        ).delete()
        assert puede(jefa, "cartera", "ver") is False

        rol = Rol.objects.create(
            clave="rol-tardio", nombre="Tardío", permisos={"cartera": ["ver"]},
        )
        jefa.roles_extra.add(rol)
        assert puede(jefa, "cartera", "ver") is True, (
            "agregar un rol no invalidó el memo"
        )


# ── 2. El contexto sólo cobra lo que la plantilla usa ────────────────────────


class TestElContextoNoCobraLoQueNadieUsa:
    """Django corre TODOS los context processors en cada petición, aunque la
    plantilla no toque ni una de sus variables. Por eso el banner de deploy —un
    div vacío que se pide cada 10 s— gastaba 65 consultas."""

    def test_armar_el_contexto_no_consulta_nada(self, jefa, rf):
        from auth_google.context_processors import google_oauth_configurado
        from buzon.context_processors import buzon_no_leidos
        from cuentas.context_processors import permisos_modulos, sidebar_orden
        from interfono.context_processors import notificaciones_no_leidas

        peticion = rf.get("/")
        peticion.user = jefa

        with CaptureQueriesContext(connection) as capturadas:
            for procesador in (permisos_modulos, sidebar_orden, buzon_no_leidos,
                               notificaciones_no_leidas, google_oauth_configurado):
                procesador(peticion)

        assert len(capturadas) == 0, (
            f"{len(capturadas)} consultas sin que nadie usara los valores"
        )

    def test_tocar_el_valor_lo_calcula(self, jefa, rf):
        from cuentas.context_processors import permisos_modulos

        peticion = rf.get("/")
        peticion.user = jefa
        valor = permisos_modulos(peticion)["permisos_modulos"]
        # Se comporta como el dict de siempre para quien lo consume.
        assert "cartera" in dict(valor)

    def test_las_claves_declaradas_son_las_que_devuelve(self, jefa, rf):
        """Si alguien agrega una variable al context processor y olvida
        declararla en `@perezoso`, esa variable desaparece del contexto **en
        silencio** y la plantilla la pinta vacía."""
        from cuentas.context_processors import sidebar_orden

        peticion = rf.get("/")
        peticion.user = jefa
        declaradas = set(sidebar_orden._perezoso_claves)
        assert declaradas == {"sidebar_orden", "sidebar_carpetas_json"}
        assert set(sidebar_orden(peticion)) == declaradas

    def test_formato_hora_sigue_siendo_inmediato(self, jefa, rf):
        """`formato_hora` NO puede ser perezoso: fija un thread-local que el
        filtro `hfmt` lee aunque la plantilla nunca nombre la variable. Diferirlo
        dejaría todas las horas en el formato equivocado."""
        from cuentas.context_processors import formato_hora

        assert not hasattr(formato_hora, "_perezoso_claves"), (
            "formato_hora tiene efectos secundarios: no puede ser perezoso"
        )
        peticion = rf.get("/")
        peticion.user = jefa
        formato_hora(peticion)
        from lib.formato_hora import get_formato

        assert get_formato() in ("24h", "ampm")

    def test_un_anonimo_tampoco_paga(self, rf):
        from django.contrib.auth.models import AnonymousUser

        from cuentas.context_processors import permisos_modulos

        peticion = rf.get("/")
        peticion.user = AnonymousUser()
        assert dict(permisos_modulos(peticion)["permisos_modulos"]) == {}


# ── 3. El push, fuera de la petición ─────────────────────────────────────────


class TestElPushNoHaceEsperar:
    """Enviar un mensaje esperaba a que Apple y Google acusaran recibo de ocho
    notificaciones, en serie y abriendo TLS nuevo cada vez. El mensaje se guarda
    en milisegundos; lo que tardaba era avisarle a los demás."""

    def test_el_trabajo_se_encola_en_vez_de_correr(self, monkeypatch):
        from lib import tareas_fondo

        encoladas: list = []

        class PoolFalso:
            def submit(self, fn, *args, **kwargs):
                encoladas.append((fn, args))

        monkeypatch.setattr(tareas_fondo, "_en_fondo_activo", lambda: True)
        monkeypatch.setattr(tareas_fondo, "_obtener_pool", PoolFalso)

        def _lento():
            raise AssertionError("esto no debía correr dentro de la petición")

        tareas_fondo.ejecutar_en_fondo(_lento)
        assert len(encoladas) == 1, "el trabajo no se encoló al fondo"

    def test_un_fallo_en_el_fondo_no_tumba_nada(self):
        from lib.tareas_fondo import ejecutar_en_fondo

        def _truena():
            raise RuntimeError("el proveedor de push está caído")

        # En pruebas corre síncrono: si no tragara la excepción, esto reventaría.
        ejecutar_en_fondo(_truena)

    def test_el_trabajo_sí_se_ejecuta(self):
        from lib.tareas_fondo import ejecutar_en_fondo

        hecho = threading.Event()
        ejecutar_en_fondo(hecho.set)
        assert hecho.is_set(), "el trabajo no se ejecutó"

    def test_el_push_del_chat_pasa_por_el_fondo(self):
        """Candado de forma: sin él alguien puede volver a poner el `on_commit`
        pelón y los 2.8 segundos regresan sin que nada falle."""
        from apps.recados import services_chat

        fuente = inspect.getsource(services_chat.enviar_mensaje)
        assert "ejecutar_en_fondo(_disparar_push" in fuente

    def test_los_avisos_de_negocio_pasan_por_el_fondo(self):
        from apps.taller_home import push_handlers

        fuente = inspect.getsource(push_handlers)
        assert "transaction.on_commit(_hacer)" not in fuente, (
            "un push quedó despachándose dentro de la petición"
        )
        assert fuente.count("_al_confirmar(_hacer)") >= 10

    def test_varias_suscripciones_reusan_la_conexion(self):
        """El handshake TLS es lo caro (160-230 ms contra Apple). Cinco
        dispositivos del mismo proveedor deben pagarlo una vez, no cinco."""
        from lib import interfono

        fuente = inspect.getsource(interfono.enviar_a_usuario)
        assert "sesion=sesion" in fuente
        assert "requests_session=sesion" in inspect.getsource(
            interfono.enviar_a_suscripcion
        )


# ── 4. Las escalas del proyecto ──────────────────────────────────────────────


class TestElProyectoNoRepreguntaPorSusEscalas:
    def test_las_escalas_vienen_precargadas(self):
        """`precio_efectivo` y compañía preguntan por la escala activa de cada
        línea. Sin prefetch eso es una consulta por línea y por acceso: el
        detalle de un proyecto gastaba 59 consultas sólo en eso."""
        from apps.los_proyectos.models.proyecto import Proyecto

        fuente = inspect.getsource(Proyecto._productos_calc)
        assert '"escalas"' in fuente, (
            "el prefetch de escalas desapareció — vuelve el N+1"
        )

    def test_leer_el_dinero_no_escala_con_el_numero_de_lineas(
        self, proyecto_factory, jefa
    ):
        from apps.el_catalogo.models import CategoriaServicio, Servicio
        from apps.los_proyectos.models import ProyectoProducto

        categoria = CategoriaServicio.objects.create(nombre="Textiles")
        proyecto = proyecto_factory(creado_por=jefa)
        for i in range(8):
            servicio = Servicio.objects.create(
                nombre=f"Playera {i}", categoria=categoria,
                precio_base="100.00", costo="40.00",
            )
            ProyectoProducto.objects.create(
                proyecto=proyecto, servicio=servicio,
                cantidad=10, incluir_en_calculo=True,
            )

        # Calienta cachés de catálogo y de config fiscal, que no dependen del
        # número de líneas.
        _ = proyecto.monto_calculado

        with CaptureQueriesContext(connection) as capturadas:
            for pp in proyecto.productos_incluidos:
                _ = pp.precio_efectivo
                _ = pp.cantidad_efectiva
                _ = pp.piezas_efectivas

        # Una carga de líneas más sus prefetch (procesos, proveedor de proceso,
        # ventas, escalas). Lo que no puede pasar es que crezca con las líneas:
        # sin el prefetch esto pasaba de 24.
        assert len(capturadas) <= 8, (
            f"{len(capturadas)} consultas para leer el dinero de 8 líneas"
        )
