from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from .models import Usuario

# 1. LOGIN REQUERIDO
def login_required_custom(function):
    """Decorador personalizado para requerir login"""
    @wraps(function)
    def wrap(request, *args, **kwargs):
        usuario_id = request.session.get('usuario_id')
        if not usuario_id:
            messages.warning(request, 'Debes iniciar sesión para acceder a esta página.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'No autenticado', 'redirect': '/login/'}, status=401)
            return redirect('login')
        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)
            request.usuario_actual = usuario
        except Usuario.DoesNotExist:
            request.session.flush()
            messages.error(request, 'Tu sesión ha expirado.')
            return redirect('login')
        return function(request, *args, **kwargs)
    return wrap

# 2. SOLO REPRESENTANTES DE FUNDACION (DESDE ADMIN)
def representante_fundacion_required(function):
    """Decorador para representantes de fundación"""
    @wraps(function)
    def wrap(request, *args, **kwargs):
        usuario_id = request.session.get('usuario_id')
        if not usuario_id:
            messages.warning(request, 'Debes iniciar sesión.')
            return redirect('login')
        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)
            request.usuario_actual = usuario
            if not usuario.es_representante_fundacion():
                messages.error(request, 'Debes ser representante de una fundación para acceder.')
                return redirect('home')
            if not usuario.fundacion_asignada:
                messages.error(request, 'No tienes una fundación asignada. Contacta al administrador.')
                return redirect('home')
        except Usuario.DoesNotExist:
            request.session.flush()
            messages.error(request, 'Tu sesión ha expirado.')
            return redirect('login')
        return function(request, *args, **kwargs)
    return wrap

# 3. SOLO MODERADOR (DESDE ADMIN)
def moderador_required(function):
    """Decorador para moderadores (solo acceso desde admin)"""
    @wraps(function)
    def wrap(request, *args, **kwargs):
        usuario_id = request.session.get('usuario_id')
        if not usuario_id:
            messages.warning(request, 'Debes iniciar sesión.')
            return redirect('login')
        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)
            request.usuario_actual = usuario
            if not usuario.es_moderador():
                messages.error(request, 'No tienes permisos de moderador.')
                return redirect('home')
            if not usuario.es_staff:
                messages.error(request, 'Debes acceder desde el panel de administración.')
                return redirect('/admin/')
        except Usuario.DoesNotExist:
            request.session.flush()
            messages.error(request, 'Tu sesión ha expirado.')
            return redirect('login')
        return function(request, *args, **kwargs)
    return wrap

# 4. SOLO ADMINISTRADOR (DESDE ADMIN)
def admin_required(function):
    """Decorador para administradores (solo acceso desde admin)"""
    @wraps(function)
    def wrap(request, *args, **kwargs):
        usuario_id = request.session.get('usuario_id')
        if not usuario_id:
            messages.warning(request, 'Debes iniciar sesión.')
            return redirect('login')
        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)
            request.usuario_actual = usuario
            if not usuario.es_administrador():
                messages.error(request, 'No tienes permisos de administrador.')
                return redirect('home')
            if not usuario.es_staff:
                messages.error(request, 'Debes acceder desde el panel de administración.')
                return redirect('/admin/')
        except Usuario.DoesNotExist:
            request.session.flush()
            messages.error(request, 'Tu sesión ha expirado.')
            return redirect('login')
        return function(request, *args, **kwargs)
    return wrap

# 5. SOLO CLIENTE
def cliente_only(function):
    """Decorador para funciones exclusivas de clientes"""
    @wraps(function)
    def wrap(request, *args, **kwargs):
        usuario_id = request.session.get('usuario_id')
        if not usuario_id:
            messages.warning(request, 'Debes iniciar sesión.')
            return redirect('login')
        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)
            request.usuario_actual = usuario
            if not usuario.es_cliente():
                messages.error(request, 'Esta función es solo para clientes.')
                return redirect('home')
        except Usuario.DoesNotExist:
            request.session.flush()
            messages.error(request, 'Tu sesión ha expirado.')
            return redirect('login')
        return function(request, *args, **kwargs)
    return wrap

# 6. SESSION VÁLIDA
def session_valid(function):
    """Verifica si existe sesión activa, si no la crea."""
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if not request.session.session_key:
            request.session.create()
        return function(request, *args, **kwargs)
    return wrap

# 7. SOLO USUARIOS NO AUTENTICADOS
def anonymous_required(function):
    """Solo para usuarios NO logueados"""
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if request.session.get('usuario_id'):
            messages.info(request, 'Ya has iniciado sesión.')
            return redirect('home')
        return function(request, *args, **kwargs)
    return wrap

# 8. AJAX LOGIN REQUERIDO
def ajax_login_required(function):
    """Para endpoints AJAX que requieren autenticación"""
    @wraps(function)
    def wrap(request, *args, **kwargs):
        usuario_id = request.session.get('usuario_id')
        if not usuario_id:
            return JsonResponse({'error': 'No autenticado', 'message': 'Debes iniciar sesión'}, status=401)
        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)
            request.usuario_actual = usuario
        except Usuario.DoesNotExist:
            request.session.flush()
            return JsonResponse({'error': 'Sesión inválida', 'message': 'Tu sesión ha expirado'}, status=401)
        return function(request, *args, **kwargs)
    return wrap

# 9. REQUIERE ROL (uno o varios)
def role_required(*roles):
    """Decorador flexible para requerir uno o más roles específicos"""
    def decorator(function):
        @wraps(function)
        def wrap(request, *args, **kwargs):
            usuario_id = request.session.get('usuario_id')
            if not usuario_id:
                messages.warning(request, 'Debes iniciar sesión.')
                return redirect('login')
            try:
                usuario = Usuario.objects.get(id_usuario=usuario_id)
                request.usuario_actual = usuario
                if usuario.rol not in roles:
                    messages.error(request, 'No tienes permisos suficientes.')
                    return redirect('home')
            except Usuario.DoesNotExist:
                request.session.flush()
                messages.error(request, 'Tu sesión ha expirado.')
                return redirect('login')
            return function(request, *args, **kwargs)
        return wrap
    return decorator