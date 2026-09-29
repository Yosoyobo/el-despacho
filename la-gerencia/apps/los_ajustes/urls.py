from django.urls import path

from . import views, views_kpis

urlpatterns = [
    path("", views.panel, name="ajustes-panel"),
    path("guardar", views.guardar, name="ajustes-guardar"),
    # Pre-S2b.1: rutas específicas antes que el slug catch-all, si no el slug
    # captura `analistas/probar` con clave='analistas' y nunca se llega a
    # probar_analistas.
    path("analistas/probar", views.probar_analistas, name="ajustes-probar-analistas"),
    path("google_oauth/probar", views.probar_google_oauth, name="ajustes-probar-google-oauth"),
    # Asistente guiado de Google Drive (OAuth sin clave). Antes del slug catch-all.
    path("google-drive/", views.google_drive_guia, name="ajustes-google-drive"),
    path("google-drive/cliente", views.google_drive_guardar_cliente, name="ajustes-google-drive-cliente"),
    path("google-drive/conectar", views.google_drive_conectar, name="ajustes-google-drive-conectar"),
    path("google-drive/oauth/callback", views.google_drive_callback, name="ajustes-google-drive-callback"),
    path("google-drive/desconectar", views.google_drive_desconectar, name="ajustes-google-drive-desconectar"),
    path("google-drive/probar", views.google_drive_probar, name="ajustes-google-drive-probar"),
    # El Cartero — canal de correo (SMTP / n8n). Antes del slug catch-all.
    path("cartero/", views.cartero_panel, name="ajustes-cartero"),
    path("cartero/guardar", views.cartero_guardar, name="ajustes-cartero-guardar"),
    path("cartero/probar", views.cartero_probar, name="ajustes-cartero-probar"),
    path("cartero/plantillas/", views.cartero_plantillas, name="ajustes-cartero-plantillas"),
    path("cartero/plantillas/nueva", views.cartero_plantilla_nueva, name="ajustes-cartero-plantilla-nueva"),
    path("cartero/remitentes/", views.cartero_remitentes, name="ajustes-cartero-remitentes"),
    path("cartero/remitentes/marcar", views.cartero_remitente_marcar, name="ajustes-cartero-remitente-marcar"),
    path("cartero/remitentes/probar", views.cartero_remitente_probar, name="ajustes-cartero-remitente-probar"),
    path("cartero/remitentes/dueno", views.cartero_remitente_dueno, name="ajustes-cartero-remitente-dueno"),
    path("cartero/reglas/", views.cartero_reglas, name="ajustes-cartero-reglas"),
    path("cartero/reglas/guardar", views.cartero_regla_guardar, name="ajustes-cartero-regla-guardar"),
    path("cartero/reglas/<int:pk>/borrar", views.cartero_regla_borrar, name="ajustes-cartero-regla-borrar"),
    path("cartero/plantillas/<slug:slug>/", views.cartero_plantilla_editar, name="ajustes-cartero-plantilla-editar"),
    path("cartero/plantillas/<slug:slug>/borrar", views.cartero_plantilla_borrar, name="ajustes-cartero-plantilla-borrar"),
    path("cartero/plantillas/<slug:slug>/probar", views.cartero_plantilla_probar, name="ajustes-cartero-plantilla-probar"),
    path("cartero/plantillas/<slug:slug>/redactar", views.cartero_plantilla_redactar, name="ajustes-cartero-plantilla-redactar"),
    path("<slug:clave>/probar", views.probar, name="ajustes-probar"),
    path("tasas/", views.tasas_lista, name="ajustes-tasas"),
    path("tasas/nueva", views.tasa_nueva, name="ajustes-tasa-nueva"),
    path("tasas/<int:pk>/editar", views.tasa_editar, name="ajustes-tasa-editar"),
    # S-LC-Feedback-V5 c6: orden y visibilidad del sidebar de El Taller (global).
    path("sidebar/", views.sidebar_panel, name="ajustes-sidebar"),
    path("sidebar/guardar", views.sidebar_guardar, name="ajustes-sidebar-guardar"),
    # S-LC-Feedback-V5 c8: metas KPI.
    # S-KPIs-V2: la pantalla de KPIs (catálogo, tableros, metas, constructor).
    # La URL vieja de metas lleva a su pestaña.
    path("metas-kpi/", views_kpis.metas_viejo, name="ajustes-metas-kpi"),
    path("kpis/", views_kpis.catalogo, name="ajustes-kpis"),
    path("kpis/catalogo/<slug:slug>/guardar", views_kpis.catalogo_guardar, name="ajustes-kpis-catalogo-guardar"),
    path("kpis/tableros/", views_kpis.tableros, name="ajustes-kpis-tableros"),
    path("kpis/tableros/accion", views_kpis.tablero_accion, name="ajustes-kpis-tablero-accion"),
    path("kpis/metas/", views_kpis.metas, name="ajustes-kpis-metas"),
    path("kpis/metas/crear", views_kpis.meta_crear, name="ajustes-kpis-meta-crear"),
    path("kpis/metas/<int:pk>/guardar", views_kpis.meta_guardar, name="ajustes-kpis-meta-guardar"),
    # S-Chalanes-UX #4: recordatorios de tareas por vencer (config global).
    path("recordatorios/", views.recordatorios_panel, name="ajustes-recordatorios"),
    # S3 resto: La Cobranza — recordatorios de pago al cliente.
    path("cobranza/", views.cobranza_panel, name="ajustes-cobranza"),
    # Figuras fiscales (régimen + ISR/PTU/IVA).
    path("fiscal/", views.fiscal_panel, name="ajustes-fiscal"),
    # El Análisis: umbrales del negocio + costo por hora de cada rol.
    path("analisis/", views.analisis_panel, name="ajustes-analisis"),
    path("rutas/", views.rutas_panel, name="ajustes-rutas"),
    path("papeleo/", views.papeleo_panel, name="ajustes-papeleo"),
    # La Recepción (portal de clientes): «Entrar con Google», apagado por default.
    path("portal/", views.portal_panel, name="ajustes-portal"),
    path("documentos/", views.documentos_panel, name="ajustes-documentos"),
    path("servicios/", views.servicios_panel, name="ajustes-servicios"),
    path("cfdi/", views.cfdi_panel, name="ajustes-cfdi"),
    path("automatizaciones/", views.automatizaciones_panel, name="ajustes-automatizaciones"),
    path("automatizaciones/interruptor", views.automatizacion_interruptor, name="ajustes-automatizacion-interruptor"),
    path("automatizaciones/instalar", views.automatizacion_instalar, name="ajustes-automatizacion-instalar"),
]
