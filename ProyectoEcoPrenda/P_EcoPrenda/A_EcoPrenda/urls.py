from django.urls import path
from . import views

urlpatterns = [
    # Home y navegación
    path('', views.home, name='home'),

    # Cookies
    path('configurar-cookies/', views.configurar_cookies, name='configurar_cookies'),
    path('aceptar-cookies/', views.aceptar_cookies, name='aceptar_cookies'),
    path('rechazar-cookies/', views.rechazar_cookies, name='rechazar_cookies'),
    path('obtener-preferencias-cookies/', views.obtener_preferencias_cookies, name='obtener_preferencias_cookies'),
    path('eliminar-cookies/', views.eliminar_cookies, name='eliminar_cookies'),
    
    # Autenticación
    path('registro/', views.registro_usuario, name='registro'),
    path('login/', views.login_usuario, name='login'),
    path('logout/', views.logout_usuario, name='logout'),
    path('perfil/', views.perfil_usuario, name='perfil'),
    
    # Subidas de imágenes
    path('perfil/actualizar-foto/', views.actualizar_foto_perfil, name='actualizar_foto_perfil'),
    
    # Prendas
    path('prendas/', views.lista_prendas, name='lista_prendas'),
    path('prenda/<int:id_prenda>/', views.detalle_prenda, name='detalle_prenda'),
    path('prenda/nueva/', views.crear_prenda, name='crear_prenda'),
    path('prenda/<int:id_prenda>/editar/', views.editar_prenda, name='editar_prenda'),
    path('prenda/<int:id_prenda>/eliminar/', views.eliminar_prenda, name='eliminar_prenda'),
    path('mis-prendas/', views.mis_prendas, name='mis_prendas'),
    path('prenda/<int:id_prenda>/actualizar-imagen/', views.actualizar_imagen_prenda, name='actualizar_imagen_prenda'),
    
    # Transacciones
    path('intercambio/<int:id_prenda>/', views.proponer_intercambio, name='proponer_intercambio'),
    path('comprar/<int:id_prenda>/', views.comprar_prenda, name='comprar_prenda'),
    path('donar/<int:id_prenda>/', views.donar_prenda, name='donar_prenda'),
    path('mis-transacciones/', views.mis_transacciones, name='mis_transacciones'),
    path('transaccion/<int:id_transaccion>/estado/', views.actualizar_estado_transaccion, name='actualizar_estado_transaccion'),

    # Acciones de transacción (marcar/confirmar/cancelar)
    path('transaccion/<int:id_transaccion>/marcar-entregada/', views.marcar_compra_entregado, name='marcar_entregada'),
    path('transaccion/<int:id_transaccion>/confirmar-recepcion/', views.confirmar_recepcion_compra, name='confirmar_recepcion'),
    path('transaccion/<int:id_transaccion>/cancelar/', views.cancelar_compra, name='cancelar_transaccion'),
    path('transaccion/<int:id_transaccion>/donacion-enviada/', views.marcar_donacion_enviada, name='marcar_donacion_enviada'),
    path('transaccion/<int:id_transaccion>/reportar-disputa/', views.reportar_disputa, name='reportar_disputa'),
    path('admin/disputa/<int:id_transaccion>/resolver/', views.resolver_disputa, name='resolver_disputa'),
    
    # Mensajería
    path('mensajes/', views.lista_mensajes, name='lista_mensajes'),
    path('mensajes/<int:id_usuario>/', views.conversacion, name='conversacion'),
    path('mensajes/enviar/', views.enviar_mensaje, name='enviar_mensaje'),
    
    # Fundaciones
    path('fundaciones/', views.lista_fundaciones, name='lista_fundaciones'),
    path('fundacion/<int:id_fundacion>/', views.detalle_fundacion, name='detalle_fundacion'),
    
    # Impacto ambiental
    path('impacto/', views.panel_impacto, name='panel_impacto'),
    path('mi-impacto/', views.mi_impacto, name='mi_impacto'),

    # Gestión de donaciones
    path('panel-fundacion/', views.panel_fundacion, name='panel_fundacion'),
    path('gestionar-donaciones/', views.gestionar_donaciones, name='gestionar_donaciones'),
    path('estadisticas-donaciones', views.estadisticas_donaciones, name='estadisticas_donaciones'),
    
    # Campañas
    path('crear-campana/', views.crear_campana, name='crear_campana'),
    path('mis-campanas/', views.mis_campanas, name='mis_campanas'),
    path('campana/<int:id_campana>/actualizar-imagen/', views.actualizar_imagen_campana, name='actualizar_imagen_campana'),
    path('campanas-solidarias', views.campanas_solidarias, name='campanas_solidarias'),
    path('detalle-campana/', views.detalle_campana, name='detalle_campana'),
    path('donar-a-campana/', views.donar_a_campana, name='donar_a_campana'),

    # Logo de fundación
    path('fundacion/<int:id_fundacion>/actualizar-logo/', views.actualizar_logo_fundacion, name='actualizar_logo_fundacion'),

    # Logros
    path('mis-logros/', views.mis_logros, name='mis_logros'),
    path('recomendaciones/', views.recomendaciones, name='recomendaciones'),

    # Búsqueda y filtros
    path('buscar/', views.buscar_prendas, name='buscar_prendas'),

    # Gestión de sesiones
    path('session-info/', views.session_info, name='session_info'),
    path('session-status/', views.session_status, name='session_status'),
    path('renovar-sesion/', views.renovar_sesion, name='renovar_sesion'),

    # Mapa interactivo
    path('mapa/', views.mapa_fundaciones, name='mapa_fundaciones'),
    path('perfil/actualizar-ubicacion/', views.actualizar_ubicacion_usuario, name='actualizar_ubicacion_usuario'),
    path('fundacion/<int:id_fundacion>/actualizar-ubicacion/', views.actualizar_ubicacion_fundacion, name='actualizar_ubicacion_fundacion'),
]