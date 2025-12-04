from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import JsonResponse
from django import forms  # Agregado para forms
import hashlib
import json
import logging  # Agregado para logging

from .models import (
    Usuario, Prenda, Transaccion, TipoTransaccion, 
    Fundacion, Mensaje, ImpactoAmbiental, 
    Logro, UsuarioLogro, CampanaFundacion
)
from .decorators import (
    login_required_custom, 
    anonymous_required,
    ajax_login_required, 
    session_valid,
    admin_required,
    representante_fundacion_required,
    moderador_required,
    cliente_only,
    role_required,
)

from django.conf import settings

from .cloudinary_utils import (
    subir_imagen_prenda,
    subir_imagen_usuario,
    subir_logo_fundacion,
    subir_imagen_campana,
    validar_imagen,
    eliminar_imagen_cloudinary,
    extraer_public_id_de_url
)

from .carbon_utils import (
    calcular_impacto_prenda,
    calcular_impacto_transaccion,
    obtener_impacto_total_usuario,
    obtener_impacto_total_plataforma,
    generar_informe_impacto,
    formatear_equivalencia
)

from .forms import RegistroForm, PerfilForm, PrendaForm

# Configuración de logging
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------------------------------------------
# Utilidades de usuario y autenticación

def hash_password(password):
    """Envuelve `make_password` de Django para generar un hash seguro."""
    from django.contrib.auth.hashers import make_password
    return make_password(password)


def verificar_password(password, password_hash, usuario=None):
    """Verifica la contraseña contra el hash almacenado.
    Soporta hashes en formato Django (contiene '$') y el hash legacy SHA256.
    Si se detecta una coincidencia legacy y se entrega `usuario`, rehashea
    la contraseña usando el esquema de Django y guarda el usuario.
    """
    import hashlib
    from django.contrib.auth.hashers import check_password as django_check, make_password
    
    if not password or not password_hash:
        return False
    # Si el hash está en formato Django (contiene '$'), usar la verificación estándar
    if '$' in password_hash:
        return django_check(password, password_hash)
    # Fallback: legacy SHA256 hex
    if hashlib.sha256(password.encode()).hexdigest() == password_hash:
        if usuario is not None:
            try:
                usuario.contrasena = make_password(password)
                usuario.save()
            except Exception as e:
                logger.error(f"Error rehasheando contraseña para usuario {usuario.id_usuario}: {e}")
        return True
    return False

def get_usuario_actual(request):
    """Obtiene el usuario actual de la sesión"""
    id_usuario = request.session.get('id_usuario')
    if id_usuario:
        try:
            return Usuario.objects.get(id=id_usuario)  # Cambiado: usa 'id' en lugar de 'id_usuario'
        except Usuario.DoesNotExist:
            return None
    return None


def puede_actualizar_transaccion(usuario, transaccion, permiso_requerido):
    """Helper para validar si usuario tiene permiso de actualizar transacción.
    
    permiso_requerido puede ser: 'origen', 'destino', 'origen_o_destino', 'representante'
    Retorna tupla: (True/False, mensaje_error o None)
    """
    if permiso_requerido == 'origen':
        if transaccion.user_origen.id != usuario.id_usuario:  # Cambiado: 'user_origen' en lugar de 'id_usuario_origen'
            return False, 'Solo el propietario/vendedor puede realizar esta acción.'
    elif permiso_requerido == 'destino':
        if not transaccion.user_destino or transaccion.user_destino.id != usuario.id_usuario:  # Cambiado: 'user_destino'
            return False, 'Solo el receptor/comprador puede realizar esta acción.'
    elif permiso_requerido == 'origen_o_destino':
        es_origen = transaccion.user_origen.id == usuario.id_usuario
        es_destino = transaccion.user_destino and transaccion.user_destino.id == usuario.id_usuario
        if not (es_origen or es_destino):
            return False, 'No tienes permiso para actualizar esta transacción.'
    elif permiso_requerido == 'representante':
        if not (usuario.es_representante_fundacion() and usuario.fundacion_asignada == transaccion.fundacion):  # Cambiado: 'fundacion'
            return False, 'Solo el representante de la fundación puede realizar esta acción.'
    return True, None

# ------------------------------------------------------------------------------------------------------------------
# Vistas Principales

def home(request):
    usuario = get_usuario_actual(request)
    total_prendas = Prenda.objects.count()
    total_usuarios = Usuario.objects.count()
    impacto_total = ImpactoAmbiental.objects.aggregate(
        total_carbono=Sum('carbono_evitar_kg'),
        total_energia=Sum('energia_ahorrada_kwh')
    )
    prendas_recientes = Prenda.objects.select_related('user').order_by('-fecha_publicacion')[:6]  # Cambiado: 'user' en lugar de 'id_usuario'
    context = {
        'usuario': usuario,
        'total_prendas': total_prendas,
        'total_usuarios': total_usuarios,
        'impacto_total': impacto_total,
        'prendas_recientes': prendas_recientes,
    }
    return render(request, 'home.html', context)

@anonymous_required
def registro_usuario(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.fecha_registro = timezone.now()
            usuario.set_password(form.cleaned_data['contrasena'])
            try:
                usuario.save()
                messages.success(request, f'¡Registro exitoso como {usuario.get_rol_display()}! Ya puedes iniciar sesión.')
                return redirect('login')
            except Exception as e:
                logger.error(f"Error guardando usuario en registro: {e}")
                messages.error(request, 'Error interno. Intenta nuevamente.')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = RegistroForm()
    return render(request, 'registro.html', {'form': form})

@anonymous_required
def login_usuario(request):
    if request.method == 'POST':
        correo = request.POST.get('correo')
        contrasena = request.POST.get('contrasena')
        if not correo or not contrasena:
            messages.error(request, 'Correo y contraseña son obligatorios.')
            return render(request, 'login.html')
        try:
            usuario = Usuario.objects.get(correo=correo)
            if verificar_password(contrasena, usuario.contrasena, usuario):
                request.session['id_usuario'] = usuario.id_usuario  # Cambiado: 'id' en lugar de 'id_usuario'
                messages.success(request, f'¡Bienvenido, {usuario.nombre}!')
                return redirect('home')
            else:
                logger.warning(f"Intento de login fallido para correo: {correo}")
                messages.error(request, 'Usuario o contraseña incorrectos.')
        except Usuario.DoesNotExist:
            logger.warning(f"Intento de login con correo inexistente: {correo}")
            messages.error(request, 'Usuario o contraseña incorrectos.')
    return render(request, 'login.html')

@login_required_custom
def logout_usuario(request):
    request.session.flush()
    messages.success(request, 'Sesión cerrada correctamente.')
    return redirect('home')

@login_required_custom
def perfil_usuario(request):
    usuario = get_usuario_actual(request)
    if not usuario:
        return redirect('login')
    if request.method == 'POST':
        form = PerfilForm(request.POST, request.FILES, instance=usuario)
        if form.is_valid():
            if 'imagen_usuario' in request.FILES:
                # Validar imagen antes de guardar
                imagen = request.FILES['imagen_usuario']
                if not validar_imagen(imagen):
                    messages.error(request, 'Imagen inválida. Solo JPG/PNG, máximo 5MB.')
                    return render(request, 'perfil.html', {'usuario': usuario, 'form': form})
            try:
                form.save()
                messages.success(request, 'Perfil actualizado correctamente.')
                return redirect('perfil')
            except Exception as e:
                logger.error(f"Error actualizando perfil para usuario {usuario.id_usuario}: {e}")
                messages.error(request, 'Error interno. Intenta nuevamente.')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = PerfilForm(instance=usuario)
    
    total_prendas = Prenda.objects.filter(user=usuario).count()  # Cambiado: 'user' en lugar de 'id_usuario'
    transacciones_realizadas = Transaccion.objects.filter(
        Q(user_origen=usuario) | Q(user_destino=usuario)  # Cambiado: 'user_origen' y 'user_destino'
    ).count()
    impactos = ImpactoAmbiental.objects.select_related('prenda').filter(prenda__user=usuario)  # Cambiado: 'prenda__user'
    impacto_personal = impactos.aggregate(
        total_carbono=Sum('carbono_evitar_kg'),
        total_energia=Sum('energia_ahorrada_kwh')
    )
    context = {
        'usuario': usuario,
        'total_prendas': total_prendas,
        'transacciones_realizadas': transacciones_realizadas,
        'impacto_personal': impacto_personal,
        'form': form,
    }
    return render(request, 'perfil.html', context)


# ------------------------------------------------------------------------------------------------------------------
# Gestión de Prendas 

@cliente_only
def lista_prendas(request):
    """Lista todas las prendas disponibles con opción de filtrado."""
    usuario = get_usuario_actual(request)
    prendas = Prenda.objects.filter(disponibilidad='DISPONIBLE').order_by('-fecha_publicacion')

    categoria = request.GET.get('categoria')
    talla = request.GET.get('talla')
    estado = request.GET.get('estado')

    if categoria:
        prendas = prendas.filter(categoria=categoria)
    if talla:
        prendas = prendas.filter(talla=talla)
    if estado:
        prendas = prendas.filter(estado=estado)

    context = {
        'usuario': usuario,
        'prendas': prendas,
        'categorias': ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios'],
        'tallas': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
        'estados': ['Nuevo', 'Excelente', 'Bueno', 'Usado'],
    }
    return render(request, 'lista_prendas.html', context)

@cliente_only
def detalle_prenda(request, id_prenda):
    """Detalle de una prenda específica y su impacto ambiental."""
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda, id_prenda=id_prenda)
    impacto = ImpactoAmbiental.objects.filter(id_prenda=prenda).first()
    # Buscar transacción actual relacionada a la prenda (si la hay)
    transaccion_actual = Transaccion.objects.filter(
        id_prenda=prenda,
        estado__in=['PENDIENTE', 'RESERVADA', 'EN_PROCESO']
    ).order_by('-fecha_transaccion').first()

    context = {
        'usuario': usuario,
        'prenda': prenda,
        'impacto': impacto,
        'transaccion_actual': transaccion_actual,
    }
    return render(request, 'detalle_prenda.html', context)

@cliente_only
def crear_prenda(request):
    """Permite al cliente crear una nueva prenda."""
    usuario = get_usuario_actual(request)
    if request.method == 'POST':
        imagen = request.FILES.get('imagen_prenda')
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        categoria = request.POST.get('categoria')
        talla = request.POST.get('talla')
        condicion = request.POST.get('estado')  # Renombrado a 'condicion' para claridad

        if not all([nombre, descripcion, categoria, talla, condicion]):
            messages.error(request, 'Todos los campos son obligatorios.')
            return render(request, 'crear_prenda.html', {
                'usuario': usuario,
                'categorias': ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios'],
                'tallas': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
                'estados': ['Nuevo', 'Excelente', 'Bueno', 'Usado'],
            })
        prenda = Prenda.objects.create(
            id_usuario=usuario,
            nombre=nombre,
            descripcion=descripcion,
            categoria=categoria,
            talla=talla,
            estado='DISPONIBLE',  # ✅ Ahora siempre se crea con estado DISPONIBLE
            imagen_prenda=imagen,
            fecha_publicacion=timezone.now()
        )
        # Impacto ambiental simulado
        carbono_evitado = 5.5
        energia_ahorrada = 2.7
        ImpactoAmbiental.objects.create(
            id_prenda=prenda,
            carbono_evitar_kg=carbono_evitado,
            energia_ahorrada_kwh=energia_ahorrada,
            fecha_calculo=timezone.now()
        )
        messages.success(request, '¡Prenda publicada exitosamente!')
        return redirect('detalle_prenda', id_prenda=prenda.id_prenda)

    context = {
        'usuario': usuario,
        'categorias': ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios'],
        'tallas': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
        'estados': ['Nuevo', 'Excelente', 'Bueno', 'Usado'],
    }
    return render(request, 'crear_prenda.html', context)

@cliente_only
def editar_prenda(request, id_prenda):
    """Permite al cliente editar una de sus prendas."""
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda, id_prenda=id_prenda)
    if prenda.id_usuario.id_usuario != usuario.id_usuario:
        messages.error(request, 'No tienes permiso para editar esta prenda.')
        return redirect('detalle_prenda', id_prenda=prenda.id_prenda)

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        categoria = request.POST.get('categoria')
        talla = request.POST.get('talla')
        condicion = request.POST.get('estado')  # Renombrado a 'condicion' (es el estado de conservación, no de transacción)
        imagen = request.FILES.get('imagen_prenda')

        if not all([nombre, descripcion, categoria, talla, condicion]):
            messages.error(request, 'Todos los campos son obligatorios.')
            # Mantener campos en el formulario
        else:
            prenda.nombre = nombre
            prenda.descripcion = descripcion
            prenda.categoria = categoria
            prenda.talla = talla
            # NO modificar prenda.estado (se controla por transacciones, no por edición)
            if imagen:
                prenda.imagen_prenda = imagen
            prenda.save()
            messages.success(request, 'Prenda actualizada correctamente.')
            return redirect('detalle_prenda', id_prenda=prenda.id_prenda)

    context = {
        'usuario': usuario,
        'prenda': prenda,
        'categorias': ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios'],
        'tallas': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
        'estados': ['Nuevo', 'Excelente', 'Bueno', 'Usado'],
    }
    return render(request, 'editar_prenda.html', context)

@cliente_only
def eliminar_prenda(request, id_prenda):
    """Permite eliminar una prenda propia del usuario cliente."""
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda, id_prenda=id_prenda)
    if prenda.id_usuario.id_usuario != usuario.id_usuario:
        messages.error(request, 'No tienes permiso para eliminar esta prenda.')
        return redirect('detalle_prenda', id_prenda=prenda.id_prenda)
    if request.method == 'POST':
        # Elimina impacto y transacciones asociadas a la prenda
        prenda.impactoambiental_set.all().delete()
        prenda.transaccion_set.all().delete()
        prenda.delete()
        messages.success(request, 'Prenda eliminada correctamente.')
        return redirect('mis_prendas')
    context = {
        'usuario': usuario,
        'prenda': prenda,
    }
    return render(request, 'eliminar_prenda.html', context)

@cliente_only
def mis_prendas(request):
    """Lista todas las prendas del usuario cliente."""
    usuario = get_usuario_actual(request)
    prendas = Prenda.objects.filter(id_usuario=usuario).order_by('-fecha_publicacion')
    context = {
        'usuario': usuario,
        'prendas': prendas,
    }
    return render(request, 'mis_prendas.html', context)

@cliente_only
def buscar_prendas(request):
    """Búsqueda avanzada de prendas para usuarios clientes."""
    usuario = get_usuario_actual(request)
    query = request.GET.get('q', '')
    categoria = request.GET.get('categoria')
    talla = request.GET.get('talla')
    estado = request.GET.get('estado')

    prendas = Prenda.objects.filter(disponibilidad='DISPONIBLE')
    if query:
        prendas = prendas.filter(
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query)
        )
    if categoria:
        prendas = prendas.filter(categoria=categoria)
    if talla:
        prendas = prendas.filter(talla=talla)
    if estado:
        prendas = prendas.filter(estado=estado)

    context = {
        'usuario': usuario,
        'prendas': prendas.order_by('-fecha_publicacion'),
        'query': query,
        'categorias': ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios'],
        'tallas': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
        'estados': ['Nuevo', 'Excelente', 'Bueno', 'Usado'],
    }
    return render(request, 'buscar_prendas.html', context)

# ------------------------------------------------------------------------------------------------------------------
# Transacciones

@login_required_custom
def proponer_intercambio(request, id_prenda):
    """Permite a un usuario proponer un intercambio por otra prenda."""
    usuario = get_usuario_actual(request)
    prenda_destino = get_object_or_404(Prenda.objects.select_related('user'), pk=id_prenda)  # Cambiado: 'pk=id_prenda', agregado select_related

    if prenda_destino.user.id == usuario.id_usuario:  # Cambiado: 'prenda_destino.user.id == usuario.id'
        messages.error(request, 'No puedes intercambiar con tu propia prenda.')
        return redirect('detalle_prenda', id_prenda=id_prenda)
    if prenda_destino.estado != 'DISPONIBLE':  # Cambiado: check directo en 'estado'
        messages.error(request, f'Esta prenda ya no está disponible para intercambio ({prenda_destino.get_estado_display()}).')
        return redirect('detalle_prenda', id_prenda=id_prenda)

    if request.method == 'POST':
        prenda_origen_id = request.POST.get('prenda_origen')
        prenda_origen = get_object_or_404(Prenda, pk=prenda_origen_id, user=usuario)  # Cambiado: 'pk=prenda_origen_id', 'user=usuario'
        if prenda_origen.estado != 'DISPONIBLE':  # Cambiado: check directo
            messages.error(request, 'La prenda ofrecida ya no está disponible.')
            return redirect('detalle_prenda', id_prenda=id_prenda)
        tipo_intercambio, _ = TipoTransaccion.objects.get_or_create(nombre_tipo='Intercambio', defaults={
            'descripcion': 'Intercambio de prendas entre usuarios'
        })
        try:
            transaccion = Transaccion.objects.create(
                prenda=prenda_destino,  # Cambiado: 'prenda=prenda_destino'
                tipo=tipo_intercambio,  # Cambiado: 'tipo=tipo_intercambio'
                user_origen=usuario,  # Cambiado: 'user_origen=usuario'
                user_destino=prenda_destino.user,  # Cambiado: 'user_destino=prenda_destino.user'
                fecha_transaccion=timezone.now(),
                estado='PENDIENTE'
            )
            messages.success(request, f'¡Intercambio propuesto! Código de seguimiento: {transaccion.id}. Ahora puedes negociar con el otro usuario.')  # Cambiado: 'transaccion.id'
            return redirect('conversacion', id_usuario=prenda_destino.user.id)  # Cambiado: 'prenda_destino.user.id'
        except Exception as e:
            logger.error(f"Error creando intercambio para usuario {usuario.id_usuario}: {e}")
            messages.error(request, 'Error interno. Intenta nuevamente.')

    mis_prendas_usuario = Prenda.objects.filter(user=usuario, estado='DISPONIBLE')  # Cambiado: 'user=usuario', 'estado'
    context = {
        'usuario': usuario,
        'prenda_destino': prenda_destino,
        'mis_prendas': mis_prendas_usuario,
    }
    return render(request, 'proponer_intercambio.html', context)

@login_required_custom
def marcar_intercambio_entregado(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda', 'user_origen'), pk=id_transaccion)  # Cambiado: agregado select_related
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado != 'RESERVADA':
        return JsonResponse({'error': 'La transacción no está en estado reservado.'}, status=400)
    
    try:
        transaccion.marcar_en_proceso()
        messages.success(request, 'Has marcado la prenda como entregada.')
        return redirect('mis_transacciones')
    except Exception as e:
        logger.error(f"Error marcando intercambio entregado {transaccion.id}: {e}")
        return JsonResponse({'error': 'Error interno'}, status=500)

@login_required_custom
def confirmar_recepcion_intercambio(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda', 'user_destino'), pk=id_transaccion)  # Cambiado: agregado select_related
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'destino')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado != 'EN_PROCESO':
        return JsonResponse({'error': 'Debes esperar a que el propietario marque como entregada.'}, status=400)
    
    try:
        transaccion.marcar_como_completada()
        messages.success(request, '¡Intercambio completado con éxito!')
        return redirect('mis_transacciones')
    except Exception as e:
        logger.error(f"Error confirmando recepción intercambio {transaccion.id}: {e}")
        return JsonResponse({'error': 'Error interno'}, status=500)

@login_required_custom
def cancelar_intercambio(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda'), pk=id_transaccion)  # Cambiado: agregado select_related
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado not in ['PENDIENTE', 'RESERVADA', 'EN_PROCESO']:
        return JsonResponse({'error': 'No puedes cancelar una transacción finalizada.'}, status=400)
    
    try:
        transaccion.cancelar()
        messages.success(request, 'Intercambio cancelado y prenda devuelta a disponible.')
        return redirect('mis_transacciones')
    except Exception as e:
        logger.error(f"Error cancelando intercambio {transaccion.id}: {e}")
        return JsonResponse({'error': 'Error interno'}, status=500)

@login_required_custom
def comprar_prenda(request, id_prenda):
    """Proponer compra de una prenda."""
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda.objects.select_related('user'), pk=id_prenda)  # Cambiado: agregado select_related
    
    if prenda.user.id == usuario.id_usuario:  # Cambiado: 'prenda.user.id == usuario.id'
        messages.error(request, "No puedes comprar tu propia prenda.")
        return redirect('detalle_prenda', id_prenda=id_prenda)
    if prenda.estado != 'DISPONIBLE':  # Cambiado: check directo
        messages.error(request, "Esta prenda ya no está disponible.")
        return redirect('detalle_prenda', id_prenda=id_prenda)

    if request.method == 'POST':
        tipo_venta, _ = TipoTransaccion.objects.get_or_create(
            nombre_tipo='Venta', defaults={'descripcion': 'Venta de prenda entre usuarios'}
        )
        try:
            transaccion = Transaccion.objects.create(
                prenda=prenda,  # Cambiado: 'prenda=prenda'
                tipo=tipo_venta,  # Cambiado: 'tipo=tipo_venta'
                user_origen=prenda.user,  # Cambiado: 'user_origen=prenda.user'
                user_destino=usuario,  # Cambiado: 'user_destino=usuario'
                fecha_transaccion=timezone.now(),
                estado='PENDIENTE'
            )
            messages.success(request, f'Solicitud de compra enviada. Código: {transaccion.id}. Ahora puedes negociar con el vendedor.')  # Cambiado: 'transaccion.id'
            return redirect('conversacion', id_usuario=prenda.user.id)  # Cambiado: 'prenda.user.id'
        except Exception as e:
            logger.error(f"Error creando compra para usuario {usuario.id_usuario}: {e}")
            messages.error(request, 'Error interno. Intenta nuevamente.')
    
    context = {"usuario": usuario, "prenda": prenda}
    return render(request, 'comprar_prenda.html', context)

@login_required_custom
def marcar_compra_entregado(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda', 'user_origen'), pk=id_transaccion)  # Cambiado: agregado select_related
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado != 'RESERVADA':
        return JsonResponse({'error': 'La transacción no está en estado reservado.'}, status=400)
    
    try:
        transaccion.marcar_en_proceso()
        messages.success(request, 'Has marcado la prenda como entregada.')
        return redirect('mis_transacciones')
    except Exception as e:
        logger.error(f"Error marcando compra entregada {transaccion.id}: {e}")
        return JsonResponse({'error': 'Error interno'}, status=500)

@login_required_custom
def marcar_donacion_enviada(request, id_transaccion):
    """Permite al donante marcar su donación como enviada."""
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda', 'user_origen'), pk=id_transaccion)  # Cambiado: agregado select_related

    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if not transaccion.es_donacion():
        return JsonResponse({'error': 'Esta acción solo aplica a donaciones.'}, status=400)
    if transaccion.estado not in ['PENDIENTE', 'RESERVADA']:
        return JsonResponse({'error': 'La transacción no está en un estado válido para marcar como enviada.'}, status=400)

    try:
        transaccion.marcar_en_proceso()
        messages.success(request, 'Has marcado la donación como enviada. La fundación confirmará la recepción.')
        return redirect('mis_transacciones')
    except Exception as e:
        logger.error(f"Error marcando donación enviada {transaccion.id}: {e}")
        return JsonResponse({'error': 'Error interno'}, status=500)

@login_required_custom
def confirmar_recepcion_compra(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda', 'user_destino'), pk=id_transaccion)  # Cambiado: agregado select_related
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'destino')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado != 'EN_PROCESO':
        return JsonResponse({'error': 'Solo puedes confirmar si ya fue marcada como entregada.'}, status=400)
    
    try:
        transaccion.marcar_como_completada()
        messages.success(request, '¡Transacción completada con éxito!')
        return redirect('mis_transacciones')
    except Exception as e:
        logger.error(f"Error confirmando recepción compra {transaccion.id}: {e}")
        return JsonResponse({'error': 'Error interno'}, status=500)

@login_required_custom
def cancelar_compra(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda'), pk=id_transaccion)  # Cambiado: agregado select_related
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado not in ['PENDIENTE', 'RESERVADA', 'EN_PROCESO']:
        return JsonResponse({'error': 'No puedes cancelar una transacción finalizada.'}, status=400)
    
    try:
        transaccion.cancelar()
        messages.success(request, 'Transacción cancelada y prenda devuelta a disponible.')
        return redirect('mis_transacciones')
    except Exception as e:
        logger.error(f"Error cancelando compra {transaccion.id}: {e}")
        return JsonResponse({'error': 'Error interno'}, status=500)

@login_required_custom
def donar_prenda(request, id_prenda):
    """Permite a un usuario donar una prenda propia a una fundación activa."""
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda.objects.select_related('user'), pk=id_prenda)  # Cambiado: agregado select_related
    if prenda.user.id != usuario.id_usuario:  # Cambiado: 'prenda.user.id != usuario.id'
        messages.error(request, 'Solo puedes donar tus propias prendas.')
        return redirect('detalle_prenda', id_prenda=id_prenda)
    if prenda.estado != 'DISPONIBLE':  # Cambiado: check directo
        messages.error(request, 'Esta prenda ya no está disponible.')
        return redirect('detalle_prenda', id_prenda=id_prenda)
    if request.method == 'POST':
        fundacion_id = request.POST.get('fundacion')
        if not fundacion_id:
            messages.error(request, 'Debes seleccionar una fundación válida.')
            return redirect('donar_prenda', id_prenda=id_prenda)
        fundacion = get_object_or_404(Fundacion.objects.select_related('representante'), pk=fundacion_id, activa=True)  # Cambiado: agregado select_related
        tipo_donacion, _ = TipoTransaccion.objects.get_or_create(nombre_tipo='Donación', defaults={
            'descripcion': 'Donación de prenda a fundación'
        })
        try:
            transaccion = Transaccion.objects.create(
                prenda=prenda,  # Cambiado: 'prenda=prenda'
                tipo=tipo_donacion,  # Cambiado: 'tipo=tipo_donacion'
                user_origen=usuario,  # Cambiado: 'user_origen=usuario'
                fundacion=fundacion,  # Cambiado: 'fundacion=fundacion'
                fecha_transaccion=timezone.now(),
                estado='PENDIENTE'
            )
            prenda.marcar_como_reservada()
            # Verificar logros
            nuevos_logros = verificar_logros(usuario)  # Asumiendo que existe
            if nuevos_logros:
                for logro in nuevos_logros:
                    messages.success(request, f'🏆 ¡Nuevo logro desbloqueado: {logro.nombre}!')
            messages.success(request, f'¡Prenda donada exitosamente a {fundacion.nombre}! Código de seguimiento: {transaccion.id}')  # Cambiado: 'transaccion.id'
            return redirect('mis_transacciones')
        except Exception as e:
            logger.error(f"Error donando prenda {prenda.pk} por usuario {usuario.id_usuario}: {e}")
            messages.error(request, 'Error interno. Intenta nuevamente.')
    fundaciones = Fundacion.objects.filter(activa=True)
    context = {
        'usuario': usuario,
        'prenda': prenda,
        'fundaciones': fundaciones,
    }
    return render(request, 'donar_prenda.html', context)

@login_required_custom
def mis_transacciones(request):
    usuario = get_usuario_actual(request)
    
    transacciones_enviadas = Transaccion.objects.filter(
        user_origen=usuario  # Cambiado: 'user_origen=usuario'
    ).select_related('prenda', 'tipo', 'user_destino', 'fundacion')  # Agregado select_related
    
    transacciones_recibidas = Transaccion.objects.filter(
        user_destino=usuario  # Cambiado: 'user_destino=usuario'
    ).exclude(
        fundacion__isnull=False  # Cambiado: 'fundacion__isnull=False'
    ).select_related('prenda', 'tipo', 'user_origen')  # Agregado select_related
    
    context = {
        "usuario": usuario,
        "transacciones_enviadas": transacciones_enviadas,
        "transacciones_recibidas": transacciones_recibidas,
    }
    return render(request, 'mis_transacciones.html', context)

@login_required_custom
def actualizar_estado_transaccion(request, id_transaccion):
    """Permite actualizar el estado de una transacción."""
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda', 'user_destino', 'user_origen'), pk=id_transaccion)  # Cambiado: agregado select_related
    if transaccion.user_destino and transaccion.user_destino.id != usuario.id_usuario:  # Cambiado: 'user_destino'
        if transaccion.user_origen.id != usuario.id_usuario:  # Cambiado: 'user_origen'
            return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if not nuevo_estado or nuevo_estado not in dict(Transaccion.ESTADO_CHOICES):
            return JsonResponse({'error': 'Estado inválido'}, status=400)
        
        if transaccion.estado == 'PENDIENTE':
            if nuevo_estado == 'ACEPTADA':
                try:
                    transaccion.prenda.marcar_como_reservada()  # Cambiado: 'prenda'
                    transaccion.estado = nuevo_estado
                    transaccion.save()
                    messages.success(request, 'Has aceptado la propuesta. La prenda ahora está reservada.')
                except Exception as e:
                    logger.error(f"Error aceptando transacción {transaccion.id}: {e}")
                    return JsonResponse({'error': 'Error interno'}, status=500)
            elif nuevo_estado == 'RECHAZADA':
                try:
                    transaccion.estado = nuevo_estado
                    transaccion.save()
                    messages.success(request, 'Has rechazado la propuesta. La prenda sigue disponible.')
                except Exception as e:
                    logger.error(f"Error rechazando transacción {transaccion.id}: {e}")
                    return JsonResponse({'error': 'Error interno'}, status=500)
            else:
                return JsonResponse({'error': 'Desde PENDIENTE solo puedes aceptar (ACEPTADA) o rechazar (RECHAZADA).'}, status=400)
        else:
            try:
                transaccion.estado = nuevo_estado
                transaccion.save()
                messages.success(request, f'Estado de la transacción actualizado a: {transaccion.get_estado_display()}')
            except Exception as e:
                logger.error(f"Error actualizando estado transacción {transaccion.id}: {e}")
                return JsonResponse({'error': 'Error interno'}, status=500)
        
        return redirect('mis_transacciones')
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required_custom
def reportar_disputa(request, id_transaccion):
    """Permite al comprador/receptor reportar un problema con la prenda."""
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda', 'user_destino'), pk=id_transaccion)  # Cambiado: agregado select_related
    
    if not transaccion.user_destino or transaccion.user_destino.id != usuario.id_usuario:  # Cambiado: 'user_destino'
        messages.error(request, 'Solo el receptor puede reportar problemas.')
        return redirect('mis_transacciones')
    
    if transaccion.estado != 'EN_PROCESO':
        messages.error(request, 'Solo puedes reportar problemas cuando la prenda está en proceso de entrega.')
        return redirect('mis_transacciones')
    
    if request.method == 'POST':
        razon = request.POST.get('razon_disputa')
        if not razon or len(razon.strip()) < 10:
            messages.error(request, 'Debes proporcionar una descripción detallada del problema (mínimo 10 caracteres).')
            return redirect('mis_transacciones')
        
        try:
            transaccion.estado = 'EN_DISPUTA'
            transaccion.en_disputa = True
            transaccion.razon_disputa = razon.strip()
            transaccion.reportado_por = usuario
            transaccion.fecha_disputa = timezone.now()
            transaccion.save()
            messages.success(request, 'Tu reporte ha sido registrado. El equipo de administración revisará la disputa.')
            return redirect('mis_transacciones')
        except Exception as e:
            logger.error(f"Error reportando disputa en transacción {transaccion.id}: {e}")
            messages.error(request, 'Error interno. Intenta nuevamente.')
    
    context = {
        'usuario': usuario,
        'transaccion': transaccion,
    }
    return render(request, 'reportar_disputa.html', context)

@admin_required
def resolver_disputa(request, id_transaccion):
    """Solo administrador: Resuelve una disputa."""
    transaccion = get_object_or_404(Transaccion.objects.select_related('prenda', 'user_origen', 'user_destino', 'reportado_por'), pk=id_transaccion)  # Cambiado: agregado select_related
    
    if transaccion.estado != 'EN_DISPUTA':
        messages.error(request, 'Esta transacción no está en disputa.')
        return redirect('admin:index')
    
    if request.method == 'POST':
        resolucion = request.POST.get('resolucion')
        notas_admin = request.POST.get('notas_admin')
        
        if resolucion not in ['COMPLETADA', 'CANCELADA']:
            return JsonResponse({'error': 'Resolución inválida'}, status=400)
        
        try:
            transaccion.estado = resolucion
            transaccion.save()
            messages.success(request, f'Disputa resuelta como {transaccion.get_estado_display()}')
            return redirect('admin:index')
        except Exception as e:
            logger.error(f"Error resolviendo disputa en transacción {transaccion.id}: {e}")
            return JsonResponse({'error': 'Error interno'}, status=500)
    
    # Obtener mensajes entre los usuarios
    mensajes = Mensaje.objects.filter(
        Q(emisor=transaccion.user_origen, receptor=transaccion.user_destino) |  # Cambiado: 'emisor', 'receptor'
        Q(emisor=transaccion.user_destino, receptor=transaccion.user_origen)
    ).order_by('fecha_envio')
    
    context = {
        'transaccion': transaccion,
        'mensajes': mensajes,
    }
    return render(request, 'admin_resolver_disputa.html', context)
                   

# ------------------------------------------------------------------------------------------------------------------
# Mensajería entre usuarios

@login_required_custom
def lista_mensajes(request):
    """Vista de la lista de conversaciones del usuario."""
    usuario = get_usuario_actual(request)
    # Usuarios con los que hay intercambio de mensajes
    enviados = Mensaje.objects.filter(emisor=usuario).values_list('receptor', flat=True)  # Cambiado: 'emisor', 'receptor'
    recibidos = Mensaje.objects.filter(receptor=usuario).values_list('emisor', flat=True)  # Cambiado: 'receptor', 'emisor'
    ids_conversaciones = set(list(enviados) + list(recibidos))
    conversaciones = Usuario.objects.filter(id__in=ids_conversaciones).select_related()  # Cambiado: 'id__in', agregado select_related
    context = {
        'usuario': usuario,
        'conversaciones': conversaciones,
    }
    return render(request, 'lista_mensajes.html', context)

@login_required_custom
def conversacion(request, id_usuario):
    """Muestra la conversación entre el usuario y otro usuario específico."""
    usuario = get_usuario_actual(request)
    otro_usuario = get_object_or_404(Usuario, pk=id_usuario)  # Cambiado: 'pk=id_usuario'
    # Mensajes entre ambos (enviado/recibido)
    mensajes_conversacion = Mensaje.objects.filter(
        Q(emisor=usuario, receptor=otro_usuario) |  # Cambiado: 'emisor', 'receptor'
        Q(emisor=otro_usuario, receptor=usuario)
    ).order_by('fecha_envio').select_related('emisor', 'receptor')  # Agregado select_related
    context = {
        'usuario': usuario,
        'otro_usuario': otro_usuario,
        'mensajes': mensajes_conversacion,
    }
    return render(request, 'conversacion.html', context)

@login_required_custom
def enviar_mensaje(request):
    """Envía un mensaje de usuario a usuario (AJAX o POST normal)."""
    usuario = get_usuario_actual(request)
    if request.method == 'POST':
        receptor_id = request.POST.get('receptor_id')
        contenido = request.POST.get('contenido')
        if not receptor_id or not contenido or len(contenido.strip()) < 2:
            return JsonResponse({'error': 'Datos incompletos.'}, status=400)
        try:
            receptor = Usuario.objects.get(pk=receptor_id)  # Cambiado: 'pk=receptor_id'
            Mensaje.objects.create(
                emisor=usuario,  # Cambiado: 'emisor'
                receptor=receptor,  # Cambiado: 'receptor'
                contenido=contenido.strip(),
                fecha_envio=timezone.now()
            )
            messages.success(request, f'Mensaje enviado a {receptor.nombre}')
            # Si usas AJAX:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('conversacion', id_usuario=receptor.pk)  # Cambiado: 'receptor.pk'
        except Usuario.DoesNotExist:
            return JsonResponse({'error': 'Receptor no encontrado.'}, status=404)
        except Exception as e:
            logger.error(f"Error enviando mensaje de {usuario.id_usuario} a {receptor_id}: {e}")
            return JsonResponse({'error': 'Error interno.'}, status=500)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

# ------------------------------------------------------------------------------------------------------------------
# Fundaciones

def lista_fundaciones(request):
    """Lista todas las fundaciones registradas."""
    usuario = get_usuario_actual(request)
    fundaciones = Fundacion.objects.filter(activa=True).select_related('representante')  # Agregado select_related
    context = {
        'usuario': usuario,
        'fundaciones': fundaciones,
    }
    return render(request, 'lista_fundaciones.html', context)

def detalle_fundacion(request, id_fundacion):
    """Muestra información y estadísticas de una fundación."""
    usuario = get_usuario_actual(request)
    fundacion = get_object_or_404(Fundacion.objects.select_related('representante'), pk=id_fundacion)  # Cambiado: 'pk=id_fundacion', agregado select_related
    # Donaciones recibidas por la fundación, ordenadas por más recientes
    donaciones = Transaccion.objects.filter(
        fundacion=fundacion,  # Cambiado: 'fundacion'
        tipo__nombre_tipo='Donación'  # Cambiado: 'tipo__nombre_tipo'
    ).select_related('prenda', 'user_origen').order_by('-fecha_transaccion')  # Cambiado: 'prenda', 'user_origen', agregado select_related

    # Impacto ambiental total de todas las prendas donadas a esta fundación
    prendas_donadas = [don.prenda for don in donaciones if don.prenda]  # Cambiado: 'don.prenda'
    impacto_total = ImpactoAmbiental.objects.filter(
        prenda__in=prendas_donadas  # Cambiado: 'prenda__in'
    ).aggregate(
        total_carbono=Sum('carbono_evitar_kg'),
        total_energia=Sum('energia_ahorrada_kwh')
    )

    context = {
        'usuario': usuario,
        'fundacion': fundacion,
        'donaciones': donaciones,
        'impacto_total': impacto_total,
    }
    return render(request, 'detalle_fundacion.html', context)

# ------------------------------------------------------------------------------------------------------------------
# Impacto ambiental

@login_required_custom
def panel_impacto(request):
    """Panel de impacto total de la comunidad."""
    usuario = get_usuario_actual(request)
    impacto_total = ImpactoAmbiental.objects.aggregate(
        total_carbono=Sum('carbono_evitar_kg'),
        total_energia=Sum('energia_ahorrada_kwh')
    )
    total_transacciones = Transaccion.objects.count()
    total_donaciones = Transaccion.objects.filter(tipo__nombre_tipo='Donación').count()  # Cambiado: 'tipo__nombre_tipo'
    total_intercambios = Transaccion.objects.filter(tipo__nombre_tipo='Intercambio').count()  # Cambiado: 'tipo__nombre_tipo'
    total_ventas = Transaccion.objects.filter(tipo__nombre_tipo='Venta').count()  # Cambiado: 'tipo__nombre_tipo'

    usuarios_activos = Usuario.objects.annotate(
        num_transacciones=Count('transacciones_origen')  # Cambiado: 'transacciones_origen' (related_name)
    ).order_by('-num_transacciones')[:5]

    fundaciones_top = Fundacion.objects.annotate(
        num_donaciones=Count('transacciones')  # Cambiado: 'transacciones' (related_name)
    ).order_by('-num_donaciones')[:5]

    context = {
        'usuario': usuario,
        'impacto_total': impacto_total,
        'total_transacciones': total_transacciones,
        'total_donaciones': total_donaciones,
        'total_intercambios': total_intercambios,
        'total_ventas': total_ventas,
        'usuarios_activos': usuarios_activos,
        'fundaciones_top': fundaciones_top,
    }
    return render(request, 'panel_impacto.html', context)

@login_required_custom
def mi_impacto(request):
    """Impacto ambiental personal del usuario y resumen de sus transacciones."""
    usuario = get_usuario_actual(request)
    if not usuario:
        messages.error(request, 'Debes iniciar sesión.')
        return redirect('login')
    mis_transacciones = Transaccion.objects.filter(
        Q(user_origen=usuario) | Q(user_destino=usuario)  # Cambiado: 'user_origen', 'user_destino'
    ).select_related('prenda', 'tipo', 'user_origen', 'user_destino', 'fundacion')  # Cambiado: nombres, agregado select_related

    prendas_ids = [t.prenda.pk for t in mis_transacciones if t.prenda]  # Cambiado: 't.prenda.pk'
    mi_impacto_total = ImpactoAmbiental.objects.filter(
        prenda__pk__in=prendas_ids  # Cambiado: 'prenda__pk__in'
    ).aggregate(
        total_carbono=Sum('carbono_evitar_kg'),
        total_energia=Sum('energia_ahorrada_kwh')
    )

    donaciones = mis_transacciones.filter(tipo__nombre_tipo='Donación').count()  # Cambiado: 'tipo__nombre_tipo'
    intercambios = mis_transacciones.filter(tipo__nombre_tipo='Intercambio').count()  # Cambiado: 'tipo__nombre_tipo'
    ventas = mis_transacciones.filter(tipo__nombre_tipo='Venta').count()  # Cambiado: 'tipo__nombre_tipo'

    context = {
        'usuario': usuario,
        'mi_impacto': mi_impacto_total,
        'total_transacciones': mis_transacciones.count(),
        'donaciones': donaciones,
        'intercambios': intercambios,
        'ventas': ventas,
        'transacciones_recientes': mis_transacciones.order_by('-fecha_transaccion')[:10],
    }
    return render(request, 'mi_impacto.html', context)


# ------------------------------------------------------------------------------------------------------------------
# Información y gestión de sesión

@login_required_custom
def session_info(request):
    """Muestra información relevante de la sesión actual"""
    usuario = get_usuario_actual(request)
    from datetime import datetime

    # Recuperar/asegurar nombre y correo en sesión
    id_usuario = request.session.get('id_usuario')
    usuario_nombre = request.session.get('usuario_nombre')
    usuario_correo = request.session.get('usuario_correo')

    if (not usuario_nombre or not usuario_correo) and id_usuario:
        try:
            u = Usuario.objects.only('nombre', 'correo').get(id=id_usuario) 
            usuario_nombre = u.nombre
            usuario_correo = u.correo
            request.session['usuario_nombre'] = usuario_nombre
            request.session['usuario_correo'] = usuario_correo
        except Usuario.DoesNotExist:
            logger.warning(f"Usuario con ID {id_usuario} no encontrado en session_info")
            usuario_nombre = None
            usuario_correo = None

    # Información de la sesión
    session_data = {
        'session_key': (request.session.session_key or '')[:10] + '...' if request.session.session_key else 'N/A',  # Limitado para seguridad
        'id_usuario': id_usuario,
        'usuario_nombre': usuario_nombre,
        'usuario_correo': usuario_correo,
    }

    # Timestamp de login
    login_timestamp = request.session.get('login_timestamp')
    if login_timestamp:
        try:
            login_dt = datetime.fromisoformat(login_timestamp)
            session_data['login_timestamp'] = login_dt.strftime('%d/%m/%Y %H:%M:%S')
            session_data['tiempo_sesion'] = str(timezone.now() - login_dt)
        except ValueError:
            logger.error(f"Error parseando login_timestamp: {login_timestamp}")
            session_data['login_timestamp'] = 'Error'

    # Última actividad
    ultima_actividad = request.session.get('ultima_actividad')
    if ultima_actividad:
        try:
            ultima_dt = datetime.fromisoformat(ultima_actividad)
            session_data['ultima_actividad'] = ultima_dt.strftime('%d/%m/%Y %H:%M:%S')
            tiempo_inactivo = (timezone.now() - ultima_dt).total_seconds()
            session_data['tiempo_inactivo'] = f"{int(tiempo_inactivo)} segundos"
        except ValueError:
            logger.error(f"Error parseando ultima_actividad: {ultima_actividad}")
            session_data['ultima_actividad'] = 'Error'

    # Expiración de la sesión
    expiry = request.session.get_expiry_age()
    if expiry:
        session_data['expira_en'] = f"{int(expiry / 60)} minutos"

    # Contador de requests opcional
    session_data['request_counter'] = request.session.get('request_counter', 0)

    context = {
        'usuario': usuario,
        'session_data': session_data,
    }

    return render(request, 'session_info.html', context)


@ajax_login_required
def session_status(request):
    """Endpoint AJAX para verificar estado de sesión"""
    from datetime import datetime

    ultima_actividad = request.session.get('ultima_actividad')
    tiempo_restante = None
    if ultima_actividad:
        try:
            ultima_dt = datetime.fromisoformat(ultima_actividad)
            tiempo_inactivo = (timezone.now() - ultima_dt).total_seconds()
            tiempo_restante = max(0, 1800 - int(tiempo_inactivo))  # 1800 segundos = 30 minutos
        except ValueError:
            logger.error(f"Error parseando ultima_actividad en session_status: {ultima_actividad}")

    # Asegurar nombre desde DB si no está en la sesión
    id_usuario = request.session.get('id_usuario')
    usuario_nombre = request.session.get('usuario_nombre')
    if (not usuario_nombre) and id_usuario:
        try:
            u = Usuario.objects.only('nombre').get(id=id_usuario)  
            usuario_nombre = u.nombre
            request.session['usuario_nombre'] = usuario_nombre
        except Usuario.DoesNotExist:
            logger.warning(f"Usuario con ID {id_usuario} no encontrado en session_status")
            usuario_nombre = None

    return JsonResponse({
        'autenticado': True,
        'id_usuario': id_usuario,
        'usuario_nombre': usuario_nombre,
        'tiempo_restante': tiempo_restante,
        'session_key': (request.session.session_key or '')[:10] + '...' if request.session.session_key else 'N/A'  # Limitado para seguridad
    })


@login_required_custom
def renovar_sesion(request):
    """Renueva la sesión y actualiza el timestamp de última actividad"""
    if request.method == 'POST':
        try:
            request.session['ultima_actividad'] = timezone.now().isoformat()
            request.session.modified = True
            if not request.session.get('login_timestamp'):
                request.session['login_timestamp'] = timezone.now().isoformat()
            return JsonResponse({
                'success': True,
                'message': 'Sesión renovada',
                'nueva_expiracion': request.session.get_expiry_age()
            })
        except Exception as e:
            logger.error(f"Error renovando sesión para usuario {request.session.get('id_usuario')}: {e}")
            return JsonResponse({'error': 'Error interno'}, status=500)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

# ------------------------------------------------------------------------------------------------------------------
# Gestión de Cookies

def configurar_cookies(request):
    """Página de configuración de cookies"""
    return render(request, 'configurar_cookies.html')

def aceptar_cookies(request):
    """Acepta todas las cookies, con preferencias personalizadas si se envían."""
    if request.method == 'POST':
        try:
            preferencias = {
                'esenciales': True,  # Siempre activadas
                'funcionalidad': request.POST.get('funcionalidad', 'true') == 'true',
                'analiticas': request.POST.get('analiticas', 'true') == 'true',
                'marketing': request.POST.get('marketing', 'true') == 'true',
                'fecha_aceptacion': timezone.now().isoformat(),
            }
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                response = JsonResponse({
                    'success': True,
                    'message': 'Preferencias de cookies guardadas',
                    'preferencias': preferencias
                })
            else:
                response = redirect('home')
            response.set_cookie(
                'cookie_consent',
                json.dumps(preferencias),
                max_age=365*24*60*60,  # 1 año
                httponly=False,  # Accesible desde JS
                samesite='Lax'
            )
            return response
        except Exception as e:
            logger.error(f"Error aceptando cookies: {e}")
            return JsonResponse({'error': 'Error interno'}, status=500)
    return redirect('configurar_cookies')

def rechazar_cookies(request):
    """Rechaza cookies no esenciales y guarda la preferencia mínima."""
    if request.method == 'POST':
        try:
            preferencias = {
                'esenciales': True,
                'funcionalidad': False,
                'analiticas': False,
                'marketing': False,
                'fecha_rechazo': timezone.now().isoformat(),
            }
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                response = JsonResponse({
                    'success': True,
                    'message': 'Solo se usarán cookies esenciales',
                    'preferencias': preferencias
                })
            else:
                response = redirect('home')
            response.set_cookie(
                'cookie_consent',
                json.dumps(preferencias),
                max_age=365*24*60*60,
                httponly=False,
                samesite='Lax'
            )
            return response
        except Exception as e:
            logger.error(f"Error rechazando cookies: {e}")
            return JsonResponse({'error': 'Error interno'}, status=500)
    return redirect('configurar_cookies')

def obtener_preferencias_cookies(request):
    """Devuelve las preferencias de cookies actuales (API)"""
    cookie_consent = request.COOKIES.get('cookie_consent')
    if cookie_consent:
        try:
            preferencias = json.loads(cookie_consent)
            return JsonResponse({
                'configurado': True,
                'preferencias': preferencias
            })
        except json.JSONDecodeError:
            logger.warning(f"Error decodificando cookie_consent: {cookie_consent}")
    return JsonResponse({
        'configurado': False,
        'preferencias': None
    })

def eliminar_cookies(request):
    """Elimina cookies no esenciales y restablece preferencias."""
    if request.method == 'POST':
        try:
            response = JsonResponse({
                'success': True,
                'message': 'Cookies eliminadas. Por favor configura tus preferencias nuevamente.'
            })
            response.delete_cookie('cookie_consent')
            # Eliminar todas menos las esenciales (puedes adaptar la lista de esenciales a tu configuración)
            for cookie_name in list(request.COOKIES.keys()):
                if cookie_name not in ['csrftoken', 'sessionid', 'ecoprendas_sessionid']:
                    response.delete_cookie(cookie_name)
            return response
        except Exception as e:
            logger.error(f"Error eliminando cookies: {e}")
            return JsonResponse({'error': 'Error interno'}, status=500)
    return JsonResponse({'error': 'Método no permitido'}, status=405)


# ------------------------------------------------------------------------------------------------------------------
# Panel y gestión de fundaciones

@representante_fundacion_required
def panel_fundacion(request):
    """Dashboard de la fundación del usuario: campañas, donaciones, estadísticas."""
    usuario = get_usuario_actual(request)
    fundacion = usuario.fundacion_asignada
    
    # Obtener donaciones recibidas
    donaciones_recibidas = Transaccion.objects.filter(
        id_fundacion=fundacion,
        id_tipo__nombre_tipo='Donación'
    ).select_related('id_prenda', 'id_usuario_origen')
    
    # Calcular impacto ambiental desde las prendas donadas
    impacto = ImpactoAmbiental.objects.filter(
        id_prenda__transaccion__id_fundacion=fundacion,
        id_prenda__transaccion__id_tipo__nombre_tipo='Donación'
    ).aggregate(
        total_carbono=Sum('carbono_evitar_kg'),
        total_energia=Sum('energia_ahorrada_kwh'),
    )
    
    # Obtener campañas de la fundación
    campanas = CampanaFundacion.objects.filter(id_fundacion=fundacion).order_by('-fecha_inicio')
    
    # Estadísticas generales
    total_donaciones = donaciones_recibidas.count()
    donaciones_pendientes = donaciones_recibidas.filter(estado='PENDIENTE').count()
    donaciones_completadas = donaciones_recibidas.filter(estado='COMPLETADA').count()
    
    context = {
        'usuario': usuario,
        'fundacion': fundacion,
        'donaciones_recibidas': donaciones_recibidas[:10],  # Últimas 10
        'total_donaciones': total_donaciones,
        'donaciones_pendientes': donaciones_pendientes,
        'donaciones_completadas': donaciones_completadas,
        'impacto': impacto,
        'campanas': campanas,
    }
    return render(request, 'panel_fundacion.html', context)

@representante_fundacion_required
def gestionar_donaciones(request):
    """Lista todas las donaciones a la fundación, permite confirmar o rechazar."""
    usuario = get_usuario_actual(request)
    fundacion = usuario.fundacion_asignada
    donaciones = Transaccion.objects.filter(id_fundacion=fundacion, id_tipo__nombre_tipo='Donación', estado='PENDIENTE')
    context = {
        'usuario': usuario,
        'fundacion': fundacion,
        'donaciones': donaciones,
    }
    return render(request, 'gestionar_donaciones.html', context)

@representante_fundacion_required
def confirmar_recepcion_donacion(request, id_transaccion):
    """Confirma la recepción de una donación y actualiza estados."""
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(
        Transaccion,
        id_transaccion=id_transaccion,
        id_fundacion=usuario.fundacion_asignada
    )

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido. Debes confirmar mediante POST.'}, status=405)

    if transaccion.estado != 'EN_PROCESO':
        return JsonResponse({'error': 'La donación aún no ha sido marcada como entregada por el donante.'}, status=400)

    transaccion.estado = 'COMPLETADA'
    transaccion.fecha_entrega = timezone.now()
    transaccion.save()
    transaccion.actualizar_disponibilidad_prenda()

    Mensaje.objects.create(
        id_emisor=usuario,
        id_receptor=transaccion.id_usuario_origen,
        contenido=f"Gracias por tu donación de {transaccion.id_prenda.nombre}! Tu prenda ha sido recibida y será destinada a {transaccion.id_fundacion.nombre}.",
        fecha_envio=timezone.now()
    )

    verificar_logros(transaccion.id_usuario_origen)
    messages.success(request, 'Donación confirmada y donante notificado.')
    return redirect('gestionar_donaciones')

@representante_fundacion_required
def enviar_mensaje_agradecimiento(request, id_usuario_donante):
    """Envía un mensaje personalizado de agradecimiento al donante."""
    usuario = get_usuario_actual(request)
    donante = get_object_or_404(Usuario, id_usuario=id_usuario_donante)
    if request.method == 'POST':
        contenido = request.POST.get('contenido')
        if not contenido:
            messages.error(request, 'Escribe un mensaje de agradecimiento.')
        else:
            Mensaje.objects.create(
                id_emisor=usuario,
                id_receptor=donante,
                contenido=contenido,
                fecha_envio=timezone.now()
            )
            messages.success(request, f'Mensaje enviado a {donante.nombre}.')
            return redirect('panel_fundacion')
    context = {
        'usuario': usuario,
        'donante': donante,
    }
    return render(request, 'enviar_mensaje_agradecimiento.html', context)

# ------------------------------------------------------------------------------------------------------------------
# Campañas solidarias

@representante_fundacion_required
def crear_campana(request):
    """Permite a la fundación/representante crear una nueva campaña."""
    usuario = get_usuario_actual(request)
    fundacion = usuario.fundacion_asignada
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        objetivo_prendas = int(request.POST.get('objetivo_prendas', 0))
        if not all([nombre, fecha_inicio, fecha_fin, objetivo_prendas > 0]):
            messages.error(request, 'Completa los campos obligatorios y un objetivo mayor a 0.')
        else:
            CampanaFundacion.objects.create(
                id_fundacion=fundacion,
                nombre=nombre,
                descripcion=descripcion,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                objetivo_prendas=objetivo_prendas,
                activa=True
            )
            messages.success(request, '¡Campaña creada exitosamente!')
            return redirect('panel_fundacion')
    context = {'usuario': usuario, 'fundacion': fundacion}
    return render(request, 'crear_campana.html', context)

@login_required_custom
def campanas_solidarias(request):
    """Muestra todas las campañas solidarias activas de fundaciones."""
    usuario = get_usuario_actual(request)
    campanas = CampanaFundacion.objects.filter(activa=True).select_related('id_fundacion').order_by('fecha_inicio')
    context = {
        'usuario': usuario,
        'campanas': campanas,
    }
    return render(request, 'campanas_solidarias.html', context)

@login_required_custom
def detalle_campana(request, id_campana):
    """Detalle de una campaña solidaria de una fundación."""
    usuario = get_usuario_actual(request)
    campana = get_object_or_404(CampanaFundacion, id_campana=id_campana)
    donaciones = Transaccion.objects.filter(id_campana=campana, id_tipo__nombre_tipo='Donación')
    prendas_donadas = [don.id_prenda for don in donaciones if don.id_prenda]
    avance = len(prendas_donadas)
    porcentaje_avance = int(100 * avance / campana.objetivo_prendas) if campana.objetivo_prendas else 0
    context = {
        'usuario': usuario,
        'campana': campana,
        'donaciones': donaciones,
        'avance': avance,
        'porcentaje_avance': porcentaje_avance,
    }
    return render(request, 'detalle_campana.html', context)

@login_required_custom
def donar_a_campana(request, id_campana):
    """Permite donar una prenda a una campaña solidaria."""
    usuario = get_usuario_actual(request)
    campana = get_object_or_404(CampanaFundacion, id_campana=id_campana, activa=True)
    if request.method == 'POST':
        prenda_id = request.POST.get('prenda_id')
        prenda = get_object_or_404(Prenda, id_prenda=prenda_id, id_usuario=usuario, disponibilidad='DISPONIBLE')
        if not prenda.esta_disponible():
            messages.error(request, 'La prenda ya no está disponible.')
            return redirect('donar_a_campana', id_campana=id_campana)
        tipo_donacion, _ = TipoTransaccion.objects.get_or_create(nombre_tipo='Donación')
        Transaccion.objects.create(
            id_prenda=prenda,
            id_tipo=tipo_donacion,
            id_usuario_origen=usuario,
            id_fundacion=campana.id_fundacion,
            id_campana=campana,
            fecha_transaccion=timezone.now(),
            estado='PENDIENTE'
        )
        prenda.disponibilidad = 'RESERVADA'
        prenda.save()
        messages.success(request, f'¡Donación asociada a la campaña "{campana.nombre}"!')
        return redirect('mis_prendas')
    prendas_usuario = Prenda.objects.filter(id_usuario=usuario, disponibilidad='DISPONIBLE')
    context = {
        'usuario': usuario,
        'campana': campana,
        'prendas': prendas_usuario,
    }
    return render(request, 'donar_a_campana.html', context)

@representante_fundacion_required
def mis_campanas(request):
    """Lista de campañas gestionadas por la fundación del usuario."""
    usuario = get_usuario_actual(request)
    fundacion = usuario.fundacion_asignada
    campanas = CampanaFundacion.objects.filter(id_fundacion=fundacion)
    context = {
        'usuario': usuario,
        'fundacion': fundacion,
        'campanas': campanas,
    }
    return render(request, 'mis_campanas.html', context)

# ------------------------------------------------------------------------------------------------------------------
# Logros y Recomendaciones

def verificar_logros(usuario):
    """Chequea y asigna logros automáticamente según reglas."""
    nuevos = []

    if not usuario:
        return []
    
    for logro in Logro.objects.all():
        # Verificar si el usuario ya tiene el logro
        if UsuarioLogro.objects.filter(id_usuario=usuario, id_logro=logro).exists():
            continue
        
        # Logro: Donador (1 donación completada)
        if logro.codigo == 'DONADOR':
            donaciones = Transaccion.objects.filter(
                id_usuario_origen=usuario,
                id_tipo__nombre_tipo='Donación',
                estado='COMPLETADA'
            ).count()
            if donaciones >= 1:
                UsuarioLogro.objects.create(
                    id_usuario=usuario,
                    id_logro=logro,
                    fecha_desbloqueo=timezone.now()
                )
                nuevos.append(logro)
        
        # Logro: SuperUser (10 prendas publicadas)
        elif logro.codigo == 'SUPERUSER':
            prendas_count = Prenda.objects.filter(id_usuario=usuario).count()
            if prendas_count >= 10:
                UsuarioLogro.objects.create(
                    id_usuario=usuario,
                    id_logro=logro,
                    fecha_desbloqueo=timezone.now()
                )
                nuevos.append(logro)
        
        # Logro: Intercambiador (5 intercambios completados)
        elif logro.codigo == 'INTERCAMBIADOR':
            intercambios = Transaccion.objects.filter(
                Q(id_usuario_origen=usuario) | Q(id_usuario_destino=usuario),
                id_tipo__nombre_tipo='Intercambio',
                estado='COMPLETADA'
            ).count()
            if intercambios >= 5:
                UsuarioLogro.objects.create(
                    id_usuario=usuario,
                    id_logro=logro,
                    fecha_desbloqueo=timezone.now()
                )
                nuevos.append(logro)
        
        # Logro: Eco Guerrero (1000 kg de carbono evitado)
        elif logro.codigo == 'ECO_GUERRERO':
            impacto = ImpactoAmbiental.objects.filter(
                id_prenda__id_usuario=usuario
            ).aggregate(total_carbono=Sum('carbono_evitar_kg'))
            carbono_total = impacto['total_carbono'] or 0
            if carbono_total >= 1000:
                UsuarioLogro.objects.create(
                    id_usuario=usuario,
                    id_logro=logro,
                    fecha_desbloqueo=timezone.now()
                )
                nuevos.append(logro)
    
    return nuevos

@login_required_custom
def desbloquear_logro(request, codigo_logro):
    """Desbloqueo manual (usado para pruebas/admin)."""
    usuario = get_usuario_actual(request)
    logro = get_object_or_404(Logro, codigo=codigo_logro)
    UsuarioLogro.objects.get_or_create(usuario=usuario, logro=logro, defaults={'fecha_desbloqueo': timezone.now()})
    messages.success(request, f'¡Logro desbloqueado: {logro.nombre}!')
    return redirect('mis_logros')

@login_required_custom
def mis_logros(request):
    """Vista de todos los logros obtenidos por el usuario."""
    usuario = get_usuario_actual(request)
    logros = UsuarioLogro.objects.filter(usuario=usuario).select_related('logro')
    context = {
        'usuario': usuario,
        'logros': logros,
    }
    return render(request, 'mis_logros.html', context)

@login_required_custom
def recomendaciones(request):
    """Muestra recomendaciones de prendas basadas en actividad/intereses del usuario."""
    usuario = get_usuario_actual(request)
    if not usuario:
        messages.error(request, 'Debes iniciar sesión.')
        return redirect('login')

    # Obtener preferencias del usuario
    prendas_usuario = Prenda.objects.filter(id_usuario=usuario).values_list('categoria', 'talla').distinct()

    if not prendas_usuario.exists():
        # Si no tiene prendas, mostrar las más recientes
        prendas_recomendadas = list(Prenda.objects.filter(
            disponibilidad='DISPONIBLE'
        ).exclude(id_usuario=usuario).order_by('-fecha_publicacion')[:12])
    else:
        categorias_favoritas = [p[0] for p in prendas_usuario if p[0]]
        tallas_favoritas = [p[1] for p in prendas_usuario if p[1]]

        principales = list(Prenda.objects.filter(
            disponibilidad='DISPONIBLE',
            categoria__in=categorias_favoritas,
            talla__in=tallas_favoritas
        ).exclude(id_usuario=usuario).order_by('-fecha_publicacion')[:12])

        prendas_recomendadas = principales

        if len(prendas_recomendadas) < 6:
            adicionales = Prenda.objects.filter(
                disponibilidad='DISPONIBLE',
                categoria__in=categorias_favoritas
            ).exclude(id_usuario=usuario).exclude(id_prenda__in=[p.id_prenda for p in principales]).order_by('-fecha_publicacion')[:12]

            prendas_recomendadas += list(adicionales)

    # Usuarios relacionados por transacciones
    mis_transacciones = Transaccion.objects.filter(
        Q(id_usuario_origen=usuario) | Q(id_usuario_destino=usuario)
    ).values_list('id_usuario_origen', 'id_usuario_destino')

    usuarios_relacionados = set()
    for origen, destino in mis_transacciones:
        if origen and origen != usuario.id_usuario:
            usuarios_relacionados.add(origen)
        if destino and destino != usuario.id_usuario:
            usuarios_relacionados.add(destino)

    context = {
        'usuario': usuario,
        'prendas_recomendadas': prendas_recomendadas,
        'total_recomendaciones': len(prendas_recomendadas),
    }
    return render(request, 'recomendaciones.html', context)

# ------------------------------------------------------------------------------------------------------------------
# Actualización de imágenes

@login_required_custom
def actualizar_foto_perfil(request):
    """Permite al usuario actualizar su foto de perfil."""
    usuario = get_usuario_actual(request)
    if request.method == 'POST' and 'imagen_usuario' in request.FILES:
        usuario.imagen_usuario = request.FILES['imagen_usuario']
        usuario.save()
        messages.success(request, 'Foto de perfil actualizada.')
        return redirect('perfil')
    messages.error(request, 'Sube una imagen válida.')
    return redirect('perfil')

@login_required_custom
def actualizar_imagen_prenda(request, id_prenda):
    """Actualiza la imagen de una prenda del usuario."""
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda, id_prenda=id_prenda, id_usuario=usuario)
    if request.method == 'POST' and 'imagen_prenda' in request.FILES:
        prenda.imagen_prenda = request.FILES['imagen_prenda']
        prenda.save()
        messages.success(request, 'Imagen de prenda actualizada.')
        return redirect('detalle_prenda', id_prenda=prenda.id_prenda)
    messages.error(request, 'Sube una imagen válida.')
    return redirect('editar_prenda', id_prenda=prenda.id_prenda)

@login_required_custom
def actualizar_logo_fundacion(request, id_fundacion):
    """Actualiza el logo de la fundación. Solo para representantes."""
    usuario = get_usuario_actual(request)
    fundacion = get_object_or_404(Fundacion, id_fundacion=id_fundacion, representante=usuario)
    if request.method == 'POST' and 'imagen_fundacion' in request.FILES:
        fundacion.imagen_fundacion = request.FILES['imagen_fundacion']
        fundacion.save()
        messages.success(request, 'Logo de fundación actualizado.')
        return redirect('panel_fundacion', id_fundacion=fundacion.id_fundacion)
    messages.error(request, 'Sube una imagen válida.')
    return redirect('panel_fundacion')

@representante_fundacion_required
def actualizar_imagen_campana(request, id_campana):
    """Actualiza la imagen de una campaña (para representantes de la fundación)."""
    usuario = get_usuario_actual(request)
    campana = get_object_or_404(CampanaFundacion, id_campana=id_campana)

    if not usuario or usuario.fundacion_asignada != campana.id_fundacion:
        messages.error(request, 'No tienes permiso para modificar esta campaña.')
        return redirect('mis_campanas')

    if request.method == 'POST' and 'imagen_campana' in request.FILES:
        campana.imagen = request.FILES['imagen_campana']
        campana.save()
        messages.success(request, 'Imagen de campaña actualizada.')
        return redirect('detalle_campana', id_campana=campana.id_campana)

    messages.error(request, 'Sube una imagen válida.')
    return redirect('detalle_campana', id_campana=id_campana)

# ------------------------------------------------------------------------------------------------------------------
# Estadísticas y reportes para fundaciones

@representante_fundacion_required
def estadisticas_donaciones(request):
    """Panel con estadísticas avanzadas de donaciones de la fundación."""
    usuario = get_usuario_actual(request)
    fundacion = usuario.fundacion_asignada
    donaciones = Transaccion.objects.filter(id_fundacion=fundacion, id_tipo__nombre_tipo='Donación')
    resumen = donaciones.values('estado').annotate(total=Count('id_transaccion'))
    prendas = Prenda.objects.filter(id_fundacion=fundacion)
    context = {
        'fundacion': fundacion,
        'donaciones': donaciones,
        'resumen': list(resumen),
        'total_prendas': prendas.count()
    }
    return render(request, 'estadisticas_donaciones.html', context)

# ==============================================================================
# VISTA DEL MAPA INTERACTIVO
# ==============================================================================

def mapa_fundaciones(request):
    """
    Mapa interactivo que muestra:
    - Todas las fundaciones activas (SIEMPRE visibles)
    - Usuarios que han activado "mostrar_en_mapa" (OPCIONAL)
    
    Usa Geoapify + Leaflet.js para renderizar el mapa.
    """
    usuario = get_usuario_actual(request)
    
    # Obtener todas las fundaciones activas con coordenadas válidas
    fundaciones = Fundacion.objects.filter(
        activa=True,
        lat__isnull=False,
        lng__isnull=False
    ).values('id_fundacion', 'nombre', 'direccion', 'lat', 'lng', 'telefono', 'correo_contacto')

    # Obtener usuarios que aceptaron mostrar su ubicación
    usuarios_visibles = Usuario.objects.filter(
        mostrar_en_mapa=True,
        lat__isnull=False,
        lng__isnull=False
    ).values('id', 'nombre', 'comuna', 'lat', 'lng')
    
    # Convertir QuerySets a listas para JSON
    fundaciones_list = list(fundaciones)
    usuarios_list = list(usuarios_visibles)
    
    # Centro del mapa (Santiago, Chile por defecto)
    centro_lat = -33.4489
    centro_lng = -70.6693
    
    # Si hay fundaciones, centrar en la primera
    if fundaciones_list:
        centro_lat = fundaciones_list[0]['lat']
        centro_lng = fundaciones_list[0]['lng']
    
    context = {
        'usuario': usuario,
        'fundaciones_json': json.dumps(fundaciones_list),
        'usuarios_json': json.dumps(usuarios_list),
        'centro_lat': centro_lat,
        'centro_lng': centro_lng,
        'geoapify_api_key': settings.GEOAPIFY_API_KEY,
        'total_fundaciones': len(fundaciones_list),
        'total_usuarios_visibles': len(usuarios_list),
    }
    
    return render(request, 'mapa_fundaciones.html', context)


@login_required_custom
def actualizar_ubicacion_usuario(request):
    """
    Permite al usuario actualizar su ubicación en el mapa.
    Usa geocodificación de Geoapify para convertir dirección en coordenadas.
    """
    usuario = get_usuario_actual(request)
    
    if request.method == 'POST':
        direccion = request.POST.get('direccion')
        mostrar_en_mapa = request.POST.get('mostrar_en_mapa') == 'on'
        
        if not direccion:
            messages.error(request, 'Debes ingresar una dirección.')
            return redirect('perfil')
        
        # Geocodificar dirección usando Geoapify
        import requests
        
        geocode_url = f"https://api.geoapify.com/v1/geocode/search"
        params = {
            'text': direccion,
            'apiKey': settings.GEOAPIFY_API_KEY,
            'limit': 1
        }
        
        try:
            response = requests.get(geocode_url, params=params)
            data = response.json()
            
            if data.get('features') and len(data['features']) > 0:
                coords = data['features'][0]['geometry']['coordinates']
                lng, lat = coords[0], coords[1]
                
                # Actualizar usuario
                usuario.direccion = direccion
                usuario.lat = lat
                usuario.lng = lng
                usuario.mostrar_en_mapa = mostrar_en_mapa
                usuario.save()
                
                messages.success(request, f'Ubicación actualizada: {direccion}')
            else:
                messages.error(request, 'No se pudo encontrar la dirección. Intenta con una más específica.')
        
        except Exception as e:
            messages.error(request, f'Error al geocodificar: {str(e)}')
    
    return redirect('perfil')


@admin_required
def actualizar_ubicacion_fundacion(request, id_fundacion):
    """
    Permite a administradores actualizar la ubicación de una fundación.
    """
    fundacion = get_object_or_404(Fundacion, id_fundacion=id_fundacion)
    
    if request.method == 'POST':
        direccion = request.POST.get('direccion')
        
        if not direccion:
            messages.error(request, 'Debes ingresar una dirección.')
            return redirect('detalle_fundacion', id_fundacion=id_fundacion)
        
        # Geocodificar dirección
        import requests
        
        geocode_url = f"https://api.geoapify.com/v1/geocode/search"
        params = {
            'text': direccion,
            'apiKey': settings.GEOAPIFY_API_KEY,
            'limit': 1
        }
        
        try:
            response = requests.get(geocode_url, params=params)
            data = response.json()
            
            if data.get('features') and len(data['features']) > 0:
                coords = data['features'][0]['geometry']['coordinates']
                lng, lat = coords[0], coords[1]
                
                fundacion.direccion = direccion
                fundacion.lat = lat
                fundacion.lng = lng
                fundacion.save()
                
                messages.success(request, f'Ubicación de fundación actualizada: {direccion}')
            else:
                messages.error(request, 'No se pudo encontrar la dirección.')
        
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('detalle_fundacion', id_fundacion=id_fundacion)

# ==============================================================================
# VISTAS ACTUALIZADAS CON CLOUDINARY - Reemplazar en views.py
# ==============================================================================

# ------------------------------------------------------------------------------
# ACTUALIZAR: crear_prenda
# ------------------------------------------------------------------------------
@cliente_only
def crear_prenda(request):
    """Permite al cliente crear una nueva prenda con imagen en Cloudinary."""
    usuario = get_usuario_actual(request)
    
    if request.method == 'POST':
        imagen = request.FILES.get('imagen_prenda')
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        categoria = request.POST.get('categoria')
        talla = request.POST.get('talla')
        condicion = request.POST.get('estado')

        if not all([nombre, descripcion, categoria, talla, condicion]):
            messages.error(request, 'Todos los campos son obligatorios.')
            return render(request, 'crear_prenda.html', {
                'usuario': usuario,
                'categorias': ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios'],
                'tallas': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
                'estados': ['Nuevo', 'Excelente', 'Bueno', 'Usado'],
            })
        
        # Validar imagen si se proporciona
        if imagen:
            es_valida, mensaje_error = validar_imagen(imagen)
            if not es_valida:
                messages.error(request, mensaje_error)
                return redirect('crear_prenda')
        
        # Crear prenda primero (sin imagen)
        prenda = Prenda.objects.create(
            id_usuario=usuario,
            nombre=nombre,
            descripcion=descripcion,
            categoria=categoria,
            talla=talla,
            estado='DISPONIBLE',
            fecha_publicacion=timezone.now()
        )
        
        # Subir imagen a Cloudinary si existe
        if imagen:
            resultado = subir_imagen_prenda(imagen, prenda.id_prenda)
            if resultado and resultado.get('secure_url'):
                prenda.imagen_prenda = resultado['secure_url']
                prenda.save()
                messages.success(request, '¡Prenda publicada con imagen en Cloudinary!')
            else:
                messages.warning(request, 'Prenda publicada pero hubo un error al subir la imagen.')
        else:
            messages.success(request, '¡Prenda publicada exitosamente!')
        
        # Calcular impacto ambiental simulado
        carbono_evitado = 5.5
        energia_ahorrada = 2.7
        ImpactoAmbiental.objects.create(
            id_prenda=prenda,
            carbono_evitar_kg=carbono_evitado,
            energia_ahorrada_kwh=energia_ahorrada,
            fecha_calculo=timezone.now()
        )
        
        return redirect('detalle_prenda', id_prenda=prenda.id_prenda)

    context = {
        'usuario': usuario,
        'categorias': ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios'],
        'tallas': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
        'estados': ['Nuevo', 'Excelente', 'Bueno', 'Usado'],
    }
    return render(request, 'crear_prenda.html', context)


# ------------------------------------------------------------------------------
# ACTUALIZAR: actualizar_imagen_prenda
# ------------------------------------------------------------------------------
@login_required_custom
def actualizar_imagen_prenda(request, id_prenda):
    """Actualiza la imagen de una prenda usando Cloudinary."""
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda, id_prenda=id_prenda, id_usuario=usuario)
    
    if request.method == 'POST' and 'imagen_prenda' in request.FILES:
        imagen = request.FILES['imagen_prenda']
        
        # Validar imagen
        es_valida, mensaje_error = validar_imagen(imagen)
        if not es_valida:
            messages.error(request, mensaje_error)
            return redirect('editar_prenda', id_prenda=prenda.id_prenda)
        
        # Eliminar imagen anterior de Cloudinary si existe
        if prenda.imagen_prenda:
            public_id = extraer_public_id_de_url(str(prenda.imagen_prenda))
            if public_id:
                eliminar_imagen_cloudinary(public_id)
        
        # Subir nueva imagen
        resultado = subir_imagen_prenda(imagen, prenda.id_prenda)
        if resultado and resultado.get('secure_url'):
            prenda.imagen_prenda = resultado['secure_url']
            prenda.save()
            messages.success(request, 'Imagen actualizada correctamente en Cloudinary.')
        else:
            messages.error(request, 'Error al subir la imagen a Cloudinary.')
        
        return redirect('detalle_prenda', id_prenda=prenda.id_prenda)
    
    messages.error(request, 'Sube una imagen válida.')
    return redirect('editar_prenda', id_prenda=prenda.id_prenda)


# ------------------------------------------------------------------------------
# ACTUALIZAR: actualizar_foto_perfil
# ------------------------------------------------------------------------------
@login_required_custom
def actualizar_foto_perfil(request):
    """Permite al usuario actualizar su foto de perfil usando Cloudinary."""
    usuario = get_usuario_actual(request)
    
    if request.method == 'POST' and 'imagen_usuario' in request.FILES:
        imagen = request.FILES['imagen_usuario']
        
        # Validar imagen
        es_valida, mensaje_error = validar_imagen(imagen)
        if not es_valida:
            messages.error(request, mensaje_error)
            return redirect('perfil')
        
        # Eliminar imagen anterior de Cloudinary si existe
        if usuario.imagen_usuario:
            public_id = extraer_public_id_de_url(str(usuario.imagen_usuario))
            if public_id:
                eliminar_imagen_cloudinary(public_id)
        
        # Subir nueva imagen
        resultado = subir_imagen_usuario(imagen, usuario.id_usuario)
        if resultado and resultado.get('secure_url'):
            usuario.imagen_usuario = resultado['secure_url']
            usuario.save()
            messages.success(request, 'Foto de perfil actualizada.')
        else:
            messages.error(request, 'Error al subir la imagen.')
        
        return redirect('perfil')
    
    messages.error(request, 'Sube una imagen válida.')
    return redirect('perfil')


# ------------------------------------------------------------------------------
# ACTUALIZAR: actualizar_logo_fundacion
# ------------------------------------------------------------------------------
@representante_fundacion_required
def actualizar_logo_fundacion(request, id_fundacion):
    """Actualiza el logo de la fundación usando Cloudinary."""
    usuario = get_usuario_actual(request)
    fundacion = get_object_or_404(Fundacion, id_fundacion=id_fundacion)
    
    # Verificar permisos
    if not (usuario.es_representante_fundacion() and usuario.fundacion_asignada == fundacion):
        messages.error(request, 'No tienes permiso para modificar esta fundación.')
        return redirect('panel_fundacion')
    
    if request.method == 'POST' and 'imagen_fundacion' in request.FILES:
        imagen = request.FILES['imagen_fundacion']
        
        # Validar imagen
        es_valida, mensaje_error = validar_imagen(imagen)
        if not es_valida:
            messages.error(request, mensaje_error)
            return redirect('panel_fundacion')
        
        # Eliminar imagen anterior
        if fundacion.imagen_fundacion:
            public_id = extraer_public_id_de_url(str(fundacion.imagen_fundacion))
            if public_id:
                eliminar_imagen_cloudinary(public_id)
        
        # Subir nueva imagen
        resultado = subir_logo_fundacion(imagen, fundacion.id_fundacion)
        if resultado and resultado.get('secure_url'):
            fundacion.imagen_fundacion = resultado['secure_url']
            fundacion.save()
            messages.success(request, 'Logo de fundación actualizado.')
        else:
            messages.error(request, 'Error al subir el logo.')
        
        return redirect('panel_fundacion')
    
    messages.error(request, 'Sube una imagen válida.')
    return redirect('panel_fundacion')


# ------------------------------------------------------------------------------
# ACTUALIZAR: actualizar_imagen_campana
# ------------------------------------------------------------------------------
@representante_fundacion_required
def actualizar_imagen_campana(request, id_campana):
    """Actualiza la imagen de una campaña usando Cloudinary."""
    usuario = get_usuario_actual(request)
    campana = get_object_or_404(CampanaFundacion, id_campana=id_campana)

    if not usuario or usuario.fundacion_asignada != campana.id_fundacion:
        messages.error(request, 'No tienes permiso para modificar esta campaña.')
        return redirect('mis_campanas')

    if request.method == 'POST' and 'imagen_campana' in request.FILES:
        imagen = request.FILES['imagen_campana']
        
        # Validar imagen
        es_valida, mensaje_error = validar_imagen(imagen)
        if not es_valida:
            messages.error(request, mensaje_error)
            return redirect('detalle_campana', id_campana=id_campana)
        
        # Eliminar imagen anterior
        if campana.imagen_campana:
            public_id = extraer_public_id_de_url(str(campana.imagen_campana))
            if public_id:
                eliminar_imagen_cloudinary(public_id)
        
        # Subir nueva imagen
        resultado = subir_imagen_campana(imagen, campana.id_campana)
        if resultado and resultado.get('secure_url'):
            campana.imagen_campana = resultado['secure_url']
            campana.save()
            messages.success(request, 'Imagen de campaña actualizada.')
        else:
            messages.error(request, 'Error al subir la imagen.')

        return redirect('detalle_campana', id_campana=campana.id_campana)

    messages.error(request, 'Sube una imagen válida.')
    return redirect('detalle_campana', id_campana=id_campana)


# ------------------------------------------------------------------------------
# NUEVA: galeria_imagenes (opcional - mostrar transformaciones)
# ------------------------------------------------------------------------------
@login_required_custom
def galeria_imagenes(request):
    """
    Muestra una galería de imágenes con diferentes transformaciones de Cloudinary.
    Útil para demostrar capacidades de optimización.
    """
    usuario = get_usuario_actual(request)
    
    # Obtener prendas del usuario con imágenes
    prendas = Prenda.objects.filter(
        id_usuario=usuario,
        imagen_prenda__isnull=False
    ).exclude(imagen_prenda='')
    
    # Para cada prenda, generar URLs transformadas
    prendas_con_transformaciones = []
    for prenda in prendas:
        if prenda.imagen_prenda:
            url_base = str(prenda.imagen_prenda)
            # Extraer public_id
            public_id = extraer_public_id_de_url(url_base)
            
            if public_id:
                from .cloudinary_utils import obtener_miniaturas
                miniaturas = obtener_miniaturas(public_id)
                
                prendas_con_transformaciones.append({
                    'prenda': prenda,
                    'url_original': url_base,
                    'miniaturas': miniaturas
                })
    
    context = {
        'usuario': usuario,
        'prendas': prendas_con_transformaciones,
    }
    
    return render(request, 'galeria_imagenes.html', context)


# ==============================================================================
# VISTAS ACTUALIZADAS CON CARBON INTERFACE
# ==============================================================================

# ------------------------------------------------------------------------------
# ACTUALIZAR: crear_prenda - Con cálculo real de impacto
# ------------------------------------------------------------------------------
@cliente_only
def crear_prenda(request):
    """Permite al cliente crear una nueva prenda con cálculo real de impacto."""
    usuario = get_usuario_actual(request)
    
    if request.method == 'POST':
        imagen = request.FILES.get('imagen_prenda')
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        categoria = request.POST.get('categoria')
        talla = request.POST.get('talla')
        condicion = request.POST.get('estado')

        if not all([nombre, descripcion, categoria, talla, condicion]):
            messages.error(request, 'Todos los campos son obligatorios.')
            return render(request, 'crear_prenda.html', {
                'usuario': usuario,
                'categorias': ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios'],
                'tallas': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
                'estados': ['Nuevo', 'Excelente', 'Bueno', 'Usado'],
            })
        
        # Validar imagen si se proporciona
        if imagen:
            from .cloudinary_utils import validar_imagen
            es_valida, mensaje_error = validar_imagen(imagen)
            if not es_valida:
                messages.error(request, mensaje_error)
                return redirect('crear_prenda')
        
        # Crear prenda
        prenda = Prenda.objects.create(
            user=usuario,
            nombre=nombre,
            descripcion=descripcion,
            categoria=categoria,
            talla=talla,
            estado='DISPONIBLE',
            fecha_publicacion=timezone.now()
        )
        
        # Subir imagen a Cloudinary si existe
        if imagen:
            from .cloudinary_utils import subir_imagen_prenda
            resultado = subir_imagen_prenda(imagen, prenda.id_prenda)
            if resultado and resultado.get('secure_url'):
                prenda.imagen_prenda = resultado['secure_url']
                prenda.save()
        
        # ✨ CALCULAR IMPACTO AMBIENTAL REAL ✨
        impacto = calcular_impacto_prenda(
            categoria=categoria,
            peso_kg=None,  # Podrías pedir el peso en el form
            usar_api=True  # Intenta usar API, sino usa valores predefinidos
        )
        
        # Guardar impacto en la base de datos
        ImpactoAmbiental.objects.create(
            id_prenda=prenda,
            carbono_evitar_kg=impacto['carbono_evitado_kg'],
            energia_ahorrada_kwh=impacto['energia_ahorrada_kwh'],
            fecha_calculo=timezone.now()
        )
        
        messages.success(
            request, 
            f'¡Prenda publicada! Evitarás {impacto["carbono_evitado_kg"]} kg de CO₂ al reutilizarla.'
        )
        
        return redirect('detalle_prenda', id_prenda=prenda.id_prenda)

    context = {
        'usuario': usuario,
        'categorias': ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios'],
        'tallas': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
        'estados': ['Nuevo', 'Excelente', 'Bueno', 'Usado'],
    }
    return render(request, 'crear_prenda.html', context)


# ------------------------------------------------------------------------------
# ACTUALIZAR: detalle_prenda - Mostrar impacto con equivalencias
# ------------------------------------------------------------------------------
@cliente_only
def detalle_prenda(request, id_prenda):
    """Detalle de prenda con impacto ambiental y equivalencias."""
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda, id_prenda=id_prenda)
    impacto_obj = ImpactoAmbiental.objects.filter(id_prenda=prenda).first()
    
    # Calcular equivalencias si hay impacto
    equivalencias = None
    if impacto_obj:
        from .carbon_utils import calcular_equivalencias
        equivalencias = calcular_equivalencias(
            carbono_kg=float(impacto_obj.carbono_evitar_kg or 0),
            energia_kwh=float(impacto_obj.energia_ahorrada_kwh or 0),
            agua_litros=5000  # Estimado
        )
    
    # Buscar transacción actual
    transaccion_actual = Transaccion.objects.filter(
        id_prenda=prenda,
        estado__in=['PENDIENTE', 'RESERVADA', 'EN_PROCESO']
    ).order_by('-fecha_transaccion').first()

    context = {
        'usuario': usuario,
        'prenda': prenda,
        'impacto': impacto_obj,
        'equivalencias': equivalencias,
        'transaccion_actual': transaccion_actual,
    }
    return render(request, 'detalle_prenda.html', context)


# ------------------------------------------------------------------------------
# ACTUALIZAR: panel_impacto - Dashboard con datos reales
# ------------------------------------------------------------------------------
@login_required_custom
def panel_impacto(request):
    """Panel de impacto ambiental de la comunidad con datos reales."""
    usuario = get_usuario_actual(request)
    
    # Obtener impacto total de la plataforma
    impacto_plataforma = obtener_impacto_total_plataforma()
    
    # Estadísticas de transacciones
    total_transacciones = Transaccion.objects.filter(estado='COMPLETADA').count()
    total_donaciones = Transaccion.objects.filter(
        id_tipo__nombre_tipo='Donación',
        estado='COMPLETADA'
    ).count()
    total_intercambios = Transaccion.objects.filter(
        id_tipo__nombre_tipo='Intercambio',
        estado='COMPLETADA'
    ).count()
    total_ventas = Transaccion.objects.filter(
        id_tipo__nombre_tipo='Venta',
        estado='COMPLETADA'
    ).count()

    # Top usuarios con más impacto
    from django.db.models import Sum, Count
    usuarios_activos = Usuario.objects.annotate(
        total_carbono=Sum('prenda__impactoambiental__carbono_evitar_kg'),
        num_transacciones=Count('transaccion_id_usuario_origen_set')
    ).filter(
        total_carbono__isnull=False
    ).order_by('-total_carbono')[:5]

    # Top fundaciones
    fundaciones_top = Fundacion.objects.annotate(
        num_donaciones=Count('transaccion', filter=Q(transaccion__estado='COMPLETADA'))
    ).filter(
        num_donaciones__gt=0
    ).order_by('-num_donaciones')[:5]

    context = {
        'usuario': usuario,
        'impacto_total': impacto_plataforma,
        'total_transacciones': total_transacciones,
        'total_donaciones': total_donaciones,
        'total_intercambios': total_intercambios,
        'total_ventas': total_ventas,
        'usuarios_activos': usuarios_activos,
        'fundaciones_top': fundaciones_top,
        'equivalencias': impacto_plataforma.get('equivalencias', {}),
    }
    
    return render(request, 'panel_impacto.html', context)


# ------------------------------------------------------------------------------
# ACTUALIZAR: mi_impacto - Impacto personal del usuario
# ------------------------------------------------------------------------------
@login_required_custom
def mi_impacto(request):
    """Impacto ambiental personal del usuario con equivalencias."""
    usuario = get_usuario_actual(request)
    
    if not usuario:
        messages.error(request, 'Debes iniciar sesión.')
        return redirect('login')
    
    # Obtener impacto total del usuario
    impacto_usuario = obtener_impacto_total_usuario(usuario)
    
    # Mis transacciones completadas
    mis_transacciones = Transaccion.objects.filter(
        Q(id_usuario_origen=usuario) | Q(id_usuario_destino=usuario),
        estado='COMPLETADA'
    ).select_related('id_prenda', 'id_tipo', 'id_usuario_origen', 'id_usuario_destino', 'id_fundacion')

    # Desglose por tipo
    donaciones = mis_transacciones.filter(id_tipo__nombre_tipo='Donación').count()
    intercambios = mis_transacciones.filter(id_tipo__nombre_tipo='Intercambio').count()
    ventas = mis_transacciones.filter(id_tipo__nombre_tipo='Venta').count()
    
    # Ranking del usuario
    from django.db.models import Sum
    ranking = Usuario.objects.annotate(
        total_carbono=Sum('prenda__impactoambiental__carbono_evitar_kg')
    ).filter(
        total_carbono__gte=impacto_usuario['total_carbono_kg']
    ).count()

    context = {
        'usuario': usuario,
        'mi_impacto': impacto_usuario,
        'total_transacciones': mis_transacciones.count(),
        'donaciones': donaciones,
        'intercambios': intercambios,
        'ventas': ventas,
        'transacciones_recientes': mis_transacciones.order_by('-fecha_transaccion')[:10],
        'equivalencias': impacto_usuario.get('equivalencias', {}),
        'ranking': ranking,
    }
    
    return render(request, 'mi_impacto.html', context)


# ------------------------------------------------------------------------------
# NUEVA: informe_impacto - Genera informe descargable
# ------------------------------------------------------------------------------
@login_required_custom
def informe_impacto(request):
    """Genera un informe detallado de impacto ambiental."""
    usuario = get_usuario_actual(request)
    
    # Determinar tipo de informe
    tipo = request.GET.get('tipo', 'personal')
    
    if tipo == 'personal':
        informe = generar_informe_impacto(usuario=usuario)
    elif tipo == 'fundacion' and usuario.es_representante_fundacion():
        informe = generar_informe_impacto(fundacion=usuario.fundacion_asignada)
    else:
        informe = generar_informe_impacto()  # Informe global
    
    context = {
        'usuario': usuario,
        'informe': informe,
        'tipo': tipo,
    }
    
    return render(request, 'informe_impacto.html', context)


# ------------------------------------------------------------------------------
# NUEVA: comparador_impacto - Compara impacto de diferentes acciones
# ------------------------------------------------------------------------------
@login_required_custom
def comparador_impacto(request):
    """Herramienta para comparar el impacto de diferentes prendas."""
    usuario = get_usuario_actual(request)
    
    # Calcular impacto de cada categoría
    categorias_impacto = []
    categorias = ['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Zapatos', 'Accesorios']
    
    for categoria in categorias:
        impacto = calcular_impacto_prenda(categoria, usar_api=False)
        categorias_impacto.append({
            'categoria': categoria,
            'carbono': impacto['carbono_evitado_kg'],
            'energia': impacto['energia_ahorrada_kwh'],
            'agua': impacto['agua_ahorrada_litros'],
        })
    
    context = {
        'usuario': usuario,
        'categorias_impacto': categorias_impacto,
    }
    
    return render(request, 'comparador_impacto.html', context)


# ------------------------------------------------------------------------------
# NUEVA: api_calcular_impacto - API endpoint para calcular impacto
# ------------------------------------------------------------------------------
@login_required_custom
def api_calcular_impacto(request):
    """
    API endpoint para calcular impacto en tiempo real.
    Útil para AJAX desde el formulario de crear prenda.
    """
    if request.method == 'GET':
        categoria = request.GET.get('categoria')
        peso = request.GET.get('peso')
        
        if not categoria:
            return JsonResponse({'error': 'Categoría requerida'}, status=400)
        
        peso_kg = float(peso) if peso else None
        
        impacto = calcular_impacto_prenda(
            categoria=categoria,
            peso_kg=peso_kg,
            usar_api=False  # Para respuesta rápida
        )
        
        return JsonResponse({
            'success': True,
            'impacto': impacto
        })
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)