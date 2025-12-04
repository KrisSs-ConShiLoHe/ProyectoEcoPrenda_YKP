from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
import hashlib

# ------------------- Usuario ----------------------

class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True, null=True)
    correo = models.EmailField(unique=True, max_length=120)  # Cambié a EmailField para validación automática.
    contrasena = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    comuna = models.CharField(max_length=100, blank=True, null=True)
    fecha_registro = models.DateTimeField(default=timezone.now, blank=True, null=True)

    ROL_CHOICES = [
        ('CLIENTE', 'Cliente'),
        ('REPRESENTANTE_FUNDACION', 'Representante de Fundación'),
        ('MODERADOR', 'Moderador'),
        ('ADMINISTRADOR', 'Administrador'),
    ]

    rol = models.CharField(
        max_length=30, 
        choices=ROL_CHOICES, 
        default='CLIENTE',
        help_text='Rol del usuario en el sistema'
    )
    fundacion_asignada = models.ForeignKey(
        'Fundacion',
        on_delete=models.SET_NULL,  # Cambié de DO_NOTHING a SET_NULL para evitar huérfanos.
        null=True,
        blank=True,
        related_name='representantes',
        help_text='Fundación a la que representa (solo para representantes)'
    )
    imagen_usuario = models.ImageField(
        upload_to='usuarios/', blank=True, null=True, max_length=200,
        help_text='Imagen de perfil del usuario'
    )
    es_staff = models.BooleanField(default=False, help_text='Puede acceder al panel de administración')

    # NUEVOS CAMPOS PARA MAPA
    direccion = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text='Dirección completa del usuario'
    )

    lat = models.FloatField(
        blank=True, 
        null=True,
        help_text='Latitud para ubicación en mapa'
    )

    lng = models.FloatField(
        blank=True, 
        null=True,
        help_text='Longitud para ubicación en mapa'
    )

    mostrar_en_mapa = models.BooleanField(
        default=False,
        help_text='¿Permitir que mi ubicación sea visible en el mapa público?'
    )

    class Meta:
        db_table = 'usuario'
        indexes = [
            models.Index(fields=['rol']),  # Índice para consultas por rol.
            models.Index(fields=['correo']),  # Para búsquedas por email.
        ]

    def __str__(self):
        return f"{self.nombre} ({dict(self.ROL_CHOICES).get(self.rol, self.rol)})"

    # Métodos para roles y permisos personalizados:
    def es_cliente(self): return self.rol == 'CLIENTE'
    def es_representante_fundacion(self): return self.rol == 'REPRESENTANTE_FUNDACION'
    def es_moderador(self): return self.rol == 'MODERADOR'
    def es_administrador(self): return self.rol == 'ADMINISTRADOR'
    def puede_gestionar_donaciones(self): 
        return self.es_representante_fundacion() and self.fundacion_asignada is not None
    def obtener_fundacion(self):
        return self.fundacion_asignada if self.es_representante_fundacion() else None
    
    def set_password(self, raw_password):
        """Hashea y asigna la contraseña de forma segura."""
        self.contrasena = make_password(raw_password)

    def check_password(self, raw_password):
        """Verifica la contraseña contra el hash almacenado.
        Soporta hashes Django (con $) y legacy SHA256 hex.
        """
        if not self.contrasena:
            return False
        if '$' in self.contrasena:
            return check_password(raw_password, self.contrasena)
        return hashlib.sha256(raw_password.encode()).hexdigest() == self.contrasena
    
    def save(self, *args, **kwargs):
        # Validación: Si mostrar_en_mapa=True, lat y lng son obligatorios.
        if self.mostrar_en_mapa and (not self.lat or not self.lng):
            raise ValueError("Latitud y longitud son obligatorias si 'mostrar_en_mapa' está activado.")
        # Hashea contraseña si no está hasheada.
        if self.contrasena and '$' not in self.contrasena:
            self.contrasena = make_password(self.contrasena)
        super().save(*args, **kwargs)

# ------------------- Fundacion ----------------------

class Fundacion(models.Model):
    id_fundacion = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    correo_contacto = models.EmailField(max_length=120, blank=True, null=True)  # Cambié a EmailField.
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    imagen_fundacion = models.ImageField(upload_to='fundaciones/', blank=True, null=True, max_length=200, help_text='Imagen o logo de la fundación')
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    representante = models.OneToOneField(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='fundacion_representada')  # Cambié a SET_NULL.

    # NUEVOS CAMPOS PARA MAPA
    lat = models.FloatField(
        blank=True, 
        null=True,
        help_text='Latitud de la fundación (OBLIGATORIO para aparecer en mapa)'
    )

    lng = models.FloatField(
        blank=True, 
        null=True,
        help_text='Longitud de la fundación (OBLIGATORIO para aparecer en mapa)'
    )

    class Meta:
        db_table = 'fundacion'
        indexes = [
            models.Index(fields=['activa']),  # Para filtrar fundaciones activas.
        ]

    def __str__(self): return self.nombre

    def obtener_representantes(self): return self.representantes.all()
    def total_donaciones_recibidas(self):
        return Transaccion.objects.filter(id_fundacion=self, id_tipo__nombre_tipo='Donación').count()
    
    def save(self, *args, **kwargs):
        # Validación: Si activa=True, lat y lng son obligatorios.
        if self.activa and (not self.lat or not self.lng):
            raise ValueError("Latitud y longitud son obligatorias para fundaciones activas.")
        super().save(*args, **kwargs)

# ------------------- Tipo Transaccion ----------------------

class TipoTransaccion(models.Model):
    nombre_tipo = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'tipo_transaccion'

    def __str__(self): return self.nombre_tipo

# ------------------- Prenda ----------------------

class Prenda(models.Model):
    user = models.ForeignKey(Usuario, on_delete=models.CASCADE)  # Cambié a CASCADE y renombré a 'user'.
    nombre = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=300, blank=True, null=True)
    categoria = models.CharField(max_length=100, blank=True, null=True)
    talla = models.CharField(max_length=10, blank=True, null=True)
    fecha_publicacion = models.DateTimeField(default=timezone.now, blank=True, null=True)

    # Estados unificados: Eliminé 'disponibilidad' y usé solo 'estado' para simplicidad.
    ESTADO_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('RESERVADA', 'Reservada'),
        ('EN_PROCESO_ENTREGA', 'En Proceso de Entrega'),
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
        ('AGOTADA', 'Agotada'),
    ]
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='DISPONIBLE')
    
    cantidad = models.PositiveIntegerField(default=1, help_text="Cantidad disponible en stock")
    
    imagen_prenda = models.ImageField(upload_to='prendas/', blank=True, null=True, max_length=200)

    class Meta:
        db_table = 'prenda'
        indexes = [
            models.Index(fields=['estado']),  # Para consultas por estado.
            models.Index(fields=['categoria']),  # Para filtros por categoría.
        ]

    def marcar_como_reservada(self):
        self.estado = 'RESERVADA'
        self.save()
    def marcar_como_en_proceso(self):
        self.estado = 'EN_PROCESO_ENTREGA'
        self.save()
    def marcar_como_completada(self):
        self.estado = 'COMPLETADA'
        self.save()
    def marcar_como_cancelada(self):
        self.estado = 'CANCELADA'
        self.save()

    def __str__(self): return self.nombre
    def esta_disponible(self): return self.estado == 'DISPONIBLE'  # Simplificado.

# ------------------- Transaccion ----------------------

class Transaccion(models.Model):
    prenda = models.ForeignKey(Prenda, on_delete=models.CASCADE)  # Cambié a CASCADE y renombré.
    tipo = models.ForeignKey(TipoTransaccion, on_delete=models.CASCADE)  # Cambié a CASCADE y renombré.
    user_origen = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='transacciones_origen')  # Cambié a CASCADE y renombré.
    user_destino = models.ForeignKey(Usuario, on_delete=models.CASCADE, blank=True, null=True, related_name='transacciones_destino')  # Cambié a CASCADE.
    fundacion = models.ForeignKey(Fundacion, on_delete=models.SET_NULL, blank=True, null=True)  # Cambié a SET_NULL.
    campana = models.ForeignKey('CampanaFundacion', on_delete=models.SET_NULL, blank=True, null=True)  # Cambié a SET_NULL.
    fecha_transaccion = models.DateTimeField(default=timezone.now, blank=True, null=True)
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ACEPTADA', 'Aceptada'),
        ('RESERVADA', 'Reservada'),
        ('EN_PROCESO', 'En Proceso de Entrega'),
        ('COMPLETADA', 'Completada'),
        ('RECHAZADA', 'Rechazada'),
        ('EN_DISPUTA', 'En Disputa'),
        ('CANCELADA', 'Cancelada'),
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    destino_final = models.CharField(max_length=300, blank=True, null=True, help_text='Destino final de la donación')
    fecha_entrega = models.DateTimeField(blank=True, null=True)

    # Nuevos campos para disputas
    en_disputa = models.BooleanField(default=False)
    razon_disputa = models.TextField(null=True, blank=True)
    reportado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='disputas_reportadas')
    fecha_disputa = models.DateTimeField(null=True, blank=True)

    # NUEVOS CAMPOS PARA LOGÍSTICA Y ENVÍOS
    direccion_retiro = models.CharField(
        max_length=300, 
        blank=True, 
        null=True,
        help_text='Dirección de retiro/origen para envío'
    )
    direccion_entrega = models.CharField(
        max_length=300, 
        blank=True, 
        null=True,
        help_text='Dirección de entrega/destino para envío'
    )
    peso_kg = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text='Peso estimado de la prenda en kilogramos'
    )
    dimensiones = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text='Dimensiones del paquete (largo x ancho x alto en cm)'
    )
    codigo_seguimiento_envio = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text='Código de seguimiento del envío (Shipit u otro)'
    )
    costo_envio = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text='Costo del envío calculado'
    )
    courier = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text='Nombre del courier (ej: Chilexpress, Correos, etc.)'
    )

    class Meta:
        db_table = 'transaccion'
        indexes = [
            models.Index(fields=['estado']),  # Para consultas por estado.
            models.Index(fields=['fecha_transaccion']),  # Para ordenar por fecha.
        ]

    def __str__(self):
        return f"{self.tipo.nombre_tipo} - {self.prenda.nombre}"
    def es_donacion(self): return self.tipo.nombre_tipo == 'Donación'
    
    def actualizar_disponibilidad_prenda(self):
        if self.estado == 'COMPLETADA':
            if self.tipo.nombre_tipo == 'Donación':
                self.prenda.estado = 'DONADA'  # Asumiendo que agregas 'DONADA' a choices si no está.
            elif self.tipo.nombre_tipo == 'Venta':
                self.prenda.estado = 'VENDIDA'
            elif self.tipo.nombre_tipo == 'Intercambio':
                self.prenda.estado = 'INTERCAMBIADA'
        elif self.estado in ['PENDIENTE', 'EN_PROCESO']:
            self.prenda.estado = 'EN_PROCESO'
        elif self.estado in ['RECHAZADA', 'CANCELADA']:
            self.prenda.estado = 'DISPONIBLE'
        self.prenda.save()

    def save(self, *args, **kwargs):
        # Validación: Si estado == 'EN_PROCESO', direccion_entrega es obligatoria.
        if self.estado == 'EN_PROCESO' and not self.direccion_entrega:
            raise ValueError("Dirección de entrega es obligatoria en estado 'EN_PROCESO'.")
        super().save(*args, **kwargs)
        # Actualiza automáticamente la prenda.
        self.actualizar_disponibilidad_prenda()

    # Métodos de permisos (sin cambios mayores, pero ajustados a nuevos nombres de campos).
    def puede_aceptar(self, usuario):
        """Verifica si el usuario puede aceptar esta transacción.
        - Donaciones: solo representante de la fundación asignada.
        - Intercambios/Ventas: solo el usuario destino.
        - Estado debe ser PENDIENTE o RESERVADA.
        """
        if self.estado not in ['PENDIENTE', 'RESERVADA']:
            return False
        if self.es_donacion():
            return (usuario.es_representante_fundacion() and 
                    usuario.fundacion_asignada == self.fundacion)
        if self.user_destino:
            return usuario.id == self.user_destino.id
        return False

    # (Los demás métodos de permisos siguen similares; omite por brevedad, pero ajusta nombres de campos).
    def puede_rechazar(self, usuario):
        """Verifica si el usuario puede rechazar esta transacción.
        - Donaciones: solo representante de la fundación.
        - Intercambios/Ventas: usuario destino siempre, origen solo en PENDIENTE.
        """
        if self.estado not in ['PENDIENTE', 'RESERVADA']:
            return False
        if self.es_donacion():
            return (usuario.es_representante_fundacion() and 
                    usuario.fundacion_asignada == self.id_fundacion)
        es_destino = (self.id_usuario_destino and 
                      usuario.id_usuario == self.id_usuario_destino.id_usuario)
        es_origen = usuario.id_usuario == self.id_usuario_origen.id_usuario
        return es_destino or (es_origen and self.estado == 'PENDIENTE')

    def puede_confirmar_entrega(self, usuario):
        """Verifica si el usuario puede confirmar entrega de la prenda.
        - Donaciones: representante de fundación en estado EN_PROCESO.
        - Intercambios/Ventas: usuario destino en estado EN_PROCESO.
        """
        if self.estado != 'EN_PROCESO':
            return False
        if self.es_donacion():
            return (usuario.es_representante_fundacion() and 
                    usuario.fundacion_asignada == self.id_fundacion)
        if self.id_usuario_destino:
            return usuario.id_usuario == self.id_usuario_destino.id_usuario
        return False

    def puede_reservar(self, usuario):
        """Verifica si el usuario puede reservar esta transacción.
        - Solo usuario destino (no es origen) en estado PENDIENTE.
        """
        if self.estado != 'PENDIENTE':
            return False
        es_destino = (self.id_usuario_destino and 
                      usuario.id_usuario == self.id_usuario_destino.id_usuario)
        es_origen = usuario.id_usuario == self.id_usuario_origen.id_usuario
        return es_destino and not es_origen

    def puede_modificar(self, usuario):
        """Verifica si el usuario puede modificar detalles de la transacción.
        - Usuario origen, admin/moderador, o representante en estado PENDIENTE.
        """
        if self.estado != 'PENDIENTE':
            return False
        es_origen = usuario.id_usuario == self.id_usuario_origen.id_usuario
        es_admin = usuario.es_administrador() or usuario.es_moderador()
        es_rep = (usuario.es_representante_fundacion() and 
                  usuario.fundacion_asignada == self.id_fundacion)
        return es_origen or es_admin or es_rep

# ------------------- Mensaje ----------------------

class Mensaje(models.Model):
    emisor = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='mensajes_enviados')  # Cambié a CASCADE y renombré.
    receptor = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='mensajes_recibidos')  # Cambié a CASCADE.
    contenido = models.CharField(max_length=500)
    fecha_envio = models.DateTimeField(default=timezone.now, blank=True, null=True)
    leido = models.BooleanField(default=False)  # Agregado para marcar mensajes leídos.

    class Meta:
        db_table = 'mensaje'
        ordering = ['fecha_envio']  # Ordena por fecha por defecto.

    def __str__(self): return f"Mensaje de {self.emisor.nombre} a {self.receptor.nombre}"

# ------------------- Impacto Ambiental ----------------------

class ImpactoAmbiental(models.Model):
    prenda = models.ForeignKey(Prenda, on_delete=models.CASCADE)  # Cambié a CASCADE.
    carbono_evitar_kg = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    energia_ahorrada_kwh = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    fecha_calculo = models.DateTimeField(default=timezone.now, blank=True, null=True)

    class Meta:
        db_table = 'impacto_ambiental'

    def __str__(self): return f"Impacto de {self.prenda.nombre}"

# ------------------- Logros ----------------------

class Logro(models.Model):
    TIPO_CHOICES = [
        ('DONACION', 'Donación'),
        ('INTERCAMBIO', 'Intercambio'),
        ('VENTA', 'Venta'),
        ('IMPACTO', 'Impacto Ambiental'),
        ('COMUNIDAD', 'Comunidad'),
    ]
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    icono = models.CharField(max_length=50, help_text='Clase de ícono Bootstrap')
    requisito_valor = models.IntegerField(help_text='Valor necesario para desbloquear')
    codigo = models.CharField(max_length=50, unique=True, default="")
    
    class Meta:
        db_table = 'logro'
        indexes = [
            models.Index(fields=['tipo']),  # Para filtrar por tipo de logro.
        ]
    
    def __str__(self): return self.nombre

class UsuarioLogro(models.Model):
    user = models.ForeignKey(Usuario, on_delete=models.CASCADE)  # Cambié a CASCADE y renombré a 'user'.
    logro = models.ForeignKey(Logro, on_delete=models.CASCADE)  # Cambié a CASCADE.
    fecha_desbloqueo = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'usuario_logro'
        unique_together = ('user', 'logro')  # Mantengo unique_together, pero ajustado al nuevo nombre.
        indexes = [
            models.Index(fields=['fecha_desbloqueo']),  # Para ordenar por fecha.
        ]
    
    def __str__(self):
        return f"{self.user.nombre} - {self.logro.nombre}"

# ------------------- Campaña Fundación ----------------------

class CampanaFundacion(models.Model):
    fundacion = models.ForeignKey(Fundacion, on_delete=models.CASCADE)  # Cambié a CASCADE y renombré a 'fundacion'.
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    imagen_campana = models.ImageField(upload_to='campanas/', blank=True, null=True, max_length=200)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    objetivo_prendas = models.IntegerField(help_text='Meta de prendas a recolectar')
    activa = models.BooleanField(default=True)
    categorias_solicitadas = models.CharField(max_length=300, help_text='Categorías separadas por comas')

    class Meta:
        db_table = 'campana_fundacion'
        indexes = [
            models.Index(fields=['activa']),  # Para filtrar campañas activas.
            models.Index(fields=['fecha_inicio']),  # Para ordenar por fecha.
        ]

    def __str__(self): return f"{self.nombre} - {self.fundacion.nombre}"

    def prendas_donadas(self):
        return Transaccion.objects.filter(
            campana=self,  # Ajusté nombre de campo.
            estado='COMPLETADA',
            tipo__nombre_tipo='Donación'  # Ajusté nombre de campo.
        ).count()
    
    def porcentaje_completado(self):
        donadas = self.prendas_donadas()
        if self.objetivo_prendas > 0:
            return min(100, (donadas / self.objetivo_prendas) * 100)
        return 0
    
    def save(self, *args, **kwargs):
        # Validación: fecha_fin debe ser posterior a fecha_inicio si existe.
        if self.fecha_fin and self.fecha_inicio >= self.fecha_fin:
            raise ValueError("La fecha de fin debe ser posterior a la fecha de inicio.")
        super().save(*args, **kwargs)
