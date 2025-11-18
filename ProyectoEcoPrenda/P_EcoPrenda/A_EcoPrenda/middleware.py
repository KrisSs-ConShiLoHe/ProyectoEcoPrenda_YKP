from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from .models import Usuario
import logging

logger = logging.getLogger(__name__)


class SessionManagementMiddleware:
    """
    Middleware para gestionar sesiones de usuario de forma centralizada
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Código que se ejecuta antes de la vista
        
        # Actualizar última actividad del usuario
        if request.session.get('usuario_id'):
            request.session['ultima_actividad'] = timezone.now().isoformat()
            request.session.modified = True
        
        # Obtener usuario de la sesión y agregarlo al request
        request.usuario_actual = None
        usuario_id = request.session.get('usuario_id')
        
        if usuario_id:
            try:
                request.usuario_actual = Usuario.objects.get(id_usuario=usuario_id)
            except Usuario.DoesNotExist:
                # Si el usuario no existe, limpiar sesión
                request.session.flush()
                logger.warning(f"Usuario {usuario_id} no encontrado, sesión eliminada")
        
        # Procesar la petición
        response = self.get_response(request)
        
        # Código que se ejecuta después de la vista
        
        return response


class InactivityLogoutMiddleware:
    """
    Middleware para cerrar sesión después de un período de inactividad
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Tiempo de inactividad en segundos (30 minutos)
        self.INACTIVITY_TIMEOUT = 1800  # 30 minutos
    
    def __call__(self, request):
        # Solo verificar si el usuario está autenticado
        if request.session.get('usuario_id'):
            ultima_actividad = request.session.get('ultima_actividad')
            
            if ultima_actividad:
                from datetime import datetime, timedelta
                ultima = datetime.fromisoformat(ultima_actividad)
                ahora = timezone.now()
                
                # Si la diferencia es mayor al timeout, cerrar sesión
                diferencia = (ahora - ultima).total_seconds()
                
                if diferencia > self.INACTIVITY_TIMEOUT:
                    request.session.flush()
                    logger.info(f"Sesión cerrada por inactividad ({diferencia} segundos)")
                    
                    # Si es una petición AJAX, retornar JSON
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        from django.http import JsonResponse
                        return JsonResponse({
                            'error': 'Sesión expirada por inactividad',
                            'redirect': reverse('login')
                        }, status=401)
                    
                    # Si es una petición normal, redirigir al login
                    return redirect('login')
        
        response = self.get_response(request)
        return response


class SessionSecurityMiddleware:
    """
    Middleware para agregar seguridad adicional a las sesiones
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Verificar si es la primera vez que se crea la sesión
        if not request.session.session_key:
            request.session.create()
        
        # Rotar la clave de sesión periódicamente (cada 100 requests)
        contador = request.session.get('request_counter', 0)
        contador += 1
        request.session['request_counter'] = contador
        
        if contador >= 100:
            request.session.cycle_key()
            request.session['request_counter'] = 0
            logger.info("Clave de sesión rotada por seguridad")
        
        # Guardar información del navegador para detección de cambios
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        sesion_user_agent = request.session.get('user_agent')
        
        if sesion_user_agent and sesion_user_agent != user_agent:
            # Posible robo de sesión, cerrar sesión
            request.session.flush()
            logger.warning("Sesión cerrada: cambio de user agent detectado")
            return redirect('login')
        
        request.session['user_agent'] = user_agent
        
        response = self.get_response(request)
        return response