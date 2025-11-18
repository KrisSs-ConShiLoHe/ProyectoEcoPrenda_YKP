from django.shortcuts import render
from django.http import JsonResponse
import json

class CookieConsentMiddleware:
    """
    Middleware para gestionar el consentimiento de cookies
    Cumple con GDPR y otras regulaciones de privacidad
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs que NO requieren consentimiento de cookies
        self.EXEMPT_URLS = [
            '/static/',
            '/media/',
            '/admin/',
            '/api/',
            '/configurar-cookies/',
            '/aceptar-cookies/',
            '/rechazar-cookies/',
        ]
    
    def __call__(self, request):
        # Verificar si la URL está exenta
        if any(request.path.startswith(url) for url in self.EXEMPT_URLS):
            return self.get_response(request)
        
        # Verificar si el usuario ha configurado las cookies
        cookie_consent = request.COOKIES.get('cookie_consent')
        
        if not cookie_consent:
            # Si no ha aceptado cookies y está intentando hacer login o acciones importantes
            if request.path in ['/login/', '/registro/', '/crear-prenda/', '/comprar/', '/donar/']:
                if request.method == 'POST':
                    # Bloquear acciones POST sin consentimiento
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'error': 'Debes aceptar las cookies para continuar',
                            'redirect': '/'
                        }, status=403)
                    
                    # Renderizar página de consentimiento
                    return render(request, 'cookie_consent_required.html', {
                        'action_attempted': request.path,
                        'message': 'Debes configurar las preferencias de cookies antes de realizar esta acción.'
                    })
        
        # Si hay consentimiento, verificar qué cookies están permitidas
        if cookie_consent:
            try:
                consent_data = json.loads(cookie_consent)
                request.cookies_accepted = consent_data
                
                # Si no aceptó cookies esenciales, bloquear login
                if not consent_data.get('esenciales', False):
                    if request.path in ['/login/', '/registro/'] and request.method == 'POST':
                        return render(request, 'cookie_consent_required.html', {
                            'message': 'Las cookies esenciales son necesarias para iniciar sesión.'
                        })
            except json.JSONDecodeError:
                request.cookies_accepted = {}
        else:
            request.cookies_accepted = {}
        
        response = self.get_response(request)
        return response


class CookiePreferencesMiddleware:
    """
    Middleware para aplicar las preferencias de cookies del usuario
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Obtener preferencias de cookies
        cookie_consent = request.COOKIES.get('cookie_consent')
        
        if cookie_consent:
            try:
                consent_data = json.loads(cookie_consent)
                
                # Si no aceptó cookies de funcionalidad, limpiar sesiones no esenciales
                if not consent_data.get('funcionalidad', False):
                    # Limpiar datos no esenciales de la sesión
                    non_essential_keys = ['user_preferences', 'theme', 'language']
                    for key in non_essential_keys:
                        if key in request.session:
                            del request.session[key]
                
                # Si no aceptó cookies analíticas, desactivar tracking
                if not consent_data.get('analiticas', False):
                    request.disable_analytics = True
                else:
                    request.disable_analytics = False
                
                # Si no aceptó cookies de marketing, desactivar
                if not consent_data.get('marketing', False):
                    request.disable_marketing = True
                else:
                    request.disable_marketing = False
                    
            except json.JSONDecodeError:
                pass
        
        response = self.get_response(request)
        return response