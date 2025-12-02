from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import JsonResponse
import hashlib
import json
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
    
    if not password_hash:
        return False
    # Si el hash está en formato Django (contiene '$'), usar la verificación estándar
    if '$' in password_hash:
        return django_check(password, password_hash)
    # Fallback: legacy SHA256 hex
    if hashlib.sha256(password.encode()).hexdigest() == password_hash:
        if usuario is not None:
            usuario.contrasena = make_password(password)
            usuario.save()
        return True
    return False

def get_usuario_actual(request):
    """Obtiene el usuario actual de la sesión"""
    usuario_id = request.session.get('usuario_id')
    if usuario_id:
        return Usuario.objects.filter(id_usuario=usuario_id).first()
    return None


def puede_actualizar_transaccion(usuario, transaccion, permiso_requerido):
    """Helper para validar si usuario tiene permiso de actualizar transacción.
    
    permiso_requerido puede ser: 'origen', 'destino', 'origen_o_destino', 'representante'
    Retorna tupla: (True/False, mensaje_error o None)
    """
    if permiso_requerido == 'origen':
        if transaccion.id_usuario_origen.id_usuario != usuario.id_usuario:
            return False, 'Solo el propietario/vendedor puede realizar esta acción.'
    elif permiso_requerido == 'destino':
        if not transaccion.id_usuario_destino or transaccion.id_usuario_destino.id_usuario != usuario.id_usuario:
            return False, 'Solo el receptor/comprador puede realizar esta acción.'
    elif permiso_requerido == 'origen_o_destino':
        es_origen = transaccion.id_usuario_origen.id_usuario == usuario.id_usuario
        es_destino = transaccion.id_usuario_destino and transaccion.id_usuario_destino.id_usuario == usuario.id_usuario
        if not (es_origen or es_destino):
            return False, 'No tienes permiso para actualizar esta transacción.'
    elif permiso_requerido == 'representante':
        if not (usuario.es_representante_fundacion() and usuario.fundacion_asignada == transaccion.id_fundacion):
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
    prendas_recientes = Prenda.objects.select_related('id_usuario').order_by('-fecha_publicacion')[:6]
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
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        correo = request.POST.get('correo')
        contrasena = request.POST.get('contrasena')
        telefono = request.POST.get('telefono')
        comuna = request.POST.get('comuna')
        rol = request.POST.get('rol', 'CLIENTE')
        # Validaciones
        if Usuario.objects.filter(correo=correo).exists():
            messages.error(request, 'El correo ya está registrado.')
            return render(request, 'registro.html')
        roles_validos = ['CLIENTE', 'REPRESENTANTE_FUNDACION', 'MODERADOR', 'ADMINISTRADOR']
        if rol not in roles_validos:
            rol = 'CLIENTE'
        usuario = Usuario(
            nombre=nombre,
            apellido=apellido,
            correo=correo,
            telefono=telefono,
            comuna=comuna,
            rol=rol,
            fecha_registro=timezone.now()
        )
        usuario.set_password(contrasena)
        usuario.save()
        messages.success(request, f'¡Registro exitoso como {usuario.get_rol_display()}! Ya puedes iniciar sesión.')
        return redirect('login')
    return render(request, 'registro.html')

@anonymous_required
def login_usuario(request):
    if request.method == 'POST':
        correo = request.POST.get('correo')
        contrasena = request.POST.get('contrasena')
        if not correo or not contrasena:
            messages.error(request, 'Correo y contraseña son obligatorios.')
            return render(request, 'login.html')
        usuario = Usuario.objects.filter(correo=correo).first()
        if usuario and verificar_password(contrasena, usuario.contrasena, usuario):
            request.session['usuario_id'] = usuario.id_usuario
            messages.success(request, f'¡Bienvenido, {usuario.nombre}!')
            return redirect('home')
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
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        telefono = request.POST.get('telefono')
        comuna = request.POST.get('comuna')
        if not all([nombre, apellido, telefono, comuna]):
            messages.error(request, 'Todos los campos son obligatorios.')
            return render(request, 'perfil.html', {'usuario': usuario})
        if 'imagen_usuario' in request.FILES:
            usuario.imagen_usuario = request.FILES['imagen_usuario']
        usuario.nombre = nombre
        usuario.apellido = apellido
        usuario.telefono = telefono
        usuario.comuna = comuna
        usuario.save()
        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('perfil')
    total_prendas = Prenda.objects.filter(id_usuario=usuario).count()
    transacciones_realizadas = Transaccion.objects.filter(
        Q(id_usuario_origen=usuario) | Q(id_usuario_destino=usuario)
    ).count()
    impactos = ImpactoAmbiental.objects.filter(id_prenda__id_usuario=usuario)
    impacto_personal = impactos.aggregate(
        total_carbono=Sum('carbono_evitar_kg'),
        total_energia=Sum('energia_ahorrada_kwh')
    )
    context = {
        'usuario': usuario,
        'total_prendas': total_prendas,
        'transacciones_realizadas': transacciones_realizadas,
        'impacto_personal': impacto_personal,
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
    prenda_destino = get_object_or_404(Prenda, id_prenda=id_prenda)

    if prenda_destino.id_usuario.id_usuario == usuario.id_usuario:
        messages.error(request, 'No puedes intercambiar con tu propia prenda.')
        return redirect('detalle_prenda', id_prenda=id_prenda)
    if not prenda_destino.esta_disponible():
        messages.error(request, f'Esta prenda ya no está disponible para intercambio ({prenda_destino.get_disponibilidad_display()}).')
        return redirect('detalle_prenda', id_prenda=id_prenda)

    if request.method == 'POST':
        prenda_origen_id = request.POST.get('prenda_origen')
        prenda_origen = get_object_or_404(Prenda, id_prenda=prenda_origen_id, id_usuario=usuario)
        if not prenda_origen.esta_disponible():
            messages.error(request, 'La prenda ofrecida ya no está disponible.')
            return redirect('detalle_prenda', id_prenda=id_prenda)
        tipo_intercambio, _ = TipoTransaccion.objects.get_or_create(nombre_tipo='Intercambio', defaults={
            'descripcion': 'Intercambio de prendas entre usuarios'
        })
        transaccion = Transaccion.objects.create(
            id_prenda=prenda_destino,
            id_tipo=tipo_intercambio,
            id_usuario_origen=usuario,
            id_usuario_destino=prenda_destino.id_usuario,
            fecha_transaccion=timezone.now(),
            estado='PENDIENTE'
        )
        # No marcar como NO_DISPONIBLE aquí; la prenda destino permanece DISPONIBLE para que otros contacten.
        # Solo se reservará cuando el destino acepte la propuesta.
        messages.success(request, f'¡Intercambio propuesto! Código de seguimiento: {transaccion.id_transaccion}. Ahora puedes negociar con el otro usuario.')
        # Redirigir a conversación con el otro usuario para negociar
        return redirect('conversacion', id_usuario=prenda_destino.id_usuario.id_usuario)

    mis_prendas_usuario = Prenda.objects.filter(id_usuario=usuario, disponibilidad='DISPONIBLE')
    context = {
        'usuario': usuario,
        'prenda_destino': prenda_destino,
        'mis_prendas': mis_prendas_usuario,
    }
    return render(request, 'proponer_intercambio.html', context)

@login_required_custom
def marcar_intercambio_entregado(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado != 'RESERVADA':
        return JsonResponse({'error': 'La transacción no está en estado reservado.'}, status=400)
    
    transaccion.marcar_en_proceso()
    messages.success(request, 'Has marcado la prenda como entregada.')
    return redirect('mis_transacciones')

@login_required_custom
def confirmar_recepcion_intercambio(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'destino')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado != 'EN_PROCESO':
        return JsonResponse({'error': 'Debes esperar a que el propietario marque como entregada.'}, status=400)
    
    transaccion.marcar_como_completada()
    messages.success(request, '¡Intercambio completado con éxito!')
    return redirect('mis_transacciones')

@login_required_custom
def cancelar_intercambio(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado not in ['PENDIENTE', 'RESERVADA', 'EN_PROCESO']:
        return JsonResponse({'error': 'No puedes cancelar una transacción finalizada.'}, status=400)
    
    transaccion.cancelar()
    messages.success(request, 'Intercambio cancelado y prenda devuelta a disponible.')
    return redirect('mis_transacciones')


@login_required_custom
def comprar_prenda(request, id_prenda):
    """Proponer compra de una prenda.
    
    FLUJO DE NEGOCIACIÓN:
    1. Usuario hace clic en "Proponer Compra"
    2. Se crea una transacción con estado PENDIENTE
    3. LA PRENDA PERMANECE COMO DISPONIBLE (no se reserva automáticamente)
    4. El comprador y vendedor pueden contactarse para negociar
    5. El vendedor ve la propuesta en 'mis_transacciones' y puede:
       - ACEPTAR: La prenda cambia a RESERVADA y comienza el envío
       - RECHAZAR: La prenda permanece DISPONIBLE para otras propuestas
    6. Una vez ACEPTADA, se sigue el flujo normal: marcar entregada → confirmar recepción
    """
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda, id_prenda=id_prenda)
    
    # Validaciones
    if prenda.id_usuario.id_usuario == usuario.id_usuario:
        messages.error(request, "No puedes comprar tu propia prenda.")
        return redirect('detalle_prenda', id_prenda=id_prenda)
    if not prenda.esta_disponible():
        messages.error(request, "Esta prenda ya no está disponible.")
        return redirect('detalle_prenda', id_prenda=id_prenda)

    if request.method == 'POST':
        tipo_venta, _ = TipoTransaccion.objects.get_or_create(
            nombre_tipo='Venta', defaults={'descripcion': 'Venta de prenda entre usuarios'}
        )
        transaccion = Transaccion.objects.create(
            id_prenda=prenda,
            id_tipo=tipo_venta,
            id_usuario_origen=prenda.id_usuario,
            id_usuario_destino=usuario,
            fecha_transaccion=timezone.now(),
            estado='PENDIENTE'
        )
        # No marcar como RESERVADA aquí; se hará cuando se acepte la propuesta.
        # Esto permite que otros usuarios contacten mientras se negocia.
        messages.success(request, f'Solicitud de compra enviada. Código: {transaccion.id_transaccion}. Ahora puedes negociar con el vendedor.')
        # Redirigir a conversación con el vendedor para negociar
        return redirect('conversacion', id_usuario=prenda.id_usuario.id_usuario)
    
    context = {"usuario": usuario, "prenda": prenda}
    return render(request, 'comprar_prenda.html', context)

@login_required_custom
def marcar_compra_entregado(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado != 'RESERVADA':
        return JsonResponse({'error': 'La transacción no está en estado reservado.'}, status=400)
    
    transaccion.marcar_en_proceso()
    messages.success(request, 'Has marcado la prenda como entregada.')
    return redirect('mis_transacciones')


@login_required_custom
def marcar_donacion_enviada(request, id_transaccion):
    """Permite al donante marcar su donación como enviada (pone la transacción en EN_PROCESO)."""
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)

    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)

    # Solo aplicable para donaciones
    if not transaccion.es_donacion():
        return JsonResponse({'error': 'Esta acción solo aplica a donaciones.'}, status=400)

    if transaccion.estado not in ['PENDIENTE', 'RESERVADA']:
        return JsonResponse({'error': 'La transacción no está en un estado válido para marcar como enviada.'}, status=400)

    transaccion.marcar_en_proceso()
    messages.success(request, 'Has marcado la donación como enviada. La fundación confirmará la recepción.')
    return redirect('mis_transacciones')

@login_required_custom
def confirmar_recepcion_compra(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'destino')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado != 'EN_PROCESO':
        return JsonResponse({'error': 'Solo puedes confirmar si ya fue marcada como entregada.'}, status=400)
    
    transaccion.marcar_como_completada()
    messages.success(request, '¡Transacción completada con éxito!')
    return redirect('mis_transacciones')

@login_required_custom
def cancelar_compra(request, id_transaccion):
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)
    
    permitido, error = puede_actualizar_transaccion(usuario, transaccion, 'origen')
    if not permitido:
        return JsonResponse({'error': error}, status=403)
    if transaccion.estado not in ['PENDIENTE', 'RESERVADA', 'EN_PROCESO']:
        return JsonResponse({'error': 'No puedes cancelar una transacción finalizada.'}, status=400)
    
    transaccion.cancelar()
    messages.success(request, 'Transacción cancelada y prenda devuelta a disponible.')
    return redirect('mis_transacciones')

@login_required_custom
def donar_prenda(request, id_prenda):
    """Permite a un usuario donar una prenda propia a una fundación activa."""
    usuario = get_usuario_actual(request)
    prenda = get_object_or_404(Prenda, id_prenda=id_prenda)
    if prenda.id_usuario.id_usuario != usuario.id_usuario:
        messages.error(request, 'Solo puedes donar tus propias prendas.')
        return redirect('detalle_prenda', id_prenda=id_prenda)
    if not prenda.esta_disponible():
        messages.error(request, 'Esta prenda ya no está disponible.')
        return redirect('detalle_prenda', id_prenda=id_prenda)
    if request.method == 'POST':
        fundacion_id = request.POST.get('fundacion')
        if not fundacion_id:
            messages.error(request, 'Debes seleccionar una fundación válida.')
            return redirect('donar_prenda', id_prenda=id_prenda)
        fundacion = get_object_or_404(Fundacion, id_fundacion=fundacion_id, activa=True)
        tipo_donacion, _ = TipoTransaccion.objects.get_or_create(nombre_tipo='Donación', defaults={
            'descripcion': 'Donación de prenda a fundación'
        })
        transaccion = Transaccion.objects.create(
            id_prenda=prenda,
            id_tipo=tipo_donacion,
            id_usuario_origen=usuario,
            id_fundacion=fundacion,
            fecha_transaccion=timezone.now(),
            estado='PENDIENTE'
        )
        # Para donaciones, marcar como RESERVADA inmediatamente (ya que es una oferta unilateral).
        # Esto evita que la prenda sea donada a múltiples fundaciones.
        prenda.marcar_como_reservada()
        # Verificar logros
        nuevos_logros = verificar_logros(usuario)
        if nuevos_logros:
            for logro in nuevos_logros:
                messages.success(request, f'🏆 ¡Nuevo logro desbloqueado: {logro.nombre}!')
        messages.success(request, f'¡Prenda donada exitosamente a {fundacion.nombre}! Código de seguimiento: {transaccion.id_transaccion}')
        return redirect('mis_transacciones')
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
    
    # ENVIADAS: El usuario es el propietario original (origen)
    # Incluye: Ventas, Intercambios, Donaciones
    transacciones_enviadas = Transaccion.objects.filter(
        id_usuario_origen=usuario
    )
    
    # RECIBIDAS: El usuario es el comprador/interesado (destino)
    # Excluye donaciones (donde id_fundacion no es NULL)
    # Solo incluye Compras e Intercambios
    transacciones_recibidas = Transaccion.objects.filter(
        id_usuario_destino=usuario
    ).exclude(
        id_fundacion__isnull=False  # Excluye donaciones
    )
    
    context = {
        "usuario": usuario,
        "transacciones_enviadas": transacciones_enviadas,
        "transacciones_recibidas": transacciones_recibidas,
    }
    return render(request, 'mis_transacciones.html', context)


@login_required_custom
def actualizar_estado_transaccion(request, id_transaccion):
    """Permite actualizar el estado de una transacción por un usuario involucrado.
    
    Flujo:
    - Cuando estado = PENDIENTE y se acepta (ACEPTADA): marca prenda como RESERVADA.
    - Cuando estado = PENDIENTE y se rechaza (RECHAZADA): prenda vuelve a DISPONIBLE.
    """
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)
    # Permisos: solo destino u origen puede actualizar (en este caso, destino acepta/rechaza)
    if transaccion.id_usuario_destino and transaccion.id_usuario_destino.id_usuario != usuario.id_usuario:
        if transaccion.id_usuario_origen.id_usuario != usuario.id_usuario:
            return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if not nuevo_estado or nuevo_estado not in dict(Transaccion.ESTADO_CHOICES):
            return JsonResponse({'error': 'Estado inválido'}, status=400)
        
        # Solo permitir cambios desde PENDIENTE a ACEPTADA o RECHAZADA por el destino
        if transaccion.estado == 'PENDIENTE':
            if nuevo_estado == 'ACEPTADA':
                # Marcar prenda como RESERVADA al aceptar
                transaccion.id_prenda.marcar_como_reservada()
                transaccion.estado = nuevo_estado
                transaccion.save()
                messages.success(request, 'Has aceptado la propuesta. La prenda ahora está reservada.')
            elif nuevo_estado == 'RECHAZADA':
                transaccion.estado = nuevo_estado
                transaccion.save()
                messages.success(request, 'Has rechazado la propuesta. La prenda sigue disponible.')
            else:
                return JsonResponse({'error': 'Desde PENDIENTE solo puedes aceptar (ACEPTADA) o rechazar (RECHAZADA).'}, status=400)
        else:
            # Para otros estados, aplicar cambios normales
            transaccion.estado = nuevo_estado
            transaccion.save()
            messages.success(request, f'Estado de la transacción actualizado a: {transaccion.get_estado_display()}')
        
        return redirect('mis_transacciones')
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required_custom
def reportar_disputa(request, id_transaccion):
    """Permite al comprador/receptor reportar un problema con la prenda cuando está EN_PROCESO_ENTREGA.
    
    Cambios:
    - Transacción pasa a estado EN_DISPUTA
    - Se registra quién reportó y la razón
    - Notificación automática al equipo de administración
    - Sistema de moderación manual para resolver
    """
    usuario = get_usuario_actual(request)
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)
    
    # Solo el receptor puede reportar
    if not transaccion.id_usuario_destino or transaccion.id_usuario_destino.id_usuario != usuario.id_usuario:
        messages.error(request, 'Solo el receptor puede reportar problemas.')
        return redirect('mis_transacciones')
    
    # Solo se puede reportar en estado EN_PROCESO_ENTREGA
    if transaccion.estado != 'EN_PROCESO':
        messages.error(request, 'Solo puedes reportar problemas cuando la prenda está en proceso de entrega.')
        return redirect('mis_transacciones')
    
    if request.method == 'POST':
        razon = request.POST.get('razon_disputa')
        if not razon or len(razon.strip()) < 10:
            messages.error(request, 'Debes proporcionar una descripción detallada del problema (mínimo 10 caracteres).')
            return redirect('mis_transacciones')
        
        # Marcar transacción como EN_DISPUTA
        transaccion.estado = 'EN_DISPUTA'
        transaccion.en_disputa = True
        transaccion.razon_disputa = razon.strip()
        transaccion.reportado_por = usuario
        transaccion.fecha_disputa = timezone.now()
        transaccion.save()
        
        messages.success(request, 'Tu reporte ha sido registrado. El equipo de administración revisará la disputa.')
        return redirect('mis_transacciones')
    
    context = {
        'usuario': usuario,
        'transaccion': transaccion,
    }
    return render(request, 'reportar_disputa.html', context)

@admin_required
def resolver_disputa(request, id_transaccion):
    """Solo administrador: Resuelve una disputa marcándola como COMPLETADA o CANCELADA.
    
    Permite al admin revisar todos los detalles de la disputa y tomar una decisión
    basada en la revisión del chat y pruebas proporcionadas.
    """
    transaccion = get_object_or_404(Transaccion, id_transaccion=id_transaccion)
    
    if transaccion.estado != 'EN_DISPUTA':
        messages.error(request, 'Esta transacción no está en disputa.')
        return redirect('admin:index')
    
    if request.method == 'POST':
        resolucion = request.POST.get('resolucion')
        notas_admin = request.POST.get('notas_admin')
        
        if resolucion not in ['COMPLETADA', 'CANCELADA']:
            return JsonResponse({'error': 'Resolución inválida'}, status=400)
        
        transaccion.estado = resolucion
        transaccion.save()
        
        # TODO: Notificar a ambos usuarios sobre la resolución
        # TODO: Si CANCELADA, posible penalización al vendedor
        
        messages.success(request, f'Disputa resuelta como {transaccion.get_estado_display()}')
        return redirect('admin:index')
    
    # Obtener mensajes entre los usuarios
    mensajes = Mensaje.objects.filter(
        Q(id_emisor=transaccion.id_usuario_origen, id_receptor=transaccion.id_usuario_destino) |
        Q(id_emisor=transaccion.id_usuario_destino, id_receptor=transaccion.id_usuario_origen)
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
    enviados = Mensaje.objects.filter(id_emisor=usuario).values_list('id_receptor', flat=True)
    recibidos = Mensaje.objects.filter(id_receptor=usuario).values_list('id_emisor', flat=True)
    ids_conversaciones = set(list(enviados) + list(recibidos))
    conversaciones = Usuario.objects.filter(id_usuario__in=ids_conversaciones)
    context = {
        'usuario': usuario,
        'conversaciones': conversaciones,
    }
    return render(request, 'lista_mensajes.html', context)

@login_required_custom
def conversacion(request, id_usuario):
    """Muestra la conversación entre el usuario y otro usuario específico."""
    usuario = get_usuario_actual(request)
    otro_usuario = get_object_or_404(Usuario, id_usuario=id_usuario)
    # Mensajes entre ambos (enviado/recibido)
    mensajes_conversacion = Mensaje.objects.filter(
        Q(id_emisor=usuario, id_receptor=otro_usuario) |
        Q(id_emisor=otro_usuario, id_receptor=usuario)
    ).order_by('fecha_envio')
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
        receptor = get_object_or_404(Usuario, id_usuario=receptor_id)
        Mensaje.objects.create(
            id_emisor=usuario,
            id_receptor=receptor,
            contenido=contenido.strip(),
            fecha_envio=timezone.now()
        )
        messages.success(request, f'Mensaje enviado a {receptor.nombre}')
        # Si usas AJAX:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('conversacion', id_usuario=receptor.id_usuario)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

# ------------------------------------------------------------------------------------------------------------------
# Fundaciones

def lista_fundaciones(request):
    """Lista todas las fundaciones registradas."""
    usuario = get_usuario_actual(request)
    fundaciones = Fundacion.objects.filter(activa=True)
    context = {
        'usuario': usuario,
        'fundaciones': fundaciones,
    }
    return render(request, 'lista_fundaciones.html', context)

def detalle_fundacion(request, id_fundacion):
    """Muestra información y estadísticas de una fundación."""
    usuario = get_usuario_actual(request)
    fundacion = get_object_or_404(Fundacion, id_fundacion=id_fundacion)
    # Donaciones recibidas por la fundación, ordenadas por más recientes
    donaciones = Transaccion.objects.filter(
        id_fundacion=fundacion,
        id_tipo__nombre_tipo='Donación'
    ).select_related('id_prenda', 'id_usuario_origen').order_by('-fecha_transaccion')

    # Impacto ambiental total de todas las prendas donadas a esta fundación
    prendas_donadas = [don.id_prenda for don in donaciones if don.id_prenda]
    impacto_total = ImpactoAmbiental.objects.filter(
        id_prenda__in=prendas_donadas
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
    total_donaciones = Transaccion.objects.filter(id_tipo__nombre_tipo='Donación').count()
    total_intercambios = Transaccion.objects.filter(id_tipo__nombre_tipo='Intercambio').count()
    total_ventas = Transaccion.objects.filter(id_tipo__nombre_tipo='Venta').count()

    usuarios_activos = Usuario.objects.annotate(
        num_transacciones=Count('transaccion_id_usuario_origen_set')
    ).order_by('-num_transacciones')[:5]

    fundaciones_top = Fundacion.objects.annotate(
        num_donaciones=Count('transaccion')
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
        Q(id_usuario_origen=usuario) | Q(id_usuario_destino=usuario)
    ).select_related('id_prenda', 'id_tipo', 'id_usuario_origen', 'id_usuario_destino', 'id_fundacion')

    prendas_ids = [t.id_prenda.id_prenda for t in mis_transacciones]
    mi_impacto_total = ImpactoAmbiental.objects.filter(
        id_prenda__id_prenda__in=prendas_ids
    ).aggregate(
        total_carbono=Sum('carbono_evitar_kg'),
        total_energia=Sum('energia_ahorrada_kwh')
    )

    donaciones = mis_transacciones.filter(id_tipo__nombre_tipo='Donación').count()
    intercambios = mis_transacciones.filter(id_tipo__nombre_tipo='Intercambio').count()
    ventas = mis_transacciones.filter(id_tipo__nombre_tipo='Venta').count()

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
    usuario_id = request.session.get('usuario_id')
    usuario_nombre = request.session.get('usuario_nombre')
    usuario_correo = request.session.get('usuario_correo')

    if (not usuario_nombre or not usuario_correo) and usuario_id:
        try:
            u = Usuario.objects.only('nombre', 'correo').get(id_usuario=usuario_id)
            usuario_nombre = u.nombre
            usuario_correo = u.correo
            request.session['usuario_nombre'] = usuario_nombre
            request.session['usuario_correo'] = usuario_correo
        except Usuario.DoesNotExist:
            usuario_nombre = None
            usuario_correo = None

    # Información de la sesión
    session_data = {
        'session_key': request.session.session_key,
        'usuario_id': usuario_id,
        'usuario_nombre': usuario_nombre,
        'usuario_correo': usuario_correo,
    }

    # Timestamp de login
    login_timestamp = request.session.get('login_timestamp')
    if login_timestamp:
        login_dt = datetime.fromisoformat(login_timestamp)
        session_data['login_timestamp'] = login_dt.strftime('%d/%m/%Y %H:%M:%S')
        session_data['tiempo_sesion'] = str(timezone.now() - login_dt)

    # Última actividad
    ultima_actividad = request.session.get('ultima_actividad')
    if ultima_actividad:
        ultima_dt = datetime.fromisoformat(ultima_actividad)
        session_data['ultima_actividad'] = ultima_dt.strftime('%d/%m/%Y %H:%M:%S')
        tiempo_inactivo = (timezone.now() - ultima_dt).total_seconds()
        session_data['tiempo_inactivo'] = f"{int(tiempo_inactivo)} segundos"

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
        ultima_dt = datetime.fromisoformat(ultima_actividad)
        tiempo_inactivo = (timezone.now() - ultima_dt).total_seconds()
        tiempo_restante = max(0, 1800 - int(tiempo_inactivo))  # 1800 segundos = 30 minutos

    # Asegurar nombre desde DB si no está en la sesión
    usuario_id = request.session.get('usuario_id')
    usuario_nombre = request.session.get('usuario_nombre')
    if (not usuario_nombre) and usuario_id:
        try:
            u = Usuario.objects.only('nombre').get(id_usuario=usuario_id)
            usuario_nombre = u.nombre
            request.session['usuario_nombre'] = usuario_nombre
        except Usuario.DoesNotExist:
            usuario_nombre = None

    return JsonResponse({
        'autenticado': True,
        'usuario_id': usuario_id,
        'usuario_nombre': usuario_nombre,
        'tiempo_restante': tiempo_restante,
        'session_key': (request.session.session_key or '')[:10] + '...'
    })


@login_required_custom
def renovar_sesion(request):
    """Renueva la sesión y actualiza el timestamp de última actividad"""
    if request.method == 'POST':
        request.session['ultima_actividad'] = timezone.now().isoformat()
        request.session.modified = True
        if not request.session.get('login_timestamp'):
            request.session['login_timestamp'] = timezone.now().isoformat()
        return JsonResponse({
            'success': True,
            'message': 'Sesión renovada',
            'nueva_expiracion': request.session.get_expiry_age()
        })
    return JsonResponse({'error': 'Método no permitido'}, status=405)

# ------------------------------------------------------------------------------------------------------------------
# Gestión de Cookies

def configurar_cookies(request):
    """Página de configuración de cookies"""
    return render(request, 'configurar_cookies.html')

def aceptar_cookies(request):
    """Acepta todas las cookies, con preferencias personalizadas si se envían."""
    if request.method == 'POST':
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
    return redirect('configurar_cookies')

def rechazar_cookies(request):
    """Rechaza cookies no esenciales y guarda la preferencia mínima."""
    if request.method == 'POST':
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
            pass
    return JsonResponse({
        'configurado': False,
        'preferencias': None
    })

def eliminar_cookies(request):
    """Elimina cookies no esenciales y restablece preferencias."""
    if request.method == 'POST':
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
# VISTA DEL MAPA INTERACTIVO - Agregar a views.py
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
    ).values('id_usuario', 'nombre', 'comuna', 'lat', 'lng')
    
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