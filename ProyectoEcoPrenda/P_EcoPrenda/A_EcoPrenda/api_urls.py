from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

# Router para ViewSets
router = DefaultRouter()
router.register(r'prendas', api_views.PrendaViewSet, basename='api-prenda')
router.register(r'usuarios', api_views.UsuarioViewSet, basename='api-usuario')
router.register(r'fundaciones', api_views.FundacionViewSet, basename='api-fundacion')
router.register(r'transacciones', api_views.TransaccionViewSet, basename='api-transaccion')
router.register(r'tipos-transaccion', api_views.TipoTransaccionViewSet, basename='api-tipo-transaccion')
router.register(r'mensajes', api_views.MensajeViewSet, basename='api-mensaje')
router.register(r'impacto-ambiental', api_views.ImpactoAmbientalViewSet, basename='api-impacto-ambiental')
router.register(r'logros', api_views.LogroViewSet, basename='api-logro')
router.register(r'usuario-logros', api_views.UsuarioLogroViewSet, basename='api-usuario-logro')
router.register(r'campanas-fundacion', api_views.CampanaFundacionViewSet, basename='api-campana-fundacion')

# URLs de la API
urlpatterns = [
    # ViewSets (CRUD completo automático)
    path('', include(router.urls)),
    
    # Function-based views
    path('prendas-list/', api_views.prenda_list, name='api-prenda-list'),
    path('prendas-detail/<int:pk>/', api_views.prenda_detail, name='api-prenda-detail'),
    
    # Class-based views (APIView)
    path('usuarios-list/', api_views.UsuarioListAPIView.as_view(), name='api-usuario-list'),
    path('usuarios-detail/<int:pk>/', api_views.UsuarioDetailAPIView.as_view(), name='api-usuario-detail'),
    
    # Generics
    path('transacciones/', api_views.TransaccionListCreateAPIView.as_view(), name='api-transaccion-list'),
    path('transacciones/<int:pk>/', api_views.TransaccionDetailAPIView.as_view(), name='api-transaccion-detail'),
    
    path('fundaciones-list/', api_views.FundacionListCreateAPIView.as_view(), name='api-fundacion-list'),
    path('fundaciones-detail/<int:pk>/', api_views.FundacionDetailAPIView.as_view(), name='api-fundacion-detail'),
    
    # Endpoints personalizados
    path('estadisticas/', api_views.EstadisticasAPIView.as_view(), name='api-estadisticas'),
    path('impacto-total/', api_views.ImpactoTotalAPIView.as_view(), name='api-impacto-total'),

    path('prendas-simple-list/', api_views.PrendaSimpleListAPIView.as_view(), name='api-prenda-simple-list'),
]